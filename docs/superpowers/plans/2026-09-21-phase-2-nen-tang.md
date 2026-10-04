# Phase 2 — Nền tảng: provider thay được, blocks khái quát hoá, tách ingest/render

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tách `ingest/`, `render/` và `providers/` ra khỏi phần lõi, khái quát hoá bảng `blocks` sang mô hình theo trang, mà đường EPUB đang chạy cho ra kết quả không đổi một byte.

**Architecture:** Phần lõi (`translator.py`, `db.py`, chia chunk) không được biết nguồn là EPUB hay PDF, cũng không được biết đang gọi Anthropic hay ai khác. Ba tầng mỏng bao quanh nó: `ingest/` nhận file trả về `Block`, `render/` nhận `Block` đã dịch dựng ra file, `providers/` nhận prompt trả về `(text, usage, stop_reason)`. Phase 2 không thêm tính năng nào cho người dùng — giá trị của nó là sau khi xong thì Phase 3 tới Phase 7 chỉ việc cắm thêm module.

**Tech Stack:** Python 3.12.6, SQLite 3.45.3 (có `json1`), ebooklib 0.20, BeautifulSoup 4.15, anthropic SDK, openai SDK, pytest.

**Spec:** `docs/superpowers/specs/2026-09-21-pdf-song-ngu-design.md`

## Global Constraints

- Hành vi đường EPUB **không đổi**: vân tay trong `tests/golden/` phải khớp sau mọi task.
- **Không test nào được gọi mạng.** Mọi test dịch thuật dùng provider giả.
- Tên cột đúng spec mục 4: `page_no`, `bbox`, `line_bboxes`, `layout`, `kind`, `cont_group`; `chunks.provider`, `chunks.model`.
- `schema_version = 2`, lưu trong bảng `meta`.
- Bốn khoá usage chuẩn hoá, không hơn không kém: `input`, `output`, `cache_read`, `cache_write`.
- Nhận diện định dạng bằng **magic bytes và nội dung file**, không bao giờ bằng phần mở rộng.
- Không thêm PyMuPDF, OCRmyPDF hay Tesseract ở Phase 2 — chúng thuộc Phase 3 trở đi.
- Module phẳng ở thư mục gốc, `import db` kiểu tương đối như code hiện có. Không đóng gói thành package `booktrans/` ở phase này.
- Docstring và comment viết tiếng Việt, khớp code đang có.
- Mỗi task kết thúc bằng đúng một commit.

### Một sai lệch nhỏ so với spec

Spec mục 4 viết `layout` giữ `{href, pos}` cho EPUB. Kế hoạch này giữ `pos` làm **cột thật** vì cả EPUB lẫn PDF đều cần thứ tự trong trang, và `layout` chỉ giữ `{"href": ...}`. Tránh lưu cùng một giá trị ở hai chỗ.

## Review Focus

Năm trường hợp spec ngụ ý nhưng không task nào tự nhiên chạm tới. Mỗi dòng đã được gắn test vào task sở hữu đoạn code đó.

1. **File nguồn là PDF nhưng mang đuôi `.epub`** (hoặc ngược lại) — phải báo lỗi rõ ràng cho người dùng, không văng traceback. Đây là lỗi đã thật sự xảy ra với `projects/astrology.pdf`. → Task 3.
2. **Project tạo bằng Phase 1 (schema v1) mở bằng code mới** — phải tự nâng cấp, giữ nguyên `dst_html`, `flag`, trạng thái chunk và số token đã đếm. Mất dữ liệu ở đây là mất tiền thật. → Task 2.
3. **File nguồn rỗng, hoặc zip hỏng, hoặc là `.docx`** (cũng bắt đầu bằng `PK`) — phải phân biệt được và nói đúng vấn đề. → Task 3.
4. **Provider trả `usage` thiếu trường hoặc `None`** — chuẩn hoá về 0, `status` không được crash khi cộng tiền. → Task 5.
5. **`--provider` gõ sai tên** — liệt kê các tên hợp lệ, không `KeyError`. → Task 5.

---

## File Structure

Tạo mới:

| File | Trách nhiệm |
|---|---|
| `blocks.py` | `Block` — đơn vị dữ liệu chung giữa ingest và lõi |
| `chunking.py` | Gom block liên tiếp thành chunk (chuyển từ `cli.py`) |
| `ingest/__init__.py` | Nhận diện định dạng, chọn adapter, `UnsupportedSource` |
| `ingest/epub.py` | Adapter EPUB, mỏng, gọi `epub_io` |
| `render/__init__.py` | Chọn adapter ghi ra theo định dạng |
| `render/epub.py` | Adapter ghi EPUB, mỏng, gọi `epub_io` |
| `providers/__init__.py` | Danh bạ provider, chuẩn hoá usage |
| `providers/anthropic_api.py` | Giao thức Anthropic (chuyển từ `translator.py`) |
| `providers/openai_compat.py` | Giao thức OpenAI — DeepSeek, Qwen, OpenRouter, Ollama |
| `tests/` | conftest, helpers, vân tay vàng, test từng tầng |

Sửa:

| File | Thay đổi |
|---|---|
| `db.py` | Schema v2, migration v1→v2, hằng số `PAGE_TOC`/`PAGE_TITLE` |
| `translator.py` | Bỏ phần gọi API trực tiếp, nhận provider từ ngoài |
| `cli.py` | Dùng ingest/render/providers; bỏ `make_chunks`; thêm cờ `--provider`, `--model` |
| `epub_io.py` | Trả về `Block`; đổi `DOC_TOC`/`DOC_TITLE` sang tên mới |
| `requirements.txt` | Thêm `openai` |

Giữ nguyên `epub_io.py` làm tầng thấp đụng BeautifulSoup và ebooklib. `ingest/epub.py` và `render/epub.py` chỉ là lớp vỏ mỏng khớp giao kèo. Đây là cách ít rủi ro nhất: code đã chạy đúng thì không chép đi chỗ khác.

---

## Task 1: Lưới an toàn — vân tay vàng cho đường EPUB

Không refactor gì trước khi có cái này. Mọi task sau đều dựa vào nó để chứng minh không làm hỏng thứ đang chạy.

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Create: `tests/helpers.py`
- Create: `tests/record_golden.py`
- Create: `tests/test_golden_epub.py`
- Create: `tests/golden/epub_fingerprint.txt`, `tests/golden/epub_fingerprint_bilingual.txt`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `cli.cmd_init`, `cli.cmd_export`, `db.connect`, `epub_io.load_box`/`ordered_documents`/`toc_entries` như đang có.
- Produces: `tests/helpers.py` với `build_epub(path)`, `run_init(source, proj)`, `seed_translations(con)`, `fingerprint(epub_path)`. Các task sau gọi lại đúng bốn hàm này.

- [ ] **Step 1: Cài pytest và ghi lại phụ thuộc phát triển**

```bash
.venv/bin/pip install pytest
printf 'pytest>=8.0\n' > requirements-dev.txt
```

- [ ] **Step 2: Cho `.gitignore` bỏ qua rác của pytest**

Thêm vào cuối `.gitignore`:

```
.pytest_cache/
```

Lưu ý: `.gitignore` hiện có dòng `*.epub`. Test sinh EPUB trong `tmp_path` nên không đụng repo, nhưng thư mục `tests/golden/` chứa file `.txt` nên vẫn commit được bình thường.

- [ ] **Step 3: Viết `tests/conftest.py`**

```python
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
```

- [ ] **Step 4: Viết `tests/helpers.py`**

```python
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
        epub=str(source), dir=str(proj), chunk_chars=chunk_chars, force=True))
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
```

- [ ] **Step 5: Viết `tests/test_golden_epub.py`**

```python
"""Lưới an toàn: đường EPUB phải cho ra đúng kết quả cũ sau mọi lần refactor.

Test này KHÔNG kiểm tra chất lượng dịch. Nó kiểm tra rằng việc tách tầng ở
Phase 2 không làm đổi một byte nào của file xuất ra.
"""
from pathlib import Path

import db
from helpers import fingerprint, run_init, seed_translations

GOLDEN_DIR = Path(__file__).parent / "golden"


def export(proj: Path, bilingual: bool) -> Path:
    import argparse

    import cli
    out = proj / ("out.bi.epub" if bilingual else "out.vi.epub")
    cli.cmd_export(argparse.Namespace(
        project=str(proj), output=str(out), bilingual=bilingual))
    return out


def test_epub_don_ngu_khop_van_tay(source_epub, tmp_path):
    proj = run_init(source_epub, tmp_path / "proj")
    seed_translations(db.connect(proj))
    expected = (GOLDEN_DIR / "epub_fingerprint.txt").read_text(encoding="utf-8")
    assert fingerprint(export(proj, False)) == expected


def test_epub_song_ngu_khop_van_tay(source_epub, tmp_path):
    proj = run_init(source_epub, tmp_path / "proj")
    seed_translations(db.connect(proj))
    expected = (GOLDEN_DIR / "epub_fingerprint_bilingual.txt").read_text(encoding="utf-8")
    assert fingerprint(export(proj, True)) == expected


def test_doan_chi_co_so_khong_duoc_tach_ra_dich(source_epub, tmp_path):
    """`<p>42</p>` không có chữ cái nên `has_letters` phải loại nó."""
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    srcs = [r[0] for r in con.execute("SELECT src_html FROM blocks")]
    assert "42" not in srcs
```

