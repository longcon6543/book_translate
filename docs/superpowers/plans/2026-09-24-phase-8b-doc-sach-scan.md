# Phase 8B — Đọc sách scan đúng Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khâu đọc sách scan không mất chữ do dòng nghiêng, nhận đúng hai cột chỉ mục, giữ mỗi mục lục một khối, và biến vùng hình vẽ thành ô "ảnh" không dịch.

**Architecture:** Hai hàm thuần mới ở `pdf_layout.py` (`tim_khe_hai_cot`, `noi_so_trang`) và một module thuần mới `vung_hinh.py` (dò vùng hình trên bytes ảnh xám). `ingest/pdf_text.py` là chỗ duy nhất chụp ảnh trang và nối chúng vào luồng đọc trang scan; vùng hình đi qua `Ingested.meta` vào bảng `meta` của project. `render/pdf_reflow.py` đọc vùng hình và vẽ ô "ảnh" trong cả bộ dàn lẫn bộ dự phòng.

**Tech Stack:** Python 3.12, PyMuPDF 1.28, pytest. Không numpy.

**Spec:** [docs/superpowers/specs/2026-09-24-doc-sach-scan-design.md](../specs/2026-09-24-doc-sach-scan-design.md)

## Global Constraints

- Chạy test: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q` — hiện 370 passed.
- Vân tay `tests/golden/` không được đổi.
- Luật tầng: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py render/dan_trang.py vung_hinh.py` phải rỗng.
- Không test nào gọi mạng. Không `init --force` vào `projects/harmonics` hay `projects/astrology`; nghiệm thu init vào thư mục MỚI.
- Mọi luật mới (E2–E6) chỉ chạy trên trang scan (`pdf_text._la_trang_scan`); text-PDF đi đúng đường cũ.
- E1: nhận dòng `|atan2(dy, dx)| < 10°` và `dx > 0`.
- E2: gom hàng `y0` lệch ≤ 3pt; khe thử tại mép phải mỗi dòng + 0,5pt trong 30–70% bề rộng; dòng bắc qua ≤ `max(2, ⌈5% số dòng⌉)`; nhận khi hàng tách ≥ 60% số hàng; cần ≥ 12 dòng thân bài.
- E3/E4: mảnh số `^\d{1,3}$` hoặc La Mã `^[ivxlc]{1,6}$` (không phân biệt hoa thường); cùng hàng = chồng dọc > 60% chiều cao nhỏ hơn; ≥ 3 hàng đã nối thì đánh dấu `ket_doan`.
- E5: 72 dpi xám; mực = trung vị − 50; hạt nhân cao ≥ 25pt ngoài dải mép 4% ngang / 3% dọc; gộp ≤ 20pt; nở ≤ 12pt trừ tâm trong dòng bảo vệ hoặc chạm dải mép 2% ngang; cắt mép tại dòng bảo vệ; bỏ vùng còn cao < 25pt.
- E6: bỏ dòng ≥ 50% diện tích trong vùng, trừ chú thích và văn xuôi ≥ 40 ký tự.
- E7: meta khoá `vung_hinh`, JSON `{"<page_no>": [[x0,y0,x1,y1], ...]}`, chỉ ghi khi có vùng.
- E8: ô cao `max(30, 0,5 · cao gốc) · s`, bề rộng gốc kẹp vào khung chữ; viền xám 0,5pt; chữ "ảnh" cỡ `than`; không vào `ghi_nhan`.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Không in nội dung sách vào log/ledger: chỉ số đếm và vị trí.

## Review Focus

1. **Trang scan chỉ có rác OCR trong hình** (sau E6 không còn dòng nào): trang phải không sinh khối, không làm vỡ `init`, và vùng hình vẫn được ghi meta để ô "ảnh" hiện ra. → test ở Task 5.
2. **Dòng chỉ có số ở đầu cột phải chỉ mục** (mục tiếp dòng): không được nối sang mục cột trái. → test ở Task 3.
3. **Hình không có nét cao** (trang toàn ô màu đều như test cũ `_anh`): không sinh vùng nào — các test Phase 7 dựng trang scan bằng ảnh một màu phải xanh nguyên. → Task 5 chạy lại toàn bộ `tests/test_pdf_ingest.py`.
4. **Ô "ảnh" trên trang không có khối chữ nào** (trang hình toàn phần): bộ dàn phải vẽ ô, không trả trang trắng. → test ở Task 6.
5. **Chế độ `overlay`** trên project có `vung_hinh`: không vẽ ô "ảnh" (ảnh gốc còn nguyên). → test ở Task 6.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `vung_hinh.py` (mới, thuần) | E5, E6: thành phần liên thông trên bytes xám, dòng bảo vệ, tìm vùng, lọc dòng |
| `pdf_layout.py` | E2 `tim_khe_hai_cot`; E3/E4 `noi_so_trang`, `Line.ket_doan`, tách đoạn sau `ket_doan` |
| `ingest/__init__.py` | `Ingested.meta` |
| `ingest/pdf_text.py` | E1; nối E2–E7 vào luồng trang scan; chụp ảnh xám |
| `cli.py` | `cmd_init` ghi `data.meta` vào bảng meta |
| `render/pdf_reflow.py` | E8: chèn và vẽ ô "ảnh" |
| `tests/test_vung_hinh.py` (mới) | test thuần E5/E6 |
| `tests/test_pdf_layout.py` | test thuần E2/E3/E4 |
| `tests/test_pdf_ingest.py` | test E1, E2, E5–E7 qua `ingest.load` / `init` |
| `tests/test_pdf_reflow.py`, `tests/test_export_pdf.py` | test E8 |

---

### Task 1: E1 — nhận dòng lệch dưới 10°

**Files:**
- Modify: `ingest/pdf_text.py` (`HUONG_NGANG`, `_doc_trang`)
- Test: `tests/test_pdf_ingest.py`

**Interfaces:**
- Consumes: không có.
- Produces: `pdf_text.GOC_NGHIENG_TOI_DA = 10.0`; `_doc_trang(page, page_no)` giữ chữ ký, nhận dòng lệch < 10°.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_pdf_ingest.py`:

```python
def _trang_co_dong_nghieng(tmp_path, goc):
    """Trang scan hơi nghiêng: OCR ghi dòng với dir lệch vài độ (đo thật trên
    harmonics: 462 dòng lệch < 10°, 16.969 ký tự, trước đây bị bỏ hết)."""
    doc = pymupdf.open()
    page = doc.new_page(width=522, height=666)
    for i in range(3):
        page.insert_text((67, 120 + i * 12), f"dong ngang {i} noi dung day du",
                         fontsize=10)
    goc_dong = pymupdf.Point(67, 300)
    page.insert_text(goc_dong, "dong nghieng van la chu that", fontsize=10,
                     morph=(goc_dong, pymupdf.Matrix(goc)))
    p = tmp_path / f"nghieng{goc}.pdf"
    doc.save(str(p)); doc.close()
    return " ".join(b.src_html for b in ingest.load(p).blocks)


def test_dong_lech_5_do_duoc_nhan(tmp_path):
    assert "dong nghieng van la chu that" in _trang_co_dong_nghieng(tmp_path, 5)


def test_dong_lech_15_do_van_bi_bo(tmp_path):
    """Nhãn xoay trong hình (đo thật: 276 dòng ≥ 10°) vẫn bỏ có kiểm soát."""
    assert "dong nghieng" not in _trang_co_dong_nghieng(tmp_path, 15)


def test_tien_de_dong_nghieng_that_su_co_dir_lech(tmp_path):
    """Nếu morph không làm dir lệch thì hai test trên xanh vô nghĩa."""
    doc = pymupdf.open()
    page = doc.new_page(width=522, height=666)
    g = pymupdf.Point(67, 300)
    page.insert_text(g, "abc", fontsize=10, morph=(g, pymupdf.Matrix(5)))
    dirs = [l["dir"] for b in page.get_text("dict")["blocks"]
            for l in b.get("lines", [])]
    assert dirs and abs(dirs[0][1]) > 0.05
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_ingest.py -q -k "lech or dir_lech"`
Expected: `test_dong_lech_5_do_duoc_nhan` FAIL (chữ nghiêng bị bỏ); hai test còn lại PASS.

- [ ] **Step 3: Viết code**

Trong `ingest/pdf_text.py`, thêm `import math` vào nhóm import chuẩn, thay khối:

```python
# Chữ xoay: bbox không phản ánh thứ tự đọc, trộn vào là vỡ mạch văn.
# dir=(1,0) là chữ nằm ngang bình thường.
HUONG_NGANG = (1.0, 0.0)
```

bằng:

```python
# Chữ xoay: bbox không phản ánh thứ tự đọc, trộn vào là vỡ mạch văn. Nhưng
# trang scan hơi nghiêng thì OCR ghi dòng lệch vài phần độ: đo thật trên sách
# scan 462 dòng lệch < 10° (16.969 ký tự; một trang mất trắng), còn ≥ 10° chỉ
# 1.164 ký tự — nhãn xoay trong hình. Người dùng chọn ngưỡng 10°.
GOC_NGHIENG_TOI_DA = 10.0


def _gan_ngang(huong) -> bool:
    dx, dy = huong
    return dx > 0 and abs(math.degrees(math.atan2(dy, dx))) < GOC_NGHIENG_TOI_DA
