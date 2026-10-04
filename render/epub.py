"""Adapter ghi EPUB: gom bản dịch từ DB rồi giao cho epub_io."""
from pathlib import Path

from bs4 import BeautifulSoup

import db
import epub_io


def _to_text(s: str) -> str:
    return BeautifulSoup(s, "html.parser").get_text().strip()


def write(project: Path, con, out_path: Path, *, bilingual: bool = False) -> None:
    doc_map, toc_map, title = {}, {}, None
    for r in con.execute(
        "SELECT page_no, pos, dst_html, json_extract(layout, '$.href') AS href "
        "FROM blocks WHERE dst_html IS NOT NULL"
    ):
        if r["page_no"] >= 0:
            doc_map.setdefault(r["href"], {})[r["pos"]] = r["dst_html"]
        elif r["page_no"] == db.PAGE_TOC:
            toc_map[r["pos"]] = _to_text(r["dst_html"])
        elif r["page_no"] == db.PAGE_TITLE:
            title = _to_text(r["dst_html"])

    book = epub_io.load_book(Path(project) / "source.epub")
    epub_io.write_translated(book, out_path, doc_map, toc_map, title,
                             bilingual=bilingual)