- [ ] **Step 6: Chạy test để thấy nó hỏng vì chưa có vân tay**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: hai test vân tay FAIL với `FileNotFoundError: ...golden/epub_fingerprint.txt`. Test thứ ba PASS.

- [ ] **Step 7: Viết `tests/record_golden.py`**

```python
"""Ghi lại vân tay của hành vi HIỆN TẠI.

Chạy một lần ở Task 1 để đóng băng hành vi Phase 1. Sau đó CHỈ chạy lại khi bạn
cố ý đổi đầu ra của đường EPUB — và khi đó phải giải thích được vì sao trong
thông điệp commit.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import db
from helpers import build_epub, fingerprint, run_init, seed_translations
from test_golden_epub import GOLDEN_DIR, export


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = build_epub(tmp / "short.epub")
        for bilingual, name in ((False, "epub_fingerprint.txt"),
                                (True, "epub_fingerprint_bilingual.txt")):
            proj = run_init(src, tmp / f"proj_{name}")
            seed_translations(db.connect(proj))
            (GOLDEN_DIR / name).write_text(fingerprint(export(proj, bilingual)),
                                           encoding="utf-8")
            print("đã ghi", name)


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Sinh vân tay và xem nó có hợp lý không**

Run: `.venv/bin/python tests/record_golden.py && cat tests/golden/epub_fingerprint.txt`
Expected: hai file được ghi. Nội dung có dòng `title`, hai dòng `toc[...]`, và các dòng `doc` kèm mã băm. Đọc qua để chắc tiêu đề và mục lục đúng là của sách mẫu — **vân tay sai mà đóng băng thì lưới an toàn thành lưới thủng.**

- [ ] **Step 9: Chạy lại toàn bộ test**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 3 passed.

- [ ] **Step 10: Commit**

```bash
git add requirements-dev.txt .gitignore tests/
git commit -m "test: lưới an toàn cho đường EPUB trước khi tách tầng

Vân tay vàng của init + export, dùng bản dịch giả nên không gọi mạng.
Mọi task của Phase 2 phải giữ hai file trong tests/golden/ không đổi."
```

---

## Task 2: Schema v2 và migration từ v1

**Files:**
- Modify: `db.py` (viết lại toàn bộ)
- Modify: `epub_io.py:130` (import `DOC_TITLE, DOC_TOC` → tên mới)
- Modify: `cli.py:246,248` (`db.DOC_TOC`, `db.DOC_TITLE` → tên mới)
- Create: `tests/test_db_migration.py`

**Interfaces:**
- Produces: `db.PAGE_TOC = -1`, `db.PAGE_TITLE = -2`, `db.SCHEMA_VERSION = 2`, `db.current_version(con) -> int`, `db.migrate(con) -> int`. `db.connect`, `db.get_meta`, `db.set_meta` giữ nguyên chữ ký. `db.init_schema(con)` giữ tên nhưng nay tạo schema v2 và ghi `schema_version`.

- [ ] **Step 1: Viết test migration**

Tạo `tests/test_db_migration.py`. Schema v1 được chép nguyên văn vào test, để test không phụ thuộc việc `db.py` còn giữ nó hay không.

```python
"""Project tạo bằng Phase 1 phải mở được bằng code mới mà không mất gì."""
import sqlite3

import db

SCHEMA_V1 = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY, status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0, error TEXT,
    in_tokens INTEGER NOT NULL DEFAULT 0, out_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read INTEGER NOT NULL DEFAULT 0, cache_write INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE blocks (
    id INTEGER PRIMARY KEY, doc_index INTEGER NOT NULL, doc_href TEXT NOT NULL,
    pos INTEGER NOT NULL, tag TEXT NOT NULL, src_html TEXT NOT NULL,
    dst_html TEXT, chunk_id INTEGER REFERENCES chunks(id), flag TEXT
);
"""


def make_v1(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA_V1)
    con.execute("INSERT INTO chunks(id, status, in_tokens, out_tokens) "
                "VALUES(1, 'done', 1234, 5678)")
    con.execute("INSERT INTO chunks(id, status) VALUES(2, 'pending')")
    con.execute(
        "INSERT INTO blocks(id, doc_index, doc_href, pos, tag, src_html, dst_html, "
        "chunk_id, flag) VALUES(1, 0, 'c1.xhtml', 3, 'p', '<em>hi</em>', "
        "'<em>chao</em>', 1, 'too_short')")
    con.execute(
        "INSERT INTO blocks(id, doc_index, doc_href, pos, tag, src_html, chunk_id) "
        "VALUES(2, -1, '', 0, 'toc', 'Chapter One', 2)")
    con.commit()
    return con


def test_nhan_dien_v1(tmp_path):
    con = make_v1(tmp_path / "project.db")
    assert db.current_version(con) == 1


def test_db_moi_tinh_la_version_hien_tai(tmp_path):
    con = db.connect(tmp_path)
    assert db.current_version(con) == 0
    db.migrate(con)
    assert db.current_version(con) == db.SCHEMA_VERSION


def test_migration_giu_nguyen_du_lieu(tmp_path):
    con = make_v1(tmp_path / "project.db")
    db.migrate(con)

    assert db.current_version(con) == 2
    b1 = con.execute("SELECT * FROM blocks WHERE id=1").fetchone()
    assert b1["dst_html"] == "<em>chao</em>"
    assert b1["flag"] == "too_short"
    assert b1["chunk_id"] == 1
    assert b1["pos"] == 3
    assert b1["page_no"] == 0
    assert b1["kind"] == "text"
    assert b1["layout"] == '{"href":"c1.xhtml"}'

    b2 = con.execute("SELECT * FROM blocks WHERE id=2").fetchone()
    assert b2["page_no"] == db.PAGE_TOC

    c1 = con.execute("SELECT * FROM chunks WHERE id=1").fetchone()
    assert (c1["status"], c1["in_tokens"], c1["out_tokens"]) == ("done", 1234, 5678)
    assert c1["provider"] is None and c1["model"] is None


def test_migration_chay_lai_khong_hong(tmp_path):
    con = make_v1(tmp_path / "project.db")
    db.migrate(con)
    db.migrate(con)
    assert con.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 2


def test_schema_tuong_lai_bao_loi_ro(tmp_path):
    con = db.connect(tmp_path)
    db.migrate(con)
    db.set_meta(con, "schema_version", 99)
    con.commit()
    try:
        db.migrate(con)
    except RuntimeError as e:
        assert "99" in str(e)
    else:
        raise AssertionError("phải báo lỗi khi gặp schema mới hơn tool")
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_db_migration.py -v`
Expected: FAIL với `AttributeError: module 'db' has no attribute 'current_version'`.

- [ ] **Step 3: Viết lại `db.py`**

```python
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
    return int(value) if value else 1


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
        con.executescript(MIGRATE_V1_V2)
        set_meta(con, "schema_version", SCHEMA_VERSION)
        con.commit()
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
```

- [ ] **Step 4: Chạy test migration**

Run: `.venv/bin/python -m pytest tests/test_db_migration.py -v`
Expected: 5 passed.

Nếu `test_migration_giu_nguyen_du_lieu` báo `layout` khác `'{"href":"c1.xhtml"}'`, in ra giá trị thật rồi sửa chuỗi mong đợi cho khớp cách `json_object` của SQLite 3.45 đặt dấu cách — đừng sửa SQL để chiều test.

- [ ] **Step 5: Đổi tên hằng số ở hai chỗ còn lại**

Trong `epub_io.py`, hàm `extract_blocks`, đổi dòng import và hai chỗ dùng:

```python
    from db import PAGE_TITLE, PAGE_TOC  # tránh import vòng khi test riêng
```

rồi `doc_index=DOC_TOC` → `doc_index=PAGE_TOC` và `doc_index=DOC_TITLE` → `doc_index=PAGE_TITLE`.

Trong `cli.py`, hàm `cmd_export`: `db.DOC_TOC` → `db.PAGE_TOC`, `db.DOC_TITLE` → `db.PAGE_TITLE`.

- [ ] **Step 6: Cho `cmd_init` gọi `migrate` thay vì `init_schema`**

Trong `cli.py`, hàm `cmd_init`, đổi:

```python
    con = db.connect(proj)
    db.init_schema(con)
```

thành:

```python
    con = db.connect(proj)
    db.migrate(con)
```

và trong `open_project`, sau khi kết nối, nâng cấp project cũ trước khi dùng:

```python
def open_project(path: str):
    proj = Path(path)
    if not (proj / "project.db").exists():
        die(f"'{proj}' không phải project (thiếu project.db). Chạy `init` trước.")
    con = db.connect(proj)
    db.migrate(con)          # project Phase 1 được nâng cấp tại chỗ
    return proj, con
```

- [ ] **Step 7: Sửa câu lệnh INSERT trong `cmd_init` cho khớp cột mới**

Trong `cli.py`, hàm `cmd_init`, đổi vòng lặp ghi block thành:

```python
    for r in rows:
        cur = con.execute(
            "INSERT INTO blocks(page_no, pos, tag, src_html, layout) VALUES(?,?,?,?,?)",
            (r["doc_index"], r["pos"], r["tag"], r["src_html"],
             json.dumps({"href": r["doc_href"]}, ensure_ascii=False)),
        )
        r["id"] = cur.lastrowid
```

Thêm `import json` ở đầu `cli.py`.

- [ ] **Step 8: Sửa `make_chunks` và `cmd_export` cho khớp tên cột**

Trong `cli.py`, `make_chunks` đang đọc `r["doc_index"]` từ dict do `epub_io.extract_blocks` trả về — dict đó chưa đổi, nên **không sửa gì ở đây**. Task 3 mới đổi.

Trong `cmd_export`, đổi truy vấn và cách đọc href:

```python
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
```

- [ ] **Step 9: Chạy toàn bộ test — lưới an toàn phải còn nguyên**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 8 passed. Đặc biệt hai test vân tay vẫn PASS — nghĩa là đổi schema không đổi đầu ra.

- [ ] **Step 10: Commit**

```bash
git add db.py epub_io.py cli.py tests/test_db_migration.py
git commit -m "feat: schema v2 theo trang, migration tự động từ project Phase 1

doc_index thành page_no, doc_href chui vào layout JSON, thêm cột bbox,
line_bboxes, kind, cont_group cho PDF và provider/model cho chunks.
open_project tự nâng cấp nên project đang dịch dở không mất tiến độ."
```

---

## Task 3: Nhận diện định dạng, tầng ingest, tách chunking

**Files:**
- Create: `blocks.py`
- Create: `chunking.py`
- Create: `ingest/__init__.py`
- Create: `ingest/epub.py`
- Create: `tests/test_ingest_detect.py`
- Create: `tests/test_chunking.py`
- Modify: `epub_io.py` (`extract_blocks` trả về `Block`)
- Modify: `cli.py` (`cmd_init` dùng `ingest.load`; bỏ `make_chunks`; đổi `args.epub` → `args.source`)
- Modify: `tests/helpers.py` (`run_init` truyền `source=`)

**Interfaces:**
- Consumes: `db.PAGE_TOC`, `db.PAGE_TITLE` từ Task 2.
- Produces:
  - `blocks.Block(page_no, pos, tag, src_html, kind='text', bbox=None, line_bboxes=None, layout=None, cont_group=None)` với `.as_row() -> tuple` và hằng `blocks.INSERT_SQL`.
  - `ingest.detect_format(path) -> str` trả `"epub"` hoặc `"pdf"`, ném `ingest.UnsupportedSource`.
  - `ingest.load(path) -> ingest.Ingested(fmt, source_name, blocks)`.
  - `chunking.make_chunks(blocks, max_chars) -> list[list[Block]]`.

- [ ] **Step 1: Viết test nhận diện định dạng**

Tạo `tests/test_ingest_detect.py`:

```python
"""Nhận diện bằng nội dung file, không bao giờ bằng phần mở rộng.

