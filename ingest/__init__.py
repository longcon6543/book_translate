"""Nhận diện định dạng nguồn và chọn tầng đọc vào tương ứng.

Nhận diện bằng magic bytes và nội dung thật của file. Phần mở rộng tên file
không được tin: một file PDF đổi tên thành .epub phải bị bắt ở đây, kèm thông
báo người dùng đọc hiểu được.
"""
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

EPUB_MIMETYPE = "application/epub+zip"

# Định dạng đã đọc được. `detect_format` nhận ra nhiều hơn thế (ví dụ "pdf") để
# báo lỗi cho đúng, nên người gọi phải hỏi riêng cái này trước khi động vào đĩa.
SUPPORTED_FORMATS = ("epub", "pdf")


class UnsupportedSource(Exception):
    """File nguồn không đọc được. Thông điệp dành cho người dùng cuối."""


@dataclass
class Ingested:
    fmt: str
    source_name: str
    blocks: list
    # Dữ liệu cấp project ngoài khối, ghi vào bảng meta khi init. PDF scan:
    # {"vung_hinh": {"<page_no>": [[x0,y0,x1,y1], ...]}} (spec 8B E7).
    meta: dict = field(default_factory=dict)


def detect_format(path) -> str:
    p = Path(path)
    if not p.exists():
        raise UnsupportedSource(f"không thấy file {p}")

    with p.open("rb") as fh:
        head = fh.read(4)

    if not head:
        raise UnsupportedSource(f"{p.name} rỗng (0 byte).")
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(p) as zf:
                mimetype = zf.read("mimetype").decode("ascii", "replace").strip()
        except KeyError:
            raise UnsupportedSource(
                f"{p.name} là file zip nhưng không phải EPUB (thiếu 'mimetype'). "
                f"File .docx hay .zip thường cũng bắt đầu bằng PK như vậy."
            ) from None
        except zipfile.BadZipFile:
            raise UnsupportedSource(f"{p.name} là zip hỏng, không đọc được.") from None
        if mimetype != EPUB_MIMETYPE:
            raise UnsupportedSource(
                f"{p.name} là zip kiểu '{mimetype}', không phải EPUB."
            )
        return "epub"

    raise UnsupportedSource(
        f"{p.name} không phải PDF hay EPUB. Bốn byte đầu: {head!r}. "
        f"Đuôi file không quyết định gì — hãy kiểm tra nội dung thật."
    )


def ensure_supported(fmt: str) -> None:
    """Ném UnsupportedSource nếu định dạng chưa đọc được.

    Tách khỏi `load` để `init` hỏi được trước khi tạo thư mục và copy file
    nguồn — sách scan cả gigabyte thì copy xong mới từ chối là quá muộn.
    """
    if fmt not in SUPPORTED_FORMATS:
        raise UnsupportedSource(
            "PDF sẽ được hỗ trợ từ Phase 3. Hiện booktrans chỉ đọc được EPUB."
        )


def load(path) -> Ingested:
    p = Path(path)
    fmt = detect_format(p)
    ensure_supported(fmt)
    if fmt == "pdf":
        from ingest import pdf_text as adapter
    else:
        from ingest import epub as adapter
    return adapter.load(p)
