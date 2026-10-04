"""Đơn vị dữ liệu chung giữa tầng đọc vào và phần lõi.

Tầng ingest nào cũng trả về Block. Phần lõi không biết Block đến từ EPUB hay PDF.
"""
import json
from dataclasses import dataclass, field


@dataclass
class Block:
    page_no: int                       # >=0 là trang; âm là mục lục / tên sách
    pos: int                           # thứ tự trong trang
    tag: str
    src_html: str
    kind: str = "text"
    bbox: str | None = None            # "x0,y0,x1,y1", chỉ PDF
    line_bboxes: str | None = None     # JSON, chỉ PDF
    layout: dict = field(default_factory=dict)
    cont_group: int | None = None
    db_id: int | None = None           # id trong bảng blocks, điền sau khi INSERT

    def as_row(self) -> tuple:
        """Đúng thứ tự tham số của INSERT_SQL."""
        return (self.page_no, self.pos, self.tag, self.kind, self.src_html,
                self.bbox, self.line_bboxes,
                json.dumps(self.layout, ensure_ascii=False, separators=(",", ":")),
                self.cont_group)


INSERT_SQL = (
    "INSERT INTO blocks(page_no, pos, tag, kind, src_html, bbox, line_bboxes, "
    "layout, cont_group) VALUES(?,?,?,?,?,?,?,?,?)"
)