```

Trong `_doc_trang`, thay:

```python
            if tuple(round(v, 3) for v in l.get("dir", HUONG_NGANG)) != HUONG_NGANG:
                continue                          # chữ xoay: bỏ qua có kiểm soát
```

bằng:

```python
            if not _gan_ngang(l.get("dir", (1.0, 0.0))):
                continue                          # chữ xoay: bỏ qua có kiểm soát
```

Run: `grep -n "HUONG_NGANG" -r --include=*.py . | grep -v .venv` — Expected: không còn chỗ dùng. Nếu còn, thay bằng `_gan_ngang` và ghi `Ruling:`.

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_ingest.py -q`
Expected: tất cả PASS, kể cả `test_chu_xoay_bi_bo_qua_khong_tron_vao_mach_van` (90°).

- [ ] **Step 5: Chạy cả bộ, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `373 passed`.

```bash
git add ingest/pdf_text.py tests/test_pdf_ingest.py
git commit -m "fix: nhận dòng OCR lệch dưới 10 độ trên trang scan nghiêng

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: E2 — dò hai cột bằng bằng chứng từng hàng

**Files:**
- Modify: `pdf_layout.py` (thêm `tim_khe_hai_cot` và hằng số, ngay sau `detect_columns`)
- Modify: `ingest/pdf_text.py` (`load`, nhánh trang scan)
- Test: `tests/test_pdf_layout.py`, `tests/test_pdf_ingest.py`

**Interfaces:**
- Consumes: `pdf_layout.vung_than_bai(page_height)`, `pdf_layout.Line`.
- Produces: `pdf_layout.tim_khe_hai_cot(lines: list, page_width: float, page_height: float) -> float | None`; hằng `TOI_THIEU_DONG_HAI_COT = 12`, `LECH_HANG = 3.0`, `TI_LE_HANG_TACH = 0.6`, `VUNG_KHE = (0.3, 0.7)`, `BAC_QUA_TOI_DA = 2`, `TI_LE_BAC_QUA = 0.05`.

- [ ] **Step 1: Viết test thuần thất bại**

Thêm vào cuối `tests/test_pdf_layout.py`:

```python
# ---- tim_khe_hai_cot (Phase 8B, E2)

def _chi_muc(so_hang=15, co_bac_qua=True):
    """Trang chỉ mục 2 cột khổ 350x548 như harmonics: cột trái x 30-150,
    cột phải x 162-300, khe 12pt; OCR để một mảnh bắc qua khe."""
    ls = []
    for i in range(so_hang):
        y = 60 + i * 12
        ls.append(line(y, f"trai {i}", x0=30, x1=150))
        ls.append(line(y, f"phai {i}", x0=162, x1=300))
    if co_bac_qua:
        ls.append(line(60 + so_hang * 12, "manh bac qua", x0=120, x1=200))
    return ls


def test_chi_muc_hai_cot_co_manh_bac_qua_van_nhan_ra_khe():
    x = pdf_layout.tim_khe_hai_cot(_chi_muc(), 350, 548)
    assert x is not None and 150 <= x <= 162


def test_trang_ghi_chu_mot_cot_dong_ngan_khong_bi_chia():
    """Trang Ghi chú 374: một cột, dòng dài ngắn khác nhau. Nới detect_columns
    đã chia sai trang này (đảo thứ tự đọc)."""
    ls = [line(60 + i * 12, f"ghi chu {i}", x0=30, x1=120 + (i * 37) % 180)
          for i in range(20)]
    assert pdf_layout.tim_khe_hai_cot(ls, 350, 548) is None


def test_it_dong_qua_thi_khong_ket_luan():
    assert pdf_layout.tim_khe_hai_cot(_chi_muc(so_hang=5), 350, 548) is None


def test_qua_nhieu_dong_bac_qua_thi_khong_phai_khe():
    ls = _chi_muc()
    for i in range(4):
        ls.append(line(300 + i * 12, f"bac qua {i}", x0=100, x1=220))
    assert pdf_layout.tim_khe_hai_cot(ls, 350, 548) is None


def test_dong_o_le_khong_tinh():
    """Tiêu đề chạy ở lề trên bắc qua khe không được làm hỏng phép dò."""
    ls = _chi_muc() + [line(5, "TIEU DE CHAY", x0=30, x1=300)]
    assert pdf_layout.tim_khe_hai_cot(ls, 350, 548) is not None
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_layout.py -q -k "khe or ghi_chu or it_dong or bac_qua or o_le"`
Expected: FAIL — `AttributeError: module 'pdf_layout' has no attribute 'tim_khe_hai_cot'`.

- [ ] **Step 3: Viết `tim_khe_hai_cot`**

Thêm vào `pdf_layout.py` ngay sau hàm `detect_columns` (cần `import math` ở đầu file nếu chưa có):

```python
# Phase 8B E2: dò hai cột trên trang scan bằng bằng chứng từng hàng.
TOI_THIEU_DONG_HAI_COT = 12
LECH_HANG = 3.0
TI_LE_HANG_TACH = 0.6
VUNG_KHE = (0.3, 0.7)
BAC_QUA_TOI_DA = 2
TI_LE_BAC_QUA = 0.05


def _gom_hang(lines: list) -> list:
    hang = []
    for l in sorted(lines, key=lambda l: l.bbox[1]):
        if hang and abs(l.bbox[1] - hang[-1][0].bbox[1]) <= LECH_HANG:
            hang[-1].append(l)
        else:
            hang.append([l])
    return hang


def tim_khe_hai_cot(lines: list, page_width: float,
                    page_height: float = CHIEU_CAO_MAU) -> "float | None":
    """x của khe giữa hai cột, hoặc None. Chỉ dùng cho trang sách scan.

    detect_columns đòi khe mà KHÔNG dòng hẹp nào bắc qua; OCR chỉ mục để 1-2
    mảnh lấn khe nên cả trang thành một cột, rồi ghép mảnh nối mục cột trái
    với mục cột phải. Nới luật đó thì trang hình (mảnh rác giả làm cột) và
    trang Ghi chú một cột bị chia sai — đo thật: 10 trang. Bằng chứng đúng
    của hai cột là HÀNG: phần lớn hàng có chữ ở cả hai bên khe. Đo thật: 14/14
    trang chỉ mục; ngoài chỉ mục chỉ còn các bảng in nhiều cột.
    """
    tren, duoi = vung_than_bai(page_height)
    than = [l for l in lines if tren <= l.bbox[1] <= duoi]
    if len(than) < TOI_THIEU_DONG_HAI_COT:
        return None
    hang = _gom_hang(than)
    cho_phep = max(BAC_QUA_TOI_DA, math.ceil(TI_LE_BAC_QUA * len(than)))
    trai, phai = VUNG_KHE[0] * page_width, VUNG_KHE[1] * page_width

    tot = None
    for x in sorted({l.bbox[2] + 0.5 for l in than}):
        if not trai <= x <= phai:
            continue
        if sum(1 for l in than if l.bbox[0] < x < l.bbox[2]) > cho_phep:
            continue
        tach = sum(1 for h in hang
                   if any(l.bbox[2] <= x for l in h)
                   and any(l.bbox[0] >= x for l in h)
                   and not any(l.bbox[0] < x < l.bbox[2] for l in h))
        if tot is None or tach > tot[0]:
            tot = (tach, x)
    if tot is None or tot[0] < TI_LE_HANG_TACH * len(hang):
        return None
    return tot[1]
```

- [ ] **Step 4: Chạy test thuần, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_layout.py -q`
Expected: tất cả PASS.

- [ ] **Step 5: Viết test mức ingest thất bại**

Thêm vào cuối `tests/test_pdf_ingest.py`:

```python
def test_trang_scan_chi_muc_hai_cot_khong_bi_ghep_ngang(tmp_path):
    """Nghiệm thu 8A: 9 trang chỉ mục rơi dự phòng vì mục cột trái và mục cột
    phải cùng hàng bị ghép thành một khối rộng cả trang. Khe 12pt < 2x cỡ chữ
    nên ghép mảnh nối chúng; khe hẹp hơn 4% trang nên detect_columns không
    thấy; một mảnh bắc qua khe."""
    doc = pymupdf.open()
    _anh(doc, doc.new_page(width=522, height=666), 0, 0, 522, 666)
    page = doc[0]
    # Cột trái phải kết thúc trong 30-70% bề rộng trang (vùng dò khe), và khe
    # 12pt: hẹp hơn 2x cỡ chữ (ghép mảnh sẽ nối) và hẹp hơn 4% trang
    # (detect_columns không thấy) — đúng như chỉ mục harmonics.
    mau = "trai14 muc chi muc ben trai day"
    x_phai = 60 + pymupdf.get_text_length(mau, fontsize=10) + 12
    assert 0.3 * 522 < x_phai - 12 < 0.7 * 522, "dựng sai: khe ngoài vùng dò"
    for i in range(15):
        y = 120 + i * 12
        page.insert_text((60, y), f"trai{i} muc chi muc ben trai day", fontsize=10)
        page.insert_text((x_phai, y), f"phai{i} muc", fontsize=10)
    page.insert_text((x_phai - 40, 120 + 15 * 12), "manh bac qua khe giua",
                     fontsize=10)
    p = tmp_path / "chimuc.pdf"
    doc.save(str(p)); doc.close()
    for b in ingest.load(p).blocks:
        assert not ("trai" in b.src_html and "phai" in b.src_html), \
            "mục hai cột bị ghép thành một khối"
```

