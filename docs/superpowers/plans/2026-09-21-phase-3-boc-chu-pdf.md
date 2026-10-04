# Phase 3 — Bóc chữ khỏi PDF text

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đọc một PDF có sẵn lớp chữ và dựng lại thành danh sách `Block` đúng thứ tự đọc, đúng đoạn văn, đúng phân loại — để phần lõi Phase 2 dịch được mà không cần biết nguồn là PDF.

**Architecture:** PDF không lưu đoạn văn, chỉ lưu mảnh chữ có toạ độ. Toàn bộ việc dựng lại là **hàm thuần trên cấu trúc dữ liệu**: mảnh → dòng → đoạn → phân loại. Phần đụng PyMuPDF mỏng và nằm ở một chỗ (`page_lines`), mọi thứ sau đó chỉ làm việc với `Line` và `Para` — chạy được trong mili giây, test không cần file PDF thật.

**Tech Stack:** Python 3.12.6, PyMuPDF 1.28.2 (wheel arm64 sẵn có), pytest 9.1.1.

**Spec:** `docs/superpowers/specs/2026-09-21-pdf-song-ngu-design.md` (mục 5)

## Global Constraints

- Bộ test EPUB hiện có phải **giữ nguyên xanh**, gồm hai vân tay trong `tests/golden/` — Phase 3 không được chạm đường EPUB.
- **Không test nào gọi mạng, và Phase 3 không tiêu một token API nào.** Toàn bộ nghiệm thu bằng mắt qua `inspect`.
- Dùng `import pymupdf`, **không dùng `import fitz`** — tên cũ đã bị SDK cảnh báo sẽ gỡ.
- Tên cột đã có sẵn từ Phase 2, không thêm cột mới: `page_no`, `bbox`, `line_bboxes`, `layout`, `kind`, `cont_group`.
- `kind` chỉ nhận đúng các giá trị trong spec mục 4: `text` / `heading` / `caption` / `table` / `formula` / `skip`.
- Lõi (`translator.py`, `cli.py`, `chunking.py`, `blocks.py`, `db.py`) không được nhắc tên nhà cung cấp nào — `tests/test_loi_doc_lap.py` canh việc này.
- Docstring và comment viết tiếng Việt, khớp code đang có.
- Mỗi task kết thúc bằng đúng một commit.

## Dữ liệu thật đã đo trên `ebook/astrology.pdf.pdf`

Mọi ngưỡng trong kế hoạch này đến từ số đo thật, không phải phỏng đoán:

| | |
|---|---|
| Khổ trang | 522 × 666 pt |
| Số trang | 925 (899 trang có chữ) |
| Mảnh mỗi dòng | 1,3 – 1,8 (chữ **không** bị băm vụn) |
| Cỡ chữ thân bài | 10,0 pt, font Goudy; có Goudy-Bold và Goudy-Italic |
| Cỡ chữ tiêu đề | ~13,6 pt |
| Cỡ chữ nhỏ | 8,2 – 9,0 pt |
| Header | y ≈ 28, dài 6–31 ký tự |
| Footer | y ≈ 627, hai dòng mỗi trang, dài 4–18 ký tự |
| Vùng thân bài | 40 < y < 615 |
| Số cột | 1 |
| Trang có ảnh | ~13% |
| Đoạn nối sang trang sau | 11/18 trang mẫu (~61%), trong đó 2 cắt ngang một từ bằng gạch nối |

### Ba điều dữ liệu thật đã bác bỏ

**1. Thứ tự block của PyMuPDF KHÔNG phải thứ tự đọc.** 18/18 trang mẫu có block không xếp theo chiều dọc tăng dần. Tin vào thứ tự thư viện trả về là đảo lộn nội dung cả cuốn sách. Mọi thứ phải được sắp xếp lại (Task 2).

**2. Spec mục 5 nói dò header/footer bằng "so trùng giữa các trang" — chưa đủ.** Các dòng thân bài ở y = 55, 571, 583, 595 cũng xuất hiện trên 15–18/18 trang mẫu, vì sách xếp chữ theo lưới đều. Chỉ so vị trí sẽ xoá nhầm văn bản thật. Phải so **nội dung chữ** lặp lại, cộng thêm điều kiện ngắn và nằm ở rìa trang (Task 6).

**3. Chữ không bị băm vụn như lo ngại.** 1,3–1,8 mảnh mỗi dòng, không phải mỗi ký tự một mảnh. Việc ghép mảnh nhẹ hơn dự kiến, nhưng vẫn phải giữ đậm/nghiêng.

## Review Focus

Năm trường hợp spec ngụ ý nhưng không task nào tự nhiên chạm tới. Mỗi dòng đã được gắn test vào task sở hữu đoạn code đó.

1. **PDF có trang trắng hoàn toàn hoặc trang chỉ có ảnh** — không được làm vỡ, không được sinh block rỗng. Sách nào cũng có trang trắng giữa các phần. → Task 8.
2. **PDF không có lớp chữ (sách scan)** — `init` phải nhận ra và nói rõ đây là việc của Phase 7, chứ không tạo project rỗng rồi để người dùng tưởng đã xong. → Task 8.
3. **Trang có chữ xoay** (tiêu đề dọc, bảng xoay ngang) — bbox không phản ánh thứ tự đọc; phải bỏ qua có kiểm soát thay vì trộn bừa vào mạch văn. → Task 8.
4. **Đoạn cuối sách** — `cont_group` không được trỏ sang trang không tồn tại. → Task 7.
5. **PDF mã hoá / có mật khẩu** — báo lỗi rõ ở `init`, không văng traceback của thư viện. → Task 8.

---

## File Structure

Tạo mới:

| File | Trách nhiệm |
|---|---|
| `ingest/pdf_text.py` | Adapter PDF: mở tài liệu, gọi các hàm thuần, trả `Ingested` |
| `pdf_layout.py` | **Hàm thuần**: mảnh→dòng→đoạn, cột, header/footer, phân loại, nối trang |
| `tests/test_pdf_layout.py` | Test cho toàn bộ hàm thuần, không cần file PDF |
| `tests/test_pdf_ingest.py` | Test adapter trên PDF dựng bằng PyMuPDF trong tmp_path |
| `tests/test_inspect.py` | Test lệnh `inspect` |

Sửa:

| File | Thay đổi |
|---|---|
| `ingest/__init__.py` | `SUPPORTED_FORMATS` thêm `"pdf"`; `load` định tuyến sang `pdf_text` |
| `cli.py` | Thêm lệnh `inspect` |
| `requirements.txt` | Thêm `pymupdf` |

**Vì sao `pdf_layout.py` nằm ở thư mục gốc chứ không trong `ingest/`:** nó không biết gì về PyMuPDF và không biết gì về `Block`. Nó chỉ nhận dict toạ độ và trả dict toạ độ. Phase 4 (render overlay) sẽ dùng lại chính nó để tính chỗ đặt chữ. Đặt trong `ingest/` là buộc tầng ghi ra phải import từ tầng đọc vào.

---

## Task 1: Phụ thuộc và xưởng dựng PDF mẫu

Không viết logic nào trước khi dựng được PDF mẫu xác định. Mọi task sau đều test trên nó.

**Files:**
- Modify: `requirements.txt`
- Modify: `tests/helpers.py`
- Create: `tests/test_pdf_ingest.py`

**Interfaces:**
- Produces: `tests/helpers.py` thêm `build_pdf(path, pages)` — dựng PDF nhiều trang từ mô tả thuần Python. Mọi task sau gọi hàm này.

- [ ] **Step 1: Cài PyMuPDF và ghi vào requirements**

```bash
.venv/bin/pip install pymupdf
printf 'pymupdf>=1.24\n' >> requirements.txt
```

- [ ] **Step 2: Thêm `build_pdf` vào `tests/helpers.py`**

Chèn vào cuối file:

```python
def build_pdf(path: Path, pages: list) -> Path:
    """Dựng PDF xác định từ mô tả thuần Python.

    Mỗi trang là list các dict: {"text", "x", "y", "size", "bold", "italic"}.
    Khổ trang 522x666pt cho khớp sách thật đã đo.

    Cố tình CHÈN KHÔNG THEO THỨ TỰ DỌC ở vài chỗ, vì PyMuPDF trả block theo
    thứ tự nội bộ chứ không theo thứ tự đọc — sách thật cũng vậy (18/18 trang
    mẫu). Test phải chứng minh code tự sắp xếp lại.
    """
    import pymupdf

    doc = pymupdf.open()
    for items in pages:
        page = doc.new_page(width=522, height=666)
        for it in items:
            font = "Times-Roman"
            if it.get("bold") and it.get("italic"):
                font = "Times-BoldItalic"
            elif it.get("bold"):
                font = "Times-Bold"
            elif it.get("italic"):
                font = "Times-Italic"
            page.insert_text((it["x"], it["y"]), it["text"],
                             fontsize=it.get("size", 10), fontname=font)
    doc.save(str(path))
    doc.close()
    return path


def trang_mot_doan(y_dau: float, so_dong: int, x: float = 67.0,
                   size: float = 10.0, tien_to: str = "dong") -> list:
    """Một đoạn văn giả: các dòng cách đều 12pt, nội dung đánh số để soi thứ tự."""
    return [{"text": f"{tien_to} {i} noi dung day du cua mot dong van ban",
             "x": x, "y": y_dau + i * 12, "size": size}
            for i in range(so_dong)]
```

