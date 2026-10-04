"""Chọn font đủ dấu tiếng Việt. Hỏng ở đây thì cả cuốn sách thành ô vuông."""
import pymupdf
import pytest

import pdf_font


def test_ky_tu_thu_gom_nhung_chu_font_latin_hay_thieu():
    for c in "ặữổỹằẵợựỡẫ":
        assert c in pdf_font.KY_TU_THU


def test_font_dung_san_cua_pymupdf_bi_phat_hien_la_thieu(tmp_path):
    """helv/tiro/cour thiếu 17/25 ký tự — tuyệt đối không được lọt qua."""
    duong = tmp_path / "helv.ttf"
    duong.write_bytes(pymupdf.Font("helv").buffer)
    thieu = pdf_font.thieu_glyph(duong)
    assert len(thieu) >= 10, f"phải phát hiện thiếu, nhưng chỉ thấy {thieu}"


def test_font_du_dau_thi_khong_bao_thieu():
    bo = pdf_font.chon_bo_font()
    assert pdf_font.thieu_glyph(bo.thuong) == []


def test_font_khong_ton_tai_bao_loi_ro(tmp_path):
    with pytest.raises(pdf_font.ThieuFont, match="không thấy"):
        pdf_font.chon_bo_font([(str(tmp_path / "khong-co.ttf"),) * 3])


def test_font_thieu_dau_bi_tu_choi_va_neu_ten_ky_tu(tmp_path):
    duong = tmp_path / "helv.ttf"
    duong.write_bytes(pymupdf.Font("helv").buffer)
    with pytest.raises(pdf_font.ThieuFont) as e:
        pdf_font.chon_bo_font([(str(duong),) * 3])
    assert "ặ" in str(e.value), "thông báo phải nêu ký tự thiếu để người dùng hiểu"


def test_chon_bo_font_tra_ve_du_ba_mat_chu():
    bo = pdf_font.chon_bo_font()
    assert bo.thuong and bo.dam and bo.nghieng
    assert bo.ten


def test_css_phai_khai_co_chu():
    """Bẫy đã dính khi dò: mặc định của insert_htmlbox là 12pt, sách là 10pt.
    Không khai cỡ chữ là mọi phép đo tràn khung phồng lên 20%."""
    css = pdf_font.dung_css(10.0)
    assert "font-size:10.00px" in css.replace(" ", "")


def test_css_dang_ky_du_ba_mat_chu():
    css = pdf_font.dung_css(10.0)
    assert css.count("@font-face") == 3
    assert "font-weight:bold" in css.replace(" ", "")
    assert "font-style:italic" in css.replace(" ", "")


def test_css_nhan_gian_dong():
    assert "line-height:0.95" in pdf_font.dung_css(10.0, 0.95).replace(" ", "")


def test_archive_nap_duoc_va_dat_chu_co_dau_khong_thanh_o_vuong():
    bo = pdf_font.chon_bo_font()
    kho = pdf_font.dung_archive(bo)
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=120)
    page.insert_htmlbox(pymupdf.Rect(10, 10, 290, 110),
                        "Những chữ khó: ặ ữ ổ ỹ ằ ẵ ợ ự",
                        css=pdf_font.dung_css(10.0), archive=kho)
    ra = page.get_text()
    for c in "ặữổỹằẵợự":
        assert c in ra, f"ký tự {c} không đặt được lên trang"
    doc.close()


# ---- sửa sau review toàn nhánh ----

def test_bien_moi_truong_la_quyet_dinh_khong_phai_goi_y(tmp_path, monkeypatch):
    """BOOKTRANS_FONT trỏ vào font thiếu dấu mà vẫn lặng lẽ lùi về font hệ
    thống thì README nói dối: nó hứa từ chối ngay đầu lệnh export."""
    duong = tmp_path / "helv.ttf"
    duong.write_bytes(pymupdf.Font("helv").buffer)
    monkeypatch.setenv(pdf_font.BIEN_MOI_TRUONG, str(duong))
    with pytest.raises(pdf_font.ThieuFont, match="thiếu"):
        pdf_font.chon_bo_font()


def test_bien_moi_truong_tro_vao_file_khong_co_thi_bao_ngay(tmp_path, monkeypatch):
    monkeypatch.setenv(pdf_font.BIEN_MOI_TRUONG, str(tmp_path / "khong-co.ttf"))
    with pytest.raises(pdf_font.ThieuFont, match="không thấy"):
        pdf_font.chon_bo_font()


def test_mat_dam_thieu_dau_cung_bi_bat(tmp_path, monkeypatch):
    """Chỉ kiểm mặt thường là để lọt cả cuốn in đậm bằng ô vuông."""
    du = pdf_font.UU_TIEN_MAC_DINH[0][0]
    thieu = tmp_path / "helv.ttf"
    thieu.write_bytes(pymupdf.Font("helv").buffer)
    monkeypatch.setenv(pdf_font.BIEN_MOI_TRUONG, f"{du}:{thieu}:{du}")
    with pytest.raises(pdf_font.ThieuFont, match="thiếu"):
        pdf_font.chon_bo_font()


def test_file_khong_phai_font_thanh_thong_bao_khong_phai_traceback(tmp_path, monkeypatch):
    rac = tmp_path / "rac.ttf"
    rac.write_bytes(b"day khong phai font" * 50)
    monkeypatch.setenv(pdf_font.BIEN_MOI_TRUONG, str(rac))
    with pytest.raises(pdf_font.ThieuFont):
        pdf_font.chon_bo_font()


# ---- đóng gói: Windows/Linux

def test_font_windows_tach_bang_dau_cham_phay():
    """Tách bằng ':' thì 'C:\\...' bị cắt ngay sau ổ đĩa — người dùng Windows
    không cách nào đặt được font. Dấu tách phải theo os.pathsep."""
    gia_tri = r"C:\F\r.ttf;C:\F\b.ttf;C:\F\i.ttf"
    assert pdf_font._tu_moi_truong(gia_tri, ";") == \
        [(r"C:\F\r.ttf", r"C:\F\b.ttf", r"C:\F\i.ttf")]
    assert pdf_font._tu_moi_truong(r"C:\F\r.ttf", ";") == [(r"C:\F\r.ttf",) * 3]


def test_font_posix_van_tach_bang_hai_cham():
    assert pdf_font._tu_moi_truong("/a/r.ttf:/a/b.ttf:/a/i.ttf", ":") == \
        [("/a/r.ttf", "/a/b.ttf", "/a/i.ttf")]


def test_font_mac_dinh_co_windows_va_linux():
    """Người dùng Windows/Linux xuất PDF được mà không phải cấu hình. macOS
    đứng đầu danh sách nên máy Mac không đổi gì."""
    tat_ca = " ".join(p for bo in pdf_font.UU_TIEN_MAC_DINH for p in bo)
    assert pdf_font.UU_TIEN_MAC_DINH[0][0].startswith("/System/Library/Fonts")
    assert "times.ttf" in tat_ca.lower() and "timesbd.ttf" in tat_ca.lower()
    assert "DejaVuSerif.ttf" in tat_ca
