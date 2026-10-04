# Phase 4 — Chế độ overlay: đè chữ Việt lên trang gốc và ghép khổ đôi

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xuất một file PDF khổ ngang, mỗi khổ là trang gốc bên trái và bản dịch bên phải, trong đó trang dịch là bản sao trang gốc đã thay chữ Anh bằng chữ Việt — ảnh, bảng, đường kẻ giữ nguyên.

**Architecture:** Trang dịch không được dựng lại; nó là **bản sao trang gốc** bị xoá chữ rồi đặt chữ mới vào đúng khung cũ. PyMuPDF làm được cả ba việc nặng: `apply_redactions` xoá glyph mà giữ ảnh, `insert_htmlbox` tự xuống dòng và tự co chữ rồi báo lại tỉ lệ, `show_pdf_page` dán nguyên trang vào khổ đôi. Việc của ta là chọn font, khai đúng cỡ chữ, và quyết định khi nào chấp nhận tỉ lệ co.

**Tech Stack:** Python 3.12.6, PyMuPDF 1.28.2, pytest 9.1.1.

**Spec:** `docs/superpowers/specs/2026-09-21-pdf-song-ngu-design.md` (mục 6)

## Global Constraints

- 154 test hiện có phải **giữ nguyên xanh**, gồm hai vân tay trong `tests/golden/`.
- **Không test nào gọi mạng, và Phase 4 không tiêu một token API nào.** Nghiệm thu bằng `--dry-run`.
- `pdf_layout.py` phải **tiếp tục không import PyMuPDF** — `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py` ra rỗng.
- Dùng `import pymupdf`, không dùng `import fitz`.
- Không thêm cột mới vào `blocks`; cờ tràn khung ghi vào cột `flag` đã có, giá trị `overflow`.
- Docstring và comment viết tiếng Việt, khớp code đang có.
- Mỗi task kết thúc bằng đúng một commit.

## Dữ liệu thật đã đo — đừng phỏng đoán lại

Tất cả đo trên máy này với PyMuPDF 1.28.2 và `ebook/astrology.pdf.pdf`.

| Câu hỏi | Kết quả đo |
|---|---|
| `insert_htmlbox` trả về gì | tuple `(chỗ thừa, tỉ lệ co)`. Vừa thì chỗ thừa ≥ 0; không vừa ở `scale_low` thì trả `(-1, scale_low)` |
| Cỡ chữ mặc định của nó | **12pt** — trong khi thân bài sách là **10pt** |
| Font dựng sẵn PyMuPDF (`helv`, `tiro`, `cour`) | **thiếu 17/25** ký tự tiếng Việt có dấu |
| Font mở đủ dấu trên máy này | **không có** (các Noto sẵn có là font chữ viết riêng) |
| Font macOS đủ dấu | Times New Roman, Georgia, Arial Unicode, NewYork (Charter thiếu 9) |
| Giữ `<b>`/`<i>` | được, nếu đăng ký **ba** `@font-face` (regular / bold / italic) |
| `apply_redactions()` mặc định | xoá chữ **và khoét trắng 100%** vùng ảnh bên dưới |
| `apply_redactions(images=PDF_REDACT_IMAGE_NONE)` | xoá chữ, ảnh **nguyên vẹn** (0% pixel trắng) |
| Tràn khung thật, 269 đoạn thân bài | trung vị giữ **98%**; ≥95% cho 67%; ≥85% cho 91%; ≥75% cho 99%; **tệ nhất 74%** |
| `get_text()` trên chữ vừa đặt | trả `\xa0` thay cho dấu cách thường |

### Ba điều dữ liệu thật quyết định thay cho phỏng đoán

**1. Phải khai cỡ chữ trong CSS, nếu không mọi phép đo đều sai 20%.** Lúc dò, tôi để `insert_htmlbox` dùng mặc định 12pt trên khung của chữ 10pt và đo ra "trung vị co còn 72%" — suýt kết luận hướng A không khả thi. Khai đúng `font-size` theo `para.size` thì con số thật là 98%.

**2. Bậc "cho tràn xuống lề" trong spec mục 6 bị bỏ.** Spec xếp nó là bậc 4 của thang tự co. Đo thật cho thấy **không đoạn nào phải co dưới 74%**, nên bậc đó không bao giờ được dùng tới — trong khi nó đòi biết khung dưới có trống không, và sai thì đè lên đoạn kế tiếp. Bỏ đi, ghi rõ lý do ở Task 4.

**3. Không có font mở đủ dấu trên máy này**, nên mặc định trỏ vào font hệ thống macOS và **đường dẫn phải cấu hình được**. Việc dùng font hệ thống cho bản PDF cá nhân là bình thường; phát hành lại là chuyện của người dùng. Tool phải **báo lỗi to** khi font thiếu dấu, tuyệt đối không âm thầm lùi về font dựng sẵn — cả cuốn sách sẽ thành ô vuông.

## Review Focus

Năm trường hợp spec ngụ ý nhưng không task nào tự nhiên chạm tới.

1. **Font cấu hình trỏ vào file không tồn tại, hoặc file font thiếu dấu tiếng Việt** — phải dừng ngay đầu `export` với thông báo nêu tên ký tự thiếu, không xuất ra một cuốn sách toàn ô vuông. → Task 2.
2. **Khung của đoạn suy biến** (rộng hoặc cao ≤ 0, hoặc nằm ngoài trang) — bỏ qua có kiểm soát, không làm vỡ cả lần xuất. → Task 4.
3. **Trang chưa có đoạn nào được dịch** — vẫn phải ra đủ cặp trang, bên phải là trang gốc chưa đụng tới, không được ra trang trắng im lặng. → Task 5.
4. **Project nguồn là EPUB nhưng gọi `--mode overlay`** — phải từ chối rõ ràng; overlay cần toạ độ PDF mà EPUB không có. → Task 6.
5. **Đoạn không vừa dù đã co tới đáy thang** — phải gắn cờ `overflow`, đếm được trong `status` và hiện trong `--probe`, không được âm thầm cắt cụt. → Task 4.

---

## File Structure

Tạo mới:

| File | Trách nhiệm |
|---|---|
| `pdf_font.py` | Chọn bộ font đủ dấu, dựng `Archive` và CSS. Chỗ duy nhất biết đường dẫn font |
| `render/pdf_overlay.py` | Dựng trang dịch và ghép khổ đôi. Chỗ duy nhất của Phase 4 đụng PyMuPDF |
| `tests/test_pdf_font.py` | Test chọn font và phủ glyph |
| `tests/test_pdf_overlay.py` | Test xoá chữ, đặt chữ, thang co, ghép khổ đôi |

Sửa:

| File | Thay đổi |
|---|---|
| `pdf_layout.py` | Thêm `thang_co()` — chính sách thang tự co, hàm thuần |
| `render/__init__.py` | Định tuyến `pdf` sang `pdf_overlay`; `mode` |
| `cli.py` | `export` nhận `--mode`, `--pages`, `--dry-run`, `--probe` |

**Vì sao `pdf_font.py` nằm ở gốc chứ không trong `render/`:** Phase 6 (`reflow`) cũng cần đúng bộ font ấy, và Phase 7 (OCR) có thể cần đo bề rộng chữ. Đặt trong `render/` là buộc các tầng khác import ngược vào tầng ghi ra.