- [ ] **Step 3: Viết test chứng minh xưởng hoạt động và PyMuPDF trả block lộn xộn**

Tạo `tests/test_pdf_ingest.py`:

```python
"""Adapter PDF, test trên PDF dựng trong tmp_path — không cần sách thật."""
import pymupdf

from helpers import build_pdf, trang_mot_doan


def test_xuong_dung_duoc_pdf_nhieu_trang(tmp_path):
    p = build_pdf(tmp_path / "m.pdf", [
        trang_mot_doan(100, 3),
        trang_mot_doan(100, 2),
    ])
    doc = pymupdf.open(p)
    assert doc.page_count == 2
    assert doc[0].rect.width == 522 and doc[0].rect.height == 666
    doc.close()


def test_pdf_giu_duoc_dam_va_nghieng(tmp_path):
    p = build_pdf(tmp_path / "m.pdf", [[
        {"text": "thuong", "x": 67, "y": 100},
        {"text": "dam", "x": 67, "y": 120, "bold": True},
        {"text": "nghieng", "x": 67, "y": 140, "italic": True},
    ]])
    doc = pymupdf.open(p)
    fonts = {s["text"].strip(): s["font"]
             for b in doc[0].get_text("dict")["blocks"] if not b["type"]
             for l in b["lines"] for s in l["spans"]}
    assert "Bold" in fonts["dam"]
    assert "Italic" in fonts["nghieng"]
    assert "Bold" not in fonts["thuong"] and "Italic" not in fonts["thuong"]
    doc.close()
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_ingest.py -v`
Expected: 2 passed.

Nếu `test_pdf_giu_duoc_dam_va_nghieng` hỏng vì tên font khác, in ra `fonts` rồi sửa điều kiện cho khớp tên font base-14 mà PyMuPDF đã cài — **đừng bỏ test này**, nó là nền cho Task 3.

- [ ] **Step 5: Chạy cả bộ để chắc chưa phá gì**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 68 passed (66 cũ + 2 mới).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt tests/helpers.py tests/test_pdf_ingest.py
git commit -m "test: xưởng dựng PDF mẫu xác định cho Phase 3

build_pdf dựng PDF nhiều trang từ mô tả Python, khổ 522x666 khớp sách
thật. Mọi test Phase 3 chạy trên nó, không cần file sách."
```

---

## Task 2: Mảnh → dòng, và sắp lại đúng thứ tự đọc

**Files:**
- Create: `pdf_layout.py`
- Create: `tests/test_pdf_layout.py`

**Interfaces:**
- Produces:
  - `pdf_layout.Line` — dataclass `(page_no, bbox, html, text, size, col=0)` với `bbox` là tuple `(x0, y0, x1, y1)`.
  - `pdf_layout.merge_spans(spans) -> (html, text, size)` — `spans` là list dict kiểu PyMuPDF (`text`, `font`, `size`, `flags`).
  - `pdf_layout.sort_reading_order(lines) -> list[Line]`.
  - `pdf_layout.VUNG_THAN_BAI = (40.0, 615.0)`.

- [ ] **Step 1: Viết test cho ghép mảnh và sắp thứ tự**

Tạo `tests/test_pdf_layout.py`:

```python
"""Dựng lại đoạn văn từ mảnh chữ rời. Hàm thuần: không PDF, không mạng."""
import pdf_layout
from pdf_layout import Line


def span(text, font="Times-Roman", size=10.0):
    return {"text": text, "font": font, "size": size, "flags": 0}


def line(y, text="x", x0=67.0, x1=400.0, size=10.0, page_no=0):
    return Line(page_no=page_no, bbox=(x0, y, x1, y + 10),
                html=text, text=text, size=size)


def test_ghep_manh_thanh_mot_dong():
    html, text, size = pdf_layout.merge_spans(
        [span("Mot cau "), span("bi cat lam doi.")])
    assert text == "Mot cau bi cat lam doi."
    assert html == "Mot cau bi cat lam doi."
    assert size == 10.0


def test_manh_nghieng_duoc_boc_the_i():
    html, text, _ = pdf_layout.merge_spans(
        [span("ten sach la "), span("Almagest", font="Times-Italic"), span(" nhe")])
    assert html == "ten sach la <i>Almagest</i> nhe"
    assert text == "ten sach la Almagest nhe"


def test_manh_dam_duoc_boc_the_b():
    html, _, _ = pdf_layout.merge_spans([span("Sao Hoa", font="Times-Bold")])
    assert html == "<b>Sao Hoa</b>"


def test_manh_vua_dam_vua_nghieng():
    html, _, _ = pdf_layout.merge_spans([span("ca hai", font="Times-BoldItalic")])
    assert html == "<b><i>ca hai</i></b>"


def test_manh_lien_nhau_cung_kieu_duoc_gop_lam_mot_the():
    """Hai mảnh nghiêng liền nhau không được thành <i>a</i><i>b</i>."""
    html, _, _ = pdf_layout.merge_spans(
        [span("Alma", font="Times-Italic"), span("gest", font="Times-Italic")])
    assert html == "<i>Almagest</i>"


def test_ky_tu_dac_biet_duoc_escape():
    html, text, _ = pdf_layout.merge_spans([span("a < b & c > d")])
    assert html == "a &lt; b &amp; c &gt; d"
    assert text == "a < b & c > d"


def test_co_chu_lay_theo_manh_dai_nhat():
    """Chữ cái đầu to ở đầu chương không được kéo cỡ cả dòng lên."""
    _, _, size = pdf_layout.merge_spans(
        [span("T", size=24.0), span("rong mot ngay dep troi thi", size=10.0)])
    assert size == 10.0


def test_manh_rong_bi_bo_qua():
    html, text, _ = pdf_layout.merge_spans([span("a"), span("   "), span("b")])
    assert text == "a   b"
    assert "<" not in html


def test_sap_lai_dung_thu_tu_doc():
    """PyMuPDF trả block theo thứ tự nội bộ — 18/18 trang sách thật lộn xộn."""
    lon_xon = [line(300, "ba"), line(100, "mot"), line(200, "hai")]
    assert [l.text for l in pdf_layout.sort_reading_order(lon_xon)] == ["mot", "hai", "ba"]


def test_cung_do_cao_thi_sap_tu_trai_sang_phai():
    trai = line(100, "trai", x0=67.0)
    phai = line(101, "phai", x0=300.0)     # lệch 1pt vẫn coi là cùng dòng
    assert [l.text for l in pdf_layout.sort_reading_order([phai, trai])] == ["trai", "phai"]


def test_sap_theo_cot_truoc_roi_moi_den_do_cao():
    c0 = line(300, "cot0-duoi"); c0.col = 0
    c1 = line(100, "cot1-tren"); c1.col = 1
    ket = pdf_layout.sort_reading_order([c1, c0])
    assert [l.text for l in ket] == ["cot0-duoi", "cot1-tren"]


def test_danh_sach_rong():
    assert pdf_layout.sort_reading_order([]) == []
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'pdf_layout'`.

- [ ] **Step 3: Viết `pdf_layout.py`**

```python
"""Dựng lại đoạn văn từ mảnh chữ rời của PDF.

Toàn bộ file này là hàm thuần trên cấu trúc dữ liệu: không import PyMuPDF,
không đụng đĩa, không đụng mạng. Nhờ vậy test chạy trong mili giây và Phase 4
(đè chữ lên trang) dùng lại được để tính chỗ đặt chữ.

Đơn vị toạ độ là point, gốc ở góc trên trái, y tăng xuống dưới.
"""
import html as _html
import re
from dataclasses import dataclass

# Vùng thân bài của sách mẫu: trên là header, dưới là footer. Đo thật trên
# ebook/astrology.pdf.pdf (header y~28, footer y~627).
VUNG_THAN_BAI = (40.0, 615.0)

# Hai dòng lệch nhau dưới ngần này point thì coi như cùng một dòng.
NGUONG_CUNG_DONG = 3.0


@dataclass
class Line:
    page_no: int
    bbox: tuple                 # (x0, y0, x1, y1)
    html: str                   # nội dung có <b>/<i>, đã escape
    text: str                   # nội dung thuần, chưa escape
    size: float                 # cỡ chữ trội nhất của dòng
    col: int = 0                # chỉ số cột, 0 là cột trái nhất


def _kieu(span) -> tuple:
    """(đậm, nghiêng) suy từ tên font. Tên font đáng tin hơn cờ bit của PDF."""
    ten = (span.get("font") or "").lower()
    return ("bold" in ten, "italic" in ten or "oblique" in ten)


