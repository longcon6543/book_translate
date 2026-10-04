# Phase 7 — Gom dòng đúng cho sách scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trên trang sách scan đã OCR, ghép các mảnh chữ cùng hàng thành một dòng trước khi gom đoạn, để chữ không bị chia sai giữa các đoạn.

**Architecture:** Một hàm thuần mới `pdf_layout.ghep_manh_cung_hang` (không PyMuPDF). `ingest/pdf_text.py` dò trang scan theo từng trang (`_la_trang_scan`: ảnh phủ ≥ 90% diện tích) và chỉ gọi hàm ghép trên trang đó, sau `detect_columns`, trước `group_paragraphs`. Text-PDF đi nguyên đường cũ.

**Tech Stack:** Python 3.12, PyMuPDF 1.28.2, pytest, SQLite.

**Spec:** `docs/superpowers/specs/2026-09-23-gom-dong-sach-scan-design.md` (G1–G5). Spec mẹ: `docs/superpowers/specs/2026-09-21-pdf-song-ngu-design.md`.

## Global Constraints

- Chạy test: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`. Không test nào gọi mạng.
- Nền: 308 test xanh ở commit `925074e`. Vân tay `tests/golden/` không đổi: `git diff --stat 925074e -- tests/golden/` phải rỗng.
- Luật tầng: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py` phải rỗng. `ghep_manh_cung_hang` là hàm thuần.
- Ngưỡng (spec G3): cùng hàng khi phần chồng dọc > 60% chiều cao của dòng có chiều cao nhỏ hơn; dòng sau nằm bên phải khi `x0` sau ≥ `x1` trước − 2pt; khe ≤ **2,0 × cỡ chữ dòng trước**. Trang scan khi một ảnh phủ ≥ **90%** diện tích trang.
- Không lọc rác OCR (spec mục 3).
- Không đổi schema DB, `translate`, `export`, `reflow`.
- Commit kết thúc bằng: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. **Trang có ảnh nền phủ kín nhưng là text-PDF có bảng** (sách thiết kế có hình nền) — bị nhận là trang scan; ô bảng cách nhau ~3× cỡ chữ không được dán thành một dòng. → Task 3.
2. **Một hàng bị OCR cắt thành ba mảnh trở lên** — ghép dồn đủ, đúng thứ tự trái sang phải. → Task 2.
3. **Mảnh đuôi mang cỡ chữ OCR bị thổi lên** (đo thật: 26–120pt) — ngưỡng khe tính theo dòng trước nên vẫn ghép; cỡ chữ dòng ghép lấy theo mảnh dài hơn, không bị thổi lên theo. → Task 2.
4. **Hai dòng OCR chồng lên nhau cùng một vùng** (chữ lặp) — không ghép, để không nhân đôi chữ. → Task 2.
5. **Trang scan không có mảnh cùng hàng nào** — kết quả y hệt đầu vào; hàm không sửa `Line` đầu vào. → Task 2.

---

## Pre-flight: giao diện giữa các task

| Task | Tạo ra | Task dùng |
|---|---|---|
| 1 | Số đo nền `-truoc` trong ledger; script `do_g7.py` trong workspace | 4 |
| 2 | `pdf_layout.ghep_manh_cung_hang(lines: list, khe_toi_da: float = NGUONG_KHE_CUNG_HANG) -> list[Line]`; hằng `NGUONG_KHE_CUNG_HANG = 2.0` | 3 |
| 3 | `ingest.pdf_text._la_trang_scan(page) -> bool`; `load()` gọi hàm ghép trên trang scan | 4 |

Task 1 PHẢI chạy trước mọi thay đổi code: nó chụp hành vi của code cũ.

---

### Task 1: Đo nền trước khi sửa — không đổi code

**Files:**
- Create: `.superpowers/sdd/2026-09-23-phase-7-gom-dong/do_g7.py` (workspace, git-ignore)
- Create: `projects/harmonics-g7-truoc/`, `projects/astrology-g7-truoc/` (git-ignore)