Chú ý dựng: nếu Step 6 PASS ngay (không tái hiện được lỗi ghép), in độ rộng khe thật và vị trí cột trong test, sửa phần dựng cho khe ≤ 20pt và nằm trong 30–70% bề rộng, ghi `Ruling:` — không sửa code sản phẩm để chiều test.

- [ ] **Step 6: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_ingest.py -q -k hai_cot`
Expected: FAIL — "mục hai cột bị ghép thành một khối".

- [ ] **Step 7: Nối vào `load`**

Trong `ingest/pdf_text.py` hàm `load`, thay:

```python
            pdf_layout.detect_columns(lines, doc[pno].rect.width)
            if _la_trang_scan(doc[pno]):
                cao_trang = doc[pno].rect.height
```

bằng:

```python
            pdf_layout.detect_columns(lines, doc[pno].rect.width)
            if _la_trang_scan(doc[pno]):
                cao_trang = doc[pno].rect.height
                if not any(l.col for l in lines):
                    # E2: chỉ mục OCR có mảnh lấn khe — detect_columns bỏ cuộc.
                    khe = pdf_layout.tim_khe_hai_cot(
                        lines, doc[pno].rect.width, cao_trang)
                    if khe is not None:
                        for l in lines:
                            l.col = 1 if l.bbox[0] >= khe else 0
```

- [ ] **Step 8: Chạy test, cả bộ, luật tầng, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `379 passed` (373 + 5 thuần + 1 ingest).

Run: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py render/dan_trang.py` — Expected: rỗng.

```bash
git add pdf_layout.py ingest/pdf_text.py tests/test_pdf_layout.py tests/test_pdf_ingest.py
git commit -m "feat: dò hai cột trang scan bằng bằng chứng từng hàng

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: E3/E4 — nối số trang vào hàng, mục lục mỗi hàng một đoạn

**Files:**
- Modify: `pdf_layout.py` (`Line.ket_doan`, `noi_so_trang`, `group_paragraphs`)
- Modify: `ingest/pdf_text.py` (`load`, sau `ghep_manh_cung_hang`)
- Test: `tests/test_pdf_layout.py`

**Interfaces:**
- Consumes: `pdf_layout._cung_hang(a, b)`, `pdf_layout._ghep_hai_dong(a, b)`, `vung_than_bai`.
- Produces: `Line.ket_doan: bool = False`; `pdf_layout.noi_so_trang(lines: list, page_height: float) -> list` (list Line mới; đánh `ket_doan=True` cho dòng đã nối khi trang có ≥ `TOI_THIEU_HANG_MUC_LUC = 3` hàng đã nối); `group_paragraphs` tách đoạn ngay sau dòng `ket_doan`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_pdf_layout.py`:

```python
# ---- noi_so_trang + ket_doan (Phase 8B, E3/E4)

def _hang_muc(y, ten, so, col_so=0):
    a = line(y, ten, x0=40, x1=200)
    b = line(y, so, x0=290, x1=305)
    b.col = col_so
    return [a, b]


def test_so_trang_cung_hang_duoc_noi_va_ket_doan():
    ls = (_hang_muc(100, "Chuong mot", "12") + _hang_muc(112, "Chuong hai", "34")
          + _hang_muc(124, "Chuong ba", "xii"))
    ra = pdf_layout.noi_so_trang(ls, 548)
    assert [l.text for l in ra] == ["Chuong mot 12", "Chuong hai 34", "Chuong ba xii"]
    assert all(l.ket_doan for l in ra)


def test_mot_hang_co_so_thi_noi_nhung_khong_tach_doan():
    """Thân bài có số lẻ loi: tách đoạn ở đó là cắt câu."""
    ls = [line(100, "cau van dai dong mot", x0=40, x1=200),
          line(100, "7", x0=290, x1=296),
          line(112, "cau van tiep theo", x0=40, x1=200)]
    ra = pdf_layout.noi_so_trang(ls, 548)
    assert ra[0].text == "cau van dai dong mot 7"
    assert not any(l.ket_doan for l in ra)


def test_so_trang_o_le_khong_bi_noi():
    ls = [line(5, "TIEU DE CHAY", x0=40, x1=200), line(5, "88", x0=290, x1=300)]
    ra = pdf_layout.noi_so_trang(ls, 548)
    assert [l.text for l in ra] == ["TIEU DE CHAY", "88"]


def test_so_dau_cot_phai_chi_muc_khong_noi_sang_cot_trai():
    """Review Focus 2: dòng chỉ có số ở đầu cột phải là phần tiếp của mục cột
    phải — cột phải có cả chữ, nên không được nối sang mục cột trái."""
    trai = [line(100 + 12 * i, f"muc trai {i}", x0=30, x1=150) for i in range(4)]
    phai = [line(100, "muc phai", x0=162, x1=260), line(112, "437", x0=162, x1=180)]
    for l in phai:
        l.col = 1
    ra = pdf_layout.noi_so_trang(trai + phai, 548)
    assert "muc trai 1" in [l.text for l in ra], "số cột phải bị nối sang cột trái"


def test_cot_toan_so_trang_duoc_noi_sang_cot_trai():
    """Mục lục: detect_columns tách số trang thành cột 1 toàn số."""
    ls = (_hang_muc(100, "Chuong mot", "12", col_so=1)
          + _hang_muc(112, "Chuong hai", "34", col_so=1)
          + _hang_muc(124, "Chuong ba", "56", col_so=1))
    ra = pdf_layout.noi_so_trang(ls, 548)
    assert [l.text for l in ra] == ["Chuong mot 12", "Chuong hai 34", "Chuong ba 56"]


def test_tach_doan_sau_dong_ket_doan():
    """Mục dài hai dòng (số ở dòng thứ hai) vẫn là một khối."""
    a1 = line(100, "Muc dai dong mot", x0=40, x1=250)
    a2 = line(112, "dong hai 307", x0=40, x1=250)
    b1 = line(124, "Muc ke tiep 335", x0=40, x1=250)
    a2.ket_doan = True
    b1.ket_doan = True
    doan = pdf_layout.group_paragraphs([a1, a2, b1])
    assert [len(d.lines) for d in doan] == [2, 1]
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_layout.py -q -k "so_trang or so_dau or cot_toan or ket_doan or mot_hang"`
Expected: FAIL — `noi_so_trang` chưa có; `test_tach_doan_sau_dong_ket_doan` FAIL vì gom thành 1 đoạn 3 dòng (gán thuộc tính lạ vào dataclass vẫn chạy được).

- [ ] **Step 3: Viết code**

Trong `pdf_layout.py`:

1. Thêm trường cuối `Line`:

```python
    ket_doan: bool = False      # 8B E4: dòng cuối một mục lục/chỉ mục
```

2. Trong `group_paragraphs`, thay:

```python
        if doi_trang or xa_qua or thut_vao:
```

bằng:

```python
        if doi_trang or xa_qua or thut_vao or truoc.ket_doan:
```

3. Thêm sau `ghep_manh_cung_hang`:

```python
# Phase 8B E3/E4: số trang của mục lục/chỉ mục nằm tách khỏi hàng chữ của nó.
_SO_TRANG = re.compile(r"^(\d{1,3}|[ivxlc]{1,6})$", re.IGNORECASE)
TOI_THIEU_HANG_MUC_LUC = 3


def noi_so_trang(lines: list, page_height: float = CHIEU_CAO_MAU) -> list:
    """Nối mảnh chỉ có số trang vào dòng chữ cùng hàng bên trái nó.

    Chỉ dùng cho trang sách scan, SAU ghép mảnh. Đo thật: mục lục sách scan có
    21 mảnh số trang nằm tách thành cột riêng; dịch ra thì số trang lạc khỏi
    mục. Chỉ nối trong cùng cột — trừ khi cột của mảnh số chỉ toàn mảnh số
    (cột số trang mục lục). Trang có từ TOI_THIEU_HANG_MUC_LUC hàng đã nối là
    mục lục/chỉ mục: mỗi dòng đã nối là cuối một đoạn. Ít hơn thì chỉ nối —
    thân bài có số lẻ loi, tách đoạn ở đó là cắt câu. Trả về list Line mới.
    """
    tren, duoi = vung_than_bai(page_height)

    def o_than(l):
        return tren <= l.bbox[1] <= duoi

    def la_so(l):
        return bool(_SO_TRANG.match(l.text.strip()))

    cot_toan_so = {c for c in {l.col for l in lines}
                   if all(la_so(l) for l in lines if l.col == c)}
    out = list(lines)
    da_noi = []
    for s in sorted([l for l in lines if o_than(l) and la_so(l)],
                    key=lambda l: (l.bbox[1], l.bbox[0])):
        ban = [m for m in out if m is not s and o_than(m) and not la_so(m)
               and (m.col == s.col or s.col in cot_toan_so)
               and m.bbox[2] <= s.bbox[0] + 1 and _cung_hang(m, s)]
        if not ban:
            continue
        m = max(ban, key=lambda m: m.bbox[2])
        moi = _ghep_hai_dong(m, s)
        # So theo danh tính: Line là dataclass nên == so từng trường, hai dòng
        # trùng chữ và khung (rác OCR lặp) sẽ bị index/remove nhầm.
        out = [moi if x is m else x for x in out if x is not s]
        da_noi = [x for x in da_noi if x is not m] + [moi]
    if len(da_noi) >= TOI_THIEU_HANG_MUC_LUC:
        for l in da_noi:
            l.ket_doan = True
    return out
```