def merge_spans(spans: list) -> tuple:
    """Ghép các mảnh của một dòng thành (html, text, size).

    Mảnh liền nhau cùng kiểu được gộp vào chung một thẻ, để không sinh ra
    <i>Alma</i><i>gest</i> — `check_translation` đếm thẻ nên chuyện đó làm
    mọi đoạn bị gắn cờ oan.
    """
    nhom = []                                   # [(đậm, nghiêng, [chuỗi])]
    for s in spans:
        t = s.get("text", "")
        if not t:
            continue
        k = _kieu(s)
        if nhom and nhom[-1][0] == k:
            nhom[-1][1].append(t)
        else:
            nhom.append((k, [t]))

    phan_html, phan_text = [], []
    for (dam, nghieng), phan in nhom:
        raw = "".join(phan)
        phan_text.append(raw)
        esc = _html.escape(raw, quote=False)
        if not esc.strip():                     # toàn khoảng trắng: không bọc thẻ
            phan_html.append(esc)
            continue
        if nghieng:
            esc = f"<i>{esc}</i>"
        if dam:
            esc = f"<b>{esc}</b>"
        phan_html.append(esc)

    text = "".join(phan_text)
    # Cỡ chữ của dòng lấy theo mảnh CÓ NHIỀU CHỮ NHẤT, không lấy lớn nhất:
    # chữ cái đầu chương cỡ 24pt không được kéo cả dòng thành tiêu đề.
    co = [(len(s.get("text", "").strip()), s.get("size", 0.0)) for s in spans
          if s.get("text", "").strip()]
    size = max(co)[1] if co else 0.0
    return "".join(phan_html), text, size


def sort_reading_order(lines: list) -> list:
    """Sắp theo cột, rồi theo chiều dọc, rồi trái sang phải.

    Bắt buộc: PyMuPDF trả block theo thứ tự nội bộ của file, và trên sách thật
    18/18 trang mẫu có block KHÔNG theo thứ tự dọc. Tin vào thứ tự thư viện
    trả về là đảo lộn nội dung cả cuốn sách.
    """
    return sorted(lines, key=lambda l: (l.col,
                                        round(l.bbox[1] / NGUONG_CUNG_DONG),
                                        l.bbox[0]))
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -v`
Expected: 12 passed.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 80 passed.

- [ ] **Step 6: Commit**

```bash
git add pdf_layout.py tests/test_pdf_layout.py
git commit -m "feat: ghép mảnh chữ thành dòng và sắp lại đúng thứ tự đọc

Mảnh liền nhau cùng kiểu gộp chung một thẻ để không làm lệch số thẻ
mà check_translation đếm. Cỡ chữ lấy theo mảnh nhiều chữ nhất nên chữ
cái đầu chương không biến cả dòng thành tiêu đề.
sort_reading_order là bắt buộc: PyMuPDF trả block lộn xộn trên 18/18
trang mẫu của sách thật."
```

---

## Task 3: Dòng → đoạn, và nối chữ bị gạch nối

**Files:**
- Modify: `pdf_layout.py`
- Modify: `tests/test_pdf_layout.py`

**Interfaces:**
- Consumes: `pdf_layout.Line`, `pdf_layout.sort_reading_order` từ Task 2.
- Produces: `pdf_layout.Para` — dataclass `(page_no, lines, html, text, size, bbox, kind="text", cont_group=None)`; `pdf_layout.group_paragraphs(lines) -> list[Para]`.

- [ ] **Step 1: Viết test cho gom đoạn**

Chèn vào cuối `tests/test_pdf_layout.py`:

```python
def test_dong_cach_deu_thi_cung_mot_doan():
    lines = [line(100), line(112), line(124)]
    paras = pdf_layout.group_paragraphs(lines)
    assert len(paras) == 1
    assert len(paras[0].lines) == 3


def test_khoang_trong_lon_thi_tach_doan():
    """Giãn dòng thường 12pt; nhảy 30pt là sang đoạn khác."""
    lines = [line(100), line(112), line(142), line(154)]
    paras = pdf_layout.group_paragraphs(lines)
    assert [len(p.lines) for p in paras] == [2, 2]


def test_thut_dau_dong_thi_tach_doan():
    """Cùng giãn dòng nhưng dòng sau thụt vào -> đoạn mới."""
    lines = [line(100, x0=67.0), line(112, x0=67.0), line(124, x0=85.0)]
    paras = pdf_layout.group_paragraphs(lines)
    assert [len(p.lines) for p in paras] == [2, 1]


def test_noi_chu_bi_gach_noi_cuoi_dong():
    a = line(100, "mot chu bi cat lam doi o cuoi dong nhu as-")
    b = line(112, "trology day")
    paras = pdf_layout.group_paragraphs([a, b])
    assert "astrology" in paras[0].text
    assert "as-" not in paras[0].text


def test_khong_noi_gach_ngang_that_su():
    """Gạch nối giữa hai từ đầy đủ (vd 'Anh-Viet') không được nuốt mất."""
    a = line(100, "day la tu ghep Anh-")
    b = line(112, "Viet nhe")
    paras = pdf_layout.group_paragraphs([a, b])
    assert "Anh-Viet" in paras[0].text


def test_dong_ghep_lai_co_dau_cach():
    a = line(100, "cau truoc")
    b = line(112, "cau sau")
    paras = pdf_layout.group_paragraphs([a, b])
    assert paras[0].text == "cau truoc cau sau"


def test_bbox_cua_doan_la_hop_cua_cac_dong():
    lines = [line(100, x0=67.0, x1=300.0), line(112, x0=67.0, x1=450.0)]
    p = pdf_layout.group_paragraphs(lines)[0]
    assert p.bbox == (67.0, 100.0, 450.0, 122.0)


def test_doan_giu_duoc_the_inline():
    a = line(100, "co <i>chu nghieng</i> o day")
    paras = pdf_layout.group_paragraphs([a])
    assert paras[0].html == "co <i>chu nghieng</i> o day"


def test_khong_co_dong_nao():
    assert pdf_layout.group_paragraphs([]) == []


def test_dong_o_trang_khac_khong_bao_gio_chung_doan():
    """Nối qua trang là việc của cont_group, không phải của group_paragraphs."""
    a = line(600, "cuoi trang", page_no=0)
    b = line(60, "dau trang sau", page_no=1)
    assert len(pdf_layout.group_paragraphs([a, b])) == 2
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -k group -v`
Expected: FAIL với `AttributeError: module 'pdf_layout' has no attribute 'group_paragraphs'`.

- [ ] **Step 3: Thêm `Para` và `group_paragraphs` vào `pdf_layout.py`**

Chèn sau `sort_reading_order`:

```python
# Dòng sau thụt vào hơn dòng trước ngần này point thì coi là mở đoạn mới.
NGUONG_THUT_DAU_DONG = 6.0
# Khoảng cách dọc lớn hơn giãn dòng thường nhân hệ số này thì tách đoạn.
HE_SO_TACH_DOAN = 1.6

_GACH_NOI_CUOI = re.compile(r"([a-zà-ỹ])-$", re.IGNORECASE)


@dataclass
class Para:
    page_no: int
    lines: list
    html: str
    text: str
    size: float
    bbox: tuple
    kind: str = "text"
    cont_group: int = None