---

## Task 1: Chính sách thang tự co (hàm thuần)

Bắt đầu bằng phần không cần PyMuPDF, để chính sách được chốt bằng test nhanh trước khi dính vào thư viện.

**Files:**
- Modify: `pdf_layout.py`
- Modify: `tests/test_pdf_layout.py`

**Interfaces:**
- Produces: `pdf_layout.THANG_CO` — tuple các bậc `(scale_low, line_height)`; `pdf_layout.thang_co() -> tuple`; `pdf_layout.co_chap_nhan_duoc(ti_le) -> bool`; `pdf_layout.DAY_THANG = 0.70`.

- [ ] **Step 1: Viết test cho thang tự co**

Chèn vào cuối `tests/test_pdf_layout.py`:

```python
def test_thang_co_bat_dau_bang_co_chu_goc():
    bac = pdf_layout.thang_co()
    assert bac[0] == (1.0, 1.0), "bậc đầu phải là cỡ gốc, giãn dòng gốc"


def test_thang_co_giam_dan_khong_bao_gio_tang():
    ti_le = [b[0] for b in pdf_layout.thang_co()]
    assert ti_le == sorted(ti_le, reverse=True)
    assert ti_le[-1] == pdf_layout.DAY_THANG


def test_thang_co_bop_gian_dong_truoc_khi_thu_chu():
    """Bóp giãn dòng ít gây chú ý hơn thu cỡ chữ, nên phải thử trước."""
    bac = pdf_layout.thang_co()
    assert bac[1][0] == 1.0 and bac[1][1] < 1.0


def test_day_thang_dung_bang_muc_spec():
    assert pdf_layout.DAY_THANG == 0.70


def test_co_chap_nhan_duoc():
    assert pdf_layout.co_chap_nhan_duoc(1.0)
    assert pdf_layout.co_chap_nhan_duoc(0.70)
    assert not pdf_layout.co_chap_nhan_duoc(0.69)
    assert not pdf_layout.co_chap_nhan_duoc(-1)      # tín hiệu "không vừa"


def test_moi_bac_deu_khac_nhau():
    bac = pdf_layout.thang_co()
    assert len(set(bac)) == len(bac)
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -k thang -v`
Expected: FAIL với `AttributeError: module 'pdf_layout' has no attribute 'thang_co'`.

- [ ] **Step 3: Thêm thang tự co vào `pdf_layout.py`**

Chèn vào cuối file:

```python
# ---- thang tự co khi chữ Việt không vừa khung chữ Anh ----
#
# Tiếng Việt dài hơn tiếng Anh, nhưng đo thật trên 269 đoạn thân bài của sách
# mẫu (cỡ chữ khớp bản gốc) thì trung vị vẫn giữ được 98%, 91% số đoạn giữ được
# từ 85% trở lên, và đoạn tệ nhất là 74%. Thang này vì thế còn dư chỗ.
#
# Spec mục 6 có một bậc "cho tràn xuống lề nếu dưới khung là chỗ trống". Bỏ đi:
# đo thật cho thấy không đoạn nào phải xuống dưới 74% nên bậc đó không bao giờ
# được dùng, trong khi nó đòi biết khung dưới có trống không và sai thì đè lên
# đoạn kế tiếp.
DAY_THANG = 0.70

THANG_CO = (
    (1.00, 1.00),     # cỡ gốc, giãn dòng gốc
    (1.00, 0.95),     # bóp giãn dòng trước — ít gây chú ý hơn thu cỡ chữ
    (0.85, 0.95),
    (0.75, 0.95),
    (DAY_THANG, 0.95),
)


def thang_co() -> tuple:
    """Các bậc (tỉ lệ cỡ chữ tối thiểu, giãn dòng) thử lần lượt, vừa là dừng."""
    return THANG_CO


def co_chap_nhan_duoc(ti_le: float) -> bool:
    """`insert_htmlbox` trả -1 khi không vừa ở tỉ lệ đã cho."""
    return ti_le >= DAY_THANG
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_layout.py -k thang -v`
Expected: 6 passed.

- [ ] **Step 5: Chạy cả bộ và kiểm ràng buộc thuần**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 160 passed.

Run: `grep -rn "pymupdf\|fitz" pdf_layout.py`
Expected: không ra dòng nào.

- [ ] **Step 6: Commit**

```bash
git add pdf_layout.py tests/test_pdf_layout.py
git commit -m "feat: chính sách thang tự co cho chữ Việt tràn khung

Bậc đầu là cỡ gốc; bóp giãn dòng trước khi thu cỡ chữ vì ít gây chú ý
hơn; đáy thang 0.70 theo spec. Bỏ bậc 'cho tràn xuống lề' của spec: đo
thật trên 269 đoạn cho thấy đoạn tệ nhất chỉ phải co còn 74%, nên bậc
đó không bao giờ dùng tới mà lại có nguy cơ đè lên đoạn kế tiếp."
```

---

## Task 2: Chọn font có đủ dấu tiếng Việt

Đây là chỗ hỏng thì cả cuốn sách thành ô vuông, nên nó phải hỏng **to và sớm**.

**Files:**
- Create: `pdf_font.py`
- Create: `tests/test_pdf_font.py`

**Interfaces:**
- Produces:
  - `pdf_font.KY_TU_THU` — chuỗi ký tự tiếng Việt dùng để thử phủ glyph.
  - `pdf_font.ThieuFont(Exception)` — thông điệp dành cho người dùng cuối.
  - `pdf_font.thieu_glyph(duong_dan) -> list[str]`.
  - `pdf_font.chon_bo_font(uu_tien=None) -> BoFont` — dataclass `(ten, thuong, dam, nghieng)`, ba trường sau là đường dẫn file.
  - `pdf_font.dung_archive(bo) -> pymupdf.Archive`.
  - `pdf_font.dung_css(size, line_height=1.0) -> str`.

- [ ] **Step 1: Viết test cho chọn font**

Tạo `tests/test_pdf_font.py`:

```python
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
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_font.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'pdf_font'`.

- [ ] **Step 3: Viết `pdf_font.py`**

