"""Lệnh CLI phải hỏng tử tế: thông báo cho người, không phải traceback,
và không để lại rác trên đĩa.
"""
import argparse

import pytest

import cli
import db
from helpers import run_init


def test_tu_choi_dinh_dang_thi_khong_de_lai_thu_muc_mo_coi(tmp_path):
    """init copy file nguồn TRƯỚC khi biết có đọc được không.

    Với sách scan 1GB, người dùng ngồi chờ copy xong mới bị từ chối — và thư
    mục project vẫn nằm lại trên đĩa kèm nguyên file 1GB, không lệnh nào dọn,
    không thông báo nào nhắc tới.
    """
    src = tmp_path / "sach.epub"
    src.write_bytes(b"Day chi la van ban thuong, khong phai PDF cung khong phai EPUB.")
    proj = tmp_path / "proj"

    with pytest.raises(SystemExit):
        cli.cmd_init(argparse.Namespace(
            source=str(src), dir=str(proj), chunk_chars=6000, force=True))

    assert not proj.exists(), f"để lại rác: {list(proj.iterdir()) if proj.exists() else ''}"


def test_schema_moi_hon_tool_thi_bao_cho_nguoi_dung(tmp_path):
    """db.migrate soạn sẵn câu tiếng Việt tử tế — nhưng không ai bắt nó."""
    proj = tmp_path / "proj"
    proj.mkdir()
    con = db.connect(proj)
    db.migrate(con)
    db.set_meta(con, "schema_version", 99)
    con.commit()
    con.close()

    # die() dùng sys.exit(chuỗi); chuỗi đó chỉ ra stderr khi lọt tới interpreter,
    # nên ở đây phải soi chính giá trị của SystemExit.
    with pytest.raises(SystemExit) as e:
        cli.cmd_status(argparse.Namespace(project=str(proj)))
    assert "99" in str(e.value)
    assert "cập nhật booktrans" in str(e.value)


def test_pdf_hong_cung_khong_de_lai_thu_muc_mo_coi(tmp_path):
    """Lá chắn theo định dạng không đủ: PDF hợp lệ về magic bytes nhưng hỏng
    ruột vẫn lọt qua ensure_supported rồi mới chết ở pymupdf.open."""
    src = tmp_path / "hong.pdf"
    src.write_bytes(b"%PDF-1.6\r\n" + b"rac" * 2000)
    proj = tmp_path / "proj"

    with pytest.raises(SystemExit):
        cli.cmd_init(argparse.Namespace(
            source=str(src), dir=str(proj), chunk_chars=6000, force=True))

    assert not proj.exists(), f"để lại rác: {list(proj.iterdir()) if proj.exists() else ''}"