def _giãn_dòng_thường(lines: list) -> float:
    """Trung vị khoảng cách dọc giữa các dòng liền nhau trong cùng trang."""
    khoang = [b.bbox[1] - a.bbox[1]
              for a, b in zip(lines, lines[1:])
              if b.page_no == a.page_no and 0 < b.bbox[1] - a.bbox[1] < 60]
    if not khoang:
        return 12.0
    khoang.sort()
    return khoang[len(khoang) // 2]


def _nối(truoc: str, sau: str) -> tuple:
    """Nối hai dòng. Trả về (chuỗi nối, có nuốt gạch nối không).

    Gạch nối cuối dòng do xếp chữ thì nuốt đi; gạch nối của từ ghép thật thì
    giữ. Phân biệt bằng: từ ghép thật hiếm khi bị đẩy xuống dòng ngay sau dấu
    gạch, nên chỉ nuốt khi phần sau bắt đầu bằng CHỮ THƯỜNG.
    """
    if _GACH_NOI_CUOI.search(truoc) and sau[:1].islower():
        return truoc[:-1] + sau, True
    return truoc + " " + sau, False


def group_paragraphs(lines: list) -> list:
    """Gom dòng liền nhau thành đoạn văn.

    Tách đoạn khi: sang trang khác, khoảng cách dọc vượt giãn dòng thường,
    hoặc dòng sau thụt vào so với dòng trước.
    """
    if not lines:
        return []

    lines = sort_reading_order(lines)
    gian = _giãn_dòng_thường(lines)
    nhom, cur = [], [lines[0]]

    for truoc, sau in zip(lines, lines[1:]):
        cach = sau.bbox[1] - truoc.bbox[1]
        doi_trang = sau.page_no != truoc.page_no
        xa_qua = cach > gian * HE_SO_TACH_DOAN
        thut_vao = sau.bbox[0] - truoc.bbox[0] > NGUONG_THUT_DAU_DONG
        if doi_trang or xa_qua or thut_vao:
            nhom.append(cur)
            cur = []
        cur.append(sau)
    nhom.append(cur)

    out = []
    for group in nhom:
        text = group[0].text
        html = group[0].html
        for l in group[1:]:
            text, nuot = _nối(text, l.text)
            html = (html[:-1] + l.html) if nuot else (html + " " + l.html)
        out.append(Para(
            page_no=group[0].page_no,
            lines=group,
            html=html,
            text=text,
            size=max(l.size for l in group),
            bbox=(min(l.bbox[0] for l in group), min(l.bbox[1] for l in group),
                  max(l.bbox[2] for l in group), max(l.bbox[3] for l in group)),
        ))
    return out
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -v`
Expected: 22 passed.

`test_noi_chu_bi_gach_noi_cuoi_dong` và `test_khong_noi_gach_ngang_that_su` là cặp đối nhau — nếu chỉ một cái xanh thì luật nuốt gạch nối đang sai, đừng nới điều kiện cho cả hai cùng qua.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 90 passed.

- [ ] **Step 6: Commit**

```bash
git add pdf_layout.py tests/test_pdf_layout.py
git commit -m "feat: gom dòng thành đoạn văn, nối chữ bị gạch nối cuối dòng

Tách đoạn theo giãn dòng thường của chính trang đó (trung vị) thay vì
một hằng số, và theo thụt đầu dòng. Gạch nối cuối dòng chỉ bị nuốt khi
phần tiếp theo bắt đầu bằng chữ thường, để không phá từ ghép thật."
```

---

## Task 4: Nhận diện cột

Sách mẫu một cột, nhưng `sort_reading_order` đã nhận trường `col` từ Task 2 và sách khác sẽ cần. Giữ nhỏ và đúng, không xây quá tay.

**Files:**
- Modify: `pdf_layout.py`
- Modify: `tests/test_pdf_layout.py`

**Interfaces:**
- Consumes: `pdf_layout.Line` từ Task 2.
- Produces: `pdf_layout.detect_columns(lines, page_width) -> None` — sửa `.col` tại chỗ.

- [ ] **Step 1: Viết test cho nhận diện cột**

Chèn vào cuối `tests/test_pdf_layout.py`:

```python
def test_mot_cot_thi_tat_ca_col_bang_khong():
    lines = [line(100 + i * 12, x0=67.0, x1=455.0) for i in range(10)]
    pdf_layout.detect_columns(lines, 522.0)
    assert {l.col for l in lines} == {0}


def test_hai_cot_duoc_tach_dung():
    trai = [line(100 + i * 12, "trai", x0=50.0, x1=240.0) for i in range(8)]
    phai = [line(100 + i * 12, "phai", x0=280.0, x1=470.0) for i in range(8)]
    lines = trai + phai
    pdf_layout.detect_columns(lines, 522.0)
    assert {l.col for l in trai} == {0}
    assert {l.col for l in phai} == {1}


def test_hai_cot_thi_doc_het_cot_trai_truoc():
    trai = [line(100 + i * 12, f"T{i}", x0=50.0, x1=240.0) for i in range(3)]
    phai = [line(100 + i * 12, f"P{i}", x0=280.0, x1=470.0) for i in range(3)]
    lines = trai + phai
    pdf_layout.detect_columns(lines, 522.0)
    ket = [l.text for l in pdf_layout.sort_reading_order(lines)]
    assert ket == ["T0", "T1", "T2", "P0", "P1", "P2"]


def test_tieu_de_vat_ngang_hai_cot_khong_lam_hong_nhan_dien():
    """Tiêu đề chạy suốt chiều ngang không được xoá mất khe giữa hai cột."""
    tieu_de = [line(80, "tieu de", x0=50.0, x1=470.0)]
    trai = [line(100 + i * 12, "trai", x0=50.0, x1=240.0) for i in range(8)]
    phai = [line(100 + i * 12, "phai", x0=280.0, x1=470.0) for i in range(8)]
    lines = tieu_de + trai + phai
    pdf_layout.detect_columns(lines, 522.0)
    assert {l.col for l in trai} == {0}
    assert {l.col for l in phai} == {1}


def test_qua_it_dong_thi_khong_doan_cot():
    """Ba dòng không đủ bằng chứng để kết luận sách hai cột."""
    lines = [line(100, x0=50.0, x1=240.0), line(112, x0=280.0, x1=470.0),
             line(124, x0=50.0, x1=240.0)]
    pdf_layout.detect_columns(lines, 522.0)
    assert {l.col for l in lines} == {0}
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -k cot -v`
Expected: FAIL với `AttributeError: module 'pdf_layout' has no attribute 'detect_columns'`.

- [ ] **Step 3: Thêm `detect_columns` vào `pdf_layout.py`**

Chèn sau `sort_reading_order`:

```python
# Cần ít nhất ngần này dòng mới dám kết luận sách nhiều cột.
TOI_THIEU_DONG_DE_DOAN_COT = 6
# Khe dọc phải rộng ít nhất ngần này phần của bề ngang trang.
KHE_COT_TOI_THIEU = 0.04


def detect_columns(lines: list, page_width: float) -> None:
    """Gán `col` cho từng dòng. Sửa tại chỗ.

    Tìm một khe dọc mà KHÔNG dòng nào bắc ngang qua. Dòng bắc ngang (tiêu đề
    chạy suốt trang) được bỏ ra khỏi phép thử và gán về cột 0, nếu không nó tự
    xoá mất cái khe mà ta đang đi tìm.
    """
    for l in lines:
        l.col = 0
    if len(lines) < TOI_THIEU_DONG_DE_DOAN_COT:
        return

    rong_tb = sum(l.bbox[2] - l.bbox[0] for l in lines) / len(lines)
    hep = [l for l in lines if l.bbox[2] - l.bbox[0] < rong_tb * 1.5]
    if len(hep) < TOI_THIEU_DONG_DE_DOAN_COT:
        return

    # Quét thử từng vị trí chia; chọn vị trí mà không dòng hẹp nào bắc qua.
    trai_nhat = min(l.bbox[0] for l in hep)
    phai_nhat = max(l.bbox[2] for l in hep)
    ung_vien = []
    buoc = page_width / 100.0
    x = trai_nhat + buoc
    while x < phai_nhat:
        if not any(l.bbox[0] < x < l.bbox[2] for l in hep):
            ung_vien.append(x)
        x += buoc

    if not ung_vien:
        return

    # Gom các vị trí liền nhau thành khe; lấy khe rộng nhất.
    khe, cur = [], [ung_vien[0]]
    for a, b in zip(ung_vien, ung_vien[1:]):
        if b - a <= buoc * 1.5:
            cur.append(b)
        else:
            khe.append(cur)
            cur = [b]
    khe.append(cur)
    rong_nhat = max(khe, key=lambda k: k[-1] - k[0])
    if rong_nhat[-1] - rong_nhat[0] < page_width * KHE_COT_TOI_THIEU:
        return

    moc = (rong_nhat[0] + rong_nhat[-1]) / 2
    for l in lines:
        if l.bbox[2] - l.bbox[0] >= rong_tb * 1.5:
            l.col = 0                      # dòng vắt ngang: coi như cột đầu
        else:
            l.col = 1 if l.bbox[0] >= moc else 0
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -v`
Expected: 27 passed.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 95 passed.

- [ ] **Step 6: Commit**

```bash
git add pdf_layout.py tests/test_pdf_layout.py
git commit -m "feat: nhận diện cột bằng khe dọc không dòng nào bắc qua

Dòng vắt ngang cả trang (tiêu đề) bị loại khỏi phép thử rồi gán về cột
0, vì nếu để nguyên thì chính nó xoá mất cái khe đang đi tìm. Dưới 6
dòng thì không đoán, coi như một cột."
```

---

## Task 5: Phân loại khối

**Files:**
- Modify: `pdf_layout.py`
- Modify: `tests/test_pdf_layout.py`

**Interfaces:**
- Consumes: `pdf_layout.Para` từ Task 3.
- Produces: `pdf_layout.classify(paras) -> None` — sửa `.kind` tại chỗ. Giá trị: `text` / `heading` / `caption` / `table` / `formula`.

- [ ] **Step 1: Viết test cho phân loại**

Chèn vào cuối `tests/test_pdf_layout.py`:

```python
def para(text, size=10.0, page_no=0, x0=67.0, y0=100.0, x1=455.0, n_lines=1):
    lines = [line(y0 + i * 12, text, x0=x0, x1=x1, size=size, page_no=page_no)
             for i in range(n_lines)]
    return pdf_layout.Para(page_no=page_no, lines=lines, html=text, text=text,
                           size=size, bbox=(x0, y0, x1, y0 + n_lines * 12))


def test_chu_to_va_ngan_la_tieu_de():
    ps = [para("Chuong Mot", size=13.6), para("noi dung " * 10, size=10.0, n_lines=5)]
    pdf_layout.classify(ps)
    assert ps[0].kind == "heading"
    assert ps[1].kind == "text"


def test_chu_to_nhung_dai_thi_khong_phai_tieu_de():
    """Một đoạn văn dài in cỡ lớn vẫn là đoạn văn."""
    ps = [para("noi dung rat dai " * 20, size=13.6, n_lines=6),
          para("binh thuong " * 10, size=10.0, n_lines=5)]
    pdf_layout.classify(ps)
    assert ps[0].kind == "text"


def test_chu_nho_la_caption():
    ps = [para("noi dung " * 10, size=10.0, n_lines=5),
          para("Hinh 1: minh hoa", size=8.2)]
    pdf_layout.classify(ps)
    assert ps[1].kind == "caption"


def test_nhieu_chu_so_va_ngan_la_bang():
    ps = [para("noi dung " * 10, size=10.0, n_lines=5),
          para("12 34 56 78 90 11 22 33", size=10.0)]
    pdf_layout.classify(ps)
    assert ps[1].kind == "table"


def test_nhieu_ky_tu_toan_la_cong_thuc():
    ps = [para("noi dung " * 10, size=10.0, n_lines=5),
          para("x = (a + b) / c × d ÷ e ± f", size=10.0)]
    pdf_layout.classify(ps)
    assert ps[1].kind == "formula"


def test_van_ban_binh_thuong_van_la_text():
    ps = [para("Mot doan van binh thuong voi vai con so nhu 1984 va 2026.",
               size=10.0, n_lines=3)]
    pdf_layout.classify(ps)
    assert ps[0].kind == "text"


def test_khong_co_doan_nao():
    pdf_layout.classify([])       # không được nổ


def test_moi_trang_tu_tinh_co_chu_trung_vi_cua_no():
    """Trang toàn chữ nhỏ không được biến cả trang thành caption."""
    ps = [para("a" * 50, size=8.0, page_no=1, n_lines=4),
          para("b" * 50, size=8.0, page_no=1, n_lines=4),
          para("Tieu De", size=11.0, page_no=1)]
    pdf_layout.classify(ps)
    assert [p.kind for p in ps] == ["text", "text", "heading"]
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -k "tieu_de or caption or bang or cong_thuc" -v`
Expected: FAIL với `AttributeError: module 'pdf_layout' has no attribute 'classify'`.

- [ ] **Step 3: Thêm `classify` vào `pdf_layout.py`**

Chèn sau `group_paragraphs`:

```python
# Tiêu đề: to hơn cỡ trội của trang ngần này lần, VÀ ngắn.
HE_SO_TIEU_DE = 1.15
DAI_TOI_DA_TIEU_DE = 80
# Caption: nhỏ hơn cỡ trội ngần này lần.
HE_SO_CAPTION = 0.9
# Bảng / công thức: tỉ lệ ký tự số hoặc ký tự toán vượt ngưỡng này.
TI_LE_SO_LA_BANG = 0.30
TI_LE_TOAN_LA_CONG_THUC = 0.08
DAI_TOI_DA_BANG = 120

_KY_TU_TOAN = set("=+×÷±∓≤≥≠∑∏√∫°′″")


def _co_troi(paras: list) -> float:
    """Cỡ chữ chiếm nhiều ký tự nhất — tức cỡ của thân bài."""
    theo_co = {}
    for p in paras:
        theo_co[p.size] = theo_co.get(p.size, 0) + len(p.text)
    return max(theo_co.items(), key=lambda kv: kv[1])[0] if theo_co else 10.0


def classify(paras: list) -> None:
    """Gán `kind` cho từng đoạn. Sửa tại chỗ.

    Cỡ trội được tính RIÊNG TỪNG TRANG: một trang in toàn chữ nhỏ không được
    biến cả trang thành caption.
    """
    theo_trang = {}
    for p in paras:
        theo_trang.setdefault(p.page_no, []).append(p)

    for cung_trang in theo_trang.values():
        troi = _co_troi(cung_trang)
        for p in cung_trang:
            t = p.text.strip()
            if not t:
                p.kind = "text"
                continue

            chu_so = sum(c.isdigit() for c in t)
            toan = sum(c in _KY_TU_TOAN for c in t)

            if toan / len(t) >= TI_LE_TOAN_LA_CONG_THUC:
                p.kind = "formula"
            elif chu_so / len(t) >= TI_LE_SO_LA_BANG and len(t) <= DAI_TOI_DA_BANG:
                p.kind = "table"
            elif p.size >= troi * HE_SO_TIEU_DE and len(t) <= DAI_TOI_DA_TIEU_DE:
                p.kind = "heading"
            elif p.size <= troi * HE_SO_CAPTION:
                p.kind = "caption"
            else:
                p.kind = "text"
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -v`
Expected: 35 passed.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 103 passed.

- [ ] **Step 6: Commit**

```bash
git add pdf_layout.py tests/test_pdf_layout.py
git commit -m "feat: phân loại đoạn thành heading/caption/table/formula/text

Cỡ trội tính riêng từng trang để trang toàn chữ nhỏ không thành caption
cả loạt. Tiêu đề phải vừa to vừa ngắn: đoạn văn dài in cỡ lớn vẫn là
đoạn văn."
```

---

## Task 6: Dò header và footer

Đây là chỗ dữ liệu thật bác bỏ spec. Spec mục 5 nói so trùng vị trí giữa các trang; đo thật cho thấy dòng thân bài cũng lặp vị trí vì sách xếp theo lưới đều. Phải so nội dung chữ.

**Files:**
- Modify: `pdf_layout.py`
- Modify: `tests/test_pdf_layout.py`

**Interfaces:**
- Consumes: `pdf_layout.Para` từ Task 3.
- Produces: `pdf_layout.mark_running(paras, so_trang) -> None` — đặt `.kind = "skip"` cho header/footer.

- [ ] **Step 1: Viết test cho dò header/footer**

Chèn vào cuối `tests/test_pdf_layout.py`:

```python
def test_header_lap_lai_bi_danh_dau_skip():
    ps = []
    for t in range(10):
        ps.append(para("Chiem Tinh Hoc Can Ban", size=9.0, page_no=t, y0=28.0))
        ps.append(para(f"noi dung rieng cua trang {t} " * 8, page_no=t, y0=100.0,
                       n_lines=5))
    pdf_layout.mark_running(ps, 10)
    assert [p.kind for p in ps if p.bbox[1] == 28.0] == ["skip"] * 10
    assert all(p.kind != "skip" for p in ps if p.bbox[1] == 100.0)


def test_so_trang_thay_doi_van_bi_skip():
    """Số trang khác nhau từng trang nhưng vẫn là footer."""
    ps = []
    for t in range(10):
        ps.append(para(str(100 + t), size=9.0, page_no=t, y0=627.0))
        ps.append(para(f"than bai trang {t} " * 10, page_no=t, y0=100.0, n_lines=5))
    pdf_layout.mark_running(ps, 10)
    assert [p.kind for p in ps if p.bbox[1] == 627.0] == ["skip"] * 10


def test_dong_than_bai_lap_VI_TRI_thi_KHONG_bi_skip():
    """Bác bỏ cách làm của spec: sách xếp lưới đều nên dòng thân bài cũng
    lặp đúng vị trí. Chỉ so vị trí là xoá nhầm nội dung thật."""
    ps = []
    for t in range(10):
        ps.append(para(f"day la cau van hoan toan khac nhau o trang so {t}, "
                       f"dai bang dong than bai binh thuong", page_no=t, y0=571.0))
    pdf_layout.mark_running(ps, 10)
    assert all(p.kind != "skip" for p in ps)


def test_chu_giua_trang_lap_lai_khong_bi_skip():
    """Câu lặp lại nhưng nằm giữa trang thì là nội dung, không phải header."""
    ps = [para("cau nay lap lai", page_no=t, y0=300.0) for t in range(10)]
    pdf_layout.mark_running(ps, 10)
    assert all(p.kind != "skip" for p in ps)


def test_sach_qua_it_trang_thi_khong_dam_ket_luan():
    ps = [para("Co the la header", size=9.0, page_no=t, y0=28.0) for t in range(2)]
    pdf_layout.mark_running(ps, 2)
    assert all(p.kind != "skip" for p in ps)


def test_mark_running_khong_co_doan_nao():
    pdf_layout.mark_running([], 0)        # không được nổ
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -k running -v`
Expected: FAIL với `AttributeError: module 'pdf_layout' has no attribute 'mark_running'`.

- [ ] **Step 3: Thêm `mark_running` vào `pdf_layout.py`**

Chèn sau `classify`:

```python
# Cần ít nhất ngần này trang mới dám kết luận có header/footer.
TOI_THIEU_TRANG_DE_DO_LAP = 4
# Phải xuất hiện trên ít nhất ngần này phần số trang.
TI_LE_TRANG_PHAI_CO = 0.6
# Header/footer là chữ ngắn.
DAI_TOI_DA_LAP = 60

_CHU_SO = re.compile(r"\d+")


def _van_tay(text: str) -> str:
    """Bỏ chữ số đi: số trang đổi từng trang nhưng vẫn là cùng một footer."""
    return _CHU_SO.sub("#", text.strip().lower())


def mark_running(paras: list, so_trang: int) -> None:
    """Đánh dấu header/footer là `skip`. Sửa tại chỗ.

    KHÔNG dò bằng vị trí lặp lại. Sách xếp chữ theo lưới đều nên dòng thân bài
    cũng rơi đúng cùng độ cao trên hầu hết các trang — đo thật trên sách mẫu
    thấy các dòng ở y=55, 571, 583, 595 xuất hiện trên 15-18/18 trang. Dò bằng
    vị trí là xoá nhầm nội dung thật.

    Ba điều kiện cùng lúc: nội dung (sau khi bỏ chữ số) lặp trên phần lớn số
    trang, chữ ngắn, và nằm ngoài vùng thân bài.
    """
    if so_trang < TOI_THIEU_TRANG_DE_DO_LAP or not paras:
        return

    tren, duoi = VUNG_THAN_BAI
    ria = [p for p in paras
           if (p.bbox[1] < tren or p.bbox[1] > duoi) and len(p.text.strip()) <= DAI_TOI_DA_LAP]

    trang_theo_van_tay = {}
    for p in ria:
        trang_theo_van_tay.setdefault(_van_tay(p.text), set()).add(p.page_no)

    lap = {vt for vt, trang in trang_theo_van_tay.items()
           if len(trang) >= so_trang * TI_LE_TRANG_PHAI_CO}

    for p in ria:
        if _van_tay(p.text) in lap:
            p.kind = "skip"
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -v`
Expected: 41 passed.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 109 passed.

- [ ] **Step 6: Commit**

```bash
git add pdf_layout.py tests/test_pdf_layout.py
git commit -m "feat: dò header/footer bằng nội dung lặp, không bằng vị trí lặp

Spec mục 5 nói so trùng giữa các trang; đo thật trên sách mẫu cho thấy
dòng thân bài ở y=55/571/583/595 cũng lặp trên 15-18/18 trang vì sách
xếp chữ theo lưới đều. Dò bằng vị trí là xoá nhầm nội dung. Nay so vân
tay nội dung (đã bỏ chữ số nên số trang vẫn khớp), cộng điều kiện ngắn
và nằm ngoài vùng thân bài."
```

---

## Task 7: Nối đoạn bị cắt ngang trang

**Files:**
- Modify: `pdf_layout.py`
- Modify: `tests/test_pdf_layout.py`

**Interfaces:**
- Consumes: `pdf_layout.Para` từ Task 3, `.kind` từ Task 5 và Task 6.
- Produces: `pdf_layout.link_continuations(paras) -> None` — đặt `.cont_group` cho các đoạn thuộc cùng một mạch văn.

- [ ] **Step 1: Viết test cho nối trang**

Chèn vào cuối `tests/test_pdf_layout.py`:

```python
def test_doan_khong_ket_cau_thi_noi_sang_trang_sau():
    a = para("cau van con dang do va chua ket thuc", page_no=0, y0=600.0)
    b = para("phan con lai cua cau do.", page_no=1, y0=60.0)
    pdf_layout.link_continuations([a, b])
    assert a.cont_group is not None
    assert a.cont_group == b.cont_group


def test_doan_ket_bang_dau_cham_thi_khong_noi():
    a = para("mot cau hoan chinh.", page_no=0, y0=600.0)
    b = para("Cau moi bat dau.", page_no=1, y0=60.0)
    pdf_layout.link_continuations([a, b])
    assert a.cont_group is None and b.cont_group is None


def test_trang_sau_bat_dau_bang_chu_hoa_thi_khong_noi():
    """Không kết câu nhưng trang sau mở bằng chữ hoa -> nhiều khả năng đoạn mới."""
    a = para("mot dong bi cat", page_no=0, y0=600.0)
    b = para("Doan Hoan Toan Moi", page_no=1, y0=60.0)
    pdf_layout.link_continuations([a, b])
    assert a.cont_group is None


def test_tieu_de_khong_bao_gio_bi_noi():
    a = para("cau con dang do", page_no=0, y0=600.0)
    b = para("Chuong Hai", page_no=1, y0=60.0)
    b.kind = "heading"
    pdf_layout.link_continuations([a, b])
    assert a.cont_group is None


def test_doan_skip_khong_can_thiep_vao_mach_van():
    """Footer nằm giữa hai nửa của một đoạn không được cắt mạch."""
    a = para("cau con dang do", page_no=0, y0=600.0)
    f = para("123", page_no=0, y0=627.0); f.kind = "skip"
    b = para("phan tiep theo.", page_no=1, y0=60.0)
    pdf_layout.link_continuations([a, f, b])
    assert a.cont_group is not None and a.cont_group == b.cont_group
    assert f.cont_group is None


def test_ba_doan_noi_lien_nhau_cung_mot_nhom():
    a = para("phan mot con do", page_no=0, y0=600.0)
    b = para("phan hai cung con do", page_no=1, y0=60.0)
    c = para("phan ba ket thuc.", page_no=2, y0=60.0)
    pdf_layout.link_continuations([a, b, c])
    assert a.cont_group == b.cont_group == c.cont_group


def test_doan_cuoi_sach_khong_tro_di_dau():
    a = para("cau cuoi sach khong co dau cham", page_no=9, y0=600.0)
    pdf_layout.link_continuations([a])
    assert a.cont_group is None


def test_hai_doan_cung_mot_trang_khong_phai_noi_trang():
    a = para("cau con do", page_no=0, y0=300.0)
    b = para("cau sau.", page_no=0, y0=400.0)
    pdf_layout.link_continuations([a, b])
    assert a.cont_group is None
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -k "noi or cont" -v`
Expected: FAIL với `AttributeError: module 'pdf_layout' has no attribute 'link_continuations'`.

- [ ] **Step 3: Thêm `link_continuations` vào `pdf_layout.py`**

Chèn sau `mark_running`:

```python
_KET_CAU = set(".!?”’")        # chấm, than, hỏi, ngoặc kép/đơn đóng


def link_continuations(paras: list) -> None:
    """Nối các đoạn bị cắt ngang trang thành cùng một `cont_group`.

    Đo thật trên sách mẫu: 11/18 trang có đoạn nối sang trang sau, trong đó 2
    trang cắt ngang giữa một từ bằng gạch nối. Đây là chuyện thường, không
    phải ngoại lệ.

    Chỉ xét các đoạn `text`: tiêu đề, caption, bảng, công thức và header/footer
    không bao giờ nối. Đoạn `skip` cũng không được cắt mạch — footer nằm giữa
    hai nửa của một đoạn là chuyện bình thường.
    """
    thuc = [p for p in paras if p.kind == "text"]
    nhom_ke = 0

    for truoc, sau in zip(thuc, thuc[1:]):
        if sau.page_no <= truoc.page_no:
            continue                                  # cùng trang: không phải nối trang
        t = truoc.text.rstrip()
        s = sau.text.lstrip()
        if not t or not s:
            continue
        if t[-1] in _KET_CAU:
            continue                                  # đã kết câu
        if s[:1].isupper():
            continue                                  # trang sau mở bằng chữ hoa

        if truoc.cont_group is None:
            nhom_ke += 1
            truoc.cont_group = nhom_ke
        sau.cont_group = truoc.cont_group
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -v`
Expected: 49 passed.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 117 passed.

- [ ] **Step 6: Commit**

```bash
git add pdf_layout.py tests/test_pdf_layout.py
git commit -m "feat: nối đoạn bị cắt ngang trang bằng cont_group

Chỉ nối đoạn kind=text, và chỉ khi trang trước không kết câu còn trang
sau không mở bằng chữ hoa. Footer xen giữa không cắt mạch. Đoạn cuối
sách không trỏ đi đâu."
```

---

## Task 8: Adapter `ingest/pdf_text.py` và nhận PDF ở `init`

**Files:**
- Create: `ingest/pdf_text.py`
- Modify: `ingest/__init__.py`
- Modify: `tests/test_pdf_ingest.py`
- Modify: `tests/test_ingest_detect.py`

**Interfaces:**
- Consumes: `blocks.Block`, `ingest.Ingested`, `ingest.UnsupportedSource` từ Phase 2; toàn bộ `pdf_layout` từ Task 2-7.
- Produces: `ingest.pdf_text.load(path) -> Ingested`; `ingest.SUPPORTED_FORMATS` nay là `("epub", "pdf")`.

- [ ] **Step 1: Viết test cho adapter**

Chèn vào cuối `tests/test_pdf_ingest.py`:

```python
import pytest

import ingest
from helpers import build_pdf, trang_mot_doan


def test_load_pdf_tra_ve_block_dung_thu_tu(tmp_path):
    p = build_pdf(tmp_path / "m.pdf", [
        [{"text": "Chuong Mot", "x": 67, "y": 80, "size": 14}] + trang_mot_doan(120, 4),
        trang_mot_doan(80, 3, tien_to="trangsau"),
    ])
    kq = ingest.load(p)
    assert kq.fmt == "pdf"
    assert kq.source_name == "m.pdf"
    assert kq.blocks, "phải bóc ra được block"
    assert [b.page_no for b in kq.blocks] == sorted(b.page_no for b in kq.blocks)
    assert kq.blocks[0].kind == "heading"


def test_block_mang_toa_do_va_layout(tmp_path):
    p = build_pdf(tmp_path / "m.pdf", [trang_mot_doan(120, 3)])
    b = ingest.load(p).blocks[0]
    assert b.bbox and len(b.bbox.split(",")) == 4
    assert b.line_bboxes
    assert b.layout.get("col") == 0
    assert b.tag == "p"


def test_doan_skip_khong_duoc_dua_vao_danh_sach_dich(tmp_path):
    """Header lặp 6 trang phải bị loại, không tốn token dịch."""
    pages = []
    for t in range(6):
        pages.append([{"text": "Sach Mau", "x": 67, "y": 28, "size": 9}]
                     + trang_mot_doan(120, 4, tien_to=f"trang{t}"))
    p = build_pdf(tmp_path / "m.pdf", pages)
    kq = ingest.load(p)
    assert all("Sach Mau" not in b.src_html for b in kq.blocks)


def test_trang_trang_khong_lam_vo(tmp_path):
    p = build_pdf(tmp_path / "m.pdf", [trang_mot_doan(120, 3), [], trang_mot_doan(120, 2)])
    kq = ingest.load(p)
    assert kq.blocks
    assert {b.page_no for b in kq.blocks} == {0, 2}


def test_pdf_khong_co_lop_chu_bao_ro(tmp_path):
    """Sách scan: PDF hợp lệ nhưng không trích được chữ nào."""
    import pymupdf
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page(width=522, height=666)
    p = tmp_path / "scan.pdf"
    doc.save(str(p)); doc.close()

    with pytest.raises(ingest.UnsupportedSource, match="Phase 7"):
        ingest.load(p)


def test_pdf_co_mat_khau_bao_ro(tmp_path):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=522, height=666)
    page.insert_text((67, 100), "noi dung bi khoa", fontsize=10)
    p = tmp_path / "khoa.pdf"
    doc.save(str(p), encryption=pymupdf.PDF_ENCRYPT_AES_256,
             owner_pw="chu", user_pw="nguoidung")
    doc.close()

    with pytest.raises(ingest.UnsupportedSource, match="mật khẩu"):
        ingest.load(p)