**Interfaces:**
- Consumes: không.
- Produces: một dòng số đo cho mỗi cuốn, ghi vào ledger; script `do_g7.py <thư mục project>`.

- [ ] **Step 1: Viết script đo**

Tạo `.superpowers/sdd/2026-09-23-phase-7-gom-dong/do_g7.py`:

```python
"""Đo chất lượng gom dòng của một project. Dùng: python do_g7.py projects/<tên>

In một dòng: số khối, số ký tự (bỏ khoảng trắng và gạch nối — gom đoạn nối từ
bị gạch ngang cuối dòng, nên đổi cách gom có thể xê dịch vài dấu '-' mà không
mất chữ nào), số chỗ cùng hàng, số chỗ cắt ngang câu, số cặp khung chồng có chữ
khác nhau, và vân tay của danh sách (page_no, pos, bbox, src_html).
"""
import hashlib, json, re, sqlite3, sys

import pymupdf

duong = sys.argv[1]
con = sqlite3.connect(f"{duong}/project.db")
con.row_factory = sqlite3.Row


def thuan(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h or "")).strip()


rows = list(con.execute("SELECT page_no, pos, bbox, line_bboxes, src_html FROM blocks "
                        "WHERE page_no >= 0 ORDER BY page_no, pos"))
van_tay = hashlib.sha256(json.dumps(
    [(r["page_no"], r["pos"], r["bbox"], r["src_html"]) for r in rows],
    ensure_ascii=False).encode()).hexdigest()[:16]
ky_tu = sum(len(re.sub(r"[\s\-]", "", thuan(r["src_html"]))) for r in rows)

theo = {}
for r in rows:
    if not r["bbox"]:
        continue
    theo.setdefault(r["page_no"], []).append(dict(
        bb=pymupdf.Rect(*[float(v) for v in r["bbox"].split(",")]),
        dong=[pymupdf.Rect(*d) for d in json.loads(r["line_bboxes"] or "[]")],
        t=thuan(r["src_html"])))

cung_hang = cat_cau = 0
for ks in theo.values():
    for a, b in zip(ks, ks[1:]):
        if not a["dong"] or not b["dong"] or not a["t"] or not b["t"]:
            continue
        cuoi, dau = a["dong"][-1], b["dong"][0]
        if (min(cuoi.y1, dau.y1) - max(cuoi.y0, dau.y0) > 0.6 * min(cuoi.height, dau.height)
                and dau.x0 >= cuoi.x1 - 2 and dau.x0 - cuoi.x1 < 40):
            cung_hang += 1
            if a["t"][-1] not in ".!?:;”’\")" and b["t"][0].islower():
                cat_cau += 1

chong = 0
for ks in theo.values():
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            a, b = ks[i], ks[j]
            if len(a["t"]) <= 15 or len(b["t"]) <= 15:
                continue
            if a["t"].lower() in b["t"].lower() or b["t"].lower() in a["t"].lower():
                continue
            g = pymupdf.Rect(a["bb"])
            g.intersect(b["bb"])
            if not g.is_valid or g.is_empty or g.height < 5:
                continue
            if g.get_area() >= 0.25 * min(a["bb"].get_area(), b["bb"].get_area()):
                chong += 1

print(f"khối {len(rows)} | ký tự {ky_tu} | cùng hàng {cung_hang} | cắt câu {cat_cau} | "
      f"khung chồng {chong} | vân tay {van_tay}")
```

- [ ] **Step 2: `init` nền bằng code CHƯA sửa**

Run:
```bash
git log --oneline -1
.venv/bin/python -W ignore::DeprecationWarning cli.py init projects/harmonics/source.pdf --dir projects/harmonics-g7-truoc
.venv/bin/python -W ignore::DeprecationWarning cli.py init projects/astrology/source.pdf --dir projects/astrology-g7-truoc
```
Expected: commit hiện tại chưa có thay đổi nào của Task 2/3. harmonics ra `4120 đoạn`, astrology ra `10411 đoạn` (khớp số đã đo lúc dựng project).