Ghi chú: `_ghep_hai_dong` dựng `Line` mới với `ket_doan` mặc định `False` — đúng ý (cờ chỉ đặt sau khi đếm đủ hàng). Dòng `m` đã nối một lần rồi lại có số thứ hai cùng hàng (chỉ mục "Einstein, 215 247") vẫn được nối tiếp vì `out` đã chứa `moi`; `da_noi` thay `m` cũ bằng `moi` để không đếm trùng hàng.

4. Trong `ingest/pdf_text.py` `load`, thay:

```python
                lines = pdf_layout.ghep_manh_cung_hang(lines, page_height=cao_trang)
```

bằng:

```python
                lines = pdf_layout.ghep_manh_cung_hang(lines, page_height=cao_trang)
                lines = pdf_layout.noi_so_trang(lines, page_height=cao_trang)
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_layout.py tests/test_pdf_ingest.py -q`
Expected: tất cả PASS.

- [ ] **Step 5: Chạy cả bộ, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `385 passed`. Vân tay golden xanh (text-PDF không đi qua `noi_so_trang`; `ket_doan` mặc định False).

```bash
git add pdf_layout.py ingest/pdf_text.py tests/test_pdf_layout.py
git commit -m "feat: nối số trang vào hàng, mục lục mỗi hàng một đoạn trên trang scan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: E5/E6 — module thuần `vung_hinh.py`

**Files:**
- Create: `vung_hinh.py`
- Create: `tests/test_vung_hinh.py`

**Interfaces:**
- Consumes: không có.
- Produces:
  - hằng `NGUONG_MUC = 50`, `CAO_HAT = 25.0`, `GOP_HAT = 20.0`, `SAT = 12.0`, `MEP_NGANG = 0.04`, `MEP_DOC = 0.03`, `MEP_NUOT = 0.02`, `TI_LE_TRONG = 0.5`, `VAN_XUOI_GIU = 40`
  - `thanh_phan(xam: bytes, rong: int, cao: int, ti_le: float) -> list[tuple]` — khung (x0, y0, x1, y1) theo point của mọi thành phần mực liên thông 4 hướng
  - `la_chu_thich(text: str) -> bool`, `la_van_xuoi(text: str) -> bool`
  - `dong_bao_ve(dong: list[tuple[tuple, str]]) -> list[tuple]` — khung các dòng được bảo vệ
  - `tim_vung(tp: list, dong: list, rong_trang: float, cao_trang: float) -> list[tuple]`
  - `loc_dong_trong_hinh(dong: list, vung: list) -> list[bool]` — True = giữ

- [ ] **Step 1: Viết test thất bại**

`tests/test_vung_hinh.py`:

```python
"""Dò vùng hình trên ảnh xám trang scan. Hàm thuần: không PDF, không mạng."""
import vung_hinh as vh

NEN, MUC = 208, 60


def anh(rong=200, cao=300):
    return bytearray([NEN]) * (rong * cao), rong, cao


def ve(buf, rong, x0, y0, x1, y1, v=MUC):
    for y in range(y0, y1):
        for x in range(x0, x1):
            buf[y * rong + x] = v


def tp_cua(buf, rong, cao):
    return vh.thanh_phan(bytes(buf), rong, cao, 1.0)


# ---- thanh_phan

def test_thanh_phan_tach_rieng_hai_net():
    buf, r, c = anh()
    ve(buf, r, 50, 50, 52, 120)
    ve(buf, r, 100, 50, 108, 58)
    k = sorted(tp_cua(buf, r, c))
    assert k == [(50, 50, 52, 120), (100, 50, 108, 58)]


def test_thanh_phan_nguong_theo_nen():
    """Mực nhạt hơn nền dưới 50 mức thì không tính (giấy ố, vết bẩn)."""
    buf, r, c = anh()
    ve(buf, r, 50, 50, 52, 120, v=NEN - 30)
    assert tp_cua(buf, r, c) == []


# ---- la_chu_thich / la_van_xuoi

def test_la_chu_thich():
    assert vh.la_chu_thich("Figure 3.8 Various factors")
    assert vh.la_chu_thich("Fig. 2 the chart")
    assert not vh.la_chu_thich("The Figure shows")


def test_la_van_xuoi():
    assert vh.la_van_xuoi("the San Diego air crash.")          # 3+ từ
    assert vh.la_van_xuoi("abcdefghij klmnopqrstu vwxyzabcd")  # >= 25 ký tự
    assert not vh.la_van_xuoi("K Ores")
    assert not vh.la_van_xuoi("SA/MC 0 = 2")


def test_dong_tiep_cua_chu_thich_cung_duoc_bao_ve():
    dong = [((20, 200, 180, 210), "Figure 1.1 A chart"),
            ((20, 211, 90, 221), "of a crash")]
    assert len(vh.dong_bao_ve(dong)) == 2


# ---- tim_vung

def test_net_cao_thanh_mot_vung():
    buf, r, c = anh()
    ve(buf, r, 90, 60, 92, 140)                 # nét dọc cao 80pt
    v = vh.tim_vung(tp_cua(buf, r, c), [], r, c)
    assert v == [(90, 60, 92, 140)]


def test_chi_co_chu_nho_khong_ra_vung():
    buf, r, c = anh()
    for i in range(10):
        ve(buf, r, 20 + i * 12, 100, 28 + i * 12, 108)
    assert vh.tim_vung(tp_cua(buf, r, c), [], r, c) == []


def test_bong_gay_o_mep_bi_bo():
    buf, r, c = anh()
    ve(buf, r, 2, 40, 5, 260)                   # mép trái, trong dải 4%
    assert vh.tim_vung(tp_cua(buf, r, c), [], r, c) == []


def test_vung_nuot_ky_hieu_gan():
    buf, r, c = anh()
    ve(buf, r, 90, 60, 92, 140)
    ve(buf, r, 100, 45, 106, 52)                # ký hiệu cách 8pt
    v = vh.tim_vung(tp_cua(buf, r, c), [], r, c)
    assert v == [(90, 45, 106, 140)]


def test_khong_nuot_chu_trong_dong_bao_ve():
    buf, r, c = anh()
    ve(buf, r, 90, 60, 92, 140)
    ve(buf, r, 100, 145, 106, 151)              # chữ của một dòng văn xuôi
    dong = [((95, 143, 190, 153), "the prose line right below")]
    v = vh.tim_vung(tp_cua(buf, r, c), dong, r, c)
    assert v == [(90, 60, 92, 140)]


def test_cat_mep_tai_chu_thich_cham_vung():
    buf, r, c = anh()
    ve(buf, r, 60, 60, 62, 160)
    dong = [((40, 150, 180, 160), "Figure 2.4 Here both the Moon")]
    v = vh.tim_vung(tp_cua(buf, r, c), dong, r, c)
    assert len(v) == 1 and v[0][3] <= 150


def test_hai_hat_xa_nhau_la_hai_vung():
    buf, r, c = anh()
    ve(buf, r, 30, 40, 32, 90)
    ve(buf, r, 150, 200, 152, 260)
    assert len(vh.tim_vung(tp_cua(buf, r, c), [], r, c)) == 2


# ---- loc_dong_trong_hinh

def test_loc_bo_rac_giu_chu_thich_va_van_xuoi_dai():
    vung = [(50, 50, 150, 150)]
    dong = [((60, 60, 90, 70), "K Ores"),
            ((60, 80, 140, 90), "Figure 1.2 inside"),
            ((55, 100, 149, 110), "a real sentence of prose that is long enough"),
            ((10, 200, 180, 210), "outside the figure")]
    assert vh.loc_dong_trong_hinh(dong, vung) == [False, True, True, True]


def test_loc_khong_co_vung_thi_giu_het():
    dong = [((60, 60, 90, 70), "K Ores")]
    assert vh.loc_dong_trong_hinh(dong, []) == [True]
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_vung_hinh.py -q`
Expected: ERROR — `ModuleNotFoundError: No module named 'vung_hinh'`.

- [ ] **Step 3: Viết `vung_hinh.py`**

```python
"""Dò vùng hình vẽ trên ảnh trang sách scan. Hàm thuần: không PyMuPDF.

Trên trang scan, OCR đọc nét vẽ và ký hiệu của hình thành chữ rác ("K Ores"
cỡ tiêu đề). Hình có một dấu hiệu chữ không có: nét mực liền cao hơn nhiều
dòng chữ (đường kẻ, vòng tròn, bản đồ). Từ các nét đó, vùng nở ra nuốt ký
hiệu và nhãn nhỏ quanh hình, nhưng không bao giờ nuốt chú thích hay văn xuôi.

Đo thật trên sách scan 484 trang: 153 trang có vùng; 0 chú thích và 0 dòng văn
xuôi bị nuốt; bỏ 303 dòng rác (trung bình 4 ký tự). Hình chỉ gồm ký hiệu
không có nét vẽ thì không nhận được — chấp nhận có ý thức.

Spec: docs/superpowers/specs/2026-09-24-doc-sach-scan-design.md (E5, E6).
"""
import re

