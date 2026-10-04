"""Tầng nhà cung cấp mô hình.

Mỗi module con là một giao thức API. Phần lõi chỉ biết đúng giao kèo dưới đây,
không biết đang nói chuyện với ai:

    NAME: str
    DEFAULT_MODEL: str | None       # None nghĩa là bắt buộc truyền --model
    SUPPORTS_CACHE: bool
    make_client()
    call(client, model, system, user, max_tokens) -> (text, usage, stop_reason)
                                    # stop_reason dùng TRUNCATED khi bị cắt
    is_fatal(exc) -> bool           # hỏng vĩnh viễn: key sai, model sai, hết tiền
    is_retryable(exc) -> bool       # tạm thời: rate limit, mạng, 5xx
"""
import importlib

_REGISTRY = {
    "anthropic": "providers.anthropic_api",
    "openai": "providers.openai_compat",
}

# Danh bạ sở hữu lựa chọn mặc định, không phải CLI: nhờ vậy lõi không cần
# nhắc tên nhà cung cấp nào (xem tests/test_loi_doc_lap.py).
DEFAULT_PROVIDER = "anthropic"

USAGE_KEYS = ("input", "output", "cache_read", "cache_write")

# Mỗi nhà cung cấp gọi "hết token nên bị cắt" một kiểu: Anthropic là
# "max_tokens", giao thức OpenAI là "length". Adapter dịch sang từ này để lõi
# chỉ phải biết một từ duy nhất.
TRUNCATED = "truncated"


def names() -> list:
    return sorted(_REGISTRY)


def get(name: str):
    if name not in _REGISTRY:
        raise ValueError(
            f"không có provider '{name}'. Chọn một trong: {', '.join(names())}"
        )
    try:
        return importlib.import_module(_REGISTRY[name])
    except ImportError as e:
        # Có tên trong danh bạ nhưng module chưa nạp được — hầu như luôn là
        # thiếu SDK của nhà cung cấp đó. Người dùng cần câu chỉ việc, không
        # cần traceback của importlib.
        raise ValueError(
            f"provider '{name}' có trong danh bạ nhưng chưa nạp được: {e}. "
            f"Thường là thiếu thư viện — thử `pip install -r requirements.txt`."
        ) from e


def normalize_usage(raw: dict) -> dict:
    """Về đúng bốn khoá, thiếu hoặc None thì thành 0.

    Mỗi nhà cung cấp đặt tên trường một kiểu và đôi khi bỏ trống. `status` cộng
    tiền từ bốn số này nên chúng không bao giờ được là None.
    """
    return {k: int(raw.get(k) or 0) for k in USAGE_KEYS}
