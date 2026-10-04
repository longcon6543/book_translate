"""`status` phải nói được: còn bao nhiêu, đáng ngờ chỗ nào, tốn bao nhiêu."""
import argparse

import cli
import db
from helpers import run_init


def chay(proj, capsys):
    cli.cmd_status(argparse.Namespace(project=str(proj)))
    return capsys.readouterr().out


def test_dem_co_theo_tung_loai(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    ids = [r[0] for r in con.execute("SELECT id FROM blocks ORDER BY id LIMIT 3")]
    for bid, co in zip(ids, ("tag_mismatch", "missing_number", "missing_number")):
        con.execute("UPDATE blocks SET flag=? WHERE id=?", (co, bid))
    con.commit()

    ra = chay(proj, capsys)
    # Ghim vào BẢNG ĐẾM THEO LOẠI, không phải danh sách liệt kê cũ: danh sách
    # cũ cũng in tên cờ nên assert lỏng sẽ xanh giả.
    assert "bản gốc có chữ số mà bản dịch không có" in ra, "thiếu lời giải thích"
    dong = [d for d in ra.splitlines() if "missing_number" in d and "2" in d]
    assert dong, f"không thấy dòng đếm 'missing_number ... 2':\n{ra}"


def test_tien_do_theo_trang(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html='xong' WHERE page_no=0")
    con.commit()
    ra = chay(proj, capsys)
    # Ghim vào dòng tiến độ MỚI; chữ "trang" đơn thuần đã có trong danh sách cũ.
    assert "Trang đã dịch xong hoàn toàn" in ra, f"thiếu dòng tiến độ:\n{ra}"


def test_khong_co_co_nao_thi_khong_in_muc_do(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    ra = chay(proj, capsys)
    assert "đáng xem lại" not in ra


def test_uoc_tinh_chi_phi_ca_cuon_tu_phan_da_dich(source_epub, tmp_path, capsys,
                                                  monkeypatch):
    """Sau khi dịch thử, phải ngoại suy được tiền cho cả cuốn."""
    monkeypatch.setenv("PRICE_IN", "3")
    monkeypatch.setenv("PRICE_OUT", "15")
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]
    con.execute("UPDATE chunks SET status='done', in_tokens=1000, out_tokens=2000 "
                "WHERE id=?", (cid,))
    con.execute("UPDATE blocks SET dst_html='x' WHERE chunk_id=?", (cid,))
    con.commit()
    ra = chay(proj, capsys)
    assert "cả cuốn" in ra.lower()


def test_gia_cache_khong_duoc_tinh_bang_gia_vao(source_epub, tmp_path, capsys,
                                                monkeypatch):
    """Cache đọc rẻ bằng 1/10 giá vào, cache ghi đắt 1.25 lần.

    Gộp cả ba vào giá vào thì thổi phồng đúng con số người dùng dựa vào để
    quyết có dịch cả cuốn hay không — và `status` còn nhân sai số đó lên khi
    ngoại suy. Ở đây: 1000*3 + 5000*0.3 + 3000*3.75 + 2000*15 = 45.750
    => $0.05, chứ không phải $0.06 của cách tính gộp.
    """
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    con.execute("UPDATE chunks SET in_tokens=1000, out_tokens=2000, "
                "cache_read=5000, cache_write=3000 "
                "WHERE id=(SELECT MIN(id) FROM chunks)")
    con.commit()
    monkeypatch.setenv("PRICE_IN", "3")
    monkeypatch.setenv("PRICE_OUT", "15")

    ra = chay(proj, capsys)
    assert "$0.05" in ra, f"tính gộp giá cache:\n{ra}"
    assert "$0.06" not in ra
