"""Cấu hình chung cho test. Không test nào được phép gọi mạng."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from helpers import build_epub  # noqa: E402


@pytest.fixture
def source_epub(tmp_path):
    """Một EPUB nhỏ nhưng đủ hình thái: tiêu đề, in nghiêng, liên kết, danh sách,
    và một đoạn chỉ có số (phải bị bỏ qua vì không có chữ cái)."""
    return build_epub(tmp_path / "short.epub")
