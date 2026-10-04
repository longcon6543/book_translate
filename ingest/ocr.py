"""Tự OCR trang sách scan chưa có lớp chữ (Phase C).

Chỉ dùng khi CẢ cuốn không có lớp chữ (xem pdf_text.load). RapidOCR cài qua
pip, mang sẵn mô hình trong wheel, chạy offline trên CPU. Đo trên sách scan
thật, so với lớp OCR có sẵn của sách: 200 dpi khớp 95,9% số từ (thân bài
98-100%), ~3 s/trang; 150 dpi chỉ 85,9%.

Spec: docs/superpowers/specs/2026-10-03-tu-ocr-design.md
"""
import html
import math

import pymupdf

import pdf_layout
from ingest import UnsupportedSource

DPI_OCR = 200
# RapidOCR chỉ trả khung dòng, không trả cỡ chữ. Đo trên 208 cặp dòng khớp với
# lớp OCR gốc: cỡ chữ ≈ 0,80 x chiều cao khung (p10 0,71, p90 0,93).
TI_LE_CO_CHU = 0.80
# Cùng ngưỡng với dòng lệch của lớp chữ có sẵn (pdf_text.GOC_NGHIENG_TOI_DA).
GOC_NGHIENG_TOI_DA = 10.0
# Khung cao hơn ngần này lần bề rộng (và có từ 3 ký tự) là chữ dọc. RapidOCR
# xếp 4 góc theo khung chứ không theo chiều chữ, nên cạnh trên của chữ dọc vẫn
# nằm ngang — luật góc không bắt được (review: nhãn dọc thành tiêu đề 108pt).
TI_LE_CHU_DOC = 1.5


def dong_tu_ket_qua(ket_qua, page_no: int, ti_le: float) -> list:
    """Đổi kết quả RapidOCR thành list Line. Hàm thuần.

    `ket_qua`: list [4 góc theo pixel (trái-trên, phải-trên, phải-dưới,
    trái-dưới), chữ, điểm] hoặc None. `ti_le`: số point trên một pixel.
    """
    out = []
    for goc4, chu, _diem in ket_qua or []:
        t = (chu or "").strip()
        if not t:
            continue
        (x0, y0), (x1, y1) = goc4[0], goc4[1]
        if abs(math.degrees(math.atan2(y1 - y0, x1 - x0))) >= GOC_NGHIENG_TOI_DA:
            continue                          # chữ chéo/xoay/ngược: bỏ như E1
        xs = [p[0] * ti_le for p in goc4]
        ys = [p[1] * ti_le for p in goc4]
        khung = (min(xs), min(ys), max(xs), max(ys))
        if len(t) >= 3 and \
                khung[3] - khung[1] > TI_LE_CHU_DOC * (khung[2] - khung[0]):
            continue                          # chữ dọc: bỏ như E1
        out.append(pdf_layout.Line(
            page_no=page_no, bbox=khung,
            html=html.escape(t, quote=False), text=t,
            size=TI_LE_CO_CHU * (khung[3] - khung[1])))
    return out


def tao_engine():
    """Dựng engine RapidOCR. Import lười: EPUB/text-PDF không phải nạp nó."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as e:
        raise UnsupportedSource(
            "Sách này là bản scan chưa có lớp chữ nên cần OCR, nhưng máy chưa "
            "cài thư viện OCR. Chạy: pip install -r requirements.txt "
            "(thư viện OCR rapidocr-onnxruntime chỉ chạy trên Python 3.12 trở "
            "xuống — Python mới hơn thì tạo môi trường Python 3.12)"
        ) from e
    return RapidOCR()


def doc_trang_ocr(page, page_no: int, engine) -> list:
    """OCR một trang: chụp DPI_OCR RGB, đưa engine, đổi về Line theo point."""
    import numpy as np                    # đi kèm rapidocr-onnxruntime

    pix = page.get_pixmap(dpi=DPI_OCR, colorspace=pymupdf.csRGB, alpha=False)
    anh = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, 3)
    # use_cls=False: bộ phân loại góc lật crop lộn ngược rồi đọc nó như chữ
    # thường, và đôi khi lật nhầm một dòng sạch thành rác (review Phase C).
    # Tắt nó thì chữ ngược/dọc ra điểm thấp và RapidOCR tự lọc.
    ket_qua, _ = engine(anh, use_cls=False)
    return dong_tu_ket_qua(ket_qua, page_no, page.rect.width / pix.width)