Đây là lỗi đã thật sự xảy ra: một file PDF được copy thành source.epub và cả
pipeline chết ở tầng sâu với thông báo vô nghĩa.
"""
import zipfile

import pytest

import ingest


def test_epub_that_duoc_nhan_dien(source_epub):
    assert ingest.detect_format(source_epub) == "epub"


def test_pdf_mang_duoi_epub_van_bi_nhan_ra(tmp_path):
    fake = tmp_path / "sach.epub"
    fake.write_bytes(b"%PDF-1.6\r\n%\xe2\xe3\xcf\xd3\r\n")
    assert ingest.detect_format(fake) == "pdf"


def test_file_rong_bao_loi_ro(tmp_path):
    empty = tmp_path / "rong.epub"
    empty.write_bytes(b"")
    with pytest.raises(ingest.UnsupportedSource, match="rỗng"):
        ingest.detect_format(empty)


def test_zip_khong_phai_epub_bao_loi_ro(tmp_path):
    z = tmp_path / "taptin.epub"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("hello.txt", "xin chao")
    with pytest.raises(ingest.UnsupportedSource, match="EPUB"):
        ingest.detect_format(z)


def test_file_khong_ton_tai(tmp_path):
    with pytest.raises(ingest.UnsupportedSource, match="không thấy"):
        ingest.detect_format(tmp_path / "khong-co.epub")


def test_file_la_bao_loi_ro(tmp_path):
    odd = tmp_path / "sach.epub"
    odd.write_bytes(b"Xin chao, day la van ban thuong.")
    with pytest.raises(ingest.UnsupportedSource, match="không phải PDF hay EPUB"):
        ingest.detect_format(odd)


def test_pdf_chua_duoc_ho_tro_nhung_thong_bao_phai_ro(tmp_path):
    fake = tmp_path / "sach.pdf"
    fake.write_bytes(b"%PDF-1.6\r\n")
    with pytest.raises(ingest.UnsupportedSource, match="Phase 3"):
        ingest.load(fake)


def test_load_epub_tra_ve_block(source_epub):
    result = ingest.load(source_epub)
    assert result.fmt == "epub"
    assert result.source_name == "short.epub"
    tags = [b.tag for b in result.blocks]
    assert "h1" in tags and "p" in tags and "li" in tags
    assert all(b.kind == "text" for b in result.blocks if b.page_no >= 0)
    assert any(b.layout.get("href") == "c1.xhtml" for b in result.blocks)
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_ingest_detect.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'ingest'`.

- [ ] **Step 3: Viết `blocks.py`**

```python
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
```

- [ ] **Step 4: Viết `ingest/__init__.py`**

```python
"""Nhận diện định dạng nguồn và chọn tầng đọc vào tương ứng.

