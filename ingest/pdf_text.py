"""Adapter PDF có sẵn lớp chữ.

Chỗ duy nhất trong Phase 3 đụng tới PyMuPDF. Mọi phép dựng lại đoạn văn nằm ở
pdf_layout.py dưới dạng hàm thuần.
"""
import json
import math
import sys
from pathlib import Path

import pymupdf

import pdf_layout
import vung_hinh
from blocks import Block
from ingest import Ingested, UnsupportedSource, ocr

# Chữ xoay: bbox không phản ánh thứ tự đọc, trộn vào là vỡ mạch văn. Nhưng
# trang scan hơi nghiêng thì OCR ghi dòng lệch vài phần độ: đo thật trên sách
# scan 462 dòng lệch < 10° (16.969 ký tự; một trang mất trắng), còn ≥ 10° chỉ
# 1.164 ký tự — nhãn xoay trong hình. Người dùng chọn ngưỡng 10°.
GOC_NGHIENG_TOI_DA = 10.0


def _gan_ngang(huong) -> bool:
    dx, dy = huong
    return dx > 0 and abs(math.degrees(math.atan2(dy, dx))) < GOC_NGHIENG_TOI_DA

# Trang sách scan: một ảnh phủ ngần này diện tích trang. Đo thật: sách scan
# 482/484 trang, text-PDF 925 trang không có trang nào.
TI_LE_ANH_PHU_TRANG = 0.9


def _la_trang_scan(page, blocks=None) -> bool:
    """Trang có một ảnh phủ >= 90% diện tích trang.

    Trên trang như vậy chữ là lớp OCR đè lên ảnh chụp, và OCR hay cắt một hàng
    chữ làm nhiều mảnh — chỉ ở đó mới ghép mảnh cùng hàng. Text-PDF có chỗ
    cùng hàng là ô bảng và cột mục lục đúng bố cục, ghép vào là phá.

    `blocks` là get_text("dict")["blocks"] của trang nếu người gọi đã đọc:
    khối ảnh (type 1) mang sẵn khung ảnh trên trang. Hỏi lại bằng
    get_image_rects tốn ~61 s trên sách scan 484 trang; đo trên cả hai sách
    mẫu (484 + 925 trang), hai cách cho cùng quyết định ở từng trang.
    """
    dien_tich = page.rect.get_area()
    if blocks is None:
        khung = [r for x in page.get_images(full=True)
                 for r in page.get_image_rects(x[0])]
    else:
        khung = [b["bbox"] for b in blocks if b.get("type") == 1]
    for r in khung:
        # Khung ảnh theo toạ độ CHƯA xoay, page.rect theo hướng hiển thị: trang
        # /Rotate 90 (sách scan chụp ngang) mà không đổi thì chỉ phủ 67%.
        g = pymupdf.Rect(r) * page.rotation_matrix
        g.intersect(page.rect)
        if g.is_valid and not g.is_empty and \
                g.get_area() >= TI_LE_ANH_PHU_TRANG * dien_tich:
            return True
    return False


# E5: độ phân giải chụp trang để dò hình. Đo thật: 40 dpi làm nét mảnh nhoè
# thành xám và không bắt được hình nào; 72 dpi bắt 147/171 trang có chú thích.
DPI_DO_HINH = 72

# Phase C: OCR ~3 s/trang — in tiến độ để init không im lặng hàng chục phút.
BUOC_TIEN_DO_OCR = 10


def _vung_hinh_trang(page, lines) -> list:
    pix = page.get_pixmap(dpi=DPI_DO_HINH, colorspace=pymupdf.csGRAY,
                          alpha=False)
    tp = vung_hinh.thanh_phan(pix.samples, pix.width, pix.height,
                              page.rect.width / pix.width)
    return vung_hinh.tim_vung(tp, [(l.bbox, l.text) for l in lines],
                              page.rect.width, page.rect.height)


def _doc_trang(page, page_no: int, blocks=None) -> list:
    """Trả về list[pdf_layout.Line] của một trang, đã bỏ chữ xoay."""
    out = []
    if blocks is None:
        blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if b.get("type") != 0:                    # 1 = ảnh
            continue
        for l in b["lines"]:
            if not _gan_ngang(l.get("dir", (1.0, 0.0))):
                continue                          # chữ xoay: bỏ qua có kiểm soát
            html, text, size = pdf_layout.merge_spans(l["spans"])
            if not text.strip():
                continue
            out.append(pdf_layout.Line(page_no=page_no, bbox=tuple(l["bbox"]),
                                       html=html, text=text, size=size))
    return out


def _line_bboxes(p) -> str:
    return json.dumps([[round(v, 1) for v in l.bbox] for l in p.lines],
                      separators=(",", ":"))


