"""Sửa tay một đoạn rồi xuất lại — bản dịch nằm trong SQLite, không nằm trong file."""
import argparse

import pytest

import cli
import db
from helpers import run_init


def test_xem_mot_doan(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks").fetchone()[0]
    con.execute("UPDATE blocks SET dst_html='bản dịch cũ' WHERE id=?", (bid,))
    con.commit()

    cli.cmd_edit(argparse.Namespace(project=str(proj), block=bid, set=None))
    ra = capsys.readouterr().out
    assert "bản dịch cũ" in ra
    assert str(bid) in ra


def test_sua_mot_doan(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks").fetchone()[0]
    con.commit()

    cli.cmd_edit(argparse.Namespace(project=str(proj), block=bid,
                                    set="bản dịch mới"))
    con2 = db.connect(proj)
    assert con2.execute("SELECT dst_html FROM blocks WHERE id=?",
                        (bid,)).fetchone()[0] == "bản dịch mới"


def test_sua_xong_thi_go_co(source_epub, tmp_path):
    """Người dùng vừa sửa tay thì cảnh báo cũ không còn đúng nữa."""
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks").fetchone()[0]
    con.execute("UPDATE blocks SET flag='tag_mismatch' WHERE id=?", (bid,))
    con.commit()

    cli.cmd_edit(argparse.Namespace(project=str(proj), block=bid, set="đã sửa"))
    con2 = db.connect(proj)
    assert con2.execute("SELECT flag FROM blocks WHERE id=?",
                        (bid,)).fetchone()[0] is None


def test_doan_khong_ton_tai_bao_loi_ro(source_epub, tmp_path):
    """Review Focus 4."""
    proj = run_init(source_epub, tmp_path / "proj")
    with pytest.raises(SystemExit) as e:
        cli.cmd_edit(argparse.Namespace(project=str(proj), block=999999, set="x"))
    assert "999999" in str(e.value)


def test_xem_doan_chua_dich(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks").fetchone()[0]
    cli.cmd_edit(argparse.Namespace(project=str(proj), block=bid, set=None))
    assert "chưa dịch" in capsys.readouterr().out


def test_set_rong_khong_duoc_xoa_ban_dich_da_tra_tien(source_epub, tmp_path):
    """`--set ""` (biến shell chưa đặt) từng ghi đè bản dịch bằng chuỗi rỗng.

    Mất tiền thật: block vẫn thoả `dst_html IS NOT NULL` nên `translate` không
    dịch lại, `status` đếm là xong, `export` ra ô trống — và bản tiếng Anh
    cũng không còn hiện. Không có đường nào từ CLI quay lại NULL.
    """
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks").fetchone()[0]
    con.execute("UPDATE blocks SET dst_html='bản dịch đã trả tiền' WHERE id=?",
                (bid,))
    con.commit()

    for rong in ("", "   ", "\n"):
        with pytest.raises(SystemExit):
            cli.cmd_edit(argparse.Namespace(project=str(proj), block=bid, set=rong))

    con2 = db.connect(proj)
    assert con2.execute("SELECT dst_html FROM blocks WHERE id=?",
                        (bid,)).fetchone()[0] == "bản dịch đã trả tiền"
