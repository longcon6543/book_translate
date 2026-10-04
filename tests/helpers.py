"""Đồ nghề dùng chung cho test."""
import argparse
import hashlib
from pathlib import Path

from ebooklib import epub

import cli
import epub_io

CHAPTER_1 = (
    "<html><head><title>c1</title></head><body>"
    "<h1>Chapter One</h1>"
    "<p>The <em>first</em> paragraph.</p>"
    '<p>A paragraph with a <a href="http://example.com/x">link</a> inside.</p>'
    "<ul><li>One item</li><li>Another item</li></ul>"
    "<p>42</p>"
    "</body></html>"
)
CHAPTER_2 = (
    "<html><head><title>c2</title></head><body>"
    "<h1>Chapter Two</h1>"
    "<p>Only one paragraph here.</p>"
    "</body></html>"
)


def build_epub(path: Path) -> Path:
    book = epub.EpubBook()
    book.set_identifier("booktrans-test-0001")
    book.set_title("A Short Book")
    book.set_language("en")
    book.add_author("Test Author")

    c1 = epub.EpubHtml(title="Chapter One", file_name="c1.xhtml", lang="en")
    c1.content = CHAPTER_1
    c2 = epub.EpubHtml(title="Chapter Two", file_name="c2.xhtml", lang="en")
    c2.content = CHAPTER_2
    book.add_item(c1)
    book.add_item(c2)

    book.toc = (epub.Link("c1.xhtml", "Chapter One", "c1"),
                epub.Link("c2.xhtml", "Chapter Two", "c2"))
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1, c2]

    epub.write_epub(str(path), book)
    return path


def run_init(source: Path, proj: Path, chunk_chars: int = 6000) -> Path:
    """Gọi `init` đúng cách CLI gọi. Chữ ký cmd_init đổi thì chỉ sửa ở đây."""
    cli.cmd_init(argparse.Namespace(
        source=str(source), dir=str(proj), chunk_chars=chunk_chars, force=True))
    return proj


def seed_translations(con) -> None:
    """Bản dịch giả, xác định: thêm tiền tố, giữ nguyên mọi thẻ HTML.

    Không gọi mạng. Đủ để kiểm tra riêng đường ghi ra, tách khỏi chất lượng dịch.
    """
    for r in con.execute("SELECT id, src_html FROM blocks ORDER BY id").fetchall():
        con.execute("UPDATE blocks SET dst_html=? WHERE id=?",
                    (f"[VI] {r['src_html']}", r["id"]))
    con.execute("UPDATE chunks SET status='done'")
    con.commit()


def fingerprint(epub_path: Path) -> str:
    """Vân tay ổn định của một EPUB: bỏ qua dấu thời gian và thứ tự nén trong zip."""
    book = epub_io.load_book(epub_path)
    lines = [f"title\t{book.title}"]
    for i, entry in enumerate(epub_io.toc_entries(book.toc)):
        lines.append(f"toc[{i}]\t{entry.title}")
    for item in epub_io.ordered_documents(book):
        digest = hashlib.sha256(item.get_content()).hexdigest()[:16]
        lines.append(f"doc\t{item.get_name()}\t{digest}")
    return "\n".join(lines) + "\n"


def build_pdf(path: Path, pages: list) -> Path:
    """Dựng PDF xác định từ mô tả thuần Python.

    Mỗi trang là list các dict: {"text", "x", "y", "size", "bold", "italic"}.
    Khổ trang 522x666pt cho khớp sách thật đã đo.

    Cố tình CHÈN KHÔNG THEO THỨ TỰ DỌC ở vài chỗ, vì PyMuPDF trả block theo
    thứ tự nội bộ chứ không theo thứ tự đọc — sách thật cũng vậy (18/18 trang
    mẫu). Test phải chứng minh code tự sắp xếp lại.
    """
    import pymupdf

    doc = pymupdf.open()
    for items in pages:
        page = doc.new_page(width=522, height=666)
        for it in items:
            font = "Times-Roman"
            if it.get("bold") and it.get("italic"):
                font = "Times-BoldItalic"
            elif it.get("bold"):
                font = "Times-Bold"
            elif it.get("italic"):
                font = "Times-Italic"
            page.insert_text((it["x"], it["y"]), it["text"],
                             fontsize=it.get("size", 10), fontname=font)
    doc.save(str(path))
    doc.close()
    return path


def trang_mot_doan(y_dau: float, so_dong: int, x: float = 67.0,
                   size: float = 10.0, tien_to: str = "dong") -> list:
    """Một đoạn văn giả: các dòng cách đều 12pt, nội dung đánh số để soi thứ tự."""
    return [{"text": f"{tien_to} {i} noi dung day du cua mot dong van ban",
             "x": x, "y": y_dau + i * 12, "size": size}
            for i in range(so_dong)]
