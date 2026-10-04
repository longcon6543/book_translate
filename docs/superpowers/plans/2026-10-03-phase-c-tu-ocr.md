# Phase C — Tự OCR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `init` một PDF scan không có lớp chữ nào ra khối chữ dịch được, bằng RapidOCR cài qua pip.

**Architecture:** Module mới `ingest/ocr.py`: hàm thuần đổi kết quả RapidOCR thành `pdf_layout.Line`, hàm dựng engine (import lười), hàm OCR một trang. `ingest/pdf_text.load` tách thân xử lý trang thành `_xu_ly_trang` dùng chung; lượt 1 như cũ, chỉ khi lượt 1 không ra đoạn nào mà sách có trang scan thì chạy lượt 2 bằng dòng OCR.

**Tech Stack:** Python 3.12, PyMuPDF 1.28, rapidocr-onnxruntime 1.4.4 (kéo theo onnxruntime, numpy, OpenCV), pytest.

**Spec:** [docs/superpowers/specs/2026-10-03-tu-ocr-design.md](../specs/2026-10-03-tu-ocr-design.md)

## Global Constraints

- Chạy test: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q` — hiện 421 passed.
- Vân tay `tests/golden/` không được đổi.
- Luật tầng: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py render/dan_trang.py vung_hinh.py` phải rỗng. `ingest/ocr.py` được import pymupdf.
- Không test nào gọi mạng (mô hình RapidOCR nằm sẵn trong wheel, 15MB — chạy offline).
- Sách có lớp chữ và text-PDF: kết quả ingest giống hệt từng byte; không bao giờ dựng engine OCR.
- `DPI_OCR = 200`; `TI_LE_CO_CHU = 0.80`; bỏ dòng có cạnh trên nghiêng ≥ 10°.
- html của dòng OCR: `html.escape(text, quote=False)` — cùng quy ước `pdf_layout.merge_spans`.
- Tiến độ: in `OCR trang i/n` ra stderr mỗi 10 trang và trang cuối.
- Thiếu thư viện: `UnsupportedSource` có chuỗi `pip install -r requirements.txt`.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Không in nội dung sách vào log/ledger: chỉ số đếm.

## Review Focus

1. **Sách scan mà OCR không đọc ra chữ nào** (trang scan trắng, ảnh hỏng): `init` phải báo lỗi rõ, không vỡ, không tạo project rỗng. → test ở Task 3.
2. **Sách có lớp chữ nhưng vài trang scan không có chữ** (bìa harmonics): không được OCR trang nào — giữ bất biến. → test ở Task 3.
3. **Trang OCR có hình vẽ**: dò vùng hình (8B) vẫn chạy trên dòng OCR, rác trong hình bị bỏ, chú thích giữ. → test ở Task 3.
4. **Dòng OCR nghiêng / ngược** (trang xoay 90° hay nhãn chéo trong hình): bị bỏ như E1, không trộn vào mạch văn. → test ở Task 1.
5. **Trang có `page.rotation` khác 0**: pixmap theo hướng hiển thị; khung `page.rect` cũng theo hướng hiển thị — tỉ lệ `page.rect.width / pix.width` đúng. Không có test (harmonics không có trang xoay); reviewer kiểm bằng đọc code.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `ingest/ocr.py` (mới) | `dong_tu_ket_qua` (thuần), `tao_engine` (import lười), `doc_trang_ocr` |
| `ingest/pdf_text.py` | Tách `_xu_ly_trang`; lượt OCR; thông báo mới; tiến độ |
| `requirements.txt` | `rapidocr-onnxruntime>=1.4` |
| `tests/test_ocr.py` (mới) | test `ingest/ocr.py` |
| `tests/test_pdf_ingest.py` | test lượt OCR trong `load` |

---

### Task 1: `ingest/ocr.py` và cài RapidOCR