- [ ] **Step 3: Đo nền và ghi vào ledger**

Run:
```bash
W=.superpowers/sdd/2026-09-23-phase-7-gom-dong
for p in harmonics-g7-truoc astrology-g7-truoc; do echo "$p: $(.venv/bin/python -W ignore::DeprecationWarning $W/do_g7.py projects/$p)"; done | tee -a $W/progress.md
```
Expected: harmonics `cắt câu` quanh 280 và `cùng hàng` quanh 1.292 (số đo trên DB cũ; chênh ít cũng được — DB cũ có thể do code cũ hơn dựng, và đó chính là lý do đo lại ở đây). Hai dòng số đo nằm trong ledger.

Không commit — không có file nào trong repo thay đổi.

---

### Task 2: `ghep_manh_cung_hang` — hàm thuần

**Files:**
- Modify: `pdf_layout.py` (thêm hằng và hai hàm ngay trước `group_paragraphs`)
- Test: `tests/test_pdf_layout.py`

**Interfaces:**
- Consumes: `pdf_layout.Line`, `pdf_layout.sort_reading_order`.
- Produces: `NGUONG_KHE_CUNG_HANG = 2.0`, `TI_LE_CHONG_CUNG_HANG = 0.6`, `ghep_manh_cung_hang(lines: list, khe_toi_da: float = NGUONG_KHE_CUNG_HANG) -> list` trả list `Line` MỚI theo thứ tự đọc; không sửa `Line` đầu vào.

- [ ] **Step 1: Viết test**

Nối vào cuối `tests/test_pdf_layout.py` (file đã có helper `line(y, text, x0, x1, size, page_no)` dựng khung `(x0, y, x1, y + 10)`):

