"""Phần dùng chung của hai chế độ xuất PDF khổ đôi. Không gọi mạng."""
from render import pdf_overlay, pdf_trang


def test_phan_dung_chung_nam_o_pdf_trang():
    for ten in ("dat_chu", "_khung_dung", "ghep_kho_doi", "_duong_nguon",
                "_chen_trang_bao_cao", "_don_cho_dai_ra", "write",
                "CO_SO_TRANG", "TI_LE_DON"):
        assert hasattr(pdf_trang, ten), ten


def test_overlay_dung_lai_chu_khong_chep_mot_ban_rieng():
    """Hai bản sao của dat_chu là hai chỗ phải sửa cùng lúc — rồi sẽ lệch nhau."""
    assert pdf_overlay.dat_chu is pdf_trang.dat_chu
    assert pdf_overlay.ghep_kho_doi is pdf_trang.ghep_kho_doi
    assert pdf_overlay._khung_dung is pdf_trang._khung_dung


def test_overlay_chi_con_viec_rieng_cua_no():
    assert hasattr(pdf_overlay, "xoa_chu")
    assert hasattr(pdf_overlay, "trang_dich")
    assert not hasattr(pdf_trang, "xoa_chu"), "reflow không có gì để xoá"


import pymupdf
import pytest

TRANG = pymupdf.Rect(0, 0, 334, 547)   # khổ trang harmonics, đo thật


def toa_do(k):
    return pytest.approx((k.x0, k.y0, k.x1, k.y1))


def test_khung_y_am_duoc_kep_vao_trang():
    """Đo thật: 53/4.120 khối của harmonics có góc trên-trái trên mép trang,
    ví dụ trang 2: 228.2,-3.0,347.5,51.5. _khung_dung loại thẳng chúng."""
    goc = pymupdf.Rect(228.2, -3.0, 347.5, 51.5)
    assert not pdf_trang._khung_dung(goc, TRANG), "tiền đề: khung này đang bị loại"
    k = pdf_trang.kep_khung(goc, TRANG)
    assert (k.x0, k.y0, k.x1, k.y1) == toa_do(pymupdf.Rect(228.2, 0, 334, 51.5))
    assert pdf_trang._khung_dung(k, TRANG), "kẹp xong phải qua được cửa kiểm"


def test_khung_da_nam_trong_trang_thi_giu_nguyen():
    goc = pymupdf.Rect(34.2, 47.8, 311.5, 93.5)
    k = pdf_trang.kep_khung(goc, TRANG)
    assert (k.x0, k.y0, k.x1, k.y1) == toa_do(goc)


def test_khung_lon_hon_ca_trang_thi_ve_dung_bang_trang():
    """Review Focus 5."""
    k = pdf_trang.kep_khung(pymupdf.Rect(-10, -10, 400, 600), TRANG)
    assert (k.x0, k.y0, k.x1, k.y1) == toa_do(TRANG)


def test_khung_nam_han_ngoai_trang_thi_khong_dung_duoc():
    """Review Focus 4: kẹp không được biến khung ngoài trang thành khung hợp lệ."""
    k = pdf_trang.kep_khung(pymupdf.Rect(400, 100, 500, 200), TRANG)
    assert not pdf_trang._khung_dung(k, TRANG)


def test_kep_khong_sua_khung_dau_vao():
    goc = pymupdf.Rect(228.2, -3.0, 347.5, 51.5)
    pdf_trang.kep_khung(goc, TRANG)
    assert goc.y0 == pytest.approx(-3.0)