Nhận diện bằng magic bytes và nội dung thật của file. Phần mở rộng tên file
không được tin: một file PDF đổi tên thành .epub phải bị bắt ở đây, kèm thông
báo người dùng đọc hiểu được.
"""
import zipfile
from dataclasses import dataclass
from pathlib import Path

EPUB_MIMETYPE = "application/epub+zip"


class UnsupportedSource(Exception):
    """File nguồn không đọc được. Thông điệp dành cho người dùng cuối."""


@dataclass
class Ingested:
    fmt: str
    source_name: str
    blocks: list


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


def load(path) -> Ingested:
    p = Path(path)
    fmt = detect_format(p)
    if fmt == "epub":
        from ingest import epub as adapter
        return adapter.load(p)
    raise UnsupportedSource(
        "PDF sẽ được hỗ trợ từ Phase 3. Hiện booktrans chỉ đọc được EPUB."
    )
```

- [ ] **Step 5: Viết `ingest/epub.py`**

```python
"""Adapter EPUB: lớp vỏ mỏng quanh epub_io, khớp giao kèo của tầng ingest."""
from pathlib import Path

import epub_io
from ingest import Ingested


def load(path: Path) -> Ingested:
    book = epub_io.load_book(path)
    return Ingested(fmt="epub", source_name=path.name,
                    blocks=epub_io.extract_blocks(book))
```

- [ ] **Step 6: Cho `epub_io.extract_blocks` trả về `Block`**

Thay toàn bộ thân hàm `extract_blocks` trong `epub_io.py`:

```python
def extract_blocks(book) -> list:
    """Trả về list[Block] đúng thứ tự dịch."""
    from blocks import Block          # tránh import vòng khi test riêng
    from db import PAGE_TITLE, PAGE_TOC

    rows = []
    for di, item in enumerate(ordered_documents(book)):
        href = item.get_name()
        for pos, tag, inner in extract_from_html(item.get_content()):
            rows.append(Block(page_no=di, pos=pos, tag=tag, src_html=inner,
                              layout={"href": href}))

    for i, entry in enumerate(toc_entries(book.toc)):
        title = (getattr(entry, "title", "") or "").strip()
        if has_letters(title):
            rows.append(Block(page_no=PAGE_TOC, pos=i, tag="toc",
                              src_html=html.escape(title, quote=False)))

    titles = book.get_metadata("DC", "title")
    if titles and has_letters(titles[0][0]):
        rows.append(Block(page_no=PAGE_TITLE, pos=0, tag="title",
                          src_html=html.escape(titles[0][0], quote=False)))
    return rows
```

- [ ] **Step 7: Viết test cho chunking**

Tạo `tests/test_chunking.py`:

```python
"""Gom block thành chunk. Hàm thuần, không đụng DB, không đụng mạng."""
from blocks import Block
from chunking import make_chunks


def b(page_no, chars, pos=0):
    return Block(page_no=page_no, pos=pos, tag="p", src_html="x" * chars)


def test_gom_den_khi_day_chunk():
    chunks = make_chunks([b(0, 40), b(0, 40), b(0, 40)], max_chars=100)
    assert [len(c) for c in chunks] == [2, 1]


def test_khong_tron_trang_that_voi_muc_luc():
    """page_no âm là mục lục và tên sách — phải nằm chunk riêng."""
    chunks = make_chunks([b(0, 10), b(-1, 10), b(-2, 10)], max_chars=1000)
    assert len(chunks) == 3


def test_sang_trang_moi_thi_cat_khi_chunk_da_kha_day():
    chunks = make_chunks([b(0, 60), b(1, 10)], max_chars=100)
    assert [len(c) for c in chunks] == [1, 1]


def test_sang_trang_moi_nhung_chunk_con_rong_thi_khong_cat():
    chunks = make_chunks([b(0, 10), b(1, 10)], max_chars=100)
    assert [len(c) for c in chunks] == [2]


def test_danh_sach_rong():
    assert make_chunks([], max_chars=100) == []


def test_mot_block_to_hon_ca_chunk_van_di_mot_minh():
    chunks = make_chunks([b(0, 500), b(0, 10)], max_chars=100)
    assert [len(c) for c in chunks] == [1, 1]


def test_as_row_dung_thu_tu_va_khong_gom_db_id():
    blk = Block(page_no=7, pos=2, tag="p", src_html="xin chao",
                layout={"href": "c1.xhtml"})
    blk.db_id = 99
    row = blk.as_row()
    assert row[0] == 7 and row[1] == 2 and row[2] == "p" and row[3] == "text"
    assert row[4] == "xin chao"
    assert row[7] == '{"href":"c1.xhtml"}'
    assert 99 not in row          # db_id là chuyện của Python, không phải của cột
    assert len(row) == 9
```

- [ ] **Step 8: Chạy test chunking để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_chunking.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'chunking'`.

- [ ] **Step 9: Viết `chunking.py`**

Chuyển `make_chunks` từ `cli.py:57-75`, đổi truy cập dict thành thuộc tính của `Block`:

```python
"""Gom block liên tiếp thành chunk để gửi đi dịch.