def test_chu_xoay_bi_bo_qua_khong_tron_vao_mach_van(tmp_path):
    """Chữ xoay có bbox không phản ánh thứ tự đọc."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=522, height=666)
    for i in range(4):
        page.insert_text((67, 120 + i * 12), f"dong ngang {i} noi dung day du",
                         fontsize=10)
    page.insert_text((480, 300), "chu xoay doc", fontsize=10, rotate=90)
    p = tmp_path / "xoay.pdf"
    doc.save(str(p)); doc.close()

    kq = ingest.load(p)
    assert all("xoay" not in b.src_html for b in kq.blocks)
```

- [ ] **Step 2: Cập nhật test nhận diện định dạng**

Trong `tests/test_ingest_detect.py`, thay test cũ nói PDF chưa hỗ trợ:

```python
def test_pdf_nay_da_duoc_ho_tro():
    assert "pdf" in ingest.SUPPORTED_FORMATS
    assert "epub" in ingest.SUPPORTED_FORMATS
```

Xoá `test_pdf_chua_duoc_ho_tro_nhung_thong_bao_phai_ro` — nó khẳng định điều nay đã sai.

- [ ] **Step 3: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_ingest.py -v`
Expected: FAIL — `ingest.load` ném `UnsupportedSource("PDF sẽ được hỗ trợ từ Phase 3...")`.

- [ ] **Step 4: Viết `ingest/pdf_text.py`**

```python
"""Adapter PDF có sẵn lớp chữ.