**Files:**
- Create: `ingest/ocr.py`
- Create: `tests/test_ocr.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `pdf_layout.Line`, `ingest.UnsupportedSource`.
- Produces:
  - `ocr.DPI_OCR = 200`, `ocr.TI_LE_CO_CHU = 0.80`, `ocr.GOC_NGHIENG_TOI_DA = 10.0`
  - `ocr.dong_tu_ket_qua(ket_qua: list | None, page_no: int, ti_le: float) -> list[Line]` — `ket_qua` là list `[4 góc [[x,y]...], chữ, điểm]` theo pixel; `ti_le` = point/pixel
  - `ocr.tao_engine() -> engine` — gọi được `engine(ndarray) -> (ket_qua, thoi_gian)`
  - `ocr.doc_trang_ocr(page, page_no: int, engine) -> list[Line]`

- [ ] **Step 1: Cài RapidOCR vào `.venv`, thêm vào requirements**

```bash
.venv/bin/pip install -q "rapidocr-onnxruntime>=1.4"
.venv/bin/pip show rapidocr-onnxruntime | grep -E "^(Name|Version|License)"
```

Expected: `rapidocr-onnxruntime`, `Version: 1.4.x`, `License: Apache-2.0`.

Thêm dòng cuối `requirements.txt`:

```
rapidocr-onnxruntime>=1.4
```

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `421 passed` (cài thư viện không đổi hành vi).

- [ ] **Step 2: Viết test thất bại**

`tests/test_ocr.py`:

```python
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
        def __call__(self, anh):
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
```

- [ ] **Step 3: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_ocr.py -q`
Expected: ERROR — `ImportError: cannot import name 'ocr' from 'ingest'`.

- [ ] **Step 4: Viết `ingest/ocr.py`**

```python
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
            "cài thư viện OCR. Chạy: pip install -r requirements.txt"
        ) from e
    return RapidOCR()


def doc_trang_ocr(page, page_no: int, engine) -> list:
    """OCR một trang: chụp DPI_OCR RGB, đưa engine, đổi về Line theo point."""
    import numpy as np                    # đi kèm rapidocr-onnxruntime

    pix = page.get_pixmap(dpi=DPI_OCR, colorspace=pymupdf.csRGB, alpha=False)
    anh = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, 3)
    ket_qua, _ = engine(anh)
    return dong_tu_ket_qua(ket_qua, page_no, page.rect.width / pix.width)
```

- [ ] **Step 5: Chạy test, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_ocr.py -q`
Expected: 7 passed (test RapidOCR thật chạy, không skip — Step 1 đã cài).

Nếu `test_doc_trang_ocr_dua_anh_200_dpi_va_doi_ti_le` lệch kích thước ảnh 1 pixel do làm tròn của `get_pixmap`: in `pix.width, pix.height` thật, sửa KỲ VỌNG theo số thật và tỉ lệ `page.rect.width / pix.width`, ghi `Ruling:`.

- [ ] **Step 6: Cả bộ, luật tầng, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `428 passed`.

Run: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py render/dan_trang.py vung_hinh.py` — Expected: rỗng.

```bash
git add ingest/ocr.py tests/test_ocr.py requirements.txt
git commit -m "feat: ingest/ocr — đổi kết quả RapidOCR thành dòng chữ, engine nạp lười

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Tách `_xu_ly_trang` khỏi `load` (không đổi hành vi)

**Files:**
- Modify: `ingest/pdf_text.py` (`load`)

**Interfaces:**
- Consumes: không có.
- Produces: `pdf_text._xu_ly_trang(page, pno: int, lines: list, la_scan: bool, hinh: dict) -> list[Para]` — trả đoạn của một trang; ghi vùng hình vào `hinh[str(pno)]` khi có. Trang mà lọc rác xong không còn dòng nào trả `[]`.

- [ ] **Step 1: Ghi lại tiền đề**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `428 passed`. Đây là refactor thuần: không có test mới; lưới an toàn là toàn bộ test ingest hiện có cộng nghiệm thu so từng byte ở Task 4.

- [ ] **Step 2: Tách hàm**

Trong `ingest/pdf_text.py`, thêm trước `def load`:

```python
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
```

và thay toàn bộ thân vòng `for pno in range(doc.page_count):` trong `load` (từ `# Đọc dict MỘT lần` tới hết nhánh `else: paras.extend(pdf_layout.group_paragraphs(lines))`) bằng:

```python
            # Đọc dict MỘT lần: vừa lấy dòng chữ, vừa lấy khung ảnh để nhận
            # trang scan (tăng tốc init, xem _la_trang_scan).
            khoi = doc[pno].get_text("dict")["blocks"]
            lines = _doc_trang(doc[pno], pno, khoi)
            if not lines:
                continue                          # trang trắng hoặc toàn ảnh
            la_scan = _la_trang_scan(doc[pno], khoi)
            paras.extend(_xu_ly_trang(doc[pno], pno, lines, la_scan, hinh))
```

- [ ] **Step 3: Chạy cả bộ, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `428 passed` — y như Step 1.

```bash
git add ingest/pdf_text.py
git commit -m "refactor: tách _xu_ly_trang khỏi load để lượt OCR dùng chung

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Lượt OCR trong `load`

**Files:**
- Modify: `ingest/pdf_text.py` (`load`, import `sys`, import `ocr`)
- Test: `tests/test_pdf_ingest.py`

**Interfaces:**
- Consumes: `ocr.tao_engine()`, `ocr.doc_trang_ocr(page, page_no, engine)`, `ocr.DPI_OCR` (Task 1); `_xu_ly_trang` (Task 2).
- Produces: `load` OCR các trang scan khi lượt 1 không ra đoạn nào; `pdf_text.BUOC_TIEN_DO_OCR = 10`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_pdf_ingest.py`:

```python
# ---- Phase C: tự OCR

from ingest import ocr as ocr_mod

PX = 200 / 72          # point -> pixel ở DPI_OCR


def _kq_pt(x0, y0, x1, y1, chu):
    """Kết quả RapidOCR giả, toạ độ cho bằng point rồi đổi ra pixel 200 dpi."""
    return [[[x0 * PX, y0 * PX], [x1 * PX, y0 * PX], [x1 * PX, y1 * PX],
             [x0 * PX, y1 * PX]], chu, 0.95]


class EngineGia:
    def __init__(self, ket_qua):
        self.ket_qua, self.so_lan = ket_qua, 0

    def __call__(self, anh):
        self.so_lan += 1
        return self.ket_qua, 0.0


def _pdf_chi_co_anh(tmp_path, ten="scan_khong_chu.pdf", so_trang=2):
    doc = pymupdf.open()
    for _ in range(so_trang):
        doc.new_page(width=522, height=666)
    for i in range(so_trang):
        _anh(doc, doc[i], 0, 0, 522, 666)
    p = tmp_path / ten
    doc.save(str(p)); doc.close()
    return p


def test_sach_scan_khong_lop_chu_duoc_ocr(tmp_path, monkeypatch):
    dong = [_kq_pt(67, 120 + 12 * i, 400, 130 + 12 * i,
                   f"fake ocr line {i} of the same paragraph here")
            for i in range(4)]
    e = EngineGia(dong)
    monkeypatch.setattr(ocr_mod, "tao_engine", lambda: e)
    kq = ingest.load(_pdf_chi_co_anh(tmp_path))
    chu = " ".join(b.src_html for b in kq.blocks)
    assert "fake ocr line 0" in chu and "fake ocr line 3" in chu
    assert e.so_lan == 2, "mỗi trang scan OCR đúng một lần"


def test_sach_co_lop_chu_khong_bao_gio_dung_ocr(tmp_path, monkeypatch):
    """Review Focus 2: harmonics có lớp chữ nhưng bìa không có chữ — không
    được OCR trang nào, bất biến từng byte."""
    def cam():
        raise AssertionError("không được dựng engine OCR")
    monkeypatch.setattr(ocr_mod, "tao_engine", cam)
    doc = pymupdf.open()
    for _ in range(2):
        doc.new_page(width=522, height=666)
    _anh(doc, doc[0], 0, 0, 522, 666)                 # bìa: ảnh, không chữ
    _anh(doc, doc[1], 0, 0, 522, 666)
    for i in range(3):
        doc[1].insert_text((67, 120 + 12 * i), f"real text layer {i} here",
                           fontsize=10)
    p = tmp_path / "co_chu.pdf"
    doc.save(str(p)); doc.close()
    assert "real text layer" in " ".join(b.src_html for b in ingest.load(p).blocks)


def test_ocr_khong_doc_ra_chu_nao_thi_bao_ro(tmp_path, monkeypatch):
    """Review Focus 1."""
    monkeypatch.setattr(ocr_mod, "tao_engine", lambda: EngineGia([]))
    with pytest.raises(ingest.UnsupportedSource, match="OCR"):
        ingest.load(_pdf_chi_co_anh(tmp_path))


def test_trang_ocr_van_do_vung_hinh(tmp_path, monkeypatch):
    """Review Focus 3: dòng OCR đi đúng luồng trang scan của 8B."""
    nhap = pymupdf.open()
    p = nhap.new_page(width=350, height=548)
    p.draw_circle((175, 250), 70, color=(0, 0, 0), width=1.5)
    pix = p.get_pixmap(dpi=72)
    doc = pymupdf.open()
    trang = doc.new_page(width=350, height=548)
    trang.insert_image(trang.rect, pixmap=pix)
    f = tmp_path / "hinh_khong_chu.pdf"
    doc.save(str(f)); doc.close(); nhap.close()
    dong = ([_kq_pt(30, 80 + 12 * i, 330, 90 + 12 * i,
                    f"prose line {i} above the figure keeps going on")
             for i in range(4)]
            + [_kq_pt(150, 240, 190, 250, "K Ores"),
               _kq_pt(30, 332, 330, 342, "Figure 1.1 A circle chart used for testing.")])
    monkeypatch.setattr(ocr_mod, "tao_engine", lambda: EngineGia(dong))
    kq = ingest.load(f)
    chu = " ".join(b.src_html for b in kq.blocks)
    assert "K Ores" not in chu
    assert "Figure 1.1" in chu and "prose line 3" in chu
    assert kq.meta["vung_hinh"]["0"]


def test_ocr_in_tien_do(tmp_path, monkeypatch, capsys):
    dong = [_kq_pt(67, 120, 400, 130, "fake ocr line of text here ok")]
    monkeypatch.setattr(ocr_mod, "tao_engine", lambda: EngineGia(dong))
    ingest.load(_pdf_chi_co_anh(tmp_path, so_trang=3))
    assert "OCR trang 3/3" in capsys.readouterr().err
```

Sửa test cũ `test_pdf_khong_co_lop_chu_bao_ro`: thay

```python
    # Phase 7 làm sạch lớp OCR có sẵn chứ không chạy OCR — thông báo không
    # được hứa một phase đã xong mà không làm việc đó.
    with pytest.raises(ingest.UnsupportedSource, match="chưa tự chạy OCR"):
        ingest.load(p)
```

bằng

```python
    # Trang trắng: không lớp chữ, không ảnh scan để OCR (Phase C). Thông báo
    # không được hứa OCR khi không có gì để OCR.
    with pytest.raises(ingest.UnsupportedSource, match="không có trang ảnh"):
        ingest.load(p)
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_ingest.py -q -k "ocr or lop_chu or vung_hinh or tien_do"`
Expected: FAIL — các test OCR báo `UnsupportedSource` "chưa tự chạy OCR"; `test_pdf_khong_co_lop_chu_bao_ro` FAIL vì thông báo cũ; `test_sach_co_lop_chu_khong_bao_gio_dung_ocr` PASS (tiền đề bất biến).

- [ ] **Step 3: Viết lượt OCR**

Trong `ingest/pdf_text.py`: thêm `import sys` vào nhóm import chuẩn, `from ingest import ocr` sau `from ingest import Ingested, UnsupportedSource`, và hằng sau `DPI_DO_HINH`:

```python
# Phase C: OCR ~3 s/trang — in tiến độ để init không im lặng hàng chục phút.
BUOC_TIEN_DO_OCR = 10
```

Trong `load`, thay vòng lặp và khối `if not paras:` hiện có:

```python
        paras = []
        hinh = {}
        for pno in range(doc.page_count):
            # Đọc dict MỘT lần: vừa lấy dòng chữ, vừa lấy khung ảnh để nhận
            # trang scan (tăng tốc init, xem _la_trang_scan).
            khoi = doc[pno].get_text("dict")["blocks"]
            lines = _doc_trang(doc[pno], pno, khoi)
            if not lines:
                continue                          # trang trắng hoặc toàn ảnh
            la_scan = _la_trang_scan(doc[pno], khoi)
            paras.extend(_xu_ly_trang(doc[pno], pno, lines, la_scan, hinh))

        if not paras:
            raise UnsupportedSource(
                f"{path.name} không có lớp chữ nào trích được — nhiều khả năng "
                f"là sách scan chưa có lớp chữ OCR, mà tool chưa tự chạy OCR."
            )
```

bằng:

```python
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
```

Ghi chú: `_la_trang_scan` nay chạy cả trên trang không có dòng chữ (để biết trang scan nào cần OCR). Chi phí ~0 (đọc từ `khoi` đã có); kết quả đoạn không đổi.

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_ingest.py tests/test_ocr.py -q`
Expected: tất cả PASS.

- [ ] **Step 5: Cả bộ, luật tầng, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `433 passed`; vân tay golden xanh.

Run: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py render/dan_trang.py vung_hinh.py` — Expected: rỗng.

```bash
git add ingest/pdf_text.py tests/test_pdf_ingest.py
git commit -m "feat: init tự OCR sách scan chưa có lớp chữ

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Nghiệm thu

**Files:**
- Create (scratchpad, KHÔNG commit): `<scratchpad>/dung_anh_1_40.py`, `<scratchpad>/nghiem_thu_c.py`
- Không sửa code sản phẩm. Kết quả ghi ledger.

**Interfaces:**
- Consumes: mọi thứ ở Task 1–3.
- Produces: số đo bảng spec mục 8.

- [ ] **Step 1: Dựng bản harmonics trang 1–40 chỉ còn ảnh**

`<scratchpad>/dung_anh_1_40.py` (chạy từ gốc repo):

```python
"""Trang 1-40 harmonics, mỗi trang chỉ còn ảnh scan gốc (bỏ lớp chữ OCR)."""
import sys
import pymupdf
S = sys.argv[1]
src = pymupdf.open("projects/harmonics-8b/source.pdf")
out = pymupdf.open()
for pno in range(40):
    p = src[pno]
    moi = out.new_page(width=p.rect.width, height=p.rect.height)
    for x in p.get_images(full=True):
        for r in p.get_image_rects(x[0]):
            moi.insert_image(r, stream=src.extract_image(x[0])["image"])
out.save(f"{S}/harmonics-anh-1-40.pdf", garbage=4, deflate=True)
kt = sum(len(out[i].get_text().strip()) for i in range(out.page_count))
print("trang", out.page_count, "| ký tự lớp chữ còn lại:", kt, "(phải = 0)")
```

Run: `.venv/bin/python -W ignore::DeprecationWarning <scratchpad>/dung_anh_1_40.py <scratchpad>`
Expected: `trang 40 | ký tự lớp chữ còn lại: 0 (phải = 0)`.

- [ ] **Step 2: Init bản chỉ ảnh, đo thời gian**

```bash
rm -rf <scratchpad>/h-ocr
/usr/bin/time -p .venv/bin/python -W ignore::DeprecationWarning cli.py init <scratchpad>/harmonics-anh-1-40.pdf --dir <scratchpad>/h-ocr --chunk-chars 6000
```

Expected: các dòng `OCR trang 10/40` … `OCR trang 40/40` trên stderr, `Xong: N đoạn, …`; `real` ≤ 40 × 4 = 160 s cộng thời gian init thường (ghi số thật).

- [ ] **Step 3: So với harmonics-8b**

`<scratchpad>/nghiem_thu_c.py` (chạy từ gốc repo, tham số scratchpad):

```python
"""Nghiệm thu Phase C. Chỉ in số đếm."""
import collections, html, json, re, sqlite3, sys
S = sys.argv[1]
goc = sqlite3.connect("projects/harmonics-8b/project.db")
ocr = sqlite3.connect(f"{S}/h-ocr/project.db")