```python
# ---- Ghép mảnh cùng hàng (sách scan, Phase 7) ----
# Đo thật trên sách scan: OCR cắt một hàng chữ làm hai; group_paragraphs coi
# mảnh đuôi là dòng thụt đầu đoạn và đẩy nó sang đoạn sau.


def test_hai_manh_cung_hang_khe_nho_duoc_ghep():
    a = line(100, "the first part of a row", x0=67, x1=200)
    b = line(100, "tail", x0=208, x1=230)            # khe 8pt = 0,8 x cỡ chữ
    ra = pdf_layout.ghep_manh_cung_hang([a, b])
    assert len(ra) == 1
    assert ra[0].text == "the first part of a row tail"
    assert ra[0].html == "the first part of a row tail"
    assert ra[0].bbox == (67, 100, 230, 110)


def test_khe_qua_hai_lan_co_chu_thi_khong_ghep():
    """Khe rộng hơn 2x cỡ chữ là ô bảng hoặc cột — đúng bố cục, không dán."""
    a = line(100, "cell one", x0=67, x1=200)
    b = line(100, "cell two", x0=221, x1=300)        # khe 21pt > 20pt
    assert len(pdf_layout.ghep_manh_cung_hang([a, b])) == 2


def test_khac_cot_khong_ghep():
    a = line(100, "left column", x0=67, x1=200)
    b = line(100, "right column", x0=208, x1=300)
    b.col = 1
    assert len(pdf_layout.ghep_manh_cung_hang([a, b])) == 2


def test_khac_hang_khong_ghep():
    a = line(100, "row one", x0=67, x1=200)
    b = line(112, "row two", x0=208, x1=300)
    assert len(pdf_layout.ghep_manh_cung_hang([a, b])) == 2


def test_ba_manh_ghep_don_dung_thu_tu():
    """Review Focus 2."""
    c = line(100, "three", x0=208, x1=240)
    a = line(100, "one", x0=67, x1=150)
    b = line(100, "two", x0=158, x1=200)
    ra = pdf_layout.ghep_manh_cung_hang([c, a, b])   # đầu vào lộn thứ tự
    assert [l.text for l in ra] == ["one two three"]


def test_khong_mat_ky_tu_nao():
    ls = [line(100, "alpha beta", x0=67, x1=150), line(100, "gamma", x0=158, x1=200),
          line(112, "delta epsilon", x0=67, x1=200)]
    dem = lambda xs: sum(len(l.text.replace(" ", "")) for l in xs)
    assert dem(pdf_layout.ghep_manh_cung_hang(ls)) == dem(ls)


def test_co_chu_lay_cua_manh_dai_hon():
    """Review Focus 3: OCR hay gán cỡ chữ thổi lên (đo thật 26-120pt) cho mảnh
    ngắn. Khe tính theo dòng trước nên vẫn ghép; cỡ chữ không bị thổi theo."""
    a = line(100, "a long ordinary line of body text", x0=67, x1=200, size=10.0)
    b = line(100, "x", x0=208, x1=215, size=60.0)
    ra = pdf_layout.ghep_manh_cung_hang([a, b])
    assert len(ra) == 1 and ra[0].size == 10.0


def test_khe_tinh_theo_co_chu_dong_truoc():
    a = line(100, "big heading text", x0=67, x1=200, size=20.0)
    b = line(100, "tail", x0=230, x1=260, size=20.0)  # khe 30pt <= 2 x 20pt
    assert len(pdf_layout.ghep_manh_cung_hang([a, b])) == 1


def test_manh_chong_len_nhau_khong_ghep():
    """Review Focus 4: dòng OCR lặp đè lên cùng vùng — ghép là nhân đôi chữ."""
    a = line(100, "duplicated ocr line", x0=67, x1=200)
    b = line(100, "duplicated ocr line", x0=150, x1=283)
    assert len(pdf_layout.ghep_manh_cung_hang([a, b])) == 2


def test_khong_co_gi_de_ghep_thi_giu_nguyen_va_khong_sua_dau_vao():
    """Review Focus 5."""
    a = line(100, "row one", x0=67, x1=200)
    b = line(112, "row two", x0=67, x1=200)
    ra = pdf_layout.ghep_manh_cung_hang([a, b])
    assert [(l.text, l.bbox) for l in ra] == [("row one", (67, 100, 200, 110)),
                                              ("row two", (67, 112, 200, 122))]
    c = line(100, "head", x0=67, x1=200)
    pdf_layout.ghep_manh_cung_hang([c, line(100, "tail", x0=208, x1=230)])
    assert c.text == "head" and c.bbox == (67, 100, 200, 110), "đã sửa Line đầu vào"


def test_danh_sach_rong():
    assert pdf_layout.ghep_manh_cung_hang([]) == []
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_layout.py -q`
Expected: 11 test hỏng — `AttributeError: module 'pdf_layout' has no attribute 'ghep_manh_cung_hang'`. Mọi test cũ trong file vẫn xanh.

- [ ] **Step 3: Viết hàm**

Trong `pdf_layout.py`, chèn ngay trước `def group_paragraphs(`:

```python
# Ghép mảnh cùng hàng — chỉ dùng cho trang sách scan (ingest/pdf_text.py quyết).
# Đo thật trên sách scan: ngưỡng 2,0x bắt 1.037/1.292 chỗ cùng hàng và 227/280
# chỗ cắt ngang câu; quá 2x thì lẫn ô bảng, chú thích nằm cạnh nhau. Không áp
# cho text-PDF: ở đó chỗ cùng hàng có khe ~3x và là ô bảng, cột mục lục ĐÚNG.
NGUONG_KHE_CUNG_HANG = 2.0
TI_LE_CHONG_CUNG_HANG = 0.6


def _cung_hang(a, b) -> bool:
    chong = min(a.bbox[3], b.bbox[3]) - max(a.bbox[1], b.bbox[1])
    thap = min(a.bbox[3] - a.bbox[1], b.bbox[3] - b.bbox[1])
    return thap > 0 and chong > TI_LE_CHONG_CUNG_HANG * thap


def _ghep_hai_dong(a, b):
    # Cỡ chữ trội lấy theo mảnh nhiều chữ hơn, như merge_spans: OCR hay gán cỡ
    # chữ thổi lên cho mảnh ngắn, lấy max là thổi theo cả dòng.
    chinh = a if len(a.text) >= len(b.text) else b
    return Line(page_no=a.page_no,
                bbox=(min(a.bbox[0], b.bbox[0]), min(a.bbox[1], b.bbox[1]),
                      max(a.bbox[2], b.bbox[2]), max(a.bbox[3], b.bbox[3])),
                html=a.html.rstrip() + " " + b.html.lstrip(),
                text=a.text.rstrip() + " " + b.text.lstrip(),
                size=chinh.size, col=a.col)


def ghep_manh_cung_hang(lines: list, khe_toi_da: float = NGUONG_KHE_CUNG_HANG) -> list:
    """Ghép các mảnh chữ OCR nằm cùng một hàng thành một dòng.

    OCR cắt một hàng chữ thành hai mảnh. group_paragraphs thấy mảnh đuôi nằm xa
    về bên phải, tưởng là dòng thụt đầu đoạn, nên đẩy nó sang đoạn SAU: đoạn
    trước mất vài chữ cuối, đoạn sau mở đầu bằng chữ lạc, và model dịch một câu
    cụt. Ghép lại trước khi gom đoạn thì chữ về đúng đoạn.

    Hai dòng liền nhau (theo thứ tự đọc) được ghép khi: cùng trang, cùng cột,
    cùng hàng, dòng sau nằm bên phải dòng trước, và khe ngang không quá
    `khe_toi_da` lần cỡ chữ dòng trước. Trả về list Line mới; không sửa đầu vào.
    """
    out = []
    for l in sort_reading_order(lines):
        truoc = out[-1] if out else None
        if (truoc is not None
                and l.page_no == truoc.page_no and l.col == truoc.col
                and _cung_hang(truoc, l)
                and l.bbox[0] >= truoc.bbox[2] - 2
                and l.bbox[0] - truoc.bbox[2] <= khe_toi_da * truoc.size):
            out[-1] = _ghep_hai_dong(truoc, l)
        else:
            out.append(l)
    return out
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_layout.py -q`
Expected: toàn bộ xanh.

- [ ] **Step 5: Cả bộ, luật tầng, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q; grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py`
Expected: `319 passed` (308 + 11); lệnh grep không in gì.

```bash
git add pdf_layout.py tests/test_pdf_layout.py
git commit -m "feat: ghep_manh_cung_hang — ghép mảnh OCR cùng hàng thành một dòng

OCR cắt một hàng chữ làm hai; group_paragraphs coi mảnh đuôi là dòng
thụt đầu đoạn và đẩy nó sang đoạn sau, làm chữ bị chia sai giữa các
đoạn. Hàm thuần, ngưỡng khe 2,0x cỡ chữ dòng trước lấy từ số đo.
Chưa nối vào ingest.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Dò trang scan và nối vào `init`

**Files:**
- Modify: `ingest/pdf_text.py` (hằng, `_la_trang_scan`, vòng trang trong `load`, thông báo lỗi dòng 64–67)
- Modify: `tests/test_pdf_ingest.py` (thêm test; sửa chữ khớp ở dòng 87)
- Modify: `README.md` (dòng 80–81)

**Interfaces:**
- Consumes: `pdf_layout.ghep_manh_cung_hang` (Task 2).
- Produces: `ingest.pdf_text._la_trang_scan(page) -> bool`; `ingest.load` ghép mảnh cùng hàng trên trang scan.

- [ ] **Step 1: Viết test**

Trong `tests/test_pdf_ingest.py`, ở test `test_pdf_khong_co_lop_chu_bao_ro`, đổi:

```python
    with pytest.raises(ingest.UnsupportedSource, match="Phase 7"):
```

thành:

```python
    # Phase 7 làm sạch lớp OCR có sẵn chứ không chạy OCR — thông báo không
    # được hứa một phase đã xong mà không làm việc đó.
    with pytest.raises(ingest.UnsupportedSource, match="chưa tự chạy OCR"):
```

Rồi nối vào cuối file:

```python
from ingest import pdf_text


def _trang_hang_bi_cat(doc, co_anh, khe=8.0):
    """Một hàng chữ bị OCR cắt làm hai mảnh, rồi ba hàng tiếp của cùng đoạn.

    Đo thật: khe 4pt thì PyMuPDF tự gộp hai mảnh thành một dòng và KHÔNG tái
    hiện được lỗi; khe 8pt và 15pt thì mảnh đuôi thành dòng riêng và ingest cũ
    ra hai khối — đúng như lớp chữ OCR thật.
    """
    page = doc.new_page(width=522, height=666)
    if co_anh:
        _anh(doc, page, 0, 0, 522, 666)          # ảnh phủ kín trang: sách scan
    dau = "the first part of a line cut by"
    page.insert_text((67, 120), dau, fontsize=10)
    x = 67 + pymupdf.get_text_length(dau, fontsize=10)
    page.insert_text((x + khe, 120), "ocr", fontsize=10)
    for i in range(1, 4):
        page.insert_text((67, 120 + i * 12),
                         f"next line {i} of the same paragraph here", fontsize=10)


def _load(tmp_path, ten, co_anh, khe=8.0):
    doc = pymupdf.open()
    _trang_hang_bi_cat(doc, co_anh, khe)
    p = tmp_path / ten
    doc.save(str(p))
    doc.close()
    return ingest.load(p).blocks


def test_tien_de_khong_co_anh_thi_hang_bi_cat_sinh_hai_khoi(tmp_path):
    """Lưới an toàn cho text-PDF: không có ảnh phủ trang thì hành vi GIỮ NGUYÊN.
    Cũng là tiền đề của test bên dưới — cách dựng này phải tái hiện được lỗi.
    Test này xanh cả trước lẫn sau bản sửa; đó là chủ ý."""
    assert len(_load(tmp_path, "chu.pdf", co_anh=False)) == 2


def test_trang_scan_hang_bi_cat_doi_van_ra_mot_doan(tmp_path):
    khoi = _load(tmp_path, "scan.pdf", co_anh=True)
    assert len(khoi) == 1, [b.src_html for b in khoi]
    assert "cut by ocr next line 1" in khoi[0].src_html


def test_anh_phu_mot_phan_trang_khong_phai_trang_scan():
    doc = pymupdf.open()
    nua = doc.new_page(width=522, height=666)
    _anh(doc, nua, 0, 0, 522, 333)
    kin = doc.new_page(width=522, height=666)
    _anh(doc, kin, 0, 0, 522, 666)
    trang = doc.new_page(width=522, height=666)
    assert not pdf_text._la_trang_scan(nua)
    assert pdf_text._la_trang_scan(kin)
    assert not pdf_text._la_trang_scan(trang)


def test_trang_scan_o_bang_cach_xa_khong_bi_dan(tmp_path):
    """Review Focus 1: text-PDF có hình nền phủ kín sẽ bị nhận là trang scan.
    Ô bảng cách nhau 3x cỡ chữ (đo thật: khe trung vị ở bảng ~3x) phải cho ra
    đúng những khối như khi không có hình nền."""
    co = _load(tmp_path, "a.pdf", co_anh=True, khe=30.0)
    khong = _load(tmp_path, "b.pdf", co_anh=False, khe=30.0)
    assert [b.src_html for b in co] == [b.src_html for b in khong]
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_ingest.py -q`
Expected: 3 test hỏng — `test_pdf_khong_co_lop_chu_bao_ro` (thông báo còn là "OCR là Phase 7"), `test_trang_scan_hang_bi_cat_doi_van_ra_mot_doan` (ra 2 khối), `test_anh_phu_mot_phan_trang_khong_phai_trang_scan` (`AttributeError: ... '_la_trang_scan'`). `test_tien_de_...` và `test_trang_scan_o_bang_...` xanh sẵn — cả hai ghim hành vi phải GIỮ, không phải tính năng mới.