Chỗ duy nhất trong Phase 3 đụng tới PyMuPDF. Mọi phép dựng lại đoạn văn nằm ở
pdf_layout.py dưới dạng hàm thuần.
"""
import json
from pathlib import Path

import pymupdf

import pdf_layout
from blocks import Block
from ingest import Ingested, UnsupportedSource

# Chữ xoay: bbox không phản ánh thứ tự đọc, trộn vào là vỡ mạch văn.
# dir=(1,0) là chữ nằm ngang bình thường.
HUONG_NGANG = (1.0, 0.0)


def _doc_trang(page, page_no: int) -> list:
    """Trả về list[pdf_layout.Line] của một trang, đã bỏ chữ xoay."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:                    # 1 = ảnh
            continue
        for l in b["lines"]:
            if tuple(round(v, 3) for v in l.get("dir", HUONG_NGANG)) != HUONG_NGANG:
                continue                          # chữ xoay: bỏ qua có kiểm soát
            html, text, size = pdf_layout.merge_spans(l["spans"])
            if not text.strip():
                continue
            out.append(pdf_layout.Line(page_no=page_no, bbox=tuple(l["bbox"]),
                                       html=html, text=text, size=size))
    return out


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
        for pno in range(doc.page_count):
            lines = _doc_trang(doc[pno], pno)
            if not lines:
                continue                          # trang trắng hoặc toàn ảnh
            pdf_layout.detect_columns(lines, doc[pno].rect.width)
            paras.extend(pdf_layout.group_paragraphs(lines))

        if not paras:
            raise UnsupportedSource(
                f"{path.name} không có lớp chữ nào trích được — nhiều khả năng "
                f"là sách scan. OCR là Phase 7."
            )

        pdf_layout.classify(paras)
        pdf_layout.mark_running(paras, doc.page_count)
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
    return Ingested(fmt="pdf", source_name=path.name, blocks=blocks)