def _xu_ly_trang(page, pno: int, lines: list, la_scan: bool, hinh: dict) -> list:
    """Đoạn văn của một trang từ các dòng của nó. Dùng chung cho dòng của lớp
    chữ có sẵn và dòng OCR (Phase C) — hai lượt không được lệch nhau.

    Ghi vùng hình của trang scan vào `hinh[str(pno)]`. Trả [] khi lọc rác
    trong hình xong không còn dòng nào.
    """
    if la_scan:
        # E5/E6: bỏ rác OCR của hình TRƯỚC dò cột và ghép mảnh — mảnh
        # rác quanh hình giả làm cột và dính vào dòng thật.
        vung = _vung_hinh_trang(page, lines)
        if vung:
            hinh[str(pno)] = [[round(v, 1) for v in k] for k in vung]
            giu = vung_hinh.loc_dong_trong_hinh(
                [(l.bbox, l.text) for l in lines], vung)
            lines = [l for l, g in zip(lines, giu) if g]
            if not lines:
                return []
    pdf_layout.detect_columns(lines, page.rect.width)
    if not la_scan:
        return pdf_layout.group_paragraphs(lines)
    cao_trang = page.rect.height
    if not any(l.col for l in lines):
        # E2: chỉ mục OCR có mảnh lấn khe — detect_columns bỏ cuộc.
        khe = pdf_layout.tim_khe_hai_cot(lines, page.rect.width, cao_trang)
        if khe is not None:
            for l in lines:
                l.col = 1 if l.bbox[0] >= khe else 0
    # Ghép SAU dò cột để "cùng cột" có nghĩa, TRƯỚC gom đoạn để mảnh đuôi
    # không bị coi là dòng thụt đầu đoạn mới.
    lines = pdf_layout.ghep_manh_cung_hang(lines, page_height=cao_trang)
    lines = pdf_layout.noi_so_trang(lines, page_height=cao_trang)
    # Gom đoạn riêng từng vùng: không để dòng thân bài lọt vào đoạn tiêu đề
    # chạy rồi bị mark_running loại theo.
    return pdf_layout.gom_doan_theo_vung(lines, page_height=cao_trang)


def load(path: Path) -> Ingested:
    path = Path(path)
    try:
        doc = pymupdf.open(str(path))
    except Exception as e:
        raise UnsupportedSource(f"không mở được {path.name}: {e}") from e

    try:
        if doc.needs_pass:
            raise UnsupportedSource(
                f"{path.name} có mật khẩu nên không đọc được nội dung."
            )

        paras = []
        hinh = {}
        trang_scan = []
        for pno in range(doc.page_count):
            # Đọc dict MỘT lần: vừa lấy dòng chữ, vừa lấy khung ảnh để nhận
            # trang scan (tăng tốc init, xem _la_trang_scan).
            khoi = doc[pno].get_text("dict")["blocks"]
            lines = _doc_trang(doc[pno], pno, khoi)
            la_scan = _la_trang_scan(doc[pno], khoi)
            if la_scan:
                trang_scan.append(pno)
            if not lines:
                continue                          # trang trắng hoặc toàn ảnh
            paras.extend(_xu_ly_trang(doc[pno], pno, lines, la_scan, hinh))

        if not paras and not trang_scan:
            raise UnsupportedSource(
                f"{path.name} không có lớp chữ nào trích được và không có trang "
                f"ảnh scan nào để OCR — có thể là PDF trắng."
            )
        if not paras:
            # Phase C: CẢ cuốn không có lớp chữ — tự OCR các trang scan. Sách
            # có lớp chữ không bao giờ tới đây (bất biến từng byte).
            engine = ocr.tao_engine()
            for i, pno in enumerate(trang_scan, 1):
                lines = ocr.doc_trang_ocr(doc[pno], pno, engine)
                if lines:
                    paras.extend(_xu_ly_trang(doc[pno], pno, lines, True, hinh))
                if i % BUOC_TIEN_DO_OCR == 0 or i == len(trang_scan):
                    print(f"OCR trang {i}/{len(trang_scan)}", file=sys.stderr,
                          flush=True)
            if not paras:
                raise UnsupportedSource(
                    f"{path.name} là sách scan chưa có lớp chữ, và OCR không đọc "
                    f"ra chữ nào trên {len(trang_scan)} trang scan."
                )

        pdf_layout.classify(paras)
        # Chiều cao trang đầu làm đại diện: sách in khổ đồng nhất.
        cao = doc[0].rect.height if doc.page_count else pdf_layout.CHIEU_CAO_MAU
        pdf_layout.mark_running(paras, doc.page_count, page_height=cao)
        pdf_layout.link_continuations(paras)
        so_trang = doc.page_count
    finally:
        doc.close()

    blocks = []
    theo_trang = {}
    for p in paras:
        if p.kind == "skip":
            continue
        pos = theo_trang.get(p.page_no, 0)
        theo_trang[p.page_no] = pos + 1
        blocks.append(Block(
            page_no=p.page_no,
            pos=pos,
            tag="h2" if p.kind == "heading" else "p",
            src_html=p.html,
            kind=p.kind,
            bbox=",".join(f"{v:.1f}" for v in p.bbox),
            line_bboxes=_line_bboxes(p),
            layout={"col": p.lines[0].col, "size": round(p.size, 1),
                    "so_trang": so_trang},
            cont_group=p.cont_group,
        ))
    meta = {"vung_hinh": hinh} if hinh else {}
    return Ingested(fmt="pdf", source_name=path.name, blocks=blocks, meta=meta)
