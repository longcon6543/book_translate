"""SQLite: lưu block nguồn, bản dịch và trạng thái từng chunk (để resume)."""
import sqlite3
from pathlib import Path

# page_no >= 0 : trang PDF, hoặc file XHTML trong EPUB (theo thứ tự đọc)
PAGE_TOC = -1     # tiêu đề mục lục
PAGE_TITLE = -2   # tên sách trong metadata

SCHEMA_VERSION = 2

BLOCKS_COLUMNS = """
    id          INTEGER PRIMARY KEY,
    page_no     INTEGER NOT NULL,
    pos         INTEGER NOT NULL,      -- vị trí trong trang (ghi lại đúng chỗ)
    tag         TEXT    NOT NULL,
    kind        TEXT    NOT NULL DEFAULT 'text',   -- text/heading/caption/table/formula/skip
    src_html    TEXT    NOT NULL,      -- innerHTML bản gốc
    dst_html    TEXT,                  -- innerHTML bản dịch (NULL = chưa dịch)
    bbox        TEXT,                  -- "x0,y0,x1,y1" trên trang PDF
    line_bboxes TEXT,                  -- JSON: khung từng dòng
    layout      TEXT    NOT NULL DEFAULT '{}',     -- JSON riêng từng định dạng
    cont_group  INTEGER,               -- nhóm đoạn bị cắt ngang trang
    chunk_id    INTEGER REFERENCES chunks(id),
    flag        TEXT                   -- NULL = ổn; tag_mismatch / too_short / overflow
"""

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY,
    status      TEXT    NOT NULL DEFAULT 'pending',   -- pending | done | failed
    attempts    INTEGER NOT NULL DEFAULT 0,
    error       TEXT,
    provider    TEXT,
    model       TEXT,
    in_tokens   INTEGER NOT NULL DEFAULT 0,
    out_tokens  INTEGER NOT NULL DEFAULT 0,
    cache_read  INTEGER NOT NULL DEFAULT 0,
    cache_write INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS blocks ({BLOCKS_COLUMNS});
CREATE INDEX IF NOT EXISTS idx_blocks_chunk ON blocks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_blocks_page  ON blocks(page_no);
"""

# v1 -> v2: doc_index thành page_no, doc_href chui vào layout, thêm cột cho PDF.
# Dựng bảng mới rồi đổi tên: cách này chạy trên mọi phiên bản SQLite và nhìn là
# thấy ngay cột nào lấy từ đâu.
MIGRATE_V1_V2 = f"""
BEGIN;
CREATE TABLE blocks_v2 ({BLOCKS_COLUMNS});
INSERT INTO blocks_v2 (id, page_no, pos, tag, src_html, dst_html, layout, chunk_id, flag)
SELECT id, doc_index, pos, tag, src_html, dst_html,
       json_object('href', doc_href), chunk_id, flag
FROM blocks;
DROP TABLE blocks;
ALTER TABLE blocks_v2 RENAME TO blocks;
CREATE INDEX idx_blocks_chunk ON blocks(chunk_id);
CREATE INDEX idx_blocks_page  ON blocks(page_no);
ALTER TABLE chunks ADD COLUMN provider TEXT;
ALTER TABLE chunks ADD COLUMN model TEXT;
INSERT INTO meta(key, value) VALUES('schema_version', '{SCHEMA_VERSION}')
    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
COMMIT;
"""


def connect(project: Path) -> sqlite3.Connection:
    con = sqlite3.connect(Path(project) / "project.db")
    con.row_factory = sqlite3.Row
    return con


def _has_table(con, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def current_version(con) -> int:
    """0 = chưa có gì; 1 = project Phase 1; >=2 = đã ghi schema_version."""
    if not _has_table(con, "blocks"):
        return 0
    value = get_meta(con, "schema_version")
    if value:
        return int(value)
    # Không có dòng schema_version: hoặc project Phase 1 thật, hoặc một lần
    # migrate hỏng dở ở bản cũ. Nhìn hình dạng bảng mới phân biệt được — tin
    # vào dòng meta thôi là khoá chết project loại thứ hai.
    cols = {r[1] for r in con.execute("PRAGMA table_info(blocks)")}
    return SCHEMA_VERSION if "page_no" in cols else 1


def init_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    set_meta(con, "schema_version", SCHEMA_VERSION)
    con.commit()


def migrate(con: sqlite3.Connection) -> int:
    """Nâng project.db lên schema hiện tại. Trả về phiên bản sau khi nâng."""
    version = current_version(con)
    if version == 0:
        init_schema(con)
        return SCHEMA_VERSION
    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"project.db dùng schema v{version}, tool này chỉ hiểu tới "
            f"v{SCHEMA_VERSION}. Hãy cập nhật booktrans."
        )
    if version == 1:
        # Cả migration nằm trong một giao dịch, gồm cả dòng schema_version:
        # hỏng giữa chừng thì lùi sạch về v1, mở lại vẫn chạy được.
        try:
            con.executescript(MIGRATE_V1_V2)
        except Exception:
            con.rollback()
            raise
    return SCHEMA_VERSION


def get_meta(con, key, default=None):
    if not _has_table(con, "meta"):
        return default
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(con, key, value) -> None:
    con.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
