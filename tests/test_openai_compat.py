"""Giao thức OpenAI. Client giả, không gọi mạng."""
import types

import openai
import pytest

from providers import openai_compat as oc


def fake_response(text, prompt=100, completion=50, cached=0, finish="stop"):
    details = types.SimpleNamespace(cached_tokens=cached)
    usage = types.SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion,
                                  prompt_tokens_details=details)
    choice = types.SimpleNamespace(
        message=types.SimpleNamespace(content=text), finish_reason=finish)
    return types.SimpleNamespace(choices=[choice], usage=usage)


class FakeClient:
    def __init__(self, response):
        self.seen = {}
        outer = self

        class Completions:
            def create(self, **kw):
                outer.seen = kw
                return response

        self.chat = types.SimpleNamespace(completions=Completions())


def test_giao_keo_module():
    assert oc.NAME == "openai"
    assert oc.DEFAULT_MODEL is None
    assert oc.SUPPORTS_CACHE is False


def test_call_tra_ve_dung_bo_ba():
    client = FakeClient(fake_response("<seg id=\"1\">chao</seg>"))
    text, usage, stop = oc.call(client, "m-1", "SYS", "USER", 4096)
    assert text == "<seg id=\"1\">chao</seg>"
    assert stop == "stop"
    assert usage == {"input": 100, "output": 50, "cache_read": 0, "cache_write": 0}


def test_system_va_user_di_dung_vai():
    client = FakeClient(fake_response("x"))
    oc.call(client, "m-1", "SYS", "USER", 4096)
    msgs = client.seen["messages"]
    assert msgs[0] == {"role": "system", "content": "SYS"}
    assert msgs[1] == {"role": "user", "content": "USER"}
    assert client.seen["model"] == "m-1"


def test_token_da_cache_bi_tru_khoi_input():
    """prompt_tokens của OpenAI đã bao gồm phần cache; không trừ là đếm đúp."""
    client = FakeClient(fake_response("x", prompt=100, cached=30))
    _, usage, _ = oc.call(client, "m-1", "SYS", "USER", 4096)
    assert usage["input"] == 70
    assert usage["cache_read"] == 30


def test_noi_dung_rong_khong_thanh_none():
    client = FakeClient(fake_response(None))
    text, _, _ = oc.call(client, "m-1", "SYS", "USER", 4096)
    assert text == ""


def test_khong_co_prompt_tokens_details():
    """Máy chủ tương thích nhưng cũ có thể không có trường này."""
    usage = types.SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    choice = types.SimpleNamespace(
        message=types.SimpleNamespace(content="x"), finish_reason="stop")
    client = FakeClient(types.SimpleNamespace(choices=[choice], usage=usage))
    _, u, _ = oc.call(client, "m-1", "SYS", "USER", 4096)
    assert u == {"input": 10, "output": 5, "cache_read": 0, "cache_write": 0}


def _fake_http_response(status: int):
    """Đủ hình dạng để SDK openai dựng được exception thật.

    SDK gọi response.request trong __init__, nên namespace phải có trường đó.
    Dựng exception thật thay vì giả lập, để test vẫn bắt được nếu SDK đổi cây
    thừa kế của các lớp lỗi.
    """
    return types.SimpleNamespace(status_code=status, headers={}, request=object())


def test_phan_loai_loi_nghiem_trong():
    fatal = openai.AuthenticationError(
        "sai key", response=_fake_http_response(401), body=None)
    assert oc.is_fatal(fatal) is True
    assert oc.is_retryable(fatal) is False


def test_phan_loai_loi_dang_thu_lai():
    """429 là quá tải tạm thời: phải thử lại, không được dừng hẳn."""
    tam = openai.RateLimitError(
        "quá tải", response=_fake_http_response(429), body=None)
    assert oc.is_fatal(tam) is False
    assert oc.is_retryable(tam) is True


def test_finish_reason_length_duoc_dich_sang_tu_vung_chung():
    """OpenAI gọi là 'length', Anthropic gọi là 'max_tokens'. Lõi chỉ biết 'truncated'."""
    import providers
    client = FakeClient(fake_response("x", finish="length"))
    _, _, stop = oc.call(client, "m-1", "SYS", "USER", 4096)
    assert stop == providers.TRUNCATED


def test_finish_reason_binh_thuong_khong_bi_doi():
    client = FakeClient(fake_response("x", finish="stop"))
    _, _, stop = oc.call(client, "m-1", "SYS", "USER", 4096)
    assert stop == "stop"


def test_het_tien_la_loi_nghiem_trong_khong_phai_thu_lai():
    """OpenAI báo hết quota bằng HTTP 429, trùng mã với quá tải tạm thời.

    Phân loại nhầm thì 300 chunk mỗi chunk thử 3 lần x 5 lần SDK retry, ngồi
    hàng giờ để dịch ra con số không.
    """
    het_tien = openai.RateLimitError(
        "quota", response=_fake_http_response(429),
        body={"code": "insufficient_quota"})
    assert oc.is_fatal(het_tien) is True
    assert oc.is_retryable(het_tien) is False


def test_khong_co_lua_chon_nao_tra_ve_khong_lam_vo():
    """Máy chủ lọc nội dung có thể trả choices rỗng."""
    client = FakeClient(types.SimpleNamespace(choices=[], usage=None))
    with pytest.raises(ValueError, match="không trả về"):
        oc.call(client, "m-1", "SYS", "USER", 4096)


def test_402_het_credit_la_loi_nghiem_trong():
    """Gặp thật: OpenRouter báo hết credit bằng HTTP 402, không phải 429.

    402 Payment Required không bao giờ là tạm thời — thử lại thì vẫn hết tiền.
    Coi nó là thử lại được thì mỗi chunk ngồi thử 3 lượt, và cả cuốn 593 chunk
    chạy rất lâu để dịch ra con số không. Đúng cái bẫy mà `_het_quota` đã
    chặn cho mã 429 của OpenAI, chỉ khác số hiệu.
    """
    het = openai.APIStatusError(
        "This request requires more credits",
        response=_fake_http_response(402),
        body={"error": {"code": 402, "message": "requires more credits"}})
    assert oc.is_fatal(het) is True
    assert oc.is_retryable(het) is False


def test_500_van_la_loi_thu_lai_duoc():
    """Đừng sửa quá tay: 5xx là hỏng tạm thời bên máy chủ, vẫn phải thử lại."""
    tam = openai.APIStatusError(
        "bad gateway", response=_fake_http_response(502), body=None)
    assert oc.is_fatal(tam) is False
    assert oc.is_retryable(tam) is True
