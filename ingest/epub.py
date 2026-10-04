"""Adapter EPUB: lớp vỏ mỏng quanh epub_io, khớp giao kèo của tầng ingest."""
from pathlib import Path

import epub_io
from ingest import Ingested


def load(path: Path) -> Ingested:
    book = epub_io.load_book(path)
    return Ingested(fmt="epub", source_name=path.name,
                    blocks=epub_io.extract_blocks(book))