```python
"""Chọn và nhúng bộ font có đủ dấu tiếng Việt.

Chỗ duy nhất trong dự án biết đường dẫn file font.

Đây là chỗ hỏng thì hỏng toàn bộ: font Latin thiếu dấu không báo lỗi gì, nó chỉ
vẽ ô vuông, và người dùng phát hiện sau khi đã dịch xong cả cuốn. Nên module
này thà dừng hẳn còn hơn lùi về một font "gần đúng".

Đo thật: toàn bộ font dựng sẵn của PyMuPDF (helv, tiro, cour) thiếu 17/25 ký tự
tiếng Việt có dấu. Máy thử nghiệm không có font giấy phép mở nào đủ dấu, nên
mặc định trỏ vào font hệ thống macOS và đường dẫn phải cấu hình được.
"""
import os
from dataclasses import dataclass

import pymupdf

# Những chữ mà font Latin hay thiếu nhất: nguyên âm có hai dấu, và chữ Đ.
KY_TU_THU = "ặữổỹằẵợựỡẫĐđỨƯờáàảãạêôơưêế"

# Biến môi trường để trỏ font khác: ba đường dẫn, ngăn bằng dấu hai chấm.
BIEN_MOI_TRUONG = "BOOKTRANS_FONT"

_MAC = "/System/Library/Fonts/Supplemental/"
UU_TIEN_MAC_DINH = [
    (_MAC + "Times New Roman.ttf", _MAC + "Times New Roman Bold.ttf",
     _MAC + "Times New Roman Italic.ttf"),
    (_MAC + "Georgia.ttf", _MAC + "Georgia Bold.ttf", _MAC + "Georgia Italic.ttf"),
    (_MAC + "Arial Unicode.ttf",) * 3,
]


class ThieuFont(Exception):
    """Không có font dùng được. Thông điệp dành cho người dùng cuối."""


@dataclass
class BoFont:
    ten: str
    thuong: str
    dam: str
    nghieng: str


def thieu_glyph(duong_dan) -> list:
    """Những ký tự trong KY_TU_THU mà font này KHÔNG vẽ được."""
    f = pymupdf.Font(fontfile=str(duong_dan))
    # has_glyph trả về MÃ glyph; thiếu thì là 0. Đừng so với False — `0 is False`
    # là False trong Python, và phép thử sẽ im lặng bỏ sót mọi ký tự thiếu.
    return [c for c in KY_TU_THU if not f.has_glyph(ord(c))]


def _tu_moi_truong():
    gia_tri = os.environ.get(BIEN_MOI_TRUONG)
    if not gia_tri:
        return []
    phan = [p for p in gia_tri.split(":") if p]
    if len(phan) == 1:
        phan = phan * 3
    if len(phan) != 3:
        raise ThieuFont(
            f"{BIEN_MOI_TRUONG} phải là 1 hoặc 3 đường dẫn ngăn bằng dấu hai "
            f"chấm (thường:đậm:nghiêng), đang có {len(phan)}."
        )
    return [tuple(phan)]


def chon_bo_font(uu_tien=None) -> BoFont:
    """Bộ font đầu tiên vừa tồn tại vừa đủ dấu. Không có thì ném ThieuFont."""
    danh_sach = list(uu_tien) if uu_tien is not None else (
        _tu_moi_truong() + UU_TIEN_MAC_DINH)

    thieu_duong, thieu_dau = [], []
    for bo in danh_sach:
        thuong, dam, nghieng = (bo * 3)[:3] if len(bo) == 1 else bo
        khong_co = [p for p in (thuong, dam, nghieng) if not os.path.exists(p)]
        if khong_co:
            thieu_duong.extend(khong_co)
            continue
        thieu = thieu_glyph(thuong)
        if thieu:
            thieu_dau.append((thuong, thieu))
            continue
        return BoFont(ten=os.path.basename(thuong), thuong=thuong,
                      dam=dam, nghieng=nghieng)

    if thieu_dau:
        duong, thieu = thieu_dau[0]
        raise ThieuFont(
            f"font {os.path.basename(duong)} thiếu {len(thieu)} ký tự tiếng "
            f"Việt ({''.join(thieu[:8])}...). Dùng font khác qua biến môi "
            f"trường {BIEN_MOI_TRUONG}."
        )
    raise ThieuFont(
        f"không thấy file font nào: {', '.join(thieu_duong[:3])}. "
        f"Trỏ font khác qua biến môi trường {BIEN_MOI_TRUONG}."
    )


def dung_archive(bo: BoFont) -> "pymupdf.Archive":
    kho = pymupdf.Archive()
    kho.add(bo.thuong, "r.ttf")
    kho.add(bo.dam, "b.ttf")
    kho.add(bo.nghieng, "i.ttf")
    return kho


def dung_css(size: float, line_height: float = 1.0) -> str:
    """CSS cho insert_htmlbox.

    PHẢI khai font-size. Mặc định của insert_htmlbox là 12pt trong khi thân bài
    sách mẫu là 10pt; bỏ qua chỗ này là mọi phép đo tràn khung phồng lên 20%.
    """
    return (
        "@font-face{font-family:viet;src:url(r.ttf);}"
        "@font-face{font-family:viet;src:url(b.ttf);font-weight:bold;}"
        "@font-face{font-family:viet;src:url(i.ttf);font-style:italic;}"
        "*{font-family:viet;"
        f"font-size:{size:.2f}px;"
        f"line-height:{line_height};"
        "margin:0;padding:0;}"
    )
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_font.py -v`
Expected: 10 passed.

Nếu `test_font_du_dau_thi_khong_bao_thieu` hỏng vì máy không phải macOS, đặt
`BOOKTRANS_FONT` trỏ vào một font đủ dấu rồi chạy lại — **đừng nới `KY_TU_THU`**.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 170 passed.

- [ ] **Step 6: Commit**

```bash
git add pdf_font.py tests/test_pdf_font.py
git commit -m "feat: chọn và nhúng bộ font đủ dấu tiếng Việt

Font Latin thiếu dấu không báo lỗi, nó chỉ vẽ ô vuông — nên module này
thà dừng hẳn còn hơn lùi về font gần đúng, và thông báo nêu đúng ký tự
thiếu. dung_css khai font-size tường minh vì mặc định của insert_htmlbox
là 12pt trong khi thân bài sách là 10pt."
```

---

## Task 3: Xoá chữ Anh mà giữ nguyên ảnh

**Files:**
- Create: `render/pdf_overlay.py`
- Create: `tests/test_pdf_overlay.py`

**Interfaces:**
- Consumes: `pdf_font` từ Task 2.
- Produces: `render.pdf_overlay.xoa_chu(page, khung_list) -> None` — xoá chữ trong các khung, giữ ảnh.

- [ ] **Step 1: Viết test cho xoá chữ**

Tạo `tests/test_pdf_overlay.py`:

```python
"""Đè chữ Việt lên bản sao trang gốc, rồi ghép khổ đôi."""
import pymupdf

from render import pdf_overlay


def trang_co_anh_va_chu(doc=None):
    """Trang 300x200 có một ảnh và một dòng chữ nằm đè lên ảnh."""
    doc = doc or pymupdf.open()
    page = doc.new_page(width=300, height=200)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 64, 64))
    pix.set_rect(pix.irect, (200, 120, 60))
    page.insert_image(pymupdf.Rect(40, 40, 260, 160), pixmap=pix)
    page.insert_text((50, 100), "chu nam de len anh", fontsize=11)
    return doc, page


def ti_le_pixel_trang(page, khung):
    p = page.get_pixmap(clip=khung)
    trang = sum(1 for i in range(0, len(p.samples), p.n)
                if all(p.samples[i + k] > 240 for k in range(3)))
    return trang / (p.width * p.height)


def test_xoa_chu_thi_chu_bien_mat():
    doc, page = trang_co_anh_va_chu()
    pdf_overlay.xoa_chu(page, [pymupdf.Rect(45, 88, 200, 105)])
    assert "chu nam de len anh" not in page.get_text()
    doc.close()


def test_xoa_chu_KHONG_duoc_khoet_anh():
    """apply_redactions mặc định khoét trắng 100% vùng ảnh bên dưới — đo thật.
    Đây là 'chỗ dễ hỏng nhất' mà spec mục 6 cảnh báo."""
    doc, page = trang_co_anh_va_chu()
    khung = pymupdf.Rect(45, 88, 200, 105)
    pdf_overlay.xoa_chu(page, [khung])
    assert ti_le_pixel_trang(page, khung) < 0.05, "đã khoét mất ảnh bên dưới"
    doc.close()


def test_anh_van_con_trong_danh_sach_tai_nguyen():
    doc, page = trang_co_anh_va_chu()
    truoc = len(page.get_images())
    pdf_overlay.xoa_chu(page, [pymupdf.Rect(45, 88, 200, 105)])
    assert len(page.get_images()) == truoc
    doc.close()


def test_khong_co_khung_nao_thi_khong_lam_gi():
    doc, page = trang_co_anh_va_chu()
    pdf_overlay.xoa_chu(page, [])
    assert "chu nam de len anh" in page.get_text()
    doc.close()


def test_chu_ngoai_khung_khong_bi_xoa():
    doc, page = trang_co_anh_va_chu()
    page.insert_text((50, 180), "dong khac o duoi", fontsize=11)
    pdf_overlay.xoa_chu(page, [pymupdf.Rect(45, 88, 200, 105)])
    assert "dong khac o duoi" in page.get_text()
    doc.close()
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_overlay.py -v`
Expected: FAIL với `ImportError: cannot import name 'pdf_overlay' from 'render'`.

