"""Xuất PDF khổ đôi từ project. Không gọi mạng, không tốn token."""
import argparse

import pymupdf
import pytest

import cli
import db
import render
from helpers import build_pdf, run_init, trang_mot_doan


@pytest.fixture
def proj(tmp_path):
    src = build_pdf(tmp_path / "m.pdf", [
        [{"text": "Chuong Mot", "x": 67, "y": 80, "size": 14}] + trang_mot_doan(120, 4),
        trang_mot_doan(80, 3, tien_to="hai"),
        trang_mot_doan(80, 3, tien_to="ba"),
    ])
    p = run_init(src, tmp_path / "proj")
    con = db.connect(p)
    for r in con.execute("SELECT id, src_html FROM blocks").fetchall():
        con.execute("UPDATE blocks SET dst_html=? WHERE id=?",
                    (f"Bản dịch tiếng Việt của đoạn {r['id']}", r["id"]))
    con.commit()
    return p


def test_xuat_ra_file_kho_ngang(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out)
    d = pymupdf.open(out)
    assert d.page_count == 3
    assert d[0].rect.width == 522 * 2 and d[0].rect.height == 666
    d.close()


def test_ban_dich_nam_ben_phai(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out)
    d = pymupdf.open(out)
    # insert_htmlbox đặt chữ bằng dấu cách không ngắt (\xa0), không phải dấu
    # cách thường — đo thật lúc dò. Mọi chỗ đọc ngược lại chữ đã đặt đều phải
    # chuẩn hoá trước khi so.
    phai = d[0].get_text(clip=pymupdf.Rect(522, 0, 1044, 666)).replace("\xa0", " ")
    assert "Bản dịch" in phai
    d.close()


def test_loc_theo_khoang_trang(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, pages=(1, 2))
    d = pymupdf.open(out)
    assert d.page_count == 2
    d.close()


def test_dry_run_khong_can_ban_dich(proj, tmp_path):
    """--dry-run đè CHÍNH chữ gốc trở lại, kèm chữ độn cho dài ra như tiếng
    Việt. Lệch chỗ nào là lỗi bóc chữ, chắc chắn không phải lỗi dịch."""
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html=NULL")
    con.commit()
    out = tmp_path / "thu.pdf"
    tk = render.write("pdf", proj, db.connect(proj), out, dry_run=True)
    assert out.exists() and tk["so_khoi"] > 0


def test_probe_them_trang_bao_cao_o_dau(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, probe=True)
    d = pymupdf.open(out)
    assert d.page_count == 4, "phải có 1 trang báo cáo + 3 khổ"
    bao_cao = d[0].get_text()
    assert "tràn" in bao_cao.lower() or "overflow" in bao_cao.lower()
    d.close()


def test_thong_ke_tra_ve_du_so_lieu(proj, tmp_path):
    tk = render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf")
    assert set(tk) >= {"so_trang", "so_khoi", "tran", "co_trung_vi"}
    assert tk["so_trang"] == 3 and tk["so_khoi"] > 0


def test_mode_reflow_xuat_duoc_kho_doi(proj, tmp_path):
    """Trước Phase 6 test này ghim 'reflow chưa làm'. Giờ nó đã làm."""
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="reflow")
    d = pymupdf.open(out)
    assert d.page_count == 3
    assert d[0].rect.width == 522 * 2 and d[0].rect.height == 666
    d.close()


def test_epub_khong_dung_duoc_mode_overlay(source_epub, tmp_path):
    """overlay cần toạ độ PDF mà EPUB không có."""
    p = run_init(source_epub, tmp_path / "proj")
    with pytest.raises(render.UnsupportedTarget, match="EPUB"):
        render.write("epub", p, db.connect(p), tmp_path / "ra.epub", mode="overlay")


def test_cli_export_pdf_chay_duoc(proj, tmp_path, capsys):
    out = tmp_path / "cli.pdf"
    cli.cmd_export(argparse.Namespace(project=str(proj), output=str(out),
                                      bilingual=False, mode="overlay",
                                      pages=None, dry_run=False, probe=False))
    assert out.exists()
    assert "Đã xuất" in capsys.readouterr().out