def test_project_da_co_san_thi_khong_bi_xoa_khi_init_hong(tmp_path):
    """Dọn dẹp chỉ được xoá thư mục do chính lần init này tạo ra."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "ghi-chu-cua-toi.txt").write_text("dung xoa", encoding="utf-8")

    src = tmp_path / "hong.pdf"
    src.write_bytes(b"%PDF-1.6\r\n" + b"rac" * 2000)

    with pytest.raises(SystemExit):
        cli.cmd_init(argparse.Namespace(
            source=str(src), dir=str(proj), chunk_chars=6000, force=True))

    assert (proj / "ghi-chu-cua-toi.txt").exists(), "đã xoá thứ không phải của mình"


def _pdf_that(path):
    """PDF tối thiểu nhưng đọc được."""
    import sys
    sys.path.insert(0, "tests")
    from helpers import build_pdf, trang_mot_doan
    return build_pdf(path, [trang_mot_doan(120, 4)])


def test_force_khong_duoc_pha_project_cu_khi_file_moi_hong(tmp_path):
    """init --force xoá project.db và đè source TRƯỚC khi biết file mới có đọc
    được không. Bản dịch đã trả tiền và cả file sách gốc đều mất trắng.
    """
    proj = tmp_path / "proj"
    _pdf_that(tmp_path / "tot.pdf")
    cli.cmd_init(argparse.Namespace(source=str(tmp_path / "tot.pdf"),
                                    dir=str(proj), chunk_chars=6000, force=True))
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html='[VI] da dich va da tra tien'")
    con.commit()
    con.close()
    kich_thuoc_cu = (proj / "source.pdf").stat().st_size

    hong = tmp_path / "hong.pdf"
    hong.write_bytes(b"%PDF-1.6\r\n" + b"rac" * 2000)
    with pytest.raises(SystemExit):
        cli.cmd_init(argparse.Namespace(source=str(hong), dir=str(proj),
                                        chunk_chars=6000, force=True))

    assert (proj / "project.db").exists(), "đã xoá bản dịch trước khi kiểm file mới"
    con = db.connect(proj)
    n = con.execute("SELECT COUNT(*) FROM blocks WHERE dst_html IS NOT NULL").fetchone()[0]
    assert n > 0, "bản dịch đã mất"
    assert (proj / "source.pdf").stat().st_size == kich_thuoc_cu, "đã đè mất sách gốc"


def test_init_lai_tren_chinh_source_cua_project_van_chay(tmp_path):
    """Dựng lại bảng block sau khi sửa code là việc hợp lệ, và người dùng sẽ
    trỏ thẳng vào proj/source.pdf. Trước đây copy2 lên chính nó ném
    SameFileError và lọt ra thành traceback, sau khi đã xoá project.db."""
    proj = tmp_path / "proj"
    _pdf_that(tmp_path / "tot.pdf")
    cli.cmd_init(argparse.Namespace(source=str(tmp_path / "tot.pdf"),
                                    dir=str(proj), chunk_chars=6000, force=True))

    cli.cmd_init(argparse.Namespace(source=str(proj / "source.pdf"),
                                    dir=str(proj), chunk_chars=6000, force=True))
    con = db.connect(proj)
    assert con.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] > 0


def test_loi_la_khi_doc_van_thanh_thong_bao_khong_phai_traceback(tmp_path, monkeypatch):
    """ingest.load có thể ném thứ không phải UnsupportedSource — MuPDF hỏng ở
    trang 500 chẳng hạn. Chỉ bắt UnsupportedSource là để lọt traceback."""
    import ingest
    _pdf_that(tmp_path / "tot.pdf")

    def no_tung(_):
        raise RuntimeError("MuPDF ngã ở giữa chừng")
    monkeypatch.setattr(ingest, "load", no_tung)

    proj = tmp_path / "proj"
    with pytest.raises(SystemExit) as e:
        cli.cmd_init(argparse.Namespace(source=str(tmp_path / "tot.pdf"),
                                        dir=str(proj), chunk_chars=6000, force=True))
    assert "MuPDF" in str(e.value)
    assert not proj.exists(), "để lại thư mục mồ côi"


def test_translate_phan_biet_khoang_nguoc_voi_khoang_ngoai_sach(
        source_epub, tmp_path, capsys, monkeypatch):
    """Một câu duy nhất cho ba tình huống khác nhau đánh lừa người dùng.

    Gõ nhầm `--pages 20-10` mà chỉ nghe "không có chunk nào cần dịch" thì họ
    tưởng 10 trang ấy đã xong. `export` đã báo riêng hai lỗi này từ Phase 4;
    `translate` là chỗ duy nhất còn gộp.

    Cả ba đường đều phải đi tới trước khi dựng client: không có khoá API vẫn
    phải nghe được câu trả lời, vì không đường nào tốn một lượt gọi nào.
    """
    import argparse

    import cli

    for bien in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(bien, raising=False)
    proj = run_init(source_epub, tmp_path / "proj")

    def chay(pages):
        with pytest.raises(SystemExit) as e:
            cli.cmd_translate(argparse.Namespace(
                project=str(proj), provider="anthropic", model="m",
                limit=None, pages=pages))
        return str(e.value)

    assert "ngược" in chay("20-10")
    assert "ngoài sách" in chay("900-999")

    # Còn khoảng đã dịch xong thì không phải lỗi: nói rồi về bình thường.
    con = db.connect(proj)
    con.execute("UPDATE chunks SET status='done'")
    con.commit()
    cli.cmd_translate(argparse.Namespace(
        project=str(proj), provider="anthropic", model="m",
        limit=None, pages="1-1"))
    assert "không có chunk nào" in capsys.readouterr().out.lower()