- [ ] **Step 3: Viết phần đầu `render/pdf_overlay.py`**

```python
"""Chế độ overlay: đè chữ Việt lên bản sao trang gốc, rồi ghép khổ đôi.

Chỗ duy nhất của Phase 4 đụng tới PyMuPDF. Chính sách thang tự co nằm ở
pdf_layout.py dưới dạng hàm thuần; chọn font nằm ở pdf_font.py.
"""
import json
import statistics
from pathlib import Path

import pymupdf

import db
import pdf_font
import pdf_layout


def xoa_chu(page, khung_list) -> None:
    """Xoá chữ trong các khung, GIỮ NGUYÊN ảnh nằm dưới.

    `images=PDF_REDACT_IMAGE_NONE` là bắt buộc, không phải tuỳ chọn. Đo thật:
    apply_redactions() mặc định xoá chữ xong khoét trắng 100% vùng ảnh bên
    dưới; với cờ này thì 0%. Chú thích đè lên hình là chuyện thường trong sách,
    nên bỏ cờ là khoét lỗ khắp cuốn.
    """
    if not khung_list:
        return
    for khung in khung_list:
        page.add_redact_annot(khung)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_overlay.py -v`
Expected: 5 passed.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 175 passed.

- [ ] **Step 6: Commit**

```bash
git add render/pdf_overlay.py tests/test_pdf_overlay.py
git commit -m "feat: xoá chữ Anh mà giữ nguyên ảnh bên dưới

PDF_REDACT_IMAGE_NONE là bắt buộc: đo thật cho thấy apply_redactions
mặc định khoét trắng 100% vùng ảnh nằm dưới chữ, với cờ này thì 0%.
Chú thích đè lên hình là chuyện thường nên bỏ cờ là khoét lỗ khắp sách."
```

---

## Task 4: Đặt chữ Việt vào khung theo thang tự co

**Files:**
- Modify: `render/pdf_overlay.py`
- Modify: `tests/test_pdf_overlay.py`

**Interfaces:**
- Consumes: `pdf_layout.thang_co`, `pdf_layout.co_chap_nhan_duoc` từ Task 1; `pdf_font.dung_css`, `pdf_font.dung_archive` từ Task 2.
- Produces: `render.pdf_overlay.dat_chu(page, khung, html, size, kho) -> (ti_le, tran)` — `ti_le` là tỉ lệ cỡ chữ giữ được, `tran` là `True` khi không vừa cả ở đáy thang.

- [ ] **Step 1: Viết test cho đặt chữ**

Chèn vào cuối `tests/test_pdf_overlay.py`:

```python
import pdf_font
import pdf_layout


def trang_trang(w=300, h=200):
    doc = pymupdf.open()
    return doc, doc.new_page(width=w, height=h)


def test_chu_vua_khung_thi_giu_nguyen_co():
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    ti_le, tran = pdf_overlay.dat_chu(page, pymupdf.Rect(10, 10, 290, 150),
                                      "Một câu ngắn.", 10.0, kho)
    assert ti_le == 1.0 and tran is False
    doc.close()


def test_chu_co_dau_hien_dung_tren_trang():
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    pdf_overlay.dat_chu(page, pymupdf.Rect(10, 10, 290, 150),
                        "Những chữ khó: ặ ữ ổ ỹ ằ ẵ ợ ự", 10.0, kho)
    ra = page.get_text()
    for c in "ặữổỹằẵợự":
        assert c in ra
    doc.close()


def test_co_chu_dat_ra_dung_bang_co_yeu_cau():
    """Bẫy: mặc định của insert_htmlbox là 12pt. Phải ra đúng 10pt."""
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    pdf_overlay.dat_chu(page, pymupdf.Rect(10, 10, 290, 150),
                        "Một câu ngắn.", 10.0, kho)
    d = page.get_text("dict")
    co = {round(s["size"], 1) for b in d["blocks"] if not b["type"]
          for l in b["lines"] for s in l["spans"]}
    assert co == {10.0}, f"cỡ chữ ra {co}, không phải 10.0"
    doc.close()


def test_the_dam_va_nghieng_duoc_giu():
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    pdf_overlay.dat_chu(page, pymupdf.Rect(10, 10, 290, 150),
                        "thường <b>đậm</b> và <i>nghiêng</i>", 10.0, kho)
    mat = {f[3] for f in page.parent.get_page_fonts(0)}
    assert any("Bold" in m or "bold" in m for m in mat), f"không có mặt đậm: {mat}"
    assert any("Italic" in m or "italic" in m for m in mat), f"không có mặt nghiêng: {mat}"
    doc.close()


def test_chu_dai_thi_bi_co_lai_va_bao_ti_le():
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    ti_le, tran = pdf_overlay.dat_chu(page, pymupdf.Rect(10, 10, 290, 40),
                                      "Một đoạn văn tiếng Việt khá dài " * 4,
                                      10.0, kho)
    assert 0 < ti_le < 1.0, f"phải co lại, nhưng ti_le={ti_le}"
    assert tran is False
    doc.close()


def test_khong_vua_ca_o_day_thang_thi_bao_tran():
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    ti_le, tran = pdf_overlay.dat_chu(page, pymupdf.Rect(10, 10, 60, 20),
                                      "Một đoạn văn rất dài không thể nào vừa " * 12,
                                      10.0, kho)
    assert tran is True
    doc.close()


def test_khong_bao_gio_co_duoi_day_thang():
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    ti_le, tran = pdf_overlay.dat_chu(page, pymupdf.Rect(10, 10, 60, 20),
                                      "Một đoạn văn rất dài không thể nào vừa " * 12,
                                      10.0, kho)
    assert ti_le >= pdf_layout.DAY_THANG or tran, "đã co xuống dưới đáy thang"
    doc.close()


def test_khung_suy_bien_bi_bo_qua_khong_lam_vo():
    """Khung rộng hoặc cao <= 0 do bóc chữ lỗi — bỏ qua, đừng làm vỡ cả lần xuất."""
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    for khung in (pymupdf.Rect(10, 10, 10, 50), pymupdf.Rect(10, 10, 100, 10),
                  pymupdf.Rect(100, 50, 10, 10)):
        ti_le, tran = pdf_overlay.dat_chu(page, khung, "Chữ gì đó", 10.0, kho)
        assert tran is True and ti_le == 0.0
    doc.close()


def test_html_rong_thi_khong_lam_gi():
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    ti_le, tran = pdf_overlay.dat_chu(page, pymupdf.Rect(10, 10, 290, 150),
                                      "   ", 10.0, kho)
    assert tran is False and ti_le == 1.0
    doc.close()
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_overlay.py -k dat_chu -v`
Expected: FAIL với `AttributeError: module 'render.pdf_overlay' has no attribute 'dat_chu'`.