# ---- sửa sau review toàn nhánh ----

def test_file_ra_khong_phinh_vi_nhung_font_lap(proj, tmp_path):
    """insert_htmlbox nhúng cả file TTF mỗi lần gọi — mỗi KHỐI một bản. Với
    garbage=3 thì 20 trang ra 75MB mà 98% là font lặp, và cả cuốn 925 trang
    không chạy xong trong 37 phút. Đo thật của reviewer."""
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out)
    goc = out.stat().st_size

    # Dọn rác triệt để rồi lưu lại: nếu file gốc lớn hơn nhiều lần thì phần
    # chênh chính là font bị nhúng lặp mỗi khối.
    d = pymupdf.open(out)
    sach = tmp_path / "sach.pdf"
    d.save(str(sach), garbage=4, deflate=True)
    d.close()
    gon = sach.stat().st_size
    assert goc < gon * 2, (
        f"file xuất {goc/1e6:.1f}MB nhưng dọn kỹ chỉ còn {gon/1e6:.1f}MB "
        f"({goc/gon:.0f}x) — font đang bị nhúng lặp mỗi khối")


def test_khoi_tran_khung_van_giu_lai_chu_goc(proj, tmp_path):
    """Spec mục 6 bậc 7: 'hết cách thì GIỮ 70%, gắn cờ overflow'. Xoá chữ Anh
    rồi không đặt được gì là để lại LỖ TRỐNG — reviewer đếm được 597 lỗ trên
    cả cuốn."""
    con = db.connect(proj)
    r = con.execute("SELECT id, page_no FROM blocks WHERE page_no=1 "
                    "ORDER BY pos LIMIT 1").fetchone()
    # khung tí hon + chữ rất dài: chắc chắn không vừa cả ở đáy thang
    # khung tí hon ĐÈ ĐÚNG chỗ có chữ gốc (trang 1 có chữ quanh y=80)
    con.execute("UPDATE blocks SET dst_html=?, bbox='67.0,72.0,105.0,84.0' "
                "WHERE id=?",
                ("Một đoạn văn tiếng Việt cực kỳ dài không thể nào vừa " * 40, r["id"]))
    con.commit()
    out = tmp_path / "ra.pdf"
    tk = render.write("pdf", proj, db.connect(proj), out, pages=(1, 1))
    assert tk["tran"] >= 1, "test không ép được khối nào tràn khung"
    # Soi ĐÚNG khung của khối bị tràn, không phải cả nửa trang: các khối khác
    # vẫn có chữ nên hỏi "nửa phải có chữ không" là xanh giả.
    d = pymupdf.open(out)
    khung = pymupdf.Rect(522 + 65, 70, 522 + 110, 86)
    trong_khung = d[0].get_text(clip=khung).replace("\xa0", " ").strip()
    d.close()
    assert trong_khung, (
        "khung của khối tràn trống trơn — đã xoá chữ Anh mà không đặt lại gì")


def test_dry_run_KHONG_duoc_ghi_co_vao_db(proj, tmp_path):
    """--dry-run đè chữ Anh độn thêm 25%; cờ sinh ra từ đó là giả. Lệnh đầu
    tiên README bảo người dùng chạy không được ghi gì vào DB."""
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html=NULL, flag=NULL")
    # thu nhỏ vài khung để dry-run chắc chắn sinh ra cờ tràn
    con.execute("UPDATE blocks SET bbox='67.0,72.0,105.0,84.0' WHERE page_no=1")
    con.commit()
    render.write("pdf", proj, db.connect(proj), tmp_path / "thu.pdf", dry_run=True)
    n = db.connect(proj).execute(
        "SELECT COUNT(*) FROM blocks WHERE flag IS NOT NULL").fetchone()[0]
    assert n == 0, f"dry-run đã ghi {n} cờ vào DB"