NGUONG_MUC = 50          # mực = tối hơn trung vị (nền giấy) ngần này mức xám
CAO_HAT = 25.0           # nét cao từ ngần này point là hạt nhân hình
GOP_HAT = 20.0           # hạt nhân cách nhau ngần này thì cùng một hình
SAT = 12.0               # vùng nuốt thành phần mực trong ngần này point
MEP_NGANG = 0.04         # hạt nhân trong dải mép này là bóng gáy sách
MEP_DOC = 0.03
MEP_NUOT = 0.02          # không nuốt thành phần chạm dải mép này
TI_LE_TRONG = 0.5        # dòng có ngần này diện tích trong vùng là của hình
VAN_XUOI_GIU = 40        # văn xuôi dài ngần này ký tự luôn giữ

_CHU_THICH = re.compile(r"^\s*(Figure|Fig\.)\s+\d+", re.IGNORECASE)


def thanh_phan(xam: bytes, rong: int, cao: int, ti_le: float) -> list:
    """Khung (point) của mọi thành phần mực liên thông 4 hướng.

    `ti_le` là số point trên một pixel. Ngưỡng mực tính theo trung vị độ xám
    (nền giấy) chứ không cố định: giấy ố mỗi trang một màu.
    """
    n = rong * cao
    mau = sorted(xam[::7])
    nguong = mau[len(mau) // 2] - NGUONG_MUC
    da_xet = bytearray(n)
    out = []
    for i in range(n):
        if xam[i] >= nguong or da_xet[i]:
            continue
        ngan = [i]
        da_xet[i] = 1
        x0 = x1 = i % rong
        y0 = y1 = i // rong
        while ngan:
            j = ngan.pop()
            x, y = j % rong, j // rong
            if x < x0: x0 = x
            if x > x1: x1 = x
            if y < y0: y0 = y
            if y > y1: y1 = y
            for k in (j - 1, j + 1, j - rong, j + rong):
                if 0 <= k < n and not da_xet[k] and xam[k] < nguong \
                        and abs(k % rong - x) <= 1:
                    da_xet[k] = 1
                    ngan.append(k)
        out.append((x0 * ti_le, y0 * ti_le, (x1 + 1) * ti_le, (y1 + 1) * ti_le))
    return out


def la_chu_thich(text: str) -> bool:
    return bool(_CHU_THICH.match(text))


def la_van_xuoi(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    tu = [w for w in t.split() if sum(c.isalpha() for c in w) >= 2]
    chu = sum(c.isalpha() or c == " " for c in t) / len(t)
    return chu >= 0.8 and (len(t) >= 25 or len(tu) >= 3)


def _gan(a, b, d) -> bool:
    return (a[0] - d <= b[2] and b[0] - d <= a[2]
            and a[1] - d <= b[3] and b[1] - d <= a[3])


def _hop(a, b) -> tuple:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _trong(l, r) -> float:
    """Tỉ lệ diện tích khung l nằm trong khung r."""
    x0, y0 = max(l[0], r[0]), max(l[1], r[1])
    x1, y1 = min(l[2], r[2]), min(l[3], r[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0) / max(1e-6, (l[2] - l[0]) * (l[3] - l[1]))


def dong_bao_ve(dong: list) -> list:
    """Khung các dòng vùng hình không được nuốt: văn xuôi, chú thích, và các
    dòng tiếp của chú thích (dòng cuối chú thích thường ngắn, không đủ dài để
    là 'văn xuôi' — đo thật: thiếu luật này là 13 chú thích lọt vào vùng)."""
    bao_ve = [k for k, t in dong if la_van_xuoi(t) or la_chu_thich(t)]
    chu_thich = [k for k, t in dong if la_chu_thich(t)]
    doi = True
    while doi:
        doi = False
        for k, _ in dong:
            if k in chu_thich:
                continue
            if any(0 <= k[1] - c[3] <= 0.8 * (c[3] - c[1])
                   and k[0] < c[2] and c[0] < k[2] for c in chu_thich):
                chu_thich.append(k)
                if k not in bao_ve:
                    bao_ve.append(k)
                doi = True
    return bao_ve


def tim_vung(tp: list, dong: list, rong_trang: float, cao_trang: float) -> list:
    """Vùng hình trên một trang: list khung (x0, y0, x1, y1) theo point.

    `tp` là kết quả thanh_phan; `dong` là list (khung, chữ) của dòng OCR.
    """
    bao_ve = dong_bao_ve(dong)
    hat = [c for c in tp
           if c[3] - c[1] >= CAO_HAT
           and c[0] > MEP_NGANG * rong_trang and c[2] < (1 - MEP_NGANG) * rong_trang
           and c[1] > MEP_DOC * cao_trang and c[3] < (1 - MEP_DOC) * cao_trang]
    vung = []
    for c in hat:
        for i, v in enumerate(vung):
            if _gan(v, c, GOP_HAT):
                vung[i] = _hop(v, c)
                break
        else:
            vung.append(c)

    def duoc_nuot(c) -> bool:
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        if any(l[0] <= cx <= l[2] and l[1] <= cy <= l[3] for l in bao_ve):
            return False
        return (c[0] >= MEP_NUOT * rong_trang
                and c[2] <= (1 - MEP_NUOT) * rong_trang)

    doi = True
    while doi:
        doi = False
        for i in range(len(vung)):
            for c in tp:
                v = vung[i]
                if c[0] >= v[0] and c[1] >= v[1] and c[2] <= v[2] and c[3] <= v[3]:
                    continue
                if _gan(v, c, SAT) and duoc_nuot(c):
                    vung[i] = _hop(v, c)
                    doi = True

    # Cắt mép tại dòng được bảo vệ chạm vùng: một nét hình chồng lên dòng chú
    # thích ngay dưới hình kéo mép vùng xuống quá dòng đó.
    ra = []
    for x0, y0, x1, y1 in vung:
        for l in bao_ve:
            if l[0] >= x1 or l[2] <= x0 or _trong(l, (x0, y0, x1, y1)) <= 0:
                continue
            if (l[1] + l[3]) / 2 > (y0 + y1) / 2:
                y1 = min(y1, l[1] - 0.5)
            else:
                y0 = max(y0, l[3] + 0.5)
        if y1 - y0 >= CAO_HAT:
            ra.append((x0, y0, x1, y1))
    return ra


def loc_dong_trong_hinh(dong: list, vung: list) -> list:
    """True = giữ dòng. Dòng nằm phần lớn trong vùng hình là rác OCR của hình,
    trừ chú thích và văn xuôi dài (luôn giữ)."""
    giu = []
    for k, t in dong:
        trong = max((_trong(k, v) for v in vung), default=0.0)
        if trong < TI_LE_TRONG:
            giu.append(True)
        else:
            giu.append(la_chu_thich(t)
                       or (la_van_xuoi(t) and len(t.strip()) >= VAN_XUOI_GIU))
    return giu
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_vung_hinh.py -q`
Expected: tất cả PASS (14 test).

Nếu `test_vung_nuot_ky_hieu_gan` hoặc `test_khong_nuot_chu_trong_dong_bao_ve` lệch vài point vì cách tính khung (x1+1): kiểm lại con số kỳ vọng bằng tay theo công thức `(x1 + 1) * ti_le` rồi sửa KỲ VỌNG của test cho khớp công thức, ghi `Ruling:` — không đổi luật.

- [ ] **Step 5: Luật tầng, cả bộ, commit**

Run: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py render/dan_trang.py vung_hinh.py` — Expected: rỗng.

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `399 passed`.

```bash
git add vung_hinh.py tests/test_vung_hinh.py
git commit -m "feat: vung_hinh — dò vùng hình vẽ trên ảnh xám trang scan, hàm thuần

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Nối E5/E6/E7 vào `init`

**Files:**
- Modify: `ingest/__init__.py` (`Ingested.meta`)
- Modify: `ingest/pdf_text.py` (`load`: chụp xám, tìm vùng, lọc dòng, trả meta)
- Modify: `cli.py` (`cmd_init` ghi meta)
- Test: `tests/test_pdf_ingest.py`

**Interfaces:**
- Consumes: `vung_hinh.thanh_phan`, `vung_hinh.tim_vung`, `vung_hinh.loc_dong_trong_hinh` (Task 4).
- Produces: `Ingested.meta: dict` (mặc định `{}`); với PDF có hình: `meta["vung_hinh"] = {"<page_no>": [[x0,y0,x1,y1], ...]}` (số làm tròn 1 chữ số); `init` ghi `db.set_meta(con, "vung_hinh", json.dumps(...))`; `pdf_text.DPI_DO_HINH = 72`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_pdf_ingest.py`:

```python
import json

import db
from helpers import run_init


def trang_scan_gia(path, ve_hinh=True, rac=True):
    """Trang scan giả: vẽ hình lên trang nháp, chụp thành ảnh phủ kín trang
    mới, rồi đặt lớp chữ OCR VÔ HÌNH đè lên — như sách scan thật (ảnh mang
    cả chữ lẫn hình, lớp OCR chỉ để trích chữ)."""
    nhap = pymupdf.open()
    p = nhap.new_page(width=350, height=548)
    if ve_hinh:
        p.draw_circle((175, 250), 70, color=(0, 0, 0), width=1.5)
    pix = p.get_pixmap(dpi=72)
    doc = pymupdf.open()
    page = doc.new_page(width=350, height=548)
    page.insert_image(page.rect, pixmap=pix)
    o = dict(fontsize=10, render_mode=3)
    for i in range(4):
        page.insert_text((30, 80 + i * 12),
                         f"prose line {i} above the figure keeps going on", **o)
    if rac:
        page.insert_text((150, 245), "K Ores", **o)
    page.insert_text((30, 340), "Figure 1.1 A circle chart used for testing.", **o)
    page.insert_text((30, 352), "the caption goes on", **o)
    for i in range(3):
        page.insert_text((30, 380 + i * 12),
                         f"prose line {i} below the figure keeps going on", **o)
    doc.save(str(path)); doc.close(); nhap.close()
    return path


def test_rac_trong_hinh_bi_bo_chu_thich_va_van_xuoi_giu(tmp_path):
    kq = ingest.load(trang_scan_gia(tmp_path / "hinh.pdf"))
    chu = " ".join(b.src_html for b in kq.blocks)
    assert "K Ores" not in chu
    assert "Figure 1.1" in chu and "the caption goes on" in chu
    assert "prose line 3 above" in chu and "prose line 0 below" in chu


def test_vung_hinh_nam_trong_meta(tmp_path):
    kq = ingest.load(trang_scan_gia(tmp_path / "hinh.pdf"))
    vung = kq.meta["vung_hinh"]["0"]
    assert len(vung) == 1
    x0, y0, x1, y1 = vung[0]
    assert x0 <= 110 and x1 >= 240 and y0 <= 185 and y1 >= 315
    assert y1 < 340 - 6, "chú thích ngay dưới hình không được nằm trong vùng"


def test_trang_scan_khong_hinh_khong_co_meta(tmp_path):
    kq = ingest.load(trang_scan_gia(tmp_path / "chu.pdf", ve_hinh=False))
    assert "vung_hinh" not in kq.meta
    assert "K Ores" in " ".join(b.src_html for b in kq.blocks)


def test_trang_chi_co_hinh_va_rac_khong_lam_vo(tmp_path):
    """Review Focus 1: sau khi lọc rác không còn dòng nào — trang không sinh
    khối, init không vỡ, vùng hình vẫn vào meta."""
    nhap = pymupdf.open()
    p = nhap.new_page(width=350, height=548)
    p.draw_circle((175, 250), 70, color=(0, 0, 0), width=1.5)
    pix = p.get_pixmap(dpi=72)
    doc = pymupdf.open()
    for i in range(2):
        doc.new_page(width=350, height=548)
    doc[0].insert_image(doc[0].rect, pixmap=pix)
    doc[0].insert_text((150, 245), "K Ores", fontsize=10, render_mode=3)
    doc[1].insert_image(doc[1].rect, pixmap=pix)
    for i in range(4):
        doc[1].insert_text((30, 80 + i * 12),
                           f"prose line {i} on the second page here", fontsize=10,
                           render_mode=3)
    f = tmp_path / "chihinh.pdf"
    doc.save(str(f)); doc.close(); nhap.close()
    kq = ingest.load(f)
    assert {b.page_no for b in kq.blocks} == {1}
    assert "0" in kq.meta["vung_hinh"]


def test_init_ghi_vung_hinh_vao_db(tmp_path):
    proj = run_init(trang_scan_gia(tmp_path / "hinh.pdf"), tmp_path / "proj")
    con = db.connect(proj)
    assert json.loads(db.get_meta(con, "vung_hinh"))["0"]


def test_text_pdf_khong_co_khoa_vung_hinh(tmp_path):
    from helpers import build_pdf, trang_mot_doan
    src = build_pdf(tmp_path / "t.pdf", [trang_mot_doan(120, 4)])
    proj = run_init(src, tmp_path / "proj")
    assert db.get_meta(db.connect(proj), "vung_hinh") is None
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_ingest.py -q -k "hinh or rac"`
Expected: FAIL — `AttributeError: 'Ingested' object has no attribute 'meta'` và `K Ores` còn trong khối. `test_text_pdf_khong_co_khoa_vung_hinh` PASS (đó là tiền đề giữ nguyên).

- [ ] **Step 3: Viết code**

1. `ingest/__init__.py`: đổi import `from dataclasses import dataclass` thành `from dataclasses import dataclass, field`, và `Ingested` thành:

```python
@dataclass
class Ingested:
    fmt: str
    source_name: str
    blocks: list
    # Dữ liệu cấp project ngoài khối, ghi vào bảng meta khi init. PDF scan:
    # {"vung_hinh": {"<page_no>": [[x0,y0,x1,y1], ...]}} (spec 8B E7).
    meta: dict = field(default_factory=dict)
```

2. `ingest/pdf_text.py`: thêm `import vung_hinh` sau `import pdf_layout`; thêm sau `_la_trang_scan`:

```python
# E5: độ phân giải chụp trang để dò hình. Đo thật: 40 dpi làm nét mảnh nhoè
# thành xám và không bắt được hình nào; 72 dpi bắt 147/171 trang có chú thích.
DPI_DO_HINH = 72


def _vung_hinh_trang(page, lines) -> list:
    pix = page.get_pixmap(dpi=DPI_DO_HINH, colorspace=pymupdf.csGRAY,
                          alpha=False)
    tp = vung_hinh.thanh_phan(pix.samples, pix.width, pix.height,
                              page.rect.width / pix.width)
    return vung_hinh.tim_vung(tp, [(l.bbox, l.text) for l in lines],
                              page.rect.width, page.rect.height)
```

Trong `load`, thay đầu vòng lặp:

```python
        paras = []
        for pno in range(doc.page_count):
            lines = _doc_trang(doc[pno], pno)
            if not lines:
                continue                          # trang trắng hoặc toàn ảnh
            pdf_layout.detect_columns(lines, doc[pno].rect.width)
            if _la_trang_scan(doc[pno]):
```

bằng:

```python
        paras = []
        hinh = {}
        for pno in range(doc.page_count):
            lines = _doc_trang(doc[pno], pno)
            if not lines:
                continue                          # trang trắng hoặc toàn ảnh
            la_scan = _la_trang_scan(doc[pno])
            if la_scan:
                # E5/E6: bỏ rác OCR của hình TRƯỚC dò cột và ghép mảnh — mảnh
                # rác quanh hình giả làm cột và dính vào dòng thật.
                vung = _vung_hinh_trang(doc[pno], lines)
                if vung:
                    hinh[str(pno)] = [[round(v, 1) for v in k] for k in vung]
                    giu = vung_hinh.loc_dong_trong_hinh(
                        [(l.bbox, l.text) for l in lines], vung)
                    lines = [l for l, g in zip(lines, giu) if g]
                    if not lines:
                        continue
            pdf_layout.detect_columns(lines, doc[pno].rect.width)
            if la_scan:
```

Và cuối hàm, thay `return Ingested(fmt="pdf", source_name=path.name, blocks=blocks)` bằng:

```python
    meta = {"vung_hinh": hinh} if hinh else {}
    return Ingested(fmt="pdf", source_name=path.name, blocks=blocks, meta=meta)
```

(`hinh` được tạo trong khối `try`; nếu `load` ném lỗi trước đó thì không tới dòng return.)

3. `cli.py` `cmd_init`: sau dòng `db.set_meta(con, "chunk_chars", args.chunk_chars)` thêm:

```python
    for khoa, gia_tri in data.meta.items():
        db.set_meta(con, khoa, json.dumps(gia_tri))
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_ingest.py -q`
Expected: tất cả PASS — kể cả các test Phase 7 dựng trang scan bằng ảnh một màu (Review Focus 3: không có nét nào nên không có vùng).

Nếu `test_vung_hinh_nam_trong_meta` lệch biên (vòng tròn chụp 72 dpi có khung 104-246 × 179-321 cộng nét): kiểm con số thật bằng một dòng `print` tạm, sửa KỲ VỌNG cho khớp hình đã vẽ, ghi `Ruling:`.

- [ ] **Step 5: Cả bộ, luật tầng, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `405 passed`; vân tay golden xanh.

Run: `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py chunking.py glossary.py render/dan_trang.py vung_hinh.py` — Expected: rỗng.

```bash
git add ingest/__init__.py ingest/pdf_text.py cli.py tests/test_pdf_ingest.py
git commit -m "feat: init dò vùng hình trang scan, bỏ rác OCR trong hình, ghi meta vung_hinh

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: E8 — ô "ảnh" khi xuất `reflow`

**Files:**
- Modify: `render/pdf_reflow.py`
- Test: `tests/test_pdf_reflow.py`, `tests/test_export_pdf.py`

**Interfaces:**
- Consumes: `dan_trang.xep_doc`, `dan_trang.khung_ngang`, `dan_trang.LE` (8A); meta `vung_hinh` (Task 5); `db.get_meta`.
- Produces:
  - `pdf_reflow.CAO_O_TOI_THIEU = 30.0`, `TI_LE_O_ANH = 0.5`, `NHAN_ANH = "ảnh"`
  - `pdf_reflow.chen_hinh(khoi: list, vung: list) -> list` — trả list mới có thêm `{"id": None, "kind": "hinh", "bbox": Rect, "html": "", "src": "", "size": 0.0}` đặt trước khối đầu tiên có `bbox.y0 > y0` của vùng
  - `pdf_reflow._ve_o_anh(page, rect, kho, co)`
  - `trang_theo_vi_tri(..., *, than: float = 9.0)` (thêm tham số từ khoá)

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_pdf_reflow.py`:

```python
# ------------------------------------------------ ô "ảnh" (spec 8B E8)

def o_hinh(x0, y0, x1, y1):
    return {"id": None, "kind": "hinh", "bbox": pymupdf.Rect(x0, y0, x1, y1),
            "html": "", "src": "", "size": 0.0}


def khung_o(page):
    """Các hình chữ nhật đã vẽ (viền ô 'ảnh')."""
    return [d["rect"] for d in page.get_drawings() if d.get("rect") is not None]


def test_chen_hinh_theo_do_cao():
    ds = [khoi(30, 50, 300, 80, "A", id_=1), khoi(30, 300, 300, 330, "B", id_=2)]
    ra = pdf_reflow.chen_hinh(ds, [(40, 100, 290, 280)])
    assert [k["kind"] if k["kind"] == "hinh" else k["html"] for k in ra] == \
        ["A", "hinh", "B"]


def test_dan_ve_o_anh_cao_mot_nua_goc():
    ghi = []
    d = dan([o_hinh(40, 100, 290, 300)], ghi=ghi)
    assert "ảnh" in chu(d[0])
    o = khung_o(d[0])
    assert o and abs(o[0].height - 100) < 1.5, [r.height for r in o]
    assert ghi == [], "ô ảnh không được vào thống kê"


def test_o_anh_nho_van_cao_toi_thieu_30():
    d = dan([o_hinh(40, 100, 290, 140)])
    assert abs(khung_o(d[0])[0].height - 30) < 1.5


def test_o_anh_khong_de_chu():
    d = dan([khoi(30, 60, 310, 110, "Moc0x " + "chữ Việt " * 30, id_=1),
             o_hinh(40, 90, 290, 290),
             khoi(30, 280, 310, 320, "Moc1x " + "chữ Việt " * 30, id_=2)])
    o = khung_o(d[0])[0]
    for w in d[0].get_text("words"):
        if w[4] == "ảnh":
            continue
        r = pymupdf.Rect(w[:4])
        assert not r.intersects(o + (0.5, 0.5, -0.5, -0.5)), f"chữ đè ô ảnh: {r} / {o}"


def test_trang_chi_co_hinh_van_ve_o():
    """Review Focus 4: trang hình toàn phần — không có khối chữ nào."""
    d = dan([o_hinh(40, 100, 290, 300)])
    assert khung_o(d[0])


def test_du_phong_ve_o_dung_khung_goc():
    d = pdf_reflow.trang_theo_vi_tri(trang_scan(), 0, [o_hinh(40, 100, 290, 300)])
    o = khung_o(d[0])
    assert o and abs(o[0].y0 - 100) < 1 and abs(o[0].height - 200) < 1
    assert "ảnh" in chu(d[0])
```

Thêm vào cuối `tests/test_export_pdf.py`:

```python
import json


def _gan_vung_hinh(proj):
    con = db.connect(proj)
    db.set_meta(con, "vung_hinh", json.dumps({"0": [[80, 300, 440, 500]]}))
    con.commit()


def test_reflow_ve_o_anh_tu_meta(proj, tmp_path):
    _gan_vung_hinh(proj)
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="reflow")
    assert "ảnh" in _nua_phai(out, 0)


def test_overlay_khong_ve_o_anh(proj, tmp_path):
    """Review Focus 5: overlay giữ ảnh gốc trên bản sao trang."""
    _gan_vung_hinh(proj)
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, mode="overlay")
    assert "ảnh" not in _nua_phai(out, 0)
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_reflow.py tests/test_export_pdf.py -q -k "hinh or o_anh"`
Expected: FAIL — `chen_hinh` chưa có; các test dàn không thấy "ảnh". `test_overlay_khong_ve_o_anh` PASS (tiền đề).

- [ ] **Step 3: Viết code**

Trong `render/pdf_reflow.py`, thêm `import db` vào nhóm import dự án, và thêm sau `_ve_bang_moi_gia`:

```python
# 8B E8: vùng hình (meta vung_hinh) vẽ thành ô "ảnh". Người dùng cho thu nhỏ.
CAO_O_TOI_THIEU = 30.0
TI_LE_O_ANH = 0.5
NHAN_ANH = "ảnh"


def chen_hinh(khoi: list, vung: list) -> list:
    """Danh sách khối mới có thêm ô hình, đặt theo độ cao để giữ thứ tự đọc."""
    out = list(khoi)
    for v in sorted(vung, key=lambda v: v[1]):
        muc = {"id": None, "kind": "hinh", "bbox": pymupdf.Rect(v),
               "html": "", "src": "", "size": 0.0}
        i = next((i for i, k in enumerate(out) if k["bbox"].y0 > v[1]),
                 len(out))
        out.insert(i, muc)
    return out


def _ve_o_anh(page, rect, kho, co) -> None:
    page.draw_rect(rect, color=(0.7, 0.7, 0.7), width=0.5)
    nhan = pymupdf.Rect(rect.x0, (rect.y0 + rect.y1) / 2 - co,
                        rect.x1, (rect.y0 + rect.y1) / 2 + co)
    page.insert_htmlbox(nhan, NHAN_ANH,
                        css=pdf_font.dung_css(co, 1.0)
                        + "*{text-align:center;color:#888888;}",
                        archive=kho, scale_low=0)
```

Trong `trang_theo_vi_tri`: đổi chữ ký thành

```python
def trang_theo_vi_tri(src_doc, page_no: int, khoi: list, kho=None,
                      ghi_nhan=None, *, than: float = 9.0) -> "pymupdf.Document":
```

và ngay đầu vòng `for k in khoi:` thêm:

```python
        if k.get("kind") == "hinh":
            o = kep_khung(k["bbox"], page.rect)
            if _khung_dung(o, page.rect):
                _ve_o_anh(page, o, kho, than)
            continue
```

Trong `trang_reflow`, thay khối dựng `muc`:

```python
    muc = []
    for k in khoi:
        da_dich = bool(k["html"].strip())
        # D7: chưa dịch thì hiện chữ Anh — khoảng trắng im lặng tệ hơn.
        html = k["html"] if da_dich else k.get("src", "")
        if html.strip():
            muc.append((k, html, da_dich))
```

bằng:

```python
    muc = []
    for k in khoi:
        if k.get("kind") == "hinh":
            muc.append((k, "", False))
            continue
        da_dich = bool(k["html"].strip())
        # D7: chưa dịch thì hiện chữ Anh — khoảng trắng im lặng tệ hơn.
        html = k["html"] if da_dich else k.get("src", "")
        if html.strip():
            muc.append((k, html, da_dich))
```

đổi lời gọi dự phòng thành `return trang_theo_vi_tri(src_doc, page_no, khoi, kho, ghi_nhan, than=than)`, và thay vòng vẽ cuối:

```python
    for (k, html, da_dich), (rect, css) in zip(muc, dat):
        page.insert_htmlbox(rect, html, css=css, archive=kho, scale_low=1)
        if ghi_nhan is not None and da_dich:
            ghi_nhan.append((k.get("id"), s, False))
```

bằng:

```python
    for (k, html, da_dich), (rect, css) in zip(muc, dat):
        if k.get("kind") == "hinh":
            _ve_o_anh(page, rect, kho, than * s)
            continue
        page.insert_htmlbox(rect, html, css=css, archive=kho, scale_low=1)
        if ghi_nhan is not None and da_dich:
            ghi_nhan.append((k.get("id"), s, False))
```

Trong `_thu_bac`, thay vòng đo:

```python
        for k, html, _ in muc:
            co = dan_trang.co_khoi(k.get("kind", "text"), k["size"], than) * s
```

bằng:

```python
        for k, html, _ in muc:
            if k.get("kind") == "hinh":
                # Ô ảnh: bề rộng gốc kẹp vào khung (không nới như D4), cao nửa
                # hình gốc, tối thiểu CAO_O_TOI_THIEU; không cần đo.
                x0 = max(k["bbox"].x0, khung.x0)
                x1 = min(k["bbox"].x1, khung.x1)
                if x1 - x0 < 1:
                    x0, x1 = khung.x0, khung.x1
                h = max(CAO_O_TOI_THIEU, TI_LE_O_ANH * k["bbox"].height) * s
                if h > khung.height:
                    return None
                ngang.append((x0, x1))
                cao.append(h)
                css_ds.append("")
                continue
            co = dan_trang.co_khoi(k.get("kind", "text"), k["size"], than) * s
```

và ở `return` cuối `_thu_bac`, ô hình không cần khoảng dư của chữ — thay:

```python
    return [(pymupdf.Rect(x0, yi, x1, yi + h + khoang), css)
            for (x0, x1), yi, h, css in zip(ngang, y, cao, css_ds)]
```

bằng:

```python
    return [(pymupdf.Rect(x0, yi, x1, yi + h + (0 if k.get("kind") == "hinh"
                                                 else khoang)), css)
            for (k, _, _), (x0, x1), yi, h, css in zip(muc, ngang, y, cao, css_ds)]
```

Trong `write`, thay:

```python
    du_phong = []
    dung = functools.partial(trang_reflow, than=co_than(con),
                             du_phong=du_phong)
```

bằng:

```python
    du_phong = []
    than = co_than(con)
    hinh = json.loads(db.get_meta(con, "vung_hinh") or "{}")

    def dung(src_doc, page_no, khoi, kho=None, ghi_nhan=None):
        return trang_reflow(src_doc, page_no,
                            chen_hinh(khoi, hinh.get(str(page_no), [])),
                            kho, ghi_nhan, than=than, du_phong=du_phong)
```

Nếu `functools` không còn dùng ở đâu khác trong file thì xoá import của nó.

Chú ý: `test_dan_ve_o_anh_cao_mot_nua_goc` đọc `get_drawings()` — viền ô là một `re` (rect). Nếu PyMuPDF trả viền dưới dạng 4 đường `l` thay vì `rect`, đổi helper `khung_o` sang lấy `d["rect"]` của mọi drawing (đó là khung bao của nét vẽ) và ghi `Ruling:`.

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/test_pdf_reflow.py tests/test_export_pdf.py -q`
Expected: tất cả PASS.

- [ ] **Step 5: Cả bộ, commit**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `413 passed`; vân tay golden xanh.

```bash
git add render/pdf_reflow.py tests/test_pdf_reflow.py tests/test_export_pdf.py
git commit -m "feat: reflow vẽ ô 'ảnh' cho vùng hình, cao nửa gốc, không đè chữ

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Nghiệm thu

**Files:**
- Create (scratchpad, KHÔNG commit): `<scratchpad>/nghiem_thu_8b.py`
- Không sửa code sản phẩm. Kết quả ghi ledger.

**Interfaces:**
- Consumes: mọi thứ ở Task 1–6.
- Produces: `projects/harmonics-8b` (init mới, chưa dịch); số đo bảng spec mục 7; ảnh khổ mẫu.

- [ ] **Step 1: Init harmonics-8b, đo thời gian**

```bash
time .venv/bin/python -W ignore::DeprecationWarning cli.py init projects/harmonics/source.pdf --dir projects/harmonics-8b --chunk-chars 6000
```

Expected: `Xong: N đoạn, M ký tự, K chunk.` Ghi N, M, K và thời gian vào ledger. KHÔNG dùng `--force` (thư mục chưa tồn tại). Nếu thư mục đã tồn tại từ lần chạy hỏng trước: nó chưa có bản dịch nào (kiểm `SELECT COUNT(*) FROM blocks WHERE dst_html IS NOT NULL` = 0) thì mới được `--force`.

- [ ] **Step 2: Init astrology vào thư mục tạm**

```bash
.venv/bin/python -W ignore::DeprecationWarning cli.py init projects/astrology/source.pdf --dir <scratchpad>/astro-8b --chunk-chars "$(sqlite3 projects/astrology/project.db "select value from meta where key='chunk_chars'")"
```

- [ ] **Step 3: Viết và chạy script đo**

`<scratchpad>/nghiem_thu_8b.py`, chạy từ gốc repo với tham số thư mục scratchpad:

```python
"""Nghiệm thu 8B. Chỉ in số đếm, không in nội dung sách."""
import html, json, re, sqlite3, sys
sys.path.insert(0, ".")
S = sys.argv[1]


def ket_noi(p):
    c = sqlite3.connect(p); c.row_factory = sqlite3.Row; return c


cu = ket_noi("projects/harmonics/project.db")
moi = ket_noi("projects/harmonics-8b/project.db")


def tong_ky_tu(c, where="1=1", tham=()):
    return c.execute(f"SELECT COALESCE(SUM(LENGTH(src_html)),0) FROM blocks WHERE {where}",
                     tham).fetchone()[0]


def txt(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h or "")).strip()


print("ký tự nguồn: cũ", tong_ky_tu(cu), "mới", tong_ky_tu(moi),
      "tăng", tong_ky_tu(moi) - tong_ky_tu(cu), "(ngưỡng >= 15000)")
print("trang 14 số khối:", moi.execute("SELECT COUNT(*) FROM blocks WHERE page_no=13").fetchone()[0],
      "(ngưỡng >= 1)")
print("trang 45 ký tự:", tong_ky_tu(moi, "page_no=44"), "(ngưỡng >= 2300)")

hai_cot = sorted(r[0] + 1 for r in moi.execute(
    "SELECT DISTINCT page_no FROM blocks WHERE json_extract(layout,'$.col')=1"))
cm = [p for p in hai_cot if 469 <= p <= 482]
print("chỉ mục 469-482 hai cột:", len(cm), "/14 | trang 2 cột khác:",
      [p for p in hai_cot if not 469 <= p <= 482])

so = re.compile(r"\s(\d{1,3}|[ivxlc]{1,6})$", re.I)
muc = sum(1 for r in moi.execute("SELECT src_html FROM blocks WHERE page_no IN (8,9)")
          for dong in [txt(r[0])] if so.search(dong))
print("trang 9-10 khối kết thúc bằng số trang:", muc, "(ngưỡng >= 21 dòng đã nối — xem Ruling nếu đếm theo khối)")

vh = json.loads(moi.execute("SELECT value FROM meta WHERE key='vung_hinh'").fetchone()[0])
print("trang có vùng hình:", len(vh), "(ngưỡng >= 150)")

cap = re.compile(r"^(Figure|Fig\.)\s+\d+", re.I)
def dem_cap(c):
    return sum(1 for (h,) in c.execute("SELECT src_html FROM blocks") if cap.match(txt(h)))
print("khối chú thích Figure: cũ", dem_cap(cu), "mới", dem_cap(moi), "(mới >= cũ)")

a_cu = ket_noi("projects/astrology/project.db")
a_moi = ket_noi(f"{S}/astro-8b/project.db")
q = ("SELECT page_no,pos,tag,kind,src_html,bbox,line_bboxes,layout FROM blocks "
     "ORDER BY page_no,pos")
r_cu = [tuple(r) for r in a_cu.execute(q)]
r_moi = [tuple(r) for r in a_moi.execute(q)]
print("astrology khối:", len(r_cu), len(r_moi), "| giống hệt:", r_cu == r_moi,
      "| khoá vung_hinh:", a_moi.execute("SELECT COUNT(*) FROM meta WHERE key='vung_hinh'").fetchone()[0])
```

Run: `.venv/bin/python -W ignore::DeprecationWarning <scratchpad>/nghiem_thu_8b.py <scratchpad>`

Expected: đủ ngưỡng spec mục 7: tăng ≥ 15.000; trang 14 ≥ 1 khối; trang 45 ≥ 2.300; chỉ mục 14/14 và trang 2 cột khác ⊆ {55, 63, 410, 460} cộng các trang vốn đã 2 cột ở DB cũ (9, 10, 145, 314, 335, 344 — kiểm bằng cùng truy vấn trên `cu`); vùng hình ≥ 150; chú thích mới ≥ cũ; astrology `giống hệt: True`, khoá `vung_hinh` 0.

Chỉ số "trang 9-10 dòng đã nối ≥ 21" trong spec đếm theo DÒNG; script đếm KHỐI kết thúc bằng số. Mục dài hai dòng chỉ là một khối, nên số khối có thể < 21 mà vẫn đúng. Nếu < 21: đếm lại theo dòng bằng cách chạy `pdf_text._doc_trang` + luồng scan trên trang 8, 9 và gọi `noi_so_trang`, đếm dòng có `ket_doan`; ghi `Ruling:` với con số theo dòng.

Nếu một ngưỡng không đạt: dùng superpowers:systematic-debugging, in page_no và số đếm, không đổi ngưỡng. Trang 2 cột ngoài danh sách dự kiến: xem ảnh trang đó bằng mắt trước khi kết luận.

- [ ] **Step 4: Soát bằng mắt trang 2 cột và xuất thử dry-run**

```bash
.venv/bin/python -W ignore::DeprecationWarning cli.py export projects/harmonics-8b --mode reflow --dry-run
```

Expected: dòng `N trang dự phòng` với N ≤ 5 (hoặc không có dòng đó nếu N = 0).

Chụp ảnh nửa gốc + nửa dịch (dry-run: chữ Anh độn) các khổ 10 (mục lục), 14, 45, 471 (chỉ mục), 30 và 60 (hình), cùng ≥ 5 trang trong danh sách 2 cột, bằng:

```bash
.venv/bin/python -W ignore::DeprecationWarning -c "
import pymupdf
d = pymupdf.open('projects/harmonics-8b/output.vi.pdf')
for k in (10, 14, 45, 471, 30, 60):
    d[k-1].get_pixmap(dpi=60).save('<scratchpad>/8b_kho%d.png' % k)"
```

Xem từng ảnh (Read). Ghi vào ledger: mục lục mỗi mục một khối và có số trang; trang 14 có chữ; chỉ mục hai cột không dính nhau; ô "ảnh" ở trang 30/60 và chữ rác "K Ores"/"Bis eas" không còn; không trang một cột nào bị chia cột.

- [ ] **Step 5: Chạy cả bộ lần cuối**

Run: `.venv/bin/python -W ignore::DeprecationWarning -m pytest tests/ -q`
Expected: `413 passed`.

Task này không có commit code. **Dừng ở đây:** dịch thử trang 1–30 tốn token — chỉ chạy khi người dùng cho phép (spec mục 7).