- [ ] **Step 3: Thêm `dat_chu` vào `render/pdf_overlay.py`**

Chèn sau `xoa_chu`:

```python
def dat_chu(page, khung, html: str, size: float, kho) -> tuple:
    """Đặt `html` vào `khung`, đi theo thang tự co. Trả về (tỉ lệ, tràn).

    `insert_htmlbox` tự xuống dòng và tự co chữ; nó trả về (chỗ thừa, tỉ lệ) và
    dùng -1 làm chỗ thừa khi không vừa ở `scale_low` đã cho. Ta chỉ việc thử
    lần lượt các bậc và dừng ở bậc đầu tiên vừa.
    """
    if not html or not html.strip():
        return 1.0, False
    if khung.width <= 0 or khung.height <= 0:
        # Khung suy biến do bóc chữ lỗi. Bỏ qua có kiểm soát: một khung hỏng
        # không được làm hỏng cả lần xuất.
        return 0.0, True

    for scale_low, gian_dong in pdf_layout.thang_co():
        css = pdf_font.dung_css(size, gian_dong)
        thua, ti_le = page.insert_htmlbox(khung, html, css=css, archive=kho,
                                          scale_low=scale_low)
        if thua >= 0:
            return ti_le, False

    return pdf_layout.DAY_THANG, True
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_overlay.py -v`
Expected: 14 passed.

Nếu `test_khong_vua_ca_o_day_thang_thi_bao_tran` không đỏ được vì
`insert_htmlbox` vẫn nhét vừa, thu nhỏ khung trong test cho tới khi nó thật sự
không vừa — **đừng nâng `DAY_THANG`**.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 184 passed.

- [ ] **Step 6: Commit**

```bash
git add render/pdf_overlay.py tests/test_pdf_overlay.py
git commit -m "feat: đặt chữ Việt vào khung theo thang tự co

insert_htmlbox tự xuống dòng và tự co, trả về (chỗ thừa, tỉ lệ) với -1
là tín hiệu không vừa — nên thang chỉ là thử lần lượt và dừng ở bậc đầu
tiên vừa. Khung suy biến bị bỏ qua có kiểm soát thay vì làm vỡ lần xuất."
```

---

## Task 5: Dựng trang dịch và ghép khổ đôi

**Files:**
- Modify: `render/pdf_overlay.py`
- Modify: `tests/test_pdf_overlay.py`

**Interfaces:**
- Consumes: `xoa_chu`, `dat_chu` từ Task 3-4.
- Produces:
  - `render.pdf_overlay.trang_dich(src_doc, page_no, khoi) -> pymupdf.Document` — tài liệu một trang là bản sao trang gốc đã thay chữ; `khoi` là list dict `{bbox, html, size}`.
  - `render.pdf_overlay.ghep_kho_doi(src_doc, cap) -> pymupdf.Document`, `cap` là list `(page_no, tài liệu một trang)`.

- [ ] **Step 1: Viết test cho dựng trang và ghép khổ**

Chèn vào cuối `tests/test_pdf_overlay.py`:

```python
def sach_mau(so_trang=2):
    doc = pymupdf.open()
    for t in range(so_trang):
        page = doc.new_page(width=300, height=400)
        page.insert_text((40, 100), f"English text on page {t}", fontsize=10)
    return doc


def khoi(x0, y0, x1, y1, html, size=10.0):
    return {"bbox": pymupdf.Rect(x0, y0, x1, y1), "html": html, "size": size}


def test_trang_dich_giu_kho_trang_goc():
    src = sach_mau(1)
    d = pdf_overlay.trang_dich(src, 0, [khoi(35, 90, 260, 110, "Chữ Việt thay thế")])
    assert d[0].rect.width == 300 and d[0].rect.height == 400
    d.close(); src.close()


def test_trang_dich_thay_chu_anh_bang_chu_viet():
    src = sach_mau(1)
    d = pdf_overlay.trang_dich(src, 0, [khoi(35, 90, 260, 110, "Chữ Việt thay thế")])
    ra = d[0].get_text()
    assert "English text" not in ra
    assert "Việt" in ra
    d.close(); src.close()


def test_trang_khong_co_khoi_nao_thi_giu_nguyen_ban_goc():
    """Trang chưa dịch đoạn nào: bên phải phải là trang gốc, không phải trang trắng."""
    src = sach_mau(1)
    d = pdf_overlay.trang_dich(src, 0, [])
    assert "English text on page 0" in d[0].get_text()
    d.close(); src.close()


def test_ghep_kho_doi_rong_gap_doi_va_cao_bang():
    src = sach_mau(2)
    dich = pdf_overlay.trang_dich(src, 0, [])
    ra = pdf_overlay.ghep_kho_doi(src, [(0, dich)])
    assert ra[0].rect.width == 600 and ra[0].rect.height == 400
    ra.close(); dich.close(); src.close()


def test_ghep_kho_doi_dung_so_kho():
    src = sach_mau(3)
    cap = [(t, pdf_overlay.trang_dich(src, t, [])) for t in range(3)]
    ra = pdf_overlay.ghep_kho_doi(src, cap)
    assert ra.page_count == 3
    ra.close()
    for _, d in cap:
        d.close()
    src.close()


def test_ban_goc_nam_ben_TRAI_ban_dich_nam_ben_PHAI():
    src = sach_mau(1)
    dich = pdf_overlay.trang_dich(src, 0, [khoi(35, 90, 260, 110, "Bản dịch tiếng Việt")])
    ra = pdf_overlay.ghep_kho_doi(src, [(0, dich)])
    trai = ra[0].get_text(clip=pymupdf.Rect(0, 0, 300, 400))
    phai = ra[0].get_text(clip=pymupdf.Rect(300, 0, 600, 400))
    assert "English text" in trai and "English text" not in phai
    assert "dịch" in phai and "dịch" not in trai
    ra.close(); dich.close(); src.close()


def test_so_trang_goc_duoc_in_giua_kho():
    src = sach_mau(1)
    dich = pdf_overlay.trang_dich(src, 0, [])
    ra = pdf_overlay.ghep_kho_doi(src, [(0, dich)])
    giua = ra[0].get_text(clip=pymupdf.Rect(270, 0, 330, 400))
    assert "1" in giua, "phải in số trang gốc (đánh số từ 1) ở giữa khổ"
    ra.close(); dich.close(); src.close()
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_pdf_overlay.py -k "trang_dich or kho_doi" -v`
Expected: FAIL với `AttributeError: module 'render.pdf_overlay' has no attribute 'trang_dich'`.

