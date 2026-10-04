"""Danh bạ provider và việc chuẩn hoá usage."""
import pytest

import providers


def test_liet_ke_ten():
    assert "anthropic" in providers.names()


def test_ten_sai_bao_loi_liet_ke_lua_chon():
    with pytest.raises(ValueError) as e:
        providers.get("khong-ton-tai")
    assert "anthropic" in str(e.value)


def test_lay_duoc_anthropic():
    p = providers.get("anthropic")
    assert p.NAME == "anthropic"
    assert p.SUPPORTS_CACHE is True


def test_chuan_hoa_usage_day_du():
    raw = {"input": 10, "output": 20, "cache_read": 5, "cache_write": 1}
    assert providers.normalize_usage(raw) == raw


def test_chuan_hoa_usage_thieu_truong_thi_ve_khong():
    assert providers.normalize_usage({"output": 7}) == {
        "input": 0, "output": 7, "cache_read": 0, "cache_write": 0}


def test_chuan_hoa_usage_gia_tri_none():
    assert providers.normalize_usage({"input": None, "output": 3})["input"] == 0


def test_chuan_hoa_bo_truong_la():
    out = providers.normalize_usage({"output": 1, "reasoning_tokens": 99})
    assert set(out) == {"input", "output", "cache_read", "cache_write"}


def test_provider_co_ten_nhung_khong_nap_duoc_bao_loi_ro(monkeypatch):
    """Có tên trong danh bạ nhưng module hỏng/thiếu thư viện.

    Người dùng phải nhận được câu nói rõ phải làm gì, không phải traceback của
    importlib. Gặp thật khi gõ --provider openai lúc chưa cài SDK openai.
    """
    monkeypatch.setitem(providers._REGISTRY, "hong", "providers.khong_he_ton_tai")
    with pytest.raises(ValueError) as e:
        providers.get("hong")
    msg = str(e.value)
    assert "hong" in msg
    assert "pip install" in msg


def test_anthropic_thieu_khoa_thi_bao_ngay_luc_tao_client(monkeypatch):
    """Phase 1 có chốt chặn này; Phase 2 làm mất nó.

    anthropic.Anthropic() dựng được kể cả khi không có khoá — lỗi chỉ nổ lúc gọi
    API, dưới dạng TypeError không phải APIError, nên không provider nào phân
    loại được và người dùng lĩnh nguyên traceback giữa chừng.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    p = providers.get("anthropic")
    with pytest.raises(Exception) as e:
        p.make_client()
    assert "ANTHROPIC_API_KEY" in str(e.value)


def test_tu_vung_cat_ngan_duoc_chuan_hoa():
    """Mỗi nhà cung cấp gọi 'hết token' một kiểu; lõi chỉ được biết một từ."""
    assert providers.TRUNCATED == "truncated"