def test_export_khong_duoc_xoa_co_cua_translator(proj, tmp_path):
    """flag là cột dùng chung: translator ghi tag_mismatch/too_short vào đó."""
    con = db.connect(proj)
    r = con.execute("SELECT id FROM blocks WHERE kind='text' AND page_no=2 "
                    "ORDER BY pos LIMIT 1").fetchone()
    con.execute("UPDATE blocks SET flag='tag_mismatch' WHERE id=?", (r["id"],))
    con.commit()
    render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf")
    con2 = db.connect(proj)
    con2.row_factory = None
    sau = con2.execute("SELECT flag FROM blocks WHERE id=?", (r["id"],)).fetchone()[0]
    assert sau == "tag_mismatch", f"cờ của translator bị đè thành {sau!r}"


def test_co_overflow_cu_duoc_don_khi_xuat_lai(proj, tmp_path):
    """Sửa bản dịch cho ngắn lại rồi xuất lại: cờ overflow cũ phải biến mất.

    Dùng khối THÂN BÀI, không dùng khối tiêu đề: tiêu đề 14pt trong khung một
    dòng thì bản dịch nào cũng tràn, nên nó không kiểm được việc dọn cờ.
    """
    con = db.connect(proj)
    r = con.execute("SELECT id FROM blocks WHERE kind='text' AND page_no=2 "
                    "ORDER BY pos LIMIT 1").fetchone()
    con.execute("UPDATE blocks SET flag='overflow' WHERE id=?", (r["id"],))
    con.commit()
    render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf")
    con2 = db.connect(proj)
    con2.row_factory = None
    sau = con2.execute("SELECT flag FROM blocks WHERE id=?", (r["id"],)).fetchone()[0]
    assert sau is None, f"cờ overflow cũ vẫn còn: {sau!r}"


def test_khoang_trang_ngoai_sach_bao_loi_ro(proj, tmp_path):
    with pytest.raises(render.UnsupportedTarget, match="trang"):
        render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf",
                     pages=(2000, 2010))


def test_khoang_trang_nguoc_bao_loi_ro(proj, tmp_path):
    with pytest.raises(render.UnsupportedTarget, match="trang"):
        render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf",
                     pages=(3, 1))


def test_pages_dem_tu_1_nhu_moi_thu_nguoi_dung_thay(proj, tmp_path, capsys):
    """README bảo --pages 1-20 là 20 trang đầu. Đếm từ 0 thì trang đầu của
    sách không bao giờ với tới được."""
    out = tmp_path / "ra.pdf"
    cli.cmd_export(argparse.Namespace(project=str(proj), output=str(out),
                                      bilingual=False, mode=None, pages="1-1",
                                      dry_run=False, probe=False))
    d = pymupdf.open(out)
    giua = d[0].get_text(clip=pymupdf.Rect(500, 0, 545, 666))
    d.close()
    assert "1" in giua, "--pages 1-1 phải ra khổ mang số trang 1"


def test_trang_bao_cao_doc_duoc_bang_tieng_viet(proj, tmp_path):
    """Trang --probe dùng insert_text với font base-14, mà chính dự án này
    chứng minh font đó thiếu 17/25 chữ có dấu. Nó tự biến thành ô vuông."""
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, probe=True)
    d = pymupdf.open(out)
    bao_cao = d[0].get_text().replace("\xa0", " ")
    d.close()
    for tu in ("Khổ", "Tỉ lệ", "chữ"):
        assert tu in bao_cao, f"trang báo cáo mất dấu ở {tu!r}: {bao_cao[:120]!r}"


def _nua_phai(out, trang):
    d = pymupdf.open(out)
    chu = d[trang].get_text(clip=pymupdf.Rect(522, 0, 1044, 666)).replace("\xa0", " ")
    d.close()
    return chu


def test_reflow_nua_phai_chi_co_chu_viet(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="reflow")
    phai = _nua_phai(out, 0)
    assert "Bản dịch" in phai
    assert "noi dung day du" not in phai, "chữ Anh gốc lọt sang nửa dịch"