- [ ] **Step 3: Thêm `trang_dich` và `ghep_kho_doi`**

Chèn vào cuối `render/pdf_overlay.py`:

```python
# Cỡ chữ của số trang in giữa khổ đôi.
CO_SO_TRANG = 7.0


def trang_dich(src_doc, page_no: int, khoi: list, kho=None,
               ghi_nhan=None) -> "pymupdf.Document":
    """Tài liệu một trang: bản sao trang gốc, chữ Anh thay bằng chữ Việt.

    `khoi` là list dict {bbox, html, size, id?}. `ghi_nhan`, nếu truyền vào, sẽ
    nhận thêm một tuple (id, tỉ lệ, tràn) cho mỗi khối đã đặt.

    Trang không có khối nào thì trả về
    bản sao nguyên vẹn — trang chưa dịch phải hiện bản gốc, không phải trang
    trắng.

    Trả về tài liệu mới; người gọi có trách nhiệm đóng.
    """
    if kho is None:
        kho = pdf_font.dung_archive(pdf_font.chon_bo_font())

    d = pymupdf.open()
    d.insert_pdf(src_doc, from_page=page_no, to_page=page_no)
    page = d[0]

    hop_le = [k for k in khoi
              if k["bbox"].width > 0 and k["bbox"].height > 0 and k["html"].strip()]
    if not hop_le:
        return d

    xoa_chu(page, [k["bbox"] for k in hop_le])
    for k in hop_le:
        ti_le, bi_tran = dat_chu(page, k["bbox"], k["html"], k["size"], kho)
        if ghi_nhan is not None:
            ghi_nhan.append((k.get("id"), ti_le, bi_tran))
    return d


def ghep_kho_doi(src_doc, cap: list) -> "pymupdf.Document":
    """Khổ ngang rộng gấp đôi: trang gốc bên trái, trang dịch bên phải.

    `cap` là list (page_no, tài liệu một trang đã dịch), đúng thứ tự muốn xuất.
    Dán ở dạng vector bằng show_pdf_page nên chữ vẫn bôi đen và tìm kiếm được,
    ảnh vẫn nguyên độ nét, và hai bên dùng chung tài nguyên nên file không
    phình gấp đôi.
    """
    ra = pymupdf.open()
    for page_no, dich in cap:
        goc = src_doc[page_no].rect
        kho_ngang = ra.new_page(width=goc.width * 2, height=goc.height)
        kho_ngang.show_pdf_page(pymupdf.Rect(0, 0, goc.width, goc.height),
                                src_doc, page_no)
        kho_ngang.show_pdf_page(pymupdf.Rect(goc.width, 0, goc.width * 2, goc.height),
                                dich, 0)
        # Số trang gốc in giữa khổ để luôn biết đang ở đâu so với sách giấy.
        nhan = f"{page_no + 1}"
        rong = len(nhan) * CO_SO_TRANG * 0.6
        kho_ngang.insert_text((goc.width - rong / 2, goc.height - 6),
                              nhan, fontsize=CO_SO_TRANG)
    return ra
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_pdf_overlay.py -v`
Expected: 21 passed.

- [ ] **Step 5: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 191 passed.

- [ ] **Step 6: Commit**

```bash
git add render/pdf_overlay.py tests/test_pdf_overlay.py
git commit -m "feat: dựng trang dịch và ghép khổ đôi

Trang dịch là BẢN SAO trang gốc đã thay chữ, không phải trang dựng lại,
nên ảnh và bố cục giữ nguyên. Trang chưa dịch đoạn nào thì hiện bản gốc
chứ không ra trang trắng. Ghép bằng show_pdf_page ở dạng vector."
```

---

## Task 6: Nối vào `export` — `--mode`, `--pages`, `--dry-run`, `--probe`

**Files:**
- Modify: `render/pdf_overlay.py`
- Modify: `render/__init__.py`
- Modify: `cli.py`
- Create: `tests/test_export_pdf.py`

**Interfaces:**
- Consumes: `trang_dich`, `ghep_kho_doi` từ Task 5; `db.connect`; bảng `blocks`.
- Produces:
  - `render.pdf_overlay.write(project, con, out_path, *, pages=None, dry_run=False, probe=False) -> dict` — trả về thống kê `{so_trang, so_khoi, tran, co_trung_vi}`.
  - `render.write(fmt, project, con, out_path, *, bilingual=False, mode="overlay", pages=None, dry_run=False, probe=False)`.
  - `render.UnsupportedTarget` nay cũng dùng cho `mode` chưa làm.

- [ ] **Step 1: Viết test cho export PDF**

Tạo `tests/test_export_pdf.py`:

```python
"""Xuất PDF khổ đôi từ project. Không gọi mạng, không tốn token."""
import argparse

import pymupdf
import pytest

import cli
import db
import render
from helpers import build_pdf, run_init, trang_mot_doan


@pytest.fixture
def proj(tmp_path):
    src = build_pdf(tmp_path / "m.pdf", [
        [{"text": "Chuong Mot", "x": 67, "y": 80, "size": 14}] + trang_mot_doan(120, 4),
        trang_mot_doan(80, 3, tien_to="hai"),
        trang_mot_doan(80, 3, tien_to="ba"),
    ])
    p = run_init(src, tmp_path / "proj")
    con = db.connect(p)
    for r in con.execute("SELECT id, src_html FROM blocks").fetchall():
        con.execute("UPDATE blocks SET dst_html=? WHERE id=?",
                    (f"Bản dịch tiếng Việt của đoạn {r['id']}", r["id"]))
    con.commit()
    return p


def test_xuat_ra_file_kho_ngang(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out)
    d = pymupdf.open(out)
    assert d.page_count == 3
    assert d[0].rect.width == 522 * 2 and d[0].rect.height == 666
    d.close()


def test_ban_dich_nam_ben_phai(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out)
    d = pymupdf.open(out)
    phai = d[0].get_text(clip=pymupdf.Rect(522, 0, 1044, 666))
    assert "Bản dịch" in phai
    d.close()


def test_loc_theo_khoang_trang(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, pages=(1, 2))
    d = pymupdf.open(out)
    assert d.page_count == 2
    d.close()


def test_dry_run_khong_can_ban_dich(proj, tmp_path):
    """--dry-run đè CHÍNH chữ gốc trở lại, kèm chữ độn cho dài ra như tiếng
    Việt. Lệch chỗ nào là lỗi bóc chữ, chắc chắn không phải lỗi dịch."""
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html=NULL")
    con.commit()
    out = tmp_path / "thu.pdf"
    tk = render.write("pdf", proj, db.connect(proj), out, dry_run=True)
    assert out.exists() and tk["so_khoi"] > 0


def test_probe_them_trang_bao_cao_o_dau(proj, tmp_path):
    out = tmp_path / "ra.pdf"
    render.write("pdf", proj, db.connect(proj), out, probe=True)
    d = pymupdf.open(out)
    assert d.page_count == 4, "phải có 1 trang báo cáo + 3 khổ"
    bao_cao = d[0].get_text()
    assert "tràn" in bao_cao.lower() or "overflow" in bao_cao.lower()
    d.close()


def test_thong_ke_tra_ve_du_so_lieu(proj, tmp_path):
    tk = render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf")
    assert set(tk) >= {"so_trang", "so_khoi", "tran", "co_trung_vi"}
    assert tk["so_trang"] == 3 and tk["so_khoi"] > 0


def test_mode_reflow_bi_tu_choi_ro_rang(proj, tmp_path):
    with pytest.raises(render.UnsupportedTarget, match="Phase 6"):
        render.write("pdf", proj, db.connect(proj), tmp_path / "ra.pdf", mode="reflow")


def test_epub_khong_dung_duoc_mode_overlay(source_epub, tmp_path):
    """overlay cần toạ độ PDF mà EPUB không có."""
    p = run_init(source_epub, tmp_path / "proj")
    with pytest.raises(render.UnsupportedTarget, match="EPUB"):
        render.write("epub", p, db.connect(p), tmp_path / "ra.epub", mode="overlay")


def test_cli_export_pdf_chay_duoc(proj, tmp_path, capsys):
    out = tmp_path / "cli.pdf"
    cli.cmd_export(argparse.Namespace(project=str(proj), output=str(out),
                                      bilingual=False, mode="overlay",
                                      pages=None, dry_run=False, probe=False))
    assert out.exists()
    assert "Đã xuất" in capsys.readouterr().out
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_export_pdf.py -v`
Expected: FAIL với `render.UnsupportedTarget: chưa ghi ra được định dạng 'pdf'. PDF là Phase 4.`