Hàm thuần: không đụng DB, không đụng mạng, không đụng thư viện ngoài.
"""

DEFAULT_CHUNK_CHARS = 6000


def make_chunks(blocks: list, max_chars: int) -> list:
    """Gom các block liên tiếp thành chunk <= max_chars. Trả về list[list[Block]].

    Cắt chunk ở ba tình huống:
      - qua lại giữa trang thật và khối giả (mục lục, tên sách)
      - thêm block nữa là vượt max_chars
      - sang trang mới trong khi chunk đã đầy quá nửa
    """
    chunks, cur, size = [], [], 0
    for blk in blocks:
        n = len(blk.src_html)
        if cur:
            prev = cur[-1]
            doi_trang = blk.page_no != prev.page_no
            qua_khoi_gia = doi_trang and (blk.page_no < 0 or prev.page_no < 0)
            qua_to = size + n > max_chars
            trang_moi = doi_trang and size >= max_chars / 2
            if qua_khoi_gia or qua_to or trang_moi:
                chunks.append(cur)
                cur, size = [], 0
        cur.append(blk)
        size += n
    if cur:
        chunks.append(cur)
    return chunks
```

- [ ] **Step 10: Chạy test chunking**

Run: `.venv/bin/python -m pytest tests/test_chunking.py -v`
Expected: 7 passed.

- [ ] **Step 11: Nối `cmd_init` vào tầng ingest**

Trong `cli.py`: xoá hàm `make_chunks` và hằng `DEFAULT_CHUNK_CHARS` (nay nằm ở `chunking.py`), thêm `import blocks`, `import chunking`, `import ingest`, rồi viết lại `cmd_init`:

```python
def cmd_init(args):
    src = Path(args.source)
    try:
        fmt = ingest.detect_format(src)
    except ingest.UnsupportedSource as e:
        die(str(e))

    proj = Path(args.dir) if args.dir else Path("projects") / src.stem
    db_path = proj / "project.db"
    if db_path.exists():
        if not args.force:
            die(f"{proj} đã có project. Dùng --force để tạo lại (sẽ xóa bản dịch cũ).")
        db_path.unlink()

    proj.mkdir(parents=True, exist_ok=True)
    stored = proj / f"source.{fmt}"
    shutil.copy2(src, stored)
    for name, content in (("style.md", DEFAULT_STYLE), ("glossary.txt", DEFAULT_GLOSSARY)):
        if not (proj / name).exists():
            (proj / name).write_text(content, encoding="utf-8")

    print(f"Đang đọc {src.name} ({fmt}) ...")
    try:
        data = ingest.load(stored)
    except ingest.UnsupportedSource as e:
        die(str(e))
    if not data.blocks:
        die("không tìm thấy đoạn văn bản nào để dịch (sách toàn ảnh? DRM?).")

    con = db.connect(proj)
    db.migrate(con)
    for blk in data.blocks:
        blk.db_id = con.execute(blocks.INSERT_SQL, blk.as_row()).lastrowid

    groups = chunking.make_chunks(data.blocks, args.chunk_chars)
    for group in groups:
        cid = con.execute("INSERT INTO chunks(status) VALUES('pending')").lastrowid
        con.executemany("UPDATE blocks SET chunk_id=? WHERE id=?",
                        [(cid, blk.db_id) for blk in group])

    db.set_meta(con, "source_name", src.name)
    db.set_meta(con, "source_format", fmt)
    db.set_meta(con, "chunk_chars", args.chunk_chars)
    con.commit()

    total = sum(len(b.src_html) for b in data.blocks)
    print(f"Xong: {len(data.blocks)} đoạn, {total:,} ký tự, {len(groups)} chunk.")
    print(f"Project: {proj}")
    print(f"Việc tiếp theo:\n  1. Sửa {proj / 'style.md'} và {proj / 'glossary.txt'}"
          f"\n  2. python cli.py status {proj}\n  3. python cli.py translate {proj} --limit 3")
```

- [ ] **Step 12: Đổi tên tham số dòng lệnh `epub` thành `source`**

Trong `cli.py`, hàm `main`, đổi:

```python
    p = sub.add_parser("init", help="tạo project từ file sách (EPUB; PDF từ Phase 3)")
    p.add_argument("source", help="đường dẫn file sách")
    p.add_argument("--dir", help="thư mục project (mặc định: projects/<tên file>)")
    p.add_argument("--chunk-chars", type=int, default=chunking.DEFAULT_CHUNK_CHARS,
                   help=f"kích thước chunk tính theo ký tự (mặc định {chunking.DEFAULT_CHUNK_CHARS})")
```

Và trong `tests/helpers.py`, hàm `run_init`, đổi `epub=str(source)` thành `source=str(source)`.

- [ ] **Step 13: Cho `cmd_export` đọc đúng tên file nguồn**

Trong `cli.py`, `cmd_export` đang mở `proj / "source.epub"`. Giữ được vì Task 4 mới chuyển sang tầng render, nhưng `source_format` nay đã có trong `meta` nên dùng luôn cho đúng:

```python
    fmt = db.get_meta(con, "source_format", "epub")
    book = epub_io.load_book(proj / f"source.{fmt}")
```

- [ ] **Step 14: Chạy toàn bộ test**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 23 passed. Hai test vân tay vẫn PASS.

- [ ] **Step 15: Thử tay đúng cái bẫy đã gặp thật**

```bash
mkdir -p /tmp/bt && cp "ebook/astrology.pdf.pdf" /tmp/bt/sach.epub
.venv/bin/python cli.py init /tmp/bt/sach.epub --dir /tmp/bt/proj
```

Expected: in ra `Lỗi: PDF sẽ được hỗ trợ từ Phase 3. Hiện booktrans chỉ đọc được EPUB.` và thoát sạch, **không có traceback**. So với Phase 1 thì đây là chỗ nó chết với `File is not a zip file`.

- [ ] **Step 16: Commit**

```bash
git add blocks.py chunking.py ingest/ epub_io.py cli.py tests/
git commit -m "feat: tầng ingest, nhận diện định dạng bằng nội dung file

detect_format đọc magic bytes và mimetype trong zip, nên PDF đổi tên
thành .epub bị bắt ngay ở init kèm thông báo đọc hiểu được.
Block thành đơn vị dữ liệu chung; make_chunks chuyển sang chunking.py
dưới dạng hàm thuần có test riêng."
```

---

## Task 4: Tầng render

**Files:**
- Create: `render/__init__.py`
- Create: `render/epub.py`
- Modify: `cli.py` (`cmd_export` gọi tầng render)
- Create: `tests/test_render.py`

**Interfaces:**
- Consumes: `db.PAGE_TOC`, `db.PAGE_TITLE`; `epub_io.write_translated`.
- Produces: `render.write(fmt, project, con, out_path, *, bilingual=False)`; `render.default_output_name(fmt, bilingual) -> str`; `render.UnsupportedTarget`.

- [ ] **Step 1: Viết test cho tầng render**

Tạo `tests/test_render.py`:

```python
"""Tầng ghi ra: chọn adapter theo định dạng, và từ chối định dạng chưa làm."""
import pytest

import db
import render
from helpers import fingerprint, run_init, seed_translations


def test_ten_file_mac_dinh():
    assert render.default_output_name("epub", False) == "output.vi.epub"
    assert render.default_output_name("epub", True) == "output.bilingual.epub"


def test_dinh_dang_chua_ho_tro_bao_loi_ro():
    with pytest.raises(render.UnsupportedTarget, match="pdf"):
        render.write("pdf", None, None, None)


def test_ghi_epub_qua_tang_render(source_epub, tmp_path):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    seed_translations(con)
    out = proj / "qua-render.epub"
    render.write("epub", proj, con, out)
    assert out.exists()
    # tên sách cũng là một block, nên bản dịch giả phải lộ ra trong vân tay
    assert "[VI] A Short Book" in fingerprint(out)


def test_con_doan_chua_dich_thi_giu_nguyen_tieng_anh(source_epub, tmp_path):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html='[VI] xong' WHERE id=1")
    con.commit()
    out = proj / "mot-phan.epub"
    render.write("epub", proj, con, out)
    assert out.exists()
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_render.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'render'`.

- [ ] **Step 3: Viết `render/__init__.py`**

```python
"""Chọn tầng ghi ra theo định dạng nguồn."""


class UnsupportedTarget(Exception):
    """Định dạng đầu ra chưa làm. Thông điệp dành cho người dùng cuối."""


def default_output_name(fmt: str, bilingual: bool) -> str:
    suffix = "bilingual" if bilingual else "vi"
    return f"output.{suffix}.{fmt}"


def write(fmt: str, project, con, out_path, *, bilingual: bool = False) -> None:
    if fmt == "epub":
        from render import epub as adapter
        adapter.write(project, con, out_path, bilingual=bilingual)
        return
    raise UnsupportedTarget(
        f"chưa ghi ra được định dạng '{fmt}'. PDF là Phase 4."
    )
```

- [ ] **Step 4: Viết `render/epub.py`**

Chuyển phần lắp `doc_map` / `toc_map` từ `cli.cmd_export` vào đây:

```python
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
```

- [ ] **Step 5: Rút gọn `cmd_export` trong `cli.py`**

```python
def cmd_export(args):
    proj, con = open_project(args.project)
    fmt = db.get_meta(con, "source_format", "epub")

    n_missing = con.execute(
        "SELECT COUNT(*) FROM blocks WHERE dst_html IS NULL").fetchone()[0]
    if n_missing:
        print(f"Lưu ý: còn {n_missing} đoạn chưa dịch, sẽ giữ nguyên tiếng Anh "
              f"trong file xuất.")

    out = Path(args.output) if args.output else \
        proj / render.default_output_name(fmt, args.bilingual)
    try:
        render.write(fmt, proj, con, out, bilingual=args.bilingual)
    except render.UnsupportedTarget as e:
        die(str(e))
    print(f"Đã xuất: {out}")
```

Thêm `import render` ở đầu `cli.py`. Xoá hàm `_to_text` khỏi `cli.py` (nay nằm ở `render/epub.py`). Xoá `import epub_io` ở đầu `cmd_export`.

- [ ] **Step 6: Chạy toàn bộ test**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 27 passed. Hai test vân tay vẫn PASS — **đây là lúc lưới an toàn có giá trị nhất, vì vừa di chuyển code ghi file.**

- [ ] **Step 7: Commit**

```bash
git add render/ cli.py tests/test_render.py
git commit -m "feat: tầng render, cmd_export không còn biết EPUB là gì

Phần lắp doc_map/toc_map chuyển vào render/epub.py. cli.py chỉ còn
chọn định dạng và đặt tên file. Vân tay vàng không đổi."
```

---

## Task 5: Tầng provider và adapter Anthropic

**Files:**
- Create: `providers/__init__.py`
- Create: `providers/anthropic_api.py`
- Modify: `translator.py` (bỏ phần gọi API trực tiếp)
- Modify: `cli.py` (`cmd_translate` lấy provider)
- Create: `tests/test_providers.py`
- Create: `tests/test_translate_chunk.py`

**Interfaces:**
- Consumes: `translator.build_system`, `translator.build_user`, `translator.check_translation`, `translator.parse_response` — giữ nguyên chữ ký.
- Produces:
  - `providers.names() -> list[str]`, `providers.get(name) -> module`, `providers.normalize_usage(dict) -> dict`.
  - Mỗi module provider có: `NAME: str`, `DEFAULT_MODEL: str | None`, `SUPPORTS_CACHE: bool`, `make_client()`, `call(client, model, system, user, max_tokens) -> (text, usage, stop_reason)`, `is_fatal(exc) -> bool`, `is_retryable(exc) -> bool`.
  - `translator.translate_chunk(con, provider, client, model, system, chunk_id) -> dict` — **chữ ký đổi**, không còn tham số `call`.

- [ ] **Step 1: Viết test cho danh bạ provider**

Tạo `tests/test_providers.py`:

```python
"""Danh bạ provider và việc chuẩn hoá usage."""
import pytest

import providers


def test_liet_ke_ten():
    assert "anthropic" in providers.names()


def test_ten_sai_bao_loi_liet_ke_lua_chon():
    with pytest.raises(ValueError) as e:
        providers.get("khong-ton-tai")
    assert "anthropic" in str(e.value)


def test_lay_duoc_anthropic():
    p = providers.get("anthropic")
    assert p.NAME == "anthropic"
    assert p.SUPPORTS_CACHE is True


def test_chuan_hoa_usage_day_du():
    raw = {"input": 10, "output": 20, "cache_read": 5, "cache_write": 1}
    assert providers.normalize_usage(raw) == raw


def test_chuan_hoa_usage_thieu_truong_thi_ve_khong():
    assert providers.normalize_usage({"output": 7}) == {
        "input": 0, "output": 7, "cache_read": 0, "cache_write": 0}


def test_chuan_hoa_usage_gia_tri_none():
    assert providers.normalize_usage({"input": None, "output": 3})["input"] == 0


def test_chuan_hoa_bo_truong_la():
    out = providers.normalize_usage({"output": 1, "reasoning_tokens": 99})
    assert set(out) == {"input", "output", "cache_read", "cache_write"}
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'providers'`.

- [ ] **Step 3: Viết `providers/__init__.py`**

```python
"""Tầng nhà cung cấp mô hình.

Mỗi module con là một giao thức API. Phần lõi chỉ biết đúng giao kèo dưới đây,
không biết đang nói chuyện với ai:

    NAME: str
    DEFAULT_MODEL: str | None       # None nghĩa là bắt buộc truyền --model
    SUPPORTS_CACHE: bool
    make_client()
    call(client, model, system, user, max_tokens) -> (text, usage, stop_reason)
    is_fatal(exc) -> bool           # hỏng vĩnh viễn: key sai, model sai, hết tiền
    is_retryable(exc) -> bool       # tạm thời: rate limit, mạng, 5xx
