"""Giao thức Anthropic."""
import os

import anthropic

import providers

NAME = "anthropic"
DEFAULT_MODEL = "claude-sonnet-5"
SUPPORTS_CACHE = True

# Lỗi không thể tự khỏi bằng cách thử lại -> dừng hẳn để khỏi đốt tiền vô ích
_FATAL = (
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.NotFoundError,
    anthropic.BadRequestError,
)


def make_client():
    # SDK dựng client được kể cả khi không có khoá; lỗi chỉ nổ lúc gọi API, dưới
    # dạng TypeError mà không hàm phân loại nào nhận ra. Chốt ngay tại đây để
    # người dùng biết trước khi bắt đầu dịch.
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise RuntimeError(
            "chưa đặt biến môi trường ANTHROPIC_API_KEY."
        )
    return anthropic.Anthropic(max_retries=5)     # SDK tự retry 429/5xx có backoff


def is_fatal(exc) -> bool:
    return isinstance(exc, _FATAL)


def is_retryable(exc) -> bool:
    return isinstance(exc, anthropic.APIError) and not is_fatal(exc)


def call(client, model: str, system: str, user: str, max_tokens: int):
    """Trả về (text, usage đã chuẩn hoá, stop_reason)."""
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        # cache_control: system prompt đủ dài thì các chunk sau được giảm giá
        system=[{"type": "text", "text": system,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    u = resp.usage
    usage = providers.normalize_usage({
        "input": getattr(u, "input_tokens", 0),
        "output": getattr(u, "output_tokens", 0),
        "cache_read": getattr(u, "cache_read_input_tokens", 0),
        "cache_write": getattr(u, "cache_creation_input_tokens", 0),
    })
    stop = providers.TRUNCATED if resp.stop_reason == "max_tokens" else resp.stop_reason
    return text, usage, stop
