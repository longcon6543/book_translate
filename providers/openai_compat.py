"""Giao thức OpenAI.

Dùng được cho chính OpenAI và cho mọi dịch vụ nói cùng giao thức: DeepSeek,
Qwen, OpenRouter, Together, và model chạy tại máy qua Ollama hoặc LM Studio.

Biến môi trường:
    OPENAI_API_KEY        khoá; với máy chủ tại máy thì đặt gì cũng được
    BOOKTRANS_BASE_URL    ví dụ http://localhost:11434/v1 cho Ollama
"""
import os

import openai

import providers

NAME = "openai"
DEFAULT_MODEL = None          # bắt buộc truyền --model: không đoán hộ người dùng
SUPPORTS_CACHE = False        # cache tự động ở phía máy chủ, không khai báo được

_FATAL = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
    openai.BadRequestError,
)


def make_client():
    return openai.OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("BOOKTRANS_BASE_URL"),
        max_retries=5,
    )


def _het_quota(exc) -> bool:
    """429 của OpenAI vừa là quá tải tạm thời, vừa là hết tiền trong tài khoản."""
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        return False
    loi = body.get("error")
    ma = body.get("code") or (loi.get("code") if isinstance(loi, dict) else None)
    return ma == "insufficient_quota"


def is_fatal(exc) -> bool:
    if isinstance(exc, openai.RateLimitError):
        # Hết tiền mà coi là thử lại được thì mỗi chunk ngồi thử 3 lần x 5 lần
        # SDK retry, cả cuốn sách chạy hàng giờ để dịch ra con số không.
        return _het_quota(exc)
    # Cùng cái bẫy đó, số hiệu khác: có dịch vụ báo hết tiền bằng 402 Payment
    # Required thay vì 429. 402 không bao giờ là tạm thời — thử lại thì vẫn
    # hết tiền. Gặp thật khi tài khoản còn quá ít credit để trả cho max_tokens.
    if getattr(exc, "status_code", None) == 402:
        return True
    return isinstance(exc, _FATAL)


def is_retryable(exc) -> bool:
    return isinstance(exc, openai.APIError) and not is_fatal(exc)


def call(client, model: str, system: str, user: str, max_tokens: int):
    """Trả về (text, usage đã chuẩn hoá, finish_reason)."""
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    if not resp.choices:
        raise ValueError(
            "máy chủ không trả về lựa chọn nào (choices rỗng) — có thể do bộ lọc "
            "nội dung hoặc máy chủ tương thích cư xử khác chuẩn."
        )
    choice = resp.choices[0]
    text = choice.message.content or ""

    u = resp.usage
    details = getattr(u, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) or 0 if details else 0
    prompt = getattr(u, "prompt_tokens", 0) or 0
    usage = providers.normalize_usage({
        # prompt_tokens đã gồm cả phần đọc từ cache; tách ra để khỏi đếm đúp
        "input": max(prompt - cached, 0),
        "output": getattr(u, "completion_tokens", 0),
        "cache_read": cached,
        "cache_write": 0,
    })
    stop = (providers.TRUNCATED if choice.finish_reason == "length"
            else choice.finish_reason)
    return text, usage, stop
