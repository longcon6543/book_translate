"""Tầng ghi ra: chọn adapter theo định dạng, và từ chối định dạng chưa làm."""
import pytest

import db
import render
from helpers import fingerprint, run_init, seed_translations


def test_ten_file_mac_dinh():
    assert render.default_output_name("epub", False) == "output.vi.epub"
    assert render.default_output_name("epub", True) == "output.bilingual.epub"


def test_dinh_dang_chua_ho_tro_bao_loi_ro():
    """PDF đã được hỗ trợ từ Phase 4, nên nay thử một định dạng thật sự chưa có."""
    with pytest.raises(render.UnsupportedTarget, match="mobi"):
        render.write("mobi", None, None, None)


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
