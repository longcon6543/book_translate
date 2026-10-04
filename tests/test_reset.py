"""Xoá bản dịch của một khoảng trang để dịch lại bằng model khác.

Lần dùng thật đầu tiên phát hiện ra lỗ hổng này: `translate` chỉ lấy đoạn có
`dst_html IS NULL`, nên bản dịch của model đầu tiên bị đóng đinh vĩnh viễn.
Muốn đổi model thì phải có đường xoá — và vì nó xoá thứ đã trả tiền, mặc định
phải là KHÔNG xoá.
"""
import argparse

import pytest

import cli
import db
from helpers import run_init


def dung(proj, **kw):
    m = dict(project=str(proj), pages=None, yes=False)
    m.update(kw)
    return argparse.Namespace(**m)


def da_dich(proj, trang=0):
    """Giả lập một lượt dịch đã trả tiền trên một trang."""
    con = db.connect(proj)
    ids = [r[0] for r in con.execute(
        "SELECT id FROM blocks WHERE page_no=?", (trang,))]
    con.execute(f"UPDATE blocks SET dst_html='ban dich cu', flag='tag_mismatch' "
                f"WHERE id IN ({','.join('?' * len(ids))})", ids)
    cids = [r[0] for r in con.execute(
        "SELECT DISTINCT chunk_id FROM blocks WHERE page_no=? "
        "AND chunk_id IS NOT NULL", (trang,))]
    con.execute(f"UPDATE chunks SET status='done', in_tokens=5000, out_tokens=3000 "
                f"WHERE id IN ({','.join('?' * len(cids))})", cids)
    con.commit()
    return ids, cids


def test_khong_co_yes_thi_khong_xoa_gi(source_epub, tmp_path, capsys):
    """Mặc định chỉ báo cáo. Xoá thứ đã trả tiền không được là hành vi mặc định."""
    proj = run_init(source_epub, tmp_path / "proj")
    ids, _ = da_dich(proj)

    cli.cmd_reset(dung(proj, pages="1-1"))

    con = db.connect(proj)
    con2 = con.execute(
        f"SELECT COUNT(*) FROM blocks WHERE id IN ({','.join('?' * len(ids))}) "
        f"AND dst_html IS NOT NULL", ids).fetchone()[0]
    assert con2 == len(ids), "đã xoá dù chưa có --yes"
    ra = capsys.readouterr().out
    assert "--yes" in ra, "phải nói rõ cách xác nhận"
    assert str(len(ids)) in ra, "phải báo sẽ xoá bao nhiêu đoạn"


def test_co_yes_thi_xoa_ban_dich_va_co(source_epub, tmp_path):
    proj = run_init(source_epub, tmp_path / "proj")
    ids, _ = da_dich(proj)

    cli.cmd_reset(dung(proj, pages="1-1", yes=True))

    con = db.connect(proj)
    con_lai = con.execute(
        f"SELECT COUNT(*) FROM blocks WHERE id IN ({','.join('?' * len(ids))}) "
        f"AND (dst_html IS NOT NULL OR flag IS NOT NULL)", ids).fetchone()[0]
    assert con_lai == 0, "còn sót bản dịch hoặc cờ cũ"


def test_chunk_quay_ve_cho_dich_de_translate_lay_lai(source_epub, tmp_path):
    """Xoá đoạn mà để chunk 'done' thì `translate` bỏ qua, xoá thành vô nghĩa."""
    proj = run_init(source_epub, tmp_path / "proj")
    _, cids = da_dich(proj)

    cli.cmd_reset(dung(proj, pages="1-1", yes=True))

    con = db.connect(proj)
    trang_thai = {r[0] for r in con.execute(
        f"SELECT status FROM chunks WHERE id IN ({','.join('?' * len(cids))})", cids)}
    assert trang_thai == {"pending"}, trang_thai


def test_xoa_luon_so_token_de_khong_ngoai_suy_sai(source_epub, tmp_path):
    """`translate` CỘNG THÊM token vào chunk. Giữ số cũ thì cùng một đoạn chữ
    mang token của hai lượt dịch, và `status` ngoại suy cả cuốn đắt gấp đôi."""
    proj = run_init(source_epub, tmp_path / "proj")
    _, cids = da_dich(proj)

    cli.cmd_reset(dung(proj, pages="1-1", yes=True))

    con = db.connect(proj)
    tong = con.execute(
        f"SELECT SUM(in_tokens + out_tokens) FROM chunks "
        f"WHERE id IN ({','.join('?' * len(cids))})", cids).fetchone()[0]
    assert tong == 0, f"còn {tong} token của lượt dịch cũ"


def test_khoang_chua_dich_gi_thi_noi_ro(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    cli.cmd_reset(dung(proj, pages="1-1", yes=True))
    assert "không có" in capsys.readouterr().out.lower()


def test_khoang_trang_nguoc_va_ngoai_sach_bi_tu_choi(source_epub, tmp_path):
    """Cùng luật với translate và export: ba tình huống, ba câu khác nhau."""
    proj = run_init(source_epub, tmp_path / "proj")
    da_dich(proj)

    with pytest.raises(SystemExit) as e:
        cli.cmd_reset(dung(proj, pages="20-10", yes=True))
    assert "ngược" in str(e.value)

    with pytest.raises(SystemExit) as e:
        cli.cmd_reset(dung(proj, pages="900-999", yes=True))
    assert "ngoài sách" in str(e.value)


def test_thieu_pages_thi_tu_choi_chu_khong_xoa_ca_cuon(source_epub, tmp_path):
    """`reset` không có --pages mà xoá sạch cả cuốn là tai hoạ. Bắt ghi rõ."""
    proj = run_init(source_epub, tmp_path / "proj")
    ids, _ = da_dich(proj)

    with pytest.raises(SystemExit):
        cli.cmd_reset(dung(proj, yes=True))

    con = db.connect(proj)
    con_lai = con.execute(
        f"SELECT COUNT(*) FROM blocks WHERE id IN ({','.join('?' * len(ids))}) "
        f"AND dst_html IS NOT NULL", ids).fetchone()[0]
    assert con_lai == len(ids)
