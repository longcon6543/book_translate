"""Project tạo bằng Phase 1 phải mở được bằng code mới mà không mất gì."""
import sqlite3

import pytest

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


def test_migration_hong_giua_chung_thi_lui_ve_nguyen_ven(tmp_path, monkeypatch):
    """Mất điện / đầy đĩa giữa migration không được khoá chết project.

    Trước khi sửa: blocks đã thành v2 nhưng chưa kịp ghi schema_version, nên
    current_version() vẫn báo 1, lần mở sau chạy lại migration và chết vĩnh viễn
    với 'no such column: doc_index'. Bản dịch đã trả tiền nằm trong file mà
    không lệnh nào mở được nữa.
    """
    con = make_v1(tmp_path / "project.db")
    hong = db.MIGRATE_V1_V2.replace(
        "DROP TABLE blocks;", "SELECT cot_khong_ton_tai FROM blocks;\nDROP TABLE blocks;")
    monkeypatch.setattr(db, "MIGRATE_V1_V2", hong)
    with pytest.raises(sqlite3.Error):
        db.migrate(con)

    # phải lùi sạch: vẫn là v1 nguyên vẹn, mở lại được
    assert db.current_version(con) == 1
    assert con.execute("SELECT doc_href FROM blocks WHERE id=1").fetchone()[0] == "c1.xhtml"
    monkeypatch.undo()                    # bỏ script hỏng đi
    db.migrate(con)                       # lần sau chạy lại phải thành công
    assert db.current_version(con) == 2
    assert con.execute("SELECT dst_html FROM blocks WHERE id=1").fetchone()[0] == "<em>chao</em>"


def test_nhan_ra_v2_ke_ca_khi_thieu_dong_schema_version(tmp_path):
    """Project đã hỏng sẵn từ bản cũ phải tự nhận ra mình là v2, không migrate lại."""
    con = db.connect(tmp_path)
    db.migrate(con)
    con.execute("DELETE FROM meta WHERE key='schema_version'")
    con.commit()
    assert db.current_version(con) == db.SCHEMA_VERSION