"""
import importlib

_REGISTRY = {
    "anthropic": "providers.anthropic_api",
    "openai": "providers.openai_compat",
}

USAGE_KEYS = ("input", "output", "cache_read", "cache_write")


def names() -> list:
    return sorted(_REGISTRY)


def get(name: str):
    if name not in _REGISTRY:
        raise ValueError(
            f"không có provider '{name}'. Chọn một trong: {', '.join(names())}"
        )
    return importlib.import_module(_REGISTRY[name])


def normalize_usage(raw: dict) -> dict:
    """Về đúng bốn khoá, thiếu hoặc None thì thành 0.

    Mỗi nhà cung cấp đặt tên trường một kiểu và đôi khi bỏ trống. `status` cộng
    tiền từ bốn số này nên chúng không bao giờ được là None.
    """
    return {k: int(raw.get(k) or 0) for k in USAGE_KEYS}
```

- [ ] **Step 4: Viết `providers/anthropic_api.py`**

Chuyển từ `translator.py:126-146` và phần `FATAL_ERRORS`:

```python
"""Giao thức Anthropic."""
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
    return text, usage, resp.stop_reason
```

- [ ] **Step 5: Chạy test provider**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: 7 passed.

- [ ] **Step 6: Viết test cho `translate_chunk` với provider giả**

Tạo `tests/test_translate_chunk.py`:

```python
"""Dịch một chunk, dùng provider giả. Không gọi mạng."""
import pytest

import db
import translator
from helpers import run_init


class FakeFatal(Exception):
    pass


class FakeRetryable(Exception):
    pass


class FakeProvider:
    """Trả lời theo một danh sách kịch bản đã soạn sẵn."""

    NAME = "fake"
    DEFAULT_MODEL = "fake-1"
    SUPPORTS_CACHE = False

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []

    def make_client(self):
        return object()

    def is_fatal(self, exc):
        return isinstance(exc, FakeFatal)

    def is_retryable(self, exc):
        return isinstance(exc, FakeRetryable)

    def call(self, client, model, system, user, max_tokens):
        self.calls.append(user)
        item = self.scripts.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def echo_segments(user: str, wrap=lambda s: f"[VI] {s}"):
    """Dựng câu trả lời hợp lệ từ chính các <seg> trong prompt."""
    import re
    out = []
    for sid, body in re.findall(r'<seg id="(\d+)"[^>]*>(.*?)</seg>', user, re.S):
        out.append(f'<seg id="{sid}">{wrap(body)}</seg>')
    return "\n".join(out)


USAGE = {"input": 10, "output": 20, "cache_read": 0, "cache_write": 0}


@pytest.fixture
def project(source_epub, tmp_path):
    proj = run_init(source_epub, tmp_path / "proj")
    return proj, db.connect(proj)


def test_dich_thanh_cong_luu_vao_db(project):
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]

    captured = {}

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            captured["user"] = user
            return echo_segments(user), USAGE, "end_turn"

    p = P([])
    res = translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)

    assert res["status"] == "done"
    assert res["missing"] == 0
    rows = con.execute(
        "SELECT dst_html FROM blocks WHERE chunk_id=?", (cid,)).fetchall()
    assert all(r["dst_html"].startswith("[VI] ") for r in rows)


def test_thieu_doan_thi_thu_lai_roi_thanh_cong(project):
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]

    class P(FakeProvider):
        def __init__(self):
            super().__init__([])
            self.n = 0

        def call(self, client, model, system, user, max_tokens):
            self.n += 1
            if self.n == 1:
                segs = echo_segments(user).split("\n")
                return "\n".join(segs[:-1]), USAGE, "end_turn"   # bỏ sót đoạn cuối
            return echo_segments(user), USAGE, "end_turn"

    p = P()
    res = translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)
    assert res["status"] == "done"
    assert p.n == 2


def test_loi_nghiem_trong_thi_dung_han(project):
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]
    p = FakeProvider([FakeFatal("api key sai")])
    with pytest.raises(translator.FatalAPIError, match="api key sai"):
        translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)


def test_le_thang_html_thi_gan_co(project):
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            # bỏ hết thẻ inline -> check_translation phải bắt được
            import re
            out = []
            for sid, body in re.findall(r'<seg id="(\d+)"[^>]*>(.*?)</seg>', user, re.S):
                out.append(f'<seg id="{sid}">{re.sub(r"<[^>]+>", "", body)}</seg>')
            return "\n".join(out), USAGE, "end_turn"

    p = P([])
    res = translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)
    flags = [r["flag"] for r in con.execute(
        "SELECT flag FROM blocks WHERE chunk_id=? AND flag IS NOT NULL", (cid,))]
    assert "tag_mismatch" in flags
    assert res["flagged"] >= 1


def test_usage_thieu_truong_khong_lam_crash(project):
    """Provider bên thứ ba có thể không trả cache_read/cache_write."""
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            import providers
            return echo_segments(user), providers.normalize_usage({"output": 5}), "end_turn"

    p = P([])
    res = translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)
    assert res["status"] == "done"
    row = con.execute("SELECT * FROM chunks WHERE id=?", (cid,)).fetchone()
    assert row["cache_read"] == 0 and row["out_tokens"] == 5
```

- [ ] **Step 7: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_translate_chunk.py -v`
Expected: FAIL — `translate_chunk()` nhận sai số tham số.

- [ ] **Step 8: Sửa `translator.py`**

Xoá `import anthropic`, khối `FATAL_ERRORS`, hàm `make_client`, hàm `call_api`. Giữ `FatalAPIError`. Đổi thân `translate_chunk`:

```python
def translate_chunk(con, provider, client, model: str, system: str, chunk_id: int) -> dict:
    """Dịch các block chưa có bản dịch trong chunk.

    `provider` là module (hoặc object) theo giao kèo ở providers/__init__.py.
    Trả về {status, error, flagged, usage, missing}.
    """
    rows = con.execute(
        "SELECT * FROM blocks WHERE chunk_id=? ORDER BY id", (chunk_id,)
    ).fetchall()
    todo = {b["id"]: b for b in rows if b["dst_html"] is None}
    context = _get_context(con, rows[0])

    best_effort = {}
    usage = dict(input=0, output=0, cache_read=0, cache_write=0)
    error = None
    attempts = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if not todo:
            break
        attempts += 1
        user = build_user(context, list(todo.values()), retry=attempt > 1)
        try:
            text, u, stop = provider.call(client, model, system, user, MAX_TOKENS)
        except Exception as e:
            if provider.is_fatal(e):
                con.rollback()
                raise FatalAPIError(f"{type(e).__name__}: {e}") from e
            if not provider.is_retryable(e):
                con.rollback()
                raise
            error = f"{type(e).__name__}: {e}"
            time.sleep(min(30, 5 * attempt))
            continue

        for k in usage:
            usage[k] += u[k]

        for bid, dst in parse_response(text).items():
            b = todo.get(bid)
            if b is None:
                continue
            problem = check_translation(b["src_html"], dst)
            if problem is None:
                con.execute("UPDATE blocks SET dst_html=?, flag=NULL WHERE id=?", (dst, bid))
                del todo[bid]
            else:
                best_effort[bid] = (dst, problem)

        if todo:
            error = f"lần {attempt}: còn {len(todo)} đoạn thiếu/lỗi" + \
                    (" (bị cắt do max_tokens, hãy giảm --chunk-chars)" if stop == "max_tokens" else "")

    flagged = 0
    for bid, (dst, problem) in best_effort.items():
        if bid in todo and dst.strip():
            con.execute("UPDATE blocks SET dst_html=?, flag=? WHERE id=?", (dst, problem, bid))
            del todo[bid]
            flagged += 1

    status = "done" if not todo else "failed"
    con.execute(
        "UPDATE chunks SET status=?, attempts=attempts+?, error=?, provider=?, model=?, "
        "in_tokens=in_tokens+?, out_tokens=out_tokens+?, cache_read=cache_read+?, "
        "cache_write=cache_write+? WHERE id=?",
        (status, attempts, None if status == "done" else error,
         getattr(provider, "NAME", None), model,
         usage["input"], usage["output"], usage["cache_read"], usage["cache_write"],
         chunk_id),
    )
    con.commit()
    return dict(status=status, error=error, flagged=flagged, usage=usage, missing=len(todo))
```

Đồng thời sửa `_get_context` cho khớp tên cột mới:

```python
def _get_context(con, first_block) -> list:
    if first_block["page_no"] < 0:                   # mục lục / tên sách: không cần ngữ cảnh
        return []
    rows = con.execute(
        "SELECT src_html, dst_html FROM blocks "
        "WHERE id < ? AND page_no >= 0 AND dst_html IS NOT NULL "
        "ORDER BY id DESC LIMIT ?",
        (first_block["id"], CONTEXT_BLOCKS),
    ).fetchall()
    return [(r["src_html"], r["dst_html"]) for r in reversed(rows)]
```

- [ ] **Step 9: Nối `cmd_translate` vào tầng provider**

Trong `cli.py`:

```python
def cmd_translate(args):
    import translator

    proj, con = open_project(args.project)
    try:
        provider = providers.get(args.provider)
    except ValueError as e:
        die(str(e))

    model = args.model or provider.DEFAULT_MODEL
    if not model:
        die(f"provider '{args.provider}' không có model mặc định. Truyền --model.")

    style_path = proj / "style.md"
    style = style_path.read_text(encoding="utf-8") if style_path.exists() else ""
    system = translator.build_system(style, translator.load_glossary(proj / "glossary.txt"))
    try:
        client = provider.make_client()
    except Exception as e:
        die(f"không khởi tạo được provider '{args.provider}': {e}")

    todo = [r["id"] for r in con.execute(
        "SELECT id FROM chunks WHERE status != 'done' ORDER BY id")]
    total_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    if not todo:
        print("Không còn chunk nào cần dịch. Chạy `export` để xuất file.")
        return
    if args.limit:
        todo = todo[:args.limit]

    print(f"Provider: {provider.NAME} | Model: {model} | Dịch {len(todo)} chunk "
          f"(tổng {total_chunks}). Ctrl+C để dừng, chạy lại sẽ tiếp tục.")
    ok = failed = 0
    try:
        for n, cid in enumerate(todo, 1):
            size = con.execute(
                "SELECT COUNT(*), SUM(LENGTH(src_html)) FROM blocks WHERE chunk_id=?",
                (cid,)).fetchone()
            print(f"[{n}/{len(todo)}] chunk {cid} ({size[0]} đoạn, {size[1]:,} ký tự) ... ",
                  end="", flush=True)
            try:
                res = translator.translate_chunk(con, provider, client, model, system, cid)
            except translator.FatalAPIError as e:
                print("LỖI NGHIÊM TRỌNG")
                die(f"{e}\nKiểm tra API key, tên model (--model), số dư tài khoản.")
            u = res["usage"]
            extra = f", {res['flagged']} đoạn gắn cờ" if res["flagged"] else ""
            if res["status"] == "done":
                ok += 1
                print(f"ok (vào {u['input'] + u['cache_read'] + u['cache_write']:,}, "
                      f"ra {u['output']:,}{extra})")
            else:
                failed += 1
                print(f"THẤT BẠI, còn {res['missing']} đoạn: {res['error']}")
    except KeyboardInterrupt:
        print("\nĐã dừng. Tiến độ đã lưu; chạy lại lệnh translate để tiếp tục.")
    print(f"Xong phiên này: {ok} chunk ok, {failed} lỗi. Xem `status` để biết chi tiết.")
```

Thêm `import providers` ở đầu `cli.py`. Bỏ khối kiểm tra `ANTHROPIC_API_KEY` — nay provider tự lo, và mỗi provider dùng biến môi trường khác nhau.

Trong `main`, thêm hai cờ cho `translate`:

```python
    p.add_argument("--provider", default=os.environ.get("BOOKTRANS_PROVIDER", "anthropic"),
                   help=f"mặc định anthropic. Có: {', '.join(providers.names())}")
    p.add_argument("--model", help="mặc định theo provider")
```

- [ ] **Step 10: Chạy toàn bộ test**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 39 passed. Vân tay vàng vẫn PASS.

- [ ] **Step 11: Kiểm tay rằng tên provider sai được báo tử tế**

```bash
.venv/bin/python cli.py translate projects/khong-co --provider gemini 2>&1 | head -3
```

Expected: báo `'projects/khong-co' không phải project` trước. Tạo một project thật từ EPUB mẫu rồi thử lại để thấy thông báo `không có provider 'gemini'. Chọn một trong: anthropic, openai`.

- [ ] **Step 12: Commit**

```bash
git add providers/ translator.py cli.py tests/
git commit -m "feat: tầng provider, translator không còn biết Anthropic là ai

make_client/call_api/FATAL_ERRORS chuyển sang providers/anthropic_api.py.
translate_chunk nhận provider từ ngoài và ghi provider/model vào chunks.
normalize_usage đảm bảo bốn khoá luôn là số, kể cả khi bên kia trả thiếu."
```

---

## Task 6: Provider giao thức OpenAI

Một module này mở ra DeepSeek, Qwen, OpenRouter, và model chạy tại máy qua Ollama hoặc LM Studio — tất cả đều nói giao thức OpenAI.

**Files:**
- Create: `providers/openai_compat.py`
- Modify: `requirements.txt`
- Create: `tests/test_openai_compat.py`

**Interfaces:**
- Consumes: `providers.normalize_usage`.
- Produces: module `providers.openai_compat` đúng giao kèo ở Task 5, với `NAME = "openai"`, `DEFAULT_MODEL = None`, `SUPPORTS_CACHE = False`.

- [ ] **Step 1: Cài SDK và ghi vào requirements**

```bash
.venv/bin/pip install 'openai>=1.40'
printf 'openai>=1.40\n' >> requirements.txt
```

- [ ] **Step 2: Viết test với client giả**

Tạo `tests/test_openai_compat.py`:

```python
"""Giao thức OpenAI. Client giả, không gọi mạng."""
import types

import openai
import pytest

from providers import openai_compat as oc


def fake_response(text, prompt=100, completion=50, cached=0, finish="stop"):
    details = types.SimpleNamespace(cached_tokens=cached)
    usage = types.SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion,
                                  prompt_tokens_details=details)
    choice = types.SimpleNamespace(
        message=types.SimpleNamespace(content=text), finish_reason=finish)
    return types.SimpleNamespace(choices=[choice], usage=usage)


class FakeClient:
    def __init__(self, response):
        self.seen = {}
        outer = self

        class Completions:
            def create(self, **kw):
                outer.seen = kw
                return response

        self.chat = types.SimpleNamespace(completions=Completions())


def test_giao_keo_module():
    assert oc.NAME == "openai"
    assert oc.DEFAULT_MODEL is None
    assert oc.SUPPORTS_CACHE is False


def test_call_tra_ve_dung_bo_ba():
    client = FakeClient(fake_response("<seg id=\"1\">chao</seg>"))
    text, usage, stop = oc.call(client, "m-1", "SYS", "USER", 4096)
    assert text == "<seg id=\"1\">chao</seg>"
    assert stop == "stop"
    assert usage == {"input": 100, "output": 50, "cache_read": 0, "cache_write": 0}


def test_system_va_user_di_dung_vai():
    client = FakeClient(fake_response("x"))
    oc.call(client, "m-1", "SYS", "USER", 4096)
    msgs = client.seen["messages"]
    assert msgs[0] == {"role": "system", "content": "SYS"}
    assert msgs[1] == {"role": "user", "content": "USER"}
    assert client.seen["model"] == "m-1"


def test_token_da_cache_bi_tru_khoi_input():
    """prompt_tokens của OpenAI đã bao gồm phần cache; không trừ là đếm đúp."""
    client = FakeClient(fake_response("x", prompt=100, cached=30))
    _, usage, _ = oc.call(client, "m-1", "SYS", "USER", 4096)
    assert usage["input"] == 70
    assert usage["cache_read"] == 30


def test_noi_dung_rong_khong_thanh_none():
    client = FakeClient(fake_response(None))
    text, _, _ = oc.call(client, "m-1", "SYS", "USER", 4096)
    assert text == ""


def test_khong_co_prompt_tokens_details():
    """Máy chủ tương thích nhưng cũ có thể không có trường này."""
    usage = types.SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    choice = types.SimpleNamespace(
        message=types.SimpleNamespace(content="x"), finish_reason="stop")
    client = FakeClient(types.SimpleNamespace(choices=[choice], usage=usage))
    _, u, _ = oc.call(client, "m-1", "SYS", "USER", 4096)
    assert u == {"input": 10, "output": 5, "cache_read": 0, "cache_write": 0}


def test_phan_loai_loi():
    fatal = openai.AuthenticationError(
        "sai key", response=types.SimpleNamespace(status_code=401, headers={}), body=None)
    assert oc.is_fatal(fatal) is True
    assert oc.is_retryable(fatal) is False
```

- [ ] **Step 3: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_openai_compat.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'providers.openai_compat'`.

- [ ] **Step 4: Viết `providers/openai_compat.py`**

```python
"""Giao thức OpenAI.

