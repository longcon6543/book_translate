"""Mục đích của cả Phase 2: phần lõi không biết nó đang nói chuyện với ai.

Điều kiện nghiệm thu số 6 của kế hoạch vốn là một lệnh grep chạy tay. Ở đây nó
thành test thường trực, để Phase 3-7 không vô tình kéo tên nhà cung cấp trở lại
vào lõi.
"""
from pathlib import Path

import providers

ROOT = Path(__file__).resolve().parent.parent
LOI = ["translator.py", "cli.py", "chunking.py", "blocks.py", "db.py"]


def test_loi_khong_nhac_ten_nha_cung_cap_nao():
    for name in LOI:
        text = (ROOT / name).read_text(encoding="utf-8").lower()
        for ten in providers.names():
            assert ten not in text, (
                f"{name} nhắc tới '{ten}'. Tên nhà cung cấp chỉ được xuất hiện "
                f"trong providers/, không được nằm trong lõi."
            )


def test_provider_mac_dinh_phai_co_that():
    assert providers.DEFAULT_PROVIDER in providers.names()