def test_reflow_chua_dich_thi_hien_chu_anh(proj, tmp_path):
    """Review Focus 1 ở mức lệnh: write phải đưa khối chưa dịch tới bộ dựng."""
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html=NULL WHERE page_no=1")
    con.commit()
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="reflow")
    assert "hai 0 noi dung" in _nua_phai(out, 1)


def test_reflow_dry_run_khong_ghi_co_vao_db(proj, tmp_path):
    """Review Focus 3 (Phase 6) / 5 (Phase 8A): chữ ở dry-run là chữ Anh độn,
    cờ sinh ra là giả. Từ 8A tràn chỉ sinh ở trang dự phòng, nên phép thử
    dùng một khối dài tới mức trang không dàn vừa ở 75% — cả ở dry-run (chữ
    Anh độn) lẫn khi xuất thật."""
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks WHERE page_no=0").fetchone()[0]
    dai = "noi dung rat dai " * 3000
    con.execute("UPDATE blocks SET src_html=?, dst_html=?, flag=NULL WHERE id=?",
                (dai, dai, bid))
    con.commit()

    def dem():
        return db.connect(proj).execute(
            "SELECT COUNT(*) FROM blocks WHERE flag='overflow'").fetchone()[0]

    render.write("pdf", proj, db.connect(proj), tmp_path / "a.pdf",
                 mode="reflow", dry_run=True)
    assert dem() == 0, "dry-run đã ghi cờ vào DB"
    render.write("pdf", proj, db.connect(proj), tmp_path / "b.pdf", mode="reflow")
    assert dem() >= 1, "khối rơi dự phòng phải gây tràn — không thì phép thử trên vô nghĩa"


def test_reflow_probe_them_trang_bao_cao(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="reflow", probe=True)
    d = pymupdf.open(out)
    assert d.page_count == 4
    d.close()


def test_epub_khong_dung_duoc_mode_reflow(source_epub, tmp_path):
    """Review Focus 2: reflow cũng cần toạ độ trang mà EPUB không có."""
    p = run_init(source_epub, tmp_path / "proj")
    with pytest.raises(render.UnsupportedTarget, match="EPUB"):
        render.write("epub", p, db.connect(p), tmp_path / "ra.epub", mode="reflow")


def test_cli_export_mode_reflow_chay_duoc(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    cli.cmd_export(argparse.Namespace(
        project=str(proj), output=str(out), bilingual=False, mode="reflow",
        pages=None, dry_run=False, probe=False))
    assert out.exists()


def test_reflow_bao_so_trang_du_phong(proj, tmp_path):
    """D6: export phải nói có bao nhiêu trang rơi về bố cục theo vị trí."""
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html=? WHERE page_no=2",
                ("Chữ Việt rất dài. " * 3000,))
    con.commit()
    tk = render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf",
                      mode="reflow")
    assert tk["trang_du_phong"] == 1


def test_reflow_trang_binh_thuong_khong_du_phong(proj, tmp_path):
    tk = render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf",
                      mode="reflow")
    assert tk["trang_du_phong"] == 0


def test_export_in_so_trang_du_phong(proj, tmp_path, capsys):
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html=? WHERE page_no=2",
                ("Chữ Việt rất dài. " * 3000,))
    con.commit()
    cli.cmd_export(argparse.Namespace(
        project=str(proj), output=str(tmp_path / "ra.pdf"), bilingual=False,
        mode="reflow", pages=None, dry_run=False, probe=False))
    assert "1 trang dự phòng" in capsys.readouterr().out


import json


def _gan_vung_hinh(proj):
    con = db.connect(proj)
    db.set_meta(con, "vung_hinh", json.dumps({"0": [[80, 300, 440, 500]]}))
    con.commit()


def test_reflow_ve_o_anh_tu_meta(proj, tmp_path):
    _gan_vung_hinh(proj)
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="reflow")
    assert "ảnh" in _nua_phai(out, 0)


def test_overlay_khong_ve_o_anh(proj, tmp_path):
    """Review Focus 5: overlay giữ ảnh gốc trên bản sao trang."""
    _gan_vung_hinh(proj)
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="overlay")
    assert "ảnh" not in _nua_phai(out, 0)