def _line_bboxes(p) -> str:
    return json.dumps([[round(v, 1) for v in l.bbox] for l in p.lines],
                      separators=(",", ":"))
```

- [ ] **Step 5: Cho `ingest/__init__.py` định tuyến sang adapter PDF**

Sửa hai chỗ:

```python
SUPPORTED_FORMATS = ("epub", "pdf")
```

```python
def load(path) -> Ingested:
    p = Path(path)
    fmt = detect_format(p)
    ensure_supported(fmt)
    if fmt == "pdf":
        from ingest import pdf_text as adapter
    else:
        from ingest import epub as adapter
    return adapter.load(p)
```

- [ ] **Step 6: Chạy test adapter**

Run: `.venv/bin/python -m pytest tests/test_pdf_ingest.py -v`
Expected: 9 passed.

- [ ] **Step 7: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 125 passed. Hai vân tay EPUB vẫn PASS.

- [ ] **Step 8: Vá lại bản sửa từ review Phase 2 mà task này vừa làm hỏng**

Phase 2 đã sửa một lỗi: `init` từ chối định dạng lạ **trước khi** tạo thư mục,
để không bỏ lại project mồ côi kèm nguyên file nguồn. Lá chắn đó là
`ingest.ensure_supported(fmt)`, và nó chỉ chặn theo *định dạng*.

Nay PDF đã được hỗ trợ, nên một file PDF **hỏng** sẽ qua được `ensure_supported`,
rồi `init` tạo thư mục, copy file, và chỉ chết ở `pymupdf.open`. Thư mục mồ côi
quay lại — với sách scan 1GB thì đúng bằng 1GB. Test
`tests/test_cli_loi.py::test_tu_choi_dinh_dang_thi_khong_de_lai_thu_muc_mo_coi`
hiện dùng một file PDF giả, nên sau Task 8 nó sẽ ĐỎ.

Sửa tận gốc: dọn thư mục vừa tạo khi `init` hỏng vì bất cứ lý do gì, không chỉ
vì sai định dạng.

Trong `tests/test_cli_loi.py`, đổi file mẫu của test cũ sang thứ không phải PDF
lẫn EPUB (để nó vẫn kiểm đúng lá chắn theo định dạng), rồi thêm test mới:

```python
def test_pdf_hong_cung_khong_de_lai_thu_muc_mo_coi(tmp_path):
    """Lá chắn theo định dạng không đủ: PDF hợp lệ về magic bytes nhưng hỏng
    ruột vẫn lọt qua ensure_supported rồi mới chết ở pymupdf.open."""
    src = tmp_path / "hong.pdf"
    src.write_bytes(b"%PDF-1.6\r\n" + b"rac" * 2000)
    proj = tmp_path / "proj"

    with pytest.raises(SystemExit):
        cli.cmd_init(argparse.Namespace(
            source=str(src), dir=str(proj), chunk_chars=6000, force=True))

    assert not proj.exists(), f"để lại rác: {list(proj.iterdir())}"


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
```

Và sửa `cmd_init` trong `cli.py` — bọc phần sau `mkdir` để dọn khi hỏng:

```python
    proj.mkdir(parents=True, exist_ok=True)
    tu_tao = not da_co_truoc                 # chỉ dọn thư mục do lần này tạo ra
    try:
        stored = proj / f"source.{fmt}"
        shutil.copy2(src, stored)
        for name, content in (("style.md", DEFAULT_STYLE),
                              ("glossary.txt", DEFAULT_GLOSSARY)):
            if not (proj / name).exists():
                (proj / name).write_text(content, encoding="utf-8")

        print(f"Đang đọc {src.name} ({fmt}) ...")
        data = ingest.load(stored)
        if not data.blocks:
            raise ingest.UnsupportedSource(
                "không tìm thấy đoạn văn bản nào để dịch (sách toàn ảnh? DRM?).")
    except ingest.UnsupportedSource as e:
        if tu_tao:
            shutil.rmtree(proj, ignore_errors=True)
        die(str(e))