- [ ] **Step 3: `_la_trang_scan` và nối vào `load`**

Trong `ingest/pdf_text.py`, chèn ngay sau hằng `HUONG_NGANG = (1.0, 0.0)`:

```python

# Trang sách scan: một ảnh phủ ngần này diện tích trang. Đo thật: sách scan
# 482/484 trang, text-PDF 925 trang không có trang nào.
TI_LE_ANH_PHU_TRANG = 0.9


def _la_trang_scan(page) -> bool:
    """Trang có một ảnh phủ >= 90% diện tích trang.

    Trên trang như vậy chữ là lớp OCR đè lên ảnh chụp, và OCR hay cắt một hàng
    chữ làm nhiều mảnh — chỉ ở đó mới ghép mảnh cùng hàng. Text-PDF có chỗ
    cùng hàng là ô bảng và cột mục lục đúng bố cục, ghép vào là phá.
    """
    dien_tich = page.rect.get_area()
    for x in page.get_images(full=True):
        for r in page.get_image_rects(x[0]):
            g = pymupdf.Rect(r)
            g.intersect(page.rect)
            if g.is_valid and not g.is_empty and \
                    g.get_area() >= TI_LE_ANH_PHU_TRANG * dien_tich:
                return True
    return False
```

Trong `load`, thay:

```python
            pdf_layout.detect_columns(lines, doc[pno].rect.width)
            paras.extend(pdf_layout.group_paragraphs(lines))
```

bằng:

```python
            pdf_layout.detect_columns(lines, doc[pno].rect.width)
            if _la_trang_scan(doc[pno]):
                # Ghép SAU dò cột để "cùng cột" có nghĩa, TRƯỚC gom đoạn để
                # mảnh đuôi không bị coi là dòng thụt đầu đoạn mới.
                lines = pdf_layout.ghep_manh_cung_hang(lines)
            paras.extend(pdf_layout.group_paragraphs(lines))
```

Và thay dòng thông báo:

```python
                f"là sách scan. OCR là Phase 7."
```

bằng:

```python
                f"là sách scan chưa có lớp chữ OCR, mà tool chưa tự chạy OCR."
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_ingest.py -q`
Expected: toàn bộ xanh.

- [ ] **Step 5: README**

Trong `README.md`, thay:

```
Sách scan đã có lớp chữ OCR
thì dùng được ngay; mảnh vụn OCR chưa được lọc (Phase 7).
```

bằng:

```
Sách scan đã có lớp chữ OCR
thì dùng được ngay: lúc `init`, trên trang scan (ảnh phủ kín trang) những mảnh
chữ OCR bị cắt rời trên cùng một hàng được ghép lại, để chữ không bị chia sai
giữa các đoạn. Mảnh vụn OCR (ký tự rác quanh biểu đồ) KHÔNG bị lọc: luật lọc
theo nội dung sẽ xoá nhầm tên riêng và thuật ngữ thật. Sách scan chưa có lớp
chữ thì chưa dùng được — tool chưa tự chạy OCR.
```

- [ ] **Step 6: Cả bộ, luật tầng, golden, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q; grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py; git diff --stat 925074e -- tests/golden/`
Expected: `323 passed` (319 + 4); hai lệnh sau không in gì.

```bash
git add ingest/pdf_text.py tests/test_pdf_ingest.py README.md
git commit -m "feat: init ghép mảnh OCR cùng hàng trên trang sách scan

Chỉ trang có ảnh phủ >= 90% diện tích (sách scan 482/484, text-PDF
0/925). Ghép sau dò cột, trước gom đoạn. Text-PDF đi nguyên đường cũ.

Thông báo 'OCR là Phase 7' đổi thành nói thẳng tool chưa tự chạy OCR:
Phase 7 làm sạch lớp OCR có sẵn chứ không chạy OCR.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Nghiệm thu trên sách thật — không tốn token