def txt(h):
    return html.unescape(re.sub(r"<[^>]+>", " ", h or ""))


def tu(c, trang):
    s = " ".join(txt(h) for (h,) in c.execute(
        "SELECT src_html FROM blocks WHERE page_no=?", (trang - 1,)))
    return collections.Counter(w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 1)


for t in (13, 20, 25, 35):
    a, b = tu(goc, t), tu(ocr, t)
    n = sum(a.values())
    print(f"trang {t}: từ 8B {n}, khớp {sum((a & b).values()) / n:.1%} (ngưỡng >= 95%)")
ky = lambda c, w: c.execute(f"SELECT COALESCE(SUM(LENGTH(src_html)),0) FROM blocks WHERE {w}").fetchone()[0]
a, b = ky(goc, "page_no < 40"), ky(ocr, "1=1")
print(f"ký tự trang 1-40: 8B {a}, OCR {b}, lệch {(b - a) / a:+.1%} (ngưỡng ±10%)")
h1 = {int(k) for k in json.loads((goc.execute("SELECT value FROM meta WHERE key='vung_hinh'").fetchone() or ['{}'])[0]) if int(k) < 40}
h2 = {int(k) for k in json.loads((ocr.execute("SELECT value FROM meta WHERE key='vung_hinh'").fetchone() or ['{}'])[0])}
print("trang có vùng hình: 8B", sorted(p + 1 for p in h1), "| OCR", sorted(p + 1 for p in h2),
      "| khác nhau", len(h1 ^ h2), "(ngưỡng <= 2)")
```

Run: `.venv/bin/python -W ignore::DeprecationWarning <scratchpad>/nghiem_thu_c.py <scratchpad>`
Expected: 4 trang thân bài khớp ≥ 95%; ký tự lệch trong ±10%; vùng hình khác nhau ≤ 2 trang.

Ghi chú về "khớp": so với 8B, mà 8B là lớp OCR gốc cộng các sửa của 8B — cận dưới của chất lượng thật. Trang dưới ngưỡng: xem ảnh trang đó (nửa gốc) trước khi kết luận lỗi ở OCR hay ở lớp gốc; ghi `Ruling:`.

- [ ] **Step 4: Bất biến harmonics và astrology**

```bash
rm -rf <scratchpad>/h-bb <scratchpad>/a-bb
.venv/bin/python -W ignore::DeprecationWarning cli.py init projects/harmonics-8b/source.pdf --dir <scratchpad>/h-bb --chunk-chars 6000
.venv/bin/python -W ignore::DeprecationWarning cli.py init projects/astrology/source.pdf --dir <scratchpad>/a-bb --chunk-chars 6000
```

So bằng cùng đoạn so sánh đã dùng khi tăng tốc init: cột `page_no,pos,tag,kind,src_html,bbox,line_bboxes,layout,cont_group,chunk_id` của mọi khối, và khoá meta `vung_hinh`, giữa `<scratchpad>/h-bb` với `projects/harmonics-8b`, `<scratchpad>/a-bb` với `projects/astrology`.

Expected: `giống hệt: True` và `vung_hinh giống: True` cho cả hai. Không dòng `OCR trang` nào được in khi init hai sách này.

- [ ] **Step 5: Cả bộ lần cuối, ghi ledger**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `433 passed`.

Ghi vào ledger một dòng `Task 4: nghiệm thu —` với: thời gian init 40 trang, s/trang, 4 tỉ lệ khớp, lệch ký tự, tập vùng hình, kết quả bất biến. Task này không có commit code.