```

Thêm ngay trước `proj.mkdir`:

```python
    da_co_truoc = proj.exists()
```

và bỏ khối `try/except ingest.UnsupportedSource` cũ quanh `ingest.load`, cùng
dòng `if not data.blocks: die(...)` cũ — nay cả hai đã nằm trong khối trên.

- [ ] **Step 9: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_cli_loi.py tests/test_pdf_ingest.py -v`
Expected: 11 passed (2 cũ đã sửa file mẫu + 2 mới + 9 của adapter... đếm theo thực tế, điều quan trọng là **không cái nào đỏ**).

- [ ] **Step 10: Commit**

```bash
git add ingest/ cli.py tests/test_pdf_ingest.py tests/test_ingest_detect.py tests/test_cli_loi.py
git commit -m "feat: adapter PDF text, init nhận PDF

Chỗ duy nhất đụng PyMuPDF. Chữ xoay bị bỏ qua có kiểm soát vì bbox của
nó không phản ánh thứ tự đọc. PDF không trích được chữ nào thì nói rõ
là sách scan và OCR là Phase 7, thay vì tạo project rỗng."
```

---

## Task 9: Lệnh `inspect`

Đây là điều kiện nghiệm thu của cả Phase 3: soi bằng mắt mà không tốn token.

**Files:**
- Modify: `cli.py`
- Create: `tests/test_inspect.py`

**Interfaces:**
- Consumes: bảng `blocks` sau `init`.
- Produces: lệnh `python cli.py inspect <project> --pages A-B`.

- [ ] **Step 1: Viết test cho `inspect`**

Tạo `tests/test_inspect.py`:

```python
"""`inspect` cho xem tool hiểu cuốn sách thế nào, trước khi tiêu tiền dịch."""
import argparse

import pytest

import cli
from helpers import build_pdf, run_init, trang_mot_doan


def run_inspect(proj, capsys, pages=None):
    cli.cmd_inspect(argparse.Namespace(project=str(proj), pages=pages))
    return capsys.readouterr().out


@pytest.fixture
def proj_pdf(tmp_path):
    src = build_pdf(tmp_path / "m.pdf", [
        [{"text": "Chuong Mot", "x": 67, "y": 80, "size": 14}] + trang_mot_doan(120, 4),
        trang_mot_doan(80, 3, tien_to="hai"),
        trang_mot_doan(80, 3, tien_to="ba"),
    ])
    return run_init(src, tmp_path / "proj")


def test_in_ra_tung_doan_theo_thu_tu(proj_pdf, capsys):
    out = run_inspect(proj_pdf, capsys)
    assert "trang 0" in out and "trang 1" in out
    assert out.index("trang 0") < out.index("trang 1")


def test_hien_phan_loai(proj_pdf, capsys):
    out = run_inspect(proj_pdf, capsys)
    assert "heading" in out


def test_loc_theo_khoang_trang(proj_pdf, capsys):
    out = run_inspect(proj_pdf, capsys, pages="2-2")
    assert "trang 2" in out
    assert "trang 0" not in out and "trang 1" not in out


def test_khoang_trang_sai_dinh_dang_bao_loi_ro(proj_pdf, capsys):
    with pytest.raises(SystemExit) as e:
        run_inspect(proj_pdf, capsys, pages="linh tinh")
    assert "--pages" in str(e.value)


def test_khoang_trang_khong_co_trang_nao(proj_pdf, capsys):
    out = run_inspect(proj_pdf, capsys, pages="900-999")
    assert "không có đoạn nào" in out


def test_in_ra_tong_ket_de_uoc_luong(proj_pdf, capsys):
    out = run_inspect(proj_pdf, capsys)
    assert "ký tự" in out
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_inspect.py -v`
Expected: FAIL với `AttributeError: module 'cli' has no attribute 'cmd_inspect'`.

- [ ] **Step 3: Thêm `parse_pages` và `cmd_inspect` vào `cli.py`**

Chèn trước mục `# ---- translate`:

```python
# ------------------------------------------------------------------ inspect

def parse_pages(spec):
    """'10-20' -> (10, 20). None -> None. Sai định dạng thì thoát có thông báo."""
    if not spec:
        return None
    try:
        dau, _, cuoi = spec.partition("-")
        if not cuoi:
            return (int(dau), int(dau))
        return (int(dau), int(cuoi))
    except ValueError:
        die(f"--pages phải có dạng 10-20 hoặc 10, không phải '{spec}'.")


def cmd_inspect(args):
    proj, con = open_project(args.project)
    khoang = parse_pages(args.pages)

    sql = ("SELECT page_no, pos, tag, kind, src_html, bbox, cont_group "
           "FROM blocks")
    tham = ()
    if khoang:
        sql += " WHERE page_no BETWEEN ? AND ?"
        tham = khoang
    sql += " ORDER BY page_no, pos"

    rows = con.execute(sql, tham).fetchall()
    if not rows:
        print("không có đoạn nào trong khoảng này.")
        return

    trang_hien = None
    tong = 0
    for r in rows:
        if r["page_no"] != trang_hien:
            trang_hien = r["page_no"]
            print(f"\n--- trang {trang_hien} ---")
        tong += len(r["src_html"])
        noi = _rut_gon(r["src_html"])
        nhom = f" ->nhóm {r['cont_group']}" if r["cont_group"] else ""
        print(f"  [{r['pos']:>2}] {r['kind']:<8} {r['tag']:<3}{nhom} | {noi}")

    trang = {r["page_no"] for r in rows}
    print(f"\n{len(rows)} đoạn trên {len(trang)} trang, {tong:,} ký tự nguồn.")
    print("Soi thứ tự đọc và phân loại ở trên. Chưa tốn token nào.")


def _rut_gon(s: str, gioi_han: int = 90) -> str:
    from bs4 import BeautifulSoup
    t = BeautifulSoup(s, "html.parser").get_text().strip()
    t = " ".join(t.split())
    return t if len(t) <= gioi_han else t[:gioi_han - 1] + "…"
```

- [ ] **Step 4: Đăng ký lệnh trong `main`**

Chèn sau parser `status`:

```python
    p = sub.add_parser("inspect", help="xem tool hiểu cuốn sách thế nào (không tốn token)")
    p.add_argument("project")
    p.add_argument("--pages", help="khoảng trang, ví dụ 1-20")
    p.set_defaults(func=cmd_inspect)
```

- [ ] **Step 5: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_inspect.py -v`
Expected: 6 passed.

- [ ] **Step 6: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 131 passed.

- [ ] **Step 7: NGHIỆM THU — chạy trên sách thật**

```bash
.venv/bin/python cli.py init ebook/astrology.pdf.pdf --dir /tmp/bt-p3 --force
.venv/bin/python cli.py inspect /tmp/bt-p3 --pages 150-155
```

Expected: `init` báo số đoạn và số chunk cho 925 trang. `inspect` in ra 6 trang.

**Đây là bước soi bằng mắt, không phải bước chạy cho có.** Kiểm bốn điều:

1. **Thứ tự đọc**: đọc dọc danh sách có thành văn xuôi liền mạch không, hay nhảy cóc.
2. **Header/footer**: tên chương chạy đầu trang và số trang chân trang phải KHÔNG xuất hiện. Nếu thấy chúng, `mark_running` đang hỏng.
3. **Phân loại**: tiêu đề chương phải là `heading`, không phải `text`. Đoạn văn thường phải là `text`, không phải `table` hay `formula`.
4. **Nối trang**: đoạn cuối trang 150 và đoạn đầu trang 151, nếu là một mạch văn, phải mang cùng số nhóm.

Chỗ nào sai thì quay lại task sở hữu nó (thứ tự→Task 2, đoạn→Task 3, phân loại→Task 5, header→Task 6, nối→Task 7), sửa bằng TDD, rồi soi lại.

- [ ] **Step 8: Dọn và commit**

```bash
rm -rf /tmp/bt-p3
git add cli.py tests/test_inspect.py
git commit -m "feat: lệnh inspect — soi cấu trúc bóc ra được, không tốn token

Điều kiện nghiệm thu của Phase 3: nhìn thấy tool hiểu cuốn sách thế nào
trước khi cam kết tiền cho việc dịch."
```

---

## Nghiệm thu Phase 3

1. `.venv/bin/python -m pytest tests/ -q` — 131 passed, không test nào gọi mạng.
2. Hai file trong `tests/golden/` **không đổi**: `git log --oneline -- tests/golden/` vẫn chỉ có đúng một commit.
3. `inspect` trên 20 trang thật của `astrology.pdf.pdf` cho thứ tự đọc liền mạch, không có header/footer, tiêu đề đúng là `heading`.
4. **Không một token API nào bị tiêu trong cả Phase 3.**
5. `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py` ra rỗng — logic dựng lại đoạn văn không dính thư viện PDF, nên Phase 4 dùng lại được.

Điều kiện 5 là phép thử cho quyết định kiến trúc chính của phase này: phần khó nhất phải là hàm thuần, test được trong mili giây, và không khoá chặt vào PyMuPDF.