Dùng được cho chính OpenAI và cho mọi dịch vụ nói cùng giao thức: DeepSeek,
Qwen, OpenRouter, Together, và model chạy tại máy qua Ollama hoặc LM Studio.

Biến môi trường:
    OPENAI_API_KEY        khoá; với máy chủ tại máy thì đặt gì cũng được
    BOOKTRANS_BASE_URL    ví dụ http://localhost:11434/v1 cho Ollama
"""
import os

import openai

import providers

NAME = "openai"
DEFAULT_MODEL = None          # bắt buộc truyền --model: không đoán hộ người dùng
SUPPORTS_CACHE = False        # cache tự động ở phía máy chủ, không khai báo được

_FATAL = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
    openai.BadRequestError,
)


def make_client():
    return openai.OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("BOOKTRANS_BASE_URL"),
        max_retries=5,
    )


def is_fatal(exc) -> bool:
    return isinstance(exc, _FATAL)


def is_retryable(exc) -> bool:
    return isinstance(exc, openai.APIError) and not is_fatal(exc)


def call(client, model: str, system: str, user: str, max_tokens: int):
    """Trả về (text, usage đã chuẩn hoá, finish_reason)."""
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    choice = resp.choices[0]
    text = choice.message.content or ""

    u = resp.usage
    details = getattr(u, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) or 0 if details else 0
    prompt = getattr(u, "prompt_tokens", 0) or 0
    usage = providers.normalize_usage({
        # prompt_tokens đã gồm cả phần đọc từ cache; tách ra để khỏi đếm đúp
        "input": max(prompt - cached, 0),
        "output": getattr(u, "completion_tokens", 0),
        "cache_read": cached,
        "cache_write": 0,
    })
    return text, usage, choice.finish_reason
```

- [ ] **Step 5: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_openai_compat.py -v`
Expected: 7 passed.

Nếu `test_phan_loai_loi` hỏng vì chữ ký khởi tạo exception của openai SDK khác, đổi cách dựng exception trong test cho khớp phiên bản đã cài — đừng nới lỏng `_FATAL`.

- [ ] **Step 6: Chạy toàn bộ test**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 46 passed.

- [ ] **Step 7: Commit**

```bash
git add providers/openai_compat.py requirements.txt tests/test_openai_compat.py
git commit -m "feat: provider giao thức OpenAI

Một module phủ DeepSeek, Qwen, OpenRouter và model chạy tại máy qua
Ollama/LM Studio. BOOKTRANS_BASE_URL trỏ tới máy chủ tương thích.
Token đã cache được tách khỏi prompt_tokens để không đếm đúp."
```

---

## Task 7: `status` theo provider, và cập nhật README

**Files:**
- Modify: `cli.py` (`cmd_status`)
- Modify: `README.md`
- Create: `tests/test_status.py`

**Interfaces:**
- Consumes: cột `chunks.provider`, `chunks.model` từ Task 2 và Task 5.
- Produces: không có API mới; đây là task hoàn thiện.

- [ ] **Step 1: Viết test cho `status`**

Tạo `tests/test_status.py`:

```python
"""`status` phải chạy được ở mọi trạng thái project, kể cả khi chưa dịch gì."""
import argparse

import cli
import db
from helpers import run_init


def run_status(proj, capsys):
    cli.cmd_status(argparse.Namespace(project=str(proj)))
    return capsys.readouterr().out


def test_project_chua_dich_gi(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    out = run_status(proj, capsys)
    assert "short.epub" in out
    assert "0/" in out or "0 " in out


def test_hien_provider_da_dung(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    con.execute("UPDATE chunks SET status='done', provider='anthropic', "
                "model='claude-sonnet-5', in_tokens=100, out_tokens=200 WHERE id=1")
    con.commit()
    out = run_status(proj, capsys)
    assert "anthropic" in out
    assert "claude-sonnet-5" in out


def test_khong_crash_khi_usage_toan_khong(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    con.execute("UPDATE chunks SET status='done'")
    con.commit()
    out = run_status(proj, capsys)
    assert "Đoạn:" in out
```

- [ ] **Step 2: Chạy test để thấy chỗ nào hỏng**

Run: `.venv/bin/python -m pytest tests/test_status.py -v`
Expected: `test_hien_provider_da_dung` FAIL vì `status` chưa in provider.

- [ ] **Step 3: Thêm phần provider vào `cmd_status`**

Chèn vào `cli.py`, hàm `cmd_status`, ngay sau khối in token đã dùng:

```python
    used = con.execute(
        "SELECT provider, model, COUNT(*) n, "
        "COALESCE(SUM(in_tokens),0) i, COALESCE(SUM(out_tokens),0) o "
        "FROM chunks WHERE provider IS NOT NULL GROUP BY provider, model "
        "ORDER BY n DESC").fetchall()
    if used:
        print("Đã dịch bằng:")
        for r in used:
            print(f"  {r['provider']} / {r['model']}: {r['n']} chunk, "
                  f"vào {r['i']:,}, ra {r['o']:,}")
```

- [ ] **Step 4: Chạy test status**

Run: `.venv/bin/python -m pytest tests/test_status.py -v`
Expected: 3 passed.

- [ ] **Step 5: Cập nhật README**

Sửa phần "Cài đặt" và "Giới hạn đã biết" của `README.md`:

```markdown
## Cài đặt

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt      # chỉ cần nếu bạn chạy test

# Anthropic (mặc định)
export ANTHROPIC_API_KEY=sk-ant-...

# hoặc bất kỳ dịch vụ nào nói giao thức OpenAI
export BOOKTRANS_PROVIDER=openai
export OPENAI_API_KEY=...
export BOOKTRANS_BASE_URL=https://.../v1     # bỏ trống nếu dùng chính OpenAI
```

Chọn provider và model ngay trên dòng lệnh:

```bash
python cli.py translate projects/sach --provider openai --model <tên-model>
```

`status` cho biết chunk nào đã dịch bằng provider và model nào.
```

Và đổi dòng giới hạn đầu tiên:

```markdown
- Chỉ EPUB. PDF là Phase 3-7 (xem `docs/superpowers/specs/`).
```

Thêm một mục mới vào cuối README:

```markdown
## Chạy test

```bash
python -m pytest tests/ -v
```

Không test nào gọi mạng. `tests/golden/` giữ vân tay của đầu ra EPUB — nếu nó
đổi mà bạn không cố ý đổi, nghĩa là vừa có gì đó hỏng.
```

- [ ] **Step 6: Chạy toàn bộ test lần cuối**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 49 passed.

- [ ] **Step 7: Nghiệm thu bằng tay — vòng đầy đủ trên EPUB thật**

Nếu bạn có sẵn một file EPUB:

```bash
.venv/bin/python cli.py init <sach.epub> --dir /tmp/bt-nghiemthu --force
.venv/bin/python cli.py status /tmp/bt-nghiemthu
```

Expected: `init` tách đoạn và chia chunk như Phase 1; `status` in ra số đoạn, số chunk, ước tính token. Không cần gọi API.

- [ ] **Step 8: Commit**

```bash
git add cli.py README.md tests/test_status.py
git commit -m "feat: status cho biết đã dịch bằng provider nào, cập nhật README

Phase 2 xong: ingest, render và providers đã tách khỏi lõi, blocks theo
trang, migration từ project Phase 1. Đường EPUB không đổi một byte."
```

---

## Nghiệm thu Phase 2

Xong Phase 2 khi tất cả những điều sau đúng:

1. `.venv/bin/python -m pytest tests/ -v` — toàn bộ pass, không test nào gọi mạng.
2. Hai file trong `tests/golden/` **không đổi** so với lúc Task 1 sinh ra chúng (`git log tests/golden/` chỉ có đúng một commit).
3. `python cli.py init <pdf đổi tên thành .epub>` báo lỗi đọc hiểu được, không traceback.
4. Một `project.db` tạo bằng Phase 1 mở được bằng code mới, giữ nguyên bản dịch và tiến độ chunk.
5. `python cli.py translate <proj> --provider openai --model <m>` chạy được đường OpenAI (cần khoá thật, đây là bước duy nhất tốn tiền — dùng `--limit 1`).
6. `grep -rn "anthropic" translator.py cli.py` không ra kết quả nào.

Điều kiện 6 là phép thử gọn nhất cho toàn bộ mục đích của Phase 2: phần lõi không còn biết nó đang nói chuyện với ai.
