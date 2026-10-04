"""Tự OCR (Phase C). Không gọi mạng — mô hình RapidOCR nằm sẵn trong wheel."""
import sys

import pymupdf
import pytest

from ingest import UnsupportedSource, ocr


def kq(x0, y0, x1, y1, chu, diem=0.9):
    """Một kết quả RapidOCR: 4 góc (trái-trên, phải-trên, phải-dưới, trái-dưới)."""
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], chu, diem]


def test_khung_doi_ve_point_va_co_chu_tu_chieu_cao():
    d = ocr.dong_tu_ket_qua([kq(100, 200, 300, 240, "Hello world")], 3, 0.36)
    assert len(d) == 1
    l = d[0]
    assert l.page_no == 3 and l.text == "Hello world"
    assert l.bbox == pytest.approx((36.0, 72.0, 108.0, 86.4))
    assert l.size == pytest.approx(0.80 * 14.4)


def test_chu_rong_bi_bo():
    assert ocr.dong_tu_ket_qua([kq(0, 0, 10, 10, "   ")], 0, 1.0) == []
    assert ocr.dong_tu_ket_qua(None, 0, 1.0) == []


def test_html_duoc_escape_nhu_merge_spans():
    d = ocr.dong_tu_ket_qua([kq(0, 0, 50, 10, "a < b & c")], 0, 1.0)
    assert d[0].html == "a &lt; b &amp; c" and d[0].text == "a < b & c"


def test_dong_nghieng_15_do_bi_bo_5_do_duoc_giu():
    """Review Focus 4: nhãn chéo trong hình, trang xoay — như luật E1."""
    nghieng15 = [[[0, 0], [100, 26.8], [100, 66.8], [0, 40]], "cheo", 0.9]
    nghieng5 = [[[0, 0], [100, 8.75], [100, 48.75], [0, 40]], "hoi lech", 0.9]
    nguoc = [[[100, 40], [0, 40], [0, 0], [100, 0]], "nguoc", 0.9]
    ra = [l.text for l in ocr.dong_tu_ket_qua([nghieng15, nghieng5, nguoc], 0, 1.0)]
    assert ra == ["hoi lech"]


def test_thieu_thu_vien_bao_lenh_cai(monkeypatch):
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)
    with pytest.raises(UnsupportedSource, match="pip install -r requirements.txt"):
        ocr.tao_engine()


def test_doc_trang_ocr_dua_anh_200_dpi_va_doi_ti_le():
    class EngineGia:
        def __call__(self, anh, **kw):
            self.co = anh.shape
            return [kq(200, 400, 1000, 460, "fake line")], 0.0

    doc = pymupdf.open()
    page = doc.new_page(width=360, height=540)
    e = EngineGia()
    d = ocr.doc_trang_ocr(page, 7, e)
    assert e.co == (1500, 1000, 3), "phải chụp 200 dpi RGB"
    assert d[0].page_no == 7
    assert d[0].bbox == pytest.approx((72.0, 144.0, 360.0, 165.6))


def test_rapidocr_that_doc_duoc_chu_in_ro():
    pytest.importorskip("rapidocr_onnxruntime")
    nhap = pymupdf.open()
    p = nhap.new_page(width=400, height=300)
    p.insert_text((40, 120), "THE QUICK BROWN FOX", fontsize=24)
    p.insert_text((40, 180), "JUMPS OVER THE LAZY DOG", fontsize=24)
    pix = p.get_pixmap(dpi=150)
    doc = pymupdf.open()
    trang = doc.new_page(width=400, height=300)
    trang.insert_image(trang.rect, pixmap=pix)
    chu = " ".join(l.text for l in ocr.doc_trang_ocr(doc[0], 0, ocr.tao_engine()))
    tu = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG".split()
    thay = sum(1 for w in tu if w in chu.upper())
    assert thay >= 0.9 * len(tu), f"chỉ đọc ra {thay}/{len(tu)} từ"


# ---- review toàn nhánh Phase C (Important)

def test_dong_doc_kieu_rapidocr_that_bi_bo():
    """RapidOCR luôn xếp 4 góc theo chiều kim đồng hồ từ góc trái-trên CỦA
    KHUNG, nên cạnh trên của chữ dọc vẫn nằm ngang (0°) — luật góc không bắt
    được. Đo thật: nhãn dọc thành khối 'heading' cỡ 108pt."""
    doc = kq(10, 10, 27, 146, "SIDEWAYS LABEL TEXT")       # cao 136 x rộng 17
    so_trang = kq(300, 500, 306, 510, "1")                 # số đứng một mình: giữ
    ra = [l.text for l in ocr.dong_tu_ket_qua([doc, so_trang], 0, 1.0)]
    assert ra == ["1"]


def test_engine_goi_khong_dung_bo_xoay_goc():
    """Bộ phân loại góc của RapidOCR lật crop lộn ngược rồi đọc nó như chữ
    thường (không bỏ được), và đôi khi lật nhầm một dòng sạch thành rác."""
    class EngineGia:
        def __call__(self, anh, **kw):
            self.kw = kw
            return [], 0.0

    d = pymupdf.open()
    d.new_page(width=100, height=100)
    e = EngineGia()
    ocr.doc_trang_ocr(d[0], 0, e)
    assert e.kw.get("use_cls") is False


def test_requirements_khong_lam_hong_cai_dat_tren_python_moi():
    """Review Phase C: rapidocr-onnxruntime 1.4.4 khai Requires-Python <3.13.
    Không có điều kiện thì `pip install -r requirements.txt` hỏng HẲN trên
    3.13+, kể cả người chỉ dịch EPUB/text-PDF."""
    from pathlib import Path
    dong = [l for l in Path("requirements.txt").read_text().splitlines()
            if l.startswith("rapidocr")]
    assert dong and 'python_version < "3.13"' in dong[0]


def test_thieu_thu_vien_noi_ro_phien_ban_python(monkeypatch):
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)
    with pytest.raises(UnsupportedSource, match="Python 3.12"):
        ocr.tao_engine()