- [ ] **Step 3: Thêm `write` vào `render/pdf_overlay.py`**

Chèn vào cuối file:

```python
# Chữ độn cho --dry-run: kéo dài chữ gốc thêm ~25% để mô phỏng tiếng Việt.
TI_LE_DON = 0.25


def _don_cho_dai_ra(html: str) -> str:
    """Nối thêm một phần chính nó, để thử sức chứa mà không cần bản dịch."""
    them = html[: max(1, int(len(html) * TI_LE_DON))]
    return f"{html} {them}"


def write(project, con, out_path, *, pages=None,
          dry_run=False, probe=False) -> dict:
    """Xuất PDF khổ đôi. Trả về thống kê để `export` in ra và `--probe` dùng."""
    fmt = "pdf"
    nguon = pymupdf.open(str(_duong_nguon(project, con, fmt)))
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())

    cot = ("SELECT id, page_no, bbox, layout, "
           "       COALESCE(dst_html, '') dst, src_html "
           "FROM blocks WHERE bbox IS NOT NULL")
    tham = ()
    if pages:
        cot += " AND page_no BETWEEN ? AND ?"
        tham = pages
    cot += " ORDER BY page_no, pos"

    theo_trang = {}
    for r in con.execute(cot, tham):
        noi_dung = _don_cho_dai_ra(r["src_html"]) if dry_run else r["dst"]
        if not noi_dung.strip():
            continue
        x0, y0, x1, y1 = (float(v) for v in r["bbox"].split(","))
        lay = json.loads(r["layout"] or "{}")
        theo_trang.setdefault(r["page_no"], []).append(
            {"id": r["id"], "bbox": pymupdf.Rect(x0, y0, x1, y1),
             "html": noi_dung, "size": float(lay.get("size") or 10.0)})

    dau, cuoi = pages if pages else (0, nguon.page_count - 1)
    dau, cuoi = max(0, dau), min(nguon.page_count - 1, cuoi)

    cap, ti_le_all, tran = [], [], []
    for pno in range(dau, cuoi + 1):
        ket = []
        d = trang_dich(nguon, pno, theo_trang.get(pno, []), kho, ghi_nhan=ket)
        for bid, ti_le, bi_tran in ket:
            ti_le_all.append(ti_le)
            if bi_tran:
                tran.append((pno, bid))
        cap.append((pno, d))

    ra = ghep_kho_doi(nguon, cap)
    tk = {"so_trang": len(cap), "so_khoi": len(ti_le_all),
          "tran": len(tran),
          "co_trung_vi": statistics.median(ti_le_all) if ti_le_all else 1.0}
    if probe:
        _chen_trang_bao_cao(ra, tk, tran, ti_le_all)

    ra.save(str(out_path), garbage=3, deflate=True)
    ra.close()
    for _, d in cap:
        d.close()
    nguon.close()

    # Cờ overflow ghi vào cột flag để `status` đếm được.
    for pno, bid in tran:
        con.execute("UPDATE blocks SET flag='overflow' WHERE id=?", (bid,))
    if tran:
        con.commit()
    return tk


def _duong_nguon(project, con, fmt):
    ten = db.get_meta(con, "source_format", fmt)
    return Path(project) / f"source.{ten}"


def _chen_trang_bao_cao(ra, tk, tran, ti_le_all):
    """Trang đầu file: soi ngay được layout có ổn không, không cần đọc hết."""
    trang = ra.new_page(width=ra[0].rect.width, height=ra[0].rect.height)
    ra.move_page(ra.page_count - 1, 0)
    duoi = [t for t in ti_le_all if t < 0.85]
    dong = [
        "BÁO CÁO DỰNG TRANG (--probe)",
        "",
        f"Khổ đã dựng        : {tk['so_trang']}",
        f"Khối đã đặt chữ    : {tk['so_khoi']}",
        f"Tỉ lệ cỡ chữ trung vị: {tk['co_trung_vi']:.0%}",
        f"Khối phải co dưới 85%: {len(duoi)}",
        f"Khối tràn khung     : {tk['tran']}",
        "",
        "Tràn khung nghĩa là không vừa ngay cả ở đáy thang; xem `status`.",
    ]
    for i, d in enumerate(dong[:12]):
        trang.insert_text((40, 60 + i * 16), d, fontsize=11)
    for i, (pno, bid) in enumerate(tran[:20]):
        trang.insert_text((40, 260 + i * 13),
                          f"  tràn: trang {pno}, block {bid}", fontsize=9)
```

- [ ] **Step 4: Cho `render/__init__.py` định tuyến và nhận `mode`**

Viết lại `write` trong `render/__init__.py`. `mode=None` nghĩa là "tự suy ra
theo định dạng" — phải phân biệt được với việc người dùng **nêu rõ** `overlay`
cho một project EPUB, vì đó là chỗ cần từ chối:

```python
def write(fmt: str, project, con, out_path, *, bilingual: bool = False,
          mode=None, pages=None, dry_run: bool = False, probe: bool = False):
    if mode is not None and mode not in ("overlay", "reflow"):
        raise UnsupportedTarget(f"chế độ '{mode}' không có. Chọn overlay hoặc reflow.")
    if mode == "reflow":
        raise UnsupportedTarget(
            "chế độ 'reflow' (dựng lại trang) là Phase 6, chưa làm."
        )

    if fmt == "epub":
        if mode == "overlay":
            raise UnsupportedTarget(
                "EPUB không có toạ độ trang nên không dùng được chế độ overlay."
            )
        if pages or dry_run or probe:
            raise UnsupportedTarget(
                "EPUB không có toạ độ trang nên không dùng được --pages, "
                "--dry-run hay --probe."
            )
        from render import epub as adapter
        adapter.write(project, con, out_path, bilingual=bilingual)
        return None

    if fmt == "pdf":
        from render import pdf_overlay as adapter
        return adapter.write(project, con, out_path, pages=pages,
                             dry_run=dry_run, probe=probe)

    raise UnsupportedTarget(f"chưa ghi ra được định dạng '{fmt}'.")
```