**Files:** không sửa code. Thư mục `projects/*-g7-*` (git-ignore). Thay `projects/harmonics`.

**Interfaces:**
- Consumes: số đo `-truoc` trong ledger (Task 1), `do_g7.py` (Task 1), `ingest.load` đã sửa (Task 3).
- Produces: số đo so với ngưỡng spec mục 6; `projects/harmonics` dựng lại bằng code mới.

- [ ] **Step 1: `init` bằng code đã sửa**

```bash
.venv/bin/python -W ignore::DeprecationWarning cli.py init projects/harmonics/source.pdf --dir projects/harmonics-g7-sau
.venv/bin/python -W ignore::DeprecationWarning cli.py init projects/astrology/source.pdf --dir projects/astrology-g7-sau
W=.superpowers/sdd/2026-09-23-phase-7-gom-dong
for p in harmonics-g7-sau astrology-g7-sau; do echo "$p: $(.venv/bin/python -W ignore::DeprecationWarning $W/do_g7.py projects/$p)"; done | tee -a $W/progress.md
grep "g7-truoc" $W/progress.md
```

Expected, so từng dòng `-sau` với dòng `-truoc`:
- astrology: `khối`, `ký tự`, `cùng hàng`, `cắt câu`, `khung chồng` và `vân tay` **giống hệt**.
- harmonics: `ký tự` **bằng nhau**; `cắt câu` ≤ 53; `khung chồng` ≤ một nửa số `-truoc`; `khối` ít hơn `-truoc`.

Chỉ số nào trượt thì đó là phát hiện: tìm trang lệch, đo, báo — không nới ngưỡng. Nếu `ký tự` của harmonics lệch, so theo từng trang giữa `-truoc` và `-sau` để biết chữ mất ở đâu trước khi làm gì khác.

- [ ] **Step 2: Nhìn tận mắt trang 60–61**

```bash
.venv/bin/python -W ignore::DeprecationWarning cli.py export projects/harmonics-g7-sau --pages 60-61 --mode reflow --dry-run -o projects/harmonics-g7-sau/rv.pdf
.venv/bin/python -W ignore::DeprecationWarning - <<'PY'
import pymupdf
d = pymupdf.open("projects/harmonics-g7-sau/rv.pdf")
p = d[0]
p.get_pixmap(dpi=130, clip=pymupdf.Rect(p.rect.width / 2, 0, p.rect.width,
                                        p.rect.height)).save("projects/harmonics-g7-sau/rv-phai.png")
print("đã xuất projects/harmonics-g7-sau/rv-phai.png")
PY
```

Expected: mở ảnh bằng công cụ Read. Nửa dịch dry-run (chữ Anh độn) không còn hai dòng đè nhau ở các đoạn văn thân bài như ảnh Phase 6. Rác OCR quanh biểu đồ vẫn còn — đúng spec mục 3.

- [ ] **Step 3: Thay `projects/harmonics` bằng bản dựng mới**

Người dùng đã chấp nhận mất bản dịch trang 60–61 ($0,01).

```bash
.venv/bin/python -W ignore::DeprecationWarning cli.py init projects/harmonics/source.pdf --dir projects/harmonics --force
.venv/bin/python -W ignore::DeprecationWarning .superpowers/sdd/2026-09-23-phase-7-gom-dong/do_g7.py projects/harmonics
```

Expected: dòng số đo giống hệt dòng `harmonics-g7-sau`.

- [ ] **Step 4: Dọn và kiểm tổng**

```bash
rm -rf projects/harmonics-g7-truoc projects/harmonics-g7-sau projects/astrology-g7-truoc projects/astrology-g7-sau
.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q; grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py; git diff --stat 925074e -- tests/golden/; git status --porcelain
```

Expected: `323 passed`; ba lệnh sau không in gì. Không commit — không file nào trong repo thay đổi.