- [ ] **Step 5: Thêm cờ vào `cmd_export` và `main` trong `cli.py`**

Trong `cmd_export`, thay lời gọi `render.write` và in thống kê:

```python
    try:
        tk = render.write(fmt, proj, con, out, bilingual=args.bilingual,
                          mode=args.mode, pages=parse_pages(args.pages),
                          dry_run=args.dry_run, probe=args.probe)
    except (render.UnsupportedTarget, pdf_font.ThieuFont) as e:
        die(str(e))
    print(f"Đã xuất: {out}")
    if tk:
        print(f"  {tk['so_trang']} khổ, {tk['so_khoi']} khối, "
              f"cỡ chữ trung vị {tk['co_trung_vi']:.0%}, {tk['tran']} khối tràn khung.")
```

Thêm `import pdf_font` ở đầu `cli.py`, và trong `main` thêm cờ cho `export`:

```python
    p.add_argument("--mode", choices=("overlay", "reflow"),
                   help="overlay: đè chữ lên trang gốc (mặc định cho PDF). "
                        "reflow: dựng lại trang (Phase 6)")
    p.add_argument("--pages", help="khoảng trang, ví dụ 1-20")
    p.add_argument("--dry-run", action="store_true",
                   help="đè chính chữ gốc kèm chữ độn — kiểm layout, không tốn token")
    p.add_argument("--probe", action="store_true",
                   help="thêm trang báo cáo dựng trang ở đầu file")
```

- [ ] **Step 6: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_export_pdf.py -v`
Expected: 10 passed.

- [ ] **Step 7: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 201 passed. Hai vân tay EPUB vẫn PASS.

- [ ] **Step 8: Commit**

```bash
git add render/ cli.py tests/test_export_pdf.py
git commit -m "feat: export PDF khổ đôi, với --mode, --pages, --dry-run, --probe

--dry-run đè chính chữ gốc kèm chữ độn cho dài ra như tiếng Việt: lệch
chỗ nào là lỗi bóc chữ, chắc chắn không phải lỗi dịch, và không tốn một
token nào. --probe thêm trang báo cáo ở đầu file. Khối tràn khung được
gắn cờ overflow để status đếm được."
```

---

## Task 7: Nghiệm thu trên sách thật

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: toàn bộ Task 1-6.
- Produces: không có API mới.

- [ ] **Step 1: Dựng project từ sách thật**

```bash
.venv/bin/python cli.py init ebook/astrology.pdf.pdf --dir /tmp/bt-p4 --force
```

Expected: `Xong: ~10400 đoạn, ~2,5 triệu ký tự, ~590 chunk.`

- [ ] **Step 2: Xuất thử 20 trang bằng `--dry-run --probe`**

```bash
.venv/bin/python cli.py export /tmp/bt-p4 --pages 150-169 --dry-run --probe \
    -o /tmp/bt-p4/thu.pdf
```

Expected: in ra `Đã xuất`, kèm dòng thống kê có `cỡ chữ trung vị` và số khối tràn khung.

- [ ] **Step 3: NGHIỆM THU — mở file ra soi**

```bash
open /tmp/bt-p4/thu.pdf
```

**Đây là bước soi bằng mắt, không phải bước chạy cho có.** Kiểm năm điều:

1. **Khổ đôi đúng chiều**: bản gốc bên trái, bản đè bên phải, số trang ở giữa.
2. **Vị trí khối khớp nhau**: các khối chữ bên phải nằm đúng chỗ như bên trái. Lệch là lỗi bóc chữ của Phase 3, không phải lỗi Phase 4.
3. **Ảnh không bị khoét**: tìm trang có hình; vùng từng có chữ đè lên hình phải còn nguyên hình, không có mảng trắng.
4. **Không có ô vuông rỗng**: `--dry-run` đè chữ tiếng Anh nên chưa thử hết dấu; chạy thêm bước 4 để thử riêng dấu tiếng Việt.
5. **Trang báo cáo ở đầu**: trung vị cỡ chữ phải quanh 95-100% (đo thật lúc lập kế hoạch: 98%), số khối tràn khung phải nhỏ.

- [ ] **Step 4: Thử riêng dấu tiếng Việt trên sách thật**

```bash
.venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, '.')
import db, render
proj = "/tmp/bt-p4"
con = db.connect(proj)
con.execute("UPDATE blocks SET dst_html='Những chữ khó: ặ ữ ổ ỹ ằ ẵ ợ ự ỡ ẫ Đ đ' "
            "WHERE page_no BETWEEN 150 AND 152")
con.commit()
render.write("pdf", proj, con, "/tmp/bt-p4/dau.pdf", pages=(150, 152))
print("đã xuất /tmp/bt-p4/dau.pdf")
EOF
open /tmp/bt-p4/dau.pdf
```

Expected: mọi chữ có dấu hiện đúng. **Một ô vuông rỗng nào cũng là hỏng** — quay lại Task 2.

- [ ] **Step 5: Cập nhật README**

Thêm vào sau phần `## Quy trình`:

```markdown
## Xuất PDF khổ đôi (sách nguồn là PDF)

```bash
# Kiểm layout trước, không tốn token: đè chính chữ gốc kèm chữ độn
python cli.py export projects/sach --pages 1-20 --dry-run --probe

# Ưng thì dịch rồi xuất thật
python cli.py translate projects/sach --pages 1-20
python cli.py export    projects/sach --pages 1-20
```

Mỗi khổ ngang gồm trang gốc bên trái và bản dịch bên phải. Trang dịch là bản
sao trang gốc đã thay chữ, nên ảnh và bố cục giữ nguyên.

Font mặc định lấy từ hệ thống macOS. Máy khác thì trỏ font đủ dấu tiếng Việt
qua biến môi trường:

```bash
export BOOKTRANS_FONT=/duong/dan/Regular.ttf:/duong/dan/Bold.ttf:/duong/dan/Italic.ttf
```
```

- [ ] **Step 6: Dọn và commit**

```bash
rm -rf /tmp/bt-p4
git add README.md
git commit -m "docs: hướng dẫn xuất PDF khổ đôi và cấu hình font

Phase 4 xong: chế độ overlay đè chữ Việt lên bản sao trang gốc, ghép
khổ đôi, và --dry-run kiểm layout mà không tốn token."
```

---

## Nghiệm thu Phase 4

1. `.venv/bin/python -m pytest tests/ -q` — 201 passed, không test nào gọi mạng.
2. `git log --oneline -- tests/golden/` vẫn chỉ có đúng một commit.
3. `export --dry-run --probe` trên 20 trang thật ra file khổ ngang, vị trí khối bên phải khớp bên trái, ảnh không bị khoét.
4. Chữ tiếng Việt có dấu hiện đúng, không ô vuông nào.
5. **Không một token API nào bị tiêu trong cả Phase 4.**
6. `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py` ra rỗng.

Điều kiện 6 giữ nguyên ranh giới đã dựng ở Phase 3: `render/pdf_overlay.py` và `ingest/pdf_text.py` là hai chỗ duy nhất biết PyMuPDF tồn tại.
