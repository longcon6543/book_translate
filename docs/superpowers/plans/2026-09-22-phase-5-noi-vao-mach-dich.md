# Phase 5 — Nối vào mạch dịch

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho người dùng dịch theo khoảng trang, duyệt thuật ngữ trước khi dịch, thấy được đoạn nào đáng ngờ, và sửa tay một đoạn rồi xuất lại — tức là biến một cái máy dịch cả cuốn thành một vòng làm việc có thể dừng, soi và sửa.

**Architecture:** Phần lõi không đổi. Thêm hai module hàm thuần (`glossary.py` để trích ứng viên, và một hàm chọn chunk trong `chunking.py`), mở rộng `check_translation` trong `translator.py`, và bốn chỗ nối ở `cli.py`. Không đụng `ingest/`, `render/`, `pdf_layout.py`.

**Tech Stack:** Python 3.12.6, SQLite 3.45.3, pytest 9.1.1.

**Spec:** `docs/superpowers/specs/2026-09-21-pdf-song-ngu-design.md` (mục 7 và mục 10 Phase 5)

## Global Constraints

- 214 test hiện có phải **giữ nguyên xanh**, gồm hai vân tay trong `tests/golden/`.
- **Không test nào gọi mạng.** Test dịch dùng provider giả, theo đúng cách `tests/test_translate_chunk.py` đang làm.
- Chỉ Task 6 tiêu token API, và nó **phải hỏi người dùng trước** — đây là tiền của họ.
- `pdf_layout.py` tiếp tục không import PyMuPDF; `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py` ra rỗng.
- Không thêm cột mới vào `blocks` hay `chunks`.
- Cột `flag` dùng chung: giá trị hợp lệ là `tag_mismatch` / `too_short` / `empty` / `overflow` cộng hai giá trị mới của phase này. Cờ layout (`overflow`) không được đè cờ chất lượng — luật đã có từ Phase 4.
- `--pages` đếm từ 1, quy đổi ở `cli.parse_pages` như Phase 4 đã làm.
- Docstring và comment viết tiếng Việt, khớp code đang có.
- Mỗi task kết thúc bằng đúng một commit.

## Dữ liệu thật đã đo — đừng phỏng đoán lại

Đo trên `ebook/astrology.pdf.pdf`: 10.411 đoạn, 593 chunk, 909 trang có chữ.

| Câu hỏi | Kết quả đo |
|---|---|
| Chunk có vắt ngang trang không | **55%** có (trung vị 2 trang, nhiều nhất 6) |
| Chọn mọi chunk chạm khoảng trang thì dư mấy trang | trang 1–20 dư **1**; 150–169 dư **2**; 300–319 dư **0** |
| Từ viết hoa khác nhau trong sách | 8.959 |
| Số từ xuất hiện ≥20 / ≥50 / ≥100 lần | 568 / **224** / 104 |
| Nhiễu trong top 200 | 29 từ chức năng (14%), 31 từ >90% đứng đầu câu |
| Sau khi lọc, từ thứ 200 xuất hiện | **45 lần** |
| Đoạn chứa chữ số | **50%** |
| Đoạn chứa từ viết hoa | **95%** |

### Ba điều dữ liệu thật quyết định thay cho phỏng đoán

**1. Không cắt chunk theo trang.** 55% chunk vắt ngang trang, nên `--pages 1-20` không khớp gọn vào ranh giới chunk. Nhưng đo thật cho thấy chọn mọi chunk *chạm* vào khoảng chỉ dư 0–2 trang. Cắt chunk ra để khớp chính xác sẽ phá mất ngữ cảnh 3 đoạn liền trước mà `translate_chunk` đang dùng, để đổi lấy 0–2 trang. Không đáng. Chọn chunk chồng lấn, rồi **báo lại vùng phủ thật** để người dùng biết mình vừa trả tiền cho những trang nào.

**2. Spec mục 7 nói "kiểm tra số và tên riêng" — nửa sau không dùng được.** 95% số đoạn chứa từ viết hoa, và tên riêng thì *được dịch*: một cái tên sang tiếng Việt vẫn viết hoa nhưng không còn ký tự nào giống bản gốc. Kiểm kiểu đó sẽ kêu ở gần như mọi đoạn, và một cảnh báo kêu ở mọi đoạn thì bằng không có cảnh báo.

Chữ số thì ngược lại: 50% số đoạn có số, và số **phải** sang bản dịch nguyên vẹn. Kiểm được thật.

Nên thiết kế là: kiểm chữ số nghiêm ngặt, còn thuật ngữ thì **chỉ kiểm những mục người dùng đã khai trong `glossary.txt`** — đúng chỗ họ đã tuyên bố muốn dịch thành gì. Vừa chính xác, vừa khiến `glossary.txt` có tác dụng thật chứ không chỉ nằm trong prompt.

**3. `--top 200` là mặc định đúng.** Sau khi lọc từ chức năng và từ chỉ đứng đầu câu, ứng viên thứ 200 vẫn xuất hiện 45 lần trong một cuốn 900 trang — tức vẫn là thuật ngữ đáng khai. Lấy sâu hơn (≥20 lần → 568 từ) là quá nhiều để duyệt bằng mắt.

## Review Focus

Năm trường hợp spec ngụ ý nhưng không task nào tự nhiên chạm tới.

1. **`--pages` trỏ vào khoảng không còn chunk nào cần dịch** (đã dịch hết, hoặc ngoài sách) — phải nói rõ và **không gọi API lần nào**, chứ không im lặng chạy rỗng. → Task 1.
2. **`glossary.txt` có dòng hỏng, rỗng, hoặc không tồn tại** — việc kiểm tra không được vỡ; không có glossary thì chỉ kiểm chữ số. → Task 3.
3. **Mục glossary có bản dịch trùng bản gốc** (`Winterfell = Winterfell`, giữ nguyên tên) — không được báo thiếu thuật ngữ một cách oan uổng. → Task 3.
4. **`edit` với id đoạn không tồn tại** — báo lỗi rõ, không traceback, không âm thầm không làm gì. → Task 4.
5. **Dừng `translate --pages` giữa chừng rồi chạy lại** — phải tiếp đúng khoảng trang đó, không nhảy sang chunk khác. → Task 1.

---

## File Structure

Tạo mới:

| File | Trách nhiệm |
|---|---|
| `glossary.py` | **Hàm thuần**: trích ứng viên thuật ngữ, đọc/ghi file glossary |
| `tests/test_glossary.py` | Test trích ứng viên |
| `tests/test_chon_chunk.py` | Test chọn chunk theo khoảng trang |
| `tests/test_kiem_tra.py` | Test kiểm chữ số và thuật ngữ |
| `tests/test_edit.py` | Test lệnh `edit` |

Sửa:

| File | Thay đổi |
|---|---|
| `chunking.py` | Thêm `chunks_cho_trang()` — hàm thuần |
| `translator.py` | `check_translation` nhận thêm bảng thuật ngữ; hai mã lỗi mới |
| `cli.py` | `translate --pages`; lệnh `glossary`; lệnh `edit`; `status` mở rộng |

**Vì sao `glossary.py` nằm ở gốc:** `translator.py` đã đọc `glossary.txt` để dựng prompt, và nay `check_translation` cũng cần nó để kiểm. Hai chỗ dùng chung một cách đọc file thì cách đọc đó phải nằm riêng, không nằm trong `translator.py`.

---

## Task 1: `translate --pages`

**Files:**
- Modify: `chunking.py`
- Modify: `cli.py`
- Create: `tests/test_chon_chunk.py`

**Interfaces:**
- Produces: `chunking.chunks_cho_trang(trang_theo_chunk, khoang) -> (list[int], tuple|None)` — trả về (danh sách chunk_id đã sắp, vùng phủ thật `(min, max)` hoặc `None` nếu không chunk nào).

- [ ] **Step 1: Viết test cho chọn chunk**

Tạo `tests/test_chon_chunk.py`:

```python
"""Chọn chunk theo khoảng trang. Hàm thuần: không DB, không mạng."""
from chunking import chunks_cho_trang


def test_chunk_nam_gon_trong_khoang():
    m = {1: {0, 1}, 2: {2, 3}, 3: {8, 9}}
    ids, phu = chunks_cho_trang(m, (0, 3))
    assert ids == [1, 2]
    assert phu == (0, 3)


def test_chunk_vat_ngang_bien_van_duoc_chon_va_bao_vung_phu_that():
    """55% chunk của sách thật vắt ngang trang. Chọn chunk chạm vào khoảng thì
    kéo theo vài trang ngoài khoảng — phải báo lại cho người dùng biết."""
    m = {1: {0, 1}, 2: {1, 2, 3}, 3: {3, 4, 5}}
    ids, phu = chunks_cho_trang(m, (0, 3))
    assert ids == [1, 2, 3]
    assert phu == (0, 5), "phải báo vùng phủ THẬT, không phải khoảng đã xin"


def test_khong_chunk_nao_cham_vao_khoang():
    m = {1: {0, 1}, 2: {2, 3}}
    ids, phu = chunks_cho_trang(m, (50, 60))
    assert ids == [] and phu is None


def test_bo_qua_trang_gia_cua_epub():
    """page_no âm là mục lục và tên sách (EPUB). --pages nói về trang thật."""
    m = {1: {-2}, 2: {-1}, 3: {0, 1}}
    ids, phu = chunks_cho_trang(m, (0, 1))
    assert ids == [3]


def test_chunk_chi_toan_trang_gia_khong_bao_gio_duoc_chon():
    m = {1: {-1, -2}}
    ids, phu = chunks_cho_trang(m, (0, 100))
    assert ids == []


def test_ket_qua_luon_sap_theo_id():
    m = {9: {0}, 3: {1}, 7: {2}}
    ids, _ = chunks_cho_trang(m, (0, 2))
    assert ids == [3, 7, 9]


def test_khoang_mot_trang():
    m = {1: {5}, 2: {6}}
    ids, phu = chunks_cho_trang(m, (5, 5))
    assert ids == [1] and phu == (5, 5)


def test_ban_do_rong():
    assert chunks_cho_trang({}, (0, 10)) == ([], None)
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_chon_chunk.py -q`
Expected: FAIL với `ImportError: cannot import name 'chunks_cho_trang' from 'chunking'`.

- [ ] **Step 3: Thêm `chunks_cho_trang` vào `chunking.py`**

Chèn vào cuối file:

```python
def chunks_cho_trang(trang_theo_chunk: dict, khoang: tuple) -> tuple:
    """Chọn mọi chunk CHẠM vào khoảng trang. Trả về (chunk_id đã sắp, vùng phủ).

    Không cắt chunk cho khớp khoảng. Đo thật trên sách mẫu: 55% chunk vắt
    ngang nhiều trang, nhưng chọn kiểu chồng lấn chỉ dư 0-2 trang. Cắt chunk
    ra để khớp chính xác sẽ phá mất ngữ cảnh ba đoạn liền trước mà
    `translate_chunk` dựa vào, đổi lấy 0-2 trang — không đáng.

    Vùng phủ trả về là vùng THẬT sẽ được dịch, không phải khoảng đã xin, để
    người dùng biết mình vừa trả tiền cho những trang nào.

    page_no âm là khối giả của EPUB (mục lục, tên sách); `--pages` nói về
    trang thật nên chúng không bao giờ được chọn theo đường này.
    """
    dau, cuoi = khoang
    chon = []
    for cid, trang in trang_theo_chunk.items():
        that = {p for p in trang if p >= 0}
        if any(dau <= p <= cuoi for p in that):
            chon.append(cid)

    if not chon:
        return [], None

    phu = {p for cid in chon for p in trang_theo_chunk[cid] if p >= 0}
    return sorted(chon), (min(phu), max(phu))
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_chon_chunk.py -q`
Expected: 8 passed.

- [ ] **Step 5: Viết test cho `translate --pages` ở mức lệnh**

Chèn vào cuối `tests/test_translate_chunk.py`:

```python
def test_translate_chi_dich_chunk_trong_khoang_trang(source_epub, tmp_path, capsys,
                                                    monkeypatch):
    """Dựng project rồi xin dịch một khoảng: chỉ những chunk chạm khoảng đó
    được gọi API, và lệnh phải báo vùng phủ thật."""
    import argparse

    import cli

    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    tong = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    assert tong >= 2, "EPUB mẫu phải có ít nhất 2 chunk để test có nghĩa"

    goi = []

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            goi.append(user)
            return echo_segments(user), USAGE, "end_turn"

    monkeypatch.setattr(cli.providers, "get", lambda ten: P([]))
    cli.cmd_translate(argparse.Namespace(
        project=str(proj), provider="fake", model="fake-1",
        limit=None, pages="1-1"))

    ra = capsys.readouterr().out
    assert "trang" in ra, "phải báo vùng trang đã dịch"
    con2 = db.connect(proj)
    xong = con2.execute("SELECT COUNT(*) FROM chunks WHERE status='done'").fetchone()[0]
    assert 0 < xong < tong, f"phải dịch một phần, không phải tất cả ({xong}/{tong})"


def test_translate_khoang_trang_khong_con_gi_thi_khong_goi_api(
        source_epub, tmp_path, capsys, monkeypatch):
    """Review Focus 1: khoảng rỗng thì nói rõ và KHÔNG tốn một lần gọi nào."""
    import argparse

    import cli

    proj = run_init(source_epub, tmp_path / "proj")
    goi = []

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            goi.append(user)
            return echo_segments(user), USAGE, "end_turn"

    monkeypatch.setattr(cli.providers, "get", lambda ten: P([]))
    cli.cmd_translate(argparse.Namespace(
        project=str(proj), provider="fake", model="fake-1",
        limit=None, pages="900-999"))

    assert goi == [], "đã gọi API dù khoảng trang rỗng"
    assert "không có chunk nào" in capsys.readouterr().out.lower()
```

Và một test nữa cho Review Focus 5:

```python
def test_chay_lai_van_ton_trong_dung_khoang_trang(source_epub, tmp_path,
                                                  capsys, monkeypatch):
    """Dừng giữa chừng rồi chạy lại phải tiếp đúng khoảng trang đó, không
    nhảy sang chunk ngoài khoảng."""
    import argparse

    import cli

    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    trong_khoang = {r["chunk_id"] for r in con.execute(
        "SELECT DISTINCT chunk_id FROM blocks WHERE page_no = 0")}

    da_goi = []

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            da_goi.append(user)
            return echo_segments(user), USAGE, "end_turn"

    monkeypatch.setattr(cli.providers, "get", lambda ten: P([]))
    lenh = argparse.Namespace(project=str(proj), provider="fake",
                              model="fake-1", limit=1, pages="1-1")
    cli.cmd_translate(lenh)                      # lượt 1: chỉ 1 chunk
    lenh.limit = None
    cli.cmd_translate(lenh)                      # lượt 2: phần còn lại

    con2 = db.connect(proj)
    xong = {r[0] for r in con2.execute(
        "SELECT id FROM chunks WHERE status='done'")}
    assert xong <= trong_khoang, (
        f"đã dịch chunk ngoài khoảng: {xong - trong_khoang}")
```

- [ ] **Step 6: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_translate_chunk.py -q`
Expected: FAIL — `cmd_translate` chưa nhận `pages`, báo `AttributeError` hoặc `TypeError`.

- [ ] **Step 7: Nối `--pages` vào `cmd_translate`**

Trong `cli.py`, hàm `cmd_translate`, thay khối lấy `todo`:

```python
    todo = [r["id"] for r in con.execute(
        "SELECT id FROM chunks WHERE status != 'done' ORDER BY id")]
    total_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
```

bằng:

```python
    total_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    chua_xong = [r["id"] for r in con.execute(
        "SELECT id FROM chunks WHERE status != 'done' ORDER BY id")]

    khoang = parse_pages(getattr(args, "pages", None))
    if khoang:
        trang_theo_chunk = {}
        for r in con.execute(
            "SELECT chunk_id, page_no FROM blocks WHERE chunk_id IS NOT NULL"
        ):
            trang_theo_chunk.setdefault(r["chunk_id"], set()).add(r["page_no"])
        trong_khoang, phu = chunking.chunks_cho_trang(trang_theo_chunk, khoang)
        todo = [c for c in chua_xong if c in set(trong_khoang)]
        if not todo:
            print("Không có chunk nào cần dịch trong khoảng trang này.")
            return
        # Vùng phủ THẬT, không phải khoảng đã xin: chunk vắt ngang trang kéo
        # theo vài trang ngoài khoảng, và người dùng đang trả tiền cho chúng.
        print(f"Khoảng trang {khoang[0] + 1}-{khoang[1] + 1} "
              f"-> thực dịch trang {phu[0] + 1}-{phu[1] + 1}.")
    else:
        todo = chua_xong

    if not todo:
        print("Không còn chunk nào cần dịch. Chạy `export` để xuất file.")
        return
```

Xoá dòng `if not todo:` cũ nằm ngay sau đó (nay đã gộp vào khối trên), và thêm `import chunking` nếu chưa có ở đầu `cli.py`.

Trong `main`, thêm cờ cho `translate`:

```python
    p.add_argument("--pages", help="chỉ dịch các chunk chạm khoảng trang, ví dụ 1-20")
```

- [ ] **Step 8: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 225 passed.

- [ ] **Step 9: Commit**

```bash
git add chunking.py cli.py tests/test_chon_chunk.py tests/test_translate_chunk.py
git commit -m "feat: translate --pages, dịch theo khoảng trang

Không cắt chunk cho khớp khoảng: 55% chunk của sách thật vắt ngang
trang, nhưng chọn chunk chồng lấn chỉ dư 0-2 trang, trong khi cắt ra
sẽ phá mất ngữ cảnh ba đoạn liền trước. Lệnh báo lại vùng phủ THẬT để
người dùng biết mình đang trả tiền cho những trang nào."
```

---

## Task 2: Lệnh `glossary` — trích ứng viên thuật ngữ

**Files:**
- Create: `glossary.py`
- Create: `tests/test_glossary.py`
- Modify: `cli.py`

**Interfaces:**
- Produces:
  - `glossary.TU_CHUC_NANG` — frozenset từ chức năng tiếng Anh.
  - `glossary.ung_vien(doan, top=200) -> list[(str, int)]` — `doan` là iterable các chuỗi HTML.
  - `glossary.doc_bang(duong_dan) -> dict[str, str]` — đọc `glossary.txt` thành `{en: vi}`.
  - `glossary.ghi_ung_vien(duong_dan, ds) -> None`.

- [ ] **Step 1: Viết test cho trích ứng viên**

Tạo `tests/test_glossary.py`:

```python
"""Trích ứng viên thuật ngữ. Hàm thuần: không DB, không mạng."""
import glossary


def test_dem_tu_viet_hoa_theo_tan_suat():
    doan = ["Sao Mars va Venus", "Mars lai xuat hien", "Mars lan nua"]
    ra = dict(glossary.ung_vien(doan))
    assert ra["Mars"] == 3
    assert ra["Venus"] == 1


def test_sap_theo_tan_suat_giam_dan():
    doan = ["Aaa Bbb", "Aaa", "Aaa", "Bbb"]
    ra = glossary.ung_vien(doan)
    assert ra[0][0] == "Aaa" and ra[0][1] == 3


def test_bo_the_html_truoc_khi_dem():
    ra = dict(glossary.ung_vien(["<b>Mars</b> va <i>Venus</i>"]))
    assert "Mars" in ra and "Venus" in ra
    assert not any(t.lower() in ("b", "i") for t in ra)


def test_loai_tu_chuc_nang_tieng_anh():
    """Đo thật: 29/200 ứng viên đầu bảng là The/This/And..."""
    doan = ["The Mars is here", "The Mars again", "This Mars too"]
    ra = dict(glossary.ung_vien(doan))
    assert "Mars" in ra
    assert "The" not in ra and "This" not in ra


def test_loai_tu_chi_bao_gio_cung_dung_dau_cau():
    """Đo thật: 31/200 ứng viên đầu bảng chỉ viết hoa vì đứng đầu câu."""
    doan = ["Nothing happens. Nothing again. Nothing more."]
    ra = dict(glossary.ung_vien(doan))
    assert "Nothing" not in ra


def test_tu_vua_dung_dau_cau_vua_dung_giua_thi_giu_lai():
    doan = ["Mars is bright. The sky shows Mars and Mars."]
    ra = dict(glossary.ung_vien(doan))
    assert "Mars" in ra


def test_bo_tu_qua_ngan():
    ra = dict(glossary.ung_vien(["Ab Cd Mars"]))
    assert "Mars" in ra and "Ab" not in ra


def test_top_cat_dung_so_luong():
    doan = [" ".join(f"Term{i}" for i in range(50)) for _ in range(3)]
    assert len(glossary.ung_vien(doan, top=10)) == 10


def test_khong_co_doan_nao():
    assert glossary.ung_vien([]) == []


def test_doc_bang_glossary():
    import io
    noi = "# chu thich\nMars = Sao Hoa\n\nVenus=Sao Kim\nhong\n"
    assert glossary.doc_bang(io.StringIO(noi)) == {"Mars": "Sao Hoa", "Venus": "Sao Kim"}


def test_doc_bang_file_khong_ton_tai(tmp_path):
    assert glossary.doc_bang(tmp_path / "khong-co.txt") == {}


def test_ghi_ung_vien_ra_dinh_dang_dan_duoc(tmp_path):
    duong = tmp_path / "ung-vien.txt"
    glossary.ghi_ung_vien(duong, [("Mars", 120), ("Venus", 45)])
    noi = duong.read_text(encoding="utf-8")
    assert "Mars = " in noi and "120" in noi
    # dán thẳng vào glossary.txt được: dòng chưa điền phải là chú thích
    assert glossary.doc_bang(duong) == {}
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_glossary.py -q`
Expected: FAIL với `ModuleNotFoundError: No module named 'glossary'`.

- [ ] **Step 3: Viết `glossary.py`**

```python
"""Thuật ngữ: trích ứng viên từ bản gốc, và đọc bảng người dùng đã khai.

Hàm thuần — không DB, không mạng, không đụng đĩa trừ hai hàm đọc/ghi file.

`translator.py` đọc glossary để dựng prompt, và `check_translation` đọc nó để
kiểm bản dịch. Hai chỗ dùng chung một cách đọc thì cách đọc đó phải nằm riêng.
"""
import collections
import re
from pathlib import Path

# Từ chức năng tiếng Anh: viết hoa vì đứng đầu câu, không phải vì là tên riêng.
# Đo thật trên sách mẫu: 29/200 ứng viên đầu bảng thuộc loại này.
TU_CHUC_NANG = frozenset("""
the this that these those there then thus they their them and but for from with
which when where while what who whom whose however therefore because since
although though after before during until unless about above below between each
every some many most much more less other another such same both either neither
all any one two three four five six seven eight nine ten first second third his
her its our your not nor only very also just even still yet once upon under over
into onto through without within toward towards against among along around behind
beyond if it is as at by be been being are was were has have had can could should
would may might must shall will do does did done say says said see seen look
looks new old now here how why than too own per via
""".split())

# Ứng viên phải dài hơn ngần này để không vơ phải viết tắt và chữ cái đầu mục.
DAI_TOI_THIEU = 3
# Từ có hơn ngần này phần số lần xuất hiện nằm ở đầu câu thì chỉ viết hoa vì
# vị trí, không phải vì là tên riêng. Đo thật: 31/200 ứng viên đầu bảng.
TI_LE_DAU_CAU = 0.9

_THE = re.compile(r"<[^>]+>")
_TU_HOA = re.compile(r"\b[A-Z][a-zA-Z'-]{%d,}\b" % (DAI_TOI_THIEU - 1))
_KET_CAU = ".!?"


def ung_vien(doan, top: int = 200) -> list:
    """[(từ, số lần)] xếp theo tần suất giảm dần, đã lọc nhiễu.

    Mặc định 200: đo thật trên sách mẫu, sau khi lọc thì ứng viên thứ 200 vẫn
    xuất hiện 45 lần trong 900 trang — vẫn là thuật ngữ đáng khai. Lấy sâu hơn
    (>=20 lần là 568 từ) thì quá nhiều để duyệt bằng mắt.
    """
    dem = collections.Counter()
    dau_cau = collections.Counter()

    for h in doan:
        t = _THE.sub("", h)
        for m in _TU_HOA.finditer(t):
            tu = m.group()
            dem[tu] += 1
            truoc = t[:m.start()].rstrip()
            if not truoc or truoc[-1] in _KET_CAU:
                dau_cau[tu] += 1

    sach = [(tu, n) for tu, n in dem.items()
            if tu.lower() not in TU_CHUC_NANG
            and dau_cau[tu] / n <= TI_LE_DAU_CAU]
    sach.sort(key=lambda x: (-x[1], x[0]))
    return sach[:top]


def doc_bang(nguon) -> dict:
    """`glossary.txt` -> {tiếng Anh: bản dịch}.

    Mỗi dòng `term = bản dịch`; dòng bắt đầu bằng # là chú thích. Dòng hỏng bị
    bỏ qua lặng lẽ — file này người dùng gõ tay, một dòng sai không được làm
    hỏng cả lần dịch.
    """
    if hasattr(nguon, "read"):
        dong = nguon.read().splitlines()
    else:
        duong = Path(nguon)
        if not duong.exists():
            return {}
        dong = duong.read_text(encoding="utf-8").splitlines()

    bang = {}
    for raw in dong:
        raw = raw.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        en, vi = (s.strip() for s in raw.split("=", 1))
        if en and vi:
            bang[en] = vi
    return bang


def ghi_ung_vien(duong_dan, ds: list) -> None:
    """Ghi file ứng viên để người dùng duyệt rồi dán vào glossary.txt.

    Mọi dòng đều là chú thích: dán nguyên file vào glossary.txt cũng không
    khai nhầm gì: người dùng phải tự bỏ dấu # của dòng nào họ muốn giữ.
    """
    dong = [
        "# Ứng viên thuật ngữ, xếp theo số lần xuất hiện.",
        "# Bỏ dấu # ở đầu dòng nào bạn muốn khai, rồi điền bản dịch sau dấu =",
        "# rồi dán sang glossary.txt.",
        "",
    ]
    dong += [f"# {tu} =            # {n} lần" for tu, n in ds]
    Path(duong_dan).write_text("\n".join(dong) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_glossary.py -q`
Expected: 12 passed.

- [ ] **Step 5: Viết test cho lệnh `glossary`**

Chèn vào cuối `tests/test_glossary.py`:

```python
def test_lenh_glossary_ghi_ra_file_ung_vien(source_epub, tmp_path, capsys):
    import argparse

    import cli
    from helpers import run_init

    proj = run_init(source_epub, tmp_path / "proj")
    cli.cmd_glossary(argparse.Namespace(project=str(proj), top=50))
    ra = (proj / "glossary.candidates.txt")
    assert ra.exists()
    assert "Chapter" in ra.read_text(encoding="utf-8")
    assert "glossary.candidates.txt" in capsys.readouterr().out


def test_lenh_glossary_khong_dung_khoi_skip(source_epub, tmp_path):
    """Header/footer là kind='skip'; chúng không phải thuật ngữ của sách."""
    import argparse

    import cli
    import db
    from helpers import run_init

    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    con.execute("UPDATE blocks SET src_html='Zzzmarker', kind='skip' "
                "WHERE id=(SELECT MIN(id) FROM blocks)")
    con.commit()
    cli.cmd_glossary(argparse.Namespace(project=str(proj), top=200))
    assert "Zzzmarker" not in (proj / "glossary.candidates.txt").read_text(
        encoding="utf-8")
```

- [ ] **Step 6: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_glossary.py -q`
Expected: FAIL với `AttributeError: module 'cli' has no attribute 'cmd_glossary'`.

- [ ] **Step 7: Thêm `cmd_glossary` vào `cli.py`**

Chèn trước mục `# ---- translate`:

```python
# ------------------------------------------------------------------ glossary

def cmd_glossary(args):
    proj, con = open_project(args.project)
    doan = [r[0] for r in con.execute(
        "SELECT src_html FROM blocks WHERE kind != 'skip'")]
    ds = glossary.ung_vien(doan, top=args.top)
    if not ds:
        die("không trích được ứng viên nào (sách quá ngắn?).")

    ra = proj / "glossary.candidates.txt"
    glossary.ghi_ung_vien(ra, ds)
    print(f"Đã ghi {len(ds)} ứng viên vào {ra}")
    print(f"  hay gặp nhất: {ds[0][1]} lần | ít nhất trong danh sách: {ds[-1][1]} lần")
    print(f"Duyệt file đó, bỏ dấu # ở dòng bạn muốn khai, điền bản dịch, "
          f"rồi dán sang {proj / 'glossary.txt'}.")
```

Thêm `import glossary` ở đầu `cli.py`, và trong `main` đăng ký lệnh sau parser `inspect`:

```python
    p = sub.add_parser("glossary", help="gom thuật ngữ hay gặp để duyệt trước khi dịch")
    p.add_argument("project")
    p.add_argument("--top", type=int, default=200,
                   help="số ứng viên (mặc định 200)")
    p.set_defaults(func=cmd_glossary)
```

- [ ] **Step 8: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 239 passed.

- [ ] **Step 9: Commit**

```bash
git add glossary.py cli.py tests/test_glossary.py
git commit -m "feat: lệnh glossary trích ứng viên thuật ngữ

Lọc hai loại nhiễu đo được trên sách thật: từ chức năng tiếng Anh
(29/200 ứng viên đầu bảng) và từ chỉ viết hoa vì đứng đầu câu (31/200).
Mặc định --top 200 vì sau khi lọc, ứng viên thứ 200 vẫn xuất hiện 45
lần trong 900 trang. File ra toàn dòng chú thích nên dán nhầm cũng
không khai nhầm."
```

---

## Task 3: Kiểm chữ số và thuật ngữ đã khai

**Files:**
- Modify: `translator.py`
- Create: `tests/test_kiem_tra.py`

**Interfaces:**
- Consumes: `glossary.doc_bang` từ Task 2.
- Produces: `translator.check_translation(src, dst, thuat_ngu=None) -> str|None` — thêm hai mã: `missing_number`, `missing_term`.

- [ ] **Step 1: Viết test cho kiểm tra mở rộng**

Tạo `tests/test_kiem_tra.py`:

```python
"""Kiểm máy móc bản dịch. Miễn phí, chạy trước khi tốn tiền thử lại."""
from translator import check_translation


def test_ban_dich_binh_thuong_khong_bi_gan_co():
    assert check_translation("A normal sentence here.",
                             "Một câu bình thường ở đây.") is None


def test_thieu_chu_so_bi_bat():
    """Đo thật: 50% đoạn của sách chứa chữ số, và số phải sang nguyên vẹn."""
    assert check_translation("He was born in 1914 exactly.",
                             "Ông sinh ra vào năm đó.") == "missing_number"


def test_du_chu_so_thi_khong_sao():
    assert check_translation("He was born in 1914 exactly.",
                             "Ông sinh năm 1914.") is None


def test_nhieu_chu_so_thieu_mot_cai_van_bi_bat():
    assert check_translation("From 1914 to 1918 and back.",
                             "Từ 1914 trở đi.") == "missing_number"


def test_chu_so_trong_the_html_khong_tinh():
    """Số trong thuộc tính thẻ không phải nội dung."""
    assert check_translation('<span class="p2">Xin chao</span>',
                             "<span>Xin chào</span>") is None


def test_thieu_thuat_ngu_da_khai_bi_bat():
    bang = {"Mars": "Sao Hoa"}
    assert check_translation("Mars is bright tonight.",
                             "Hành tinh đỏ sáng tối nay.",
                             thuat_ngu=bang) == "missing_term"


def test_dung_thuat_ngu_da_khai_thi_khong_sao():
    bang = {"Mars": "Sao Hoa"}
    assert check_translation("Mars is bright tonight.",
                             "Sao Hoa sáng tối nay.", thuat_ngu=bang) is None


def test_thuat_ngu_giu_nguyen_ten_khong_bi_bao_oan():
    """Review Focus 3: 'Winterfell = Winterfell' là cách khai giữ nguyên tên."""
    bang = {"Winterfell": "Winterfell"}
    assert check_translation("They rode to Winterfell.",
                             "Họ phi ngựa tới Winterfell.", thuat_ngu=bang) is None


def test_thuat_ngu_khong_co_trong_ban_goc_thi_khong_xet():
    bang = {"Mars": "Sao Hoa", "Venus": "Sao Kim"}
    assert check_translation("Venus is bright.", "Sao Kim sáng.",
                             thuat_ngu=bang) is None


def test_khong_co_bang_thuat_ngu_thi_chi_kiem_chu_so():
    """Review Focus 2: không có glossary thì vẫn phải chạy được."""
    assert check_translation("Mars is bright.", "Hành tinh đỏ sáng.") is None
    assert check_translation("Mars in 1914.", "Hành tinh đỏ.") == "missing_number"


def test_bang_thuat_ngu_rong():
    assert check_translation("Mars is bright.", "Hành tinh đỏ.",
                             thuat_ngu={}) is None


def test_thuat_ngu_khop_theo_ranh_gioi_tu():
    """'Sun' không được khớp vào 'Sunday'."""
    bang = {"Sun": "Mặt Trời"}
    assert check_translation("It was Sunday morning.",
                             "Đó là sáng chủ nhật.", thuat_ngu=bang) is None


def test_thuat_ngu_khong_phan_biet_hoa_thuong_o_ban_goc():
    bang = {"Mars": "Sao Hoa"}
    assert check_translation("the planet mars appears",
                             "hành tinh Sao Hoa xuất hiện",
                             thuat_ngu=bang) is None


def test_cac_luat_cu_van_chay():
    assert check_translation("<em>hi</em>", "") == "empty"
    assert check_translation("<em>hi there</em>", "chào") == "tag_mismatch"
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_kiem_tra.py -q`
Expected: FAIL — `check_translation() got an unexpected keyword argument 'thuat_ngu'`.

- [ ] **Step 3: Mở rộng `check_translation` trong `translator.py`**

Thay hàm `check_translation` bằng:

`translator.py` đã có `from collections import Counter` ở đầu file; dùng lại
`Counter` đó, không thêm `import collections`.

```python
_CHU_SO = re.compile(r"\d+")


def _so_trong(s: str) -> Counter:
    """Các cụm chữ số trong phần NỘI DUNG, bỏ qua thuộc tính thẻ."""
    return Counter(_CHU_SO.findall(STRIP_TAGS_RE.sub("", s)))


def check_translation(src: str, dst: str, thuat_ngu: dict = None):
    """None nếu ổn, hoặc mã lỗi.

    empty | tag_mismatch | too_short | missing_number | missing_term

    Kiểm chữ số thì đáng tin: số phải sang bản dịch nguyên vẹn, và đo thật cho
    thấy 50% số đoạn có chữ số.

    KHÔNG kiểm tên riêng nói chung. 95% số đoạn chứa từ viết hoa, mà tên riêng
    thì được DỊCH — sang tiếng Việt vẫn viết hoa nhưng không còn ký tự nào
    giống bản gốc. Cảnh báo kêu ở mọi đoạn thì bằng không có cảnh báo. Chỉ kiểm
    những thuật ngữ người dùng đã khai trong glossary.txt, tức đúng chỗ họ đã
    tuyên bố muốn dịch thành gì.
    """
    if not dst.strip():
        return "empty"
    if Counter(TAG_RE.findall(src.lower())) != Counter(TAG_RE.findall(dst.lower())):
        return "tag_mismatch"

    thieu_so = _so_trong(src) - _so_trong(dst)
    if thieu_so:
        return "missing_number"

    if thuat_ngu:
        than_src = STRIP_TAGS_RE.sub("", src)
        than_dst = STRIP_TAGS_RE.sub("", dst)
        for en, vi in thuat_ngu.items():
            co_trong_goc = re.search(rf"\b{re.escape(en)}\b", than_src, re.I)
            if co_trong_goc and vi.lower() not in than_dst.lower():
                return "missing_term"

    s, d = _text_len(src), _text_len(dst)
    if s > 80 and d < 0.4 * s:       # tiếng Việt thường dài hơn hoặc bằng tiếng Anh
        return "too_short"
    return None
```

Không thêm import nào: `Counter` và `re` đều đã có sẵn ở đầu `translator.py`.

- [ ] **Step 4: Chạy test**

Run: `.venv/bin/python -m pytest tests/test_kiem_tra.py -q`
Expected: 14 passed.

- [ ] **Step 5: Truyền bảng thuật ngữ vào `translate_chunk`**

Trong `translator.py`, đổi chữ ký và lời gọi:

```python
def translate_chunk(con, provider, client, model: str, system: str, chunk_id: int,
                    thuat_ngu: dict = None) -> dict:
```

và trong thân hàm, đổi:

```python
            problem = check_translation(b["src_html"], dst)
```

thành:

```python
            problem = check_translation(b["src_html"], dst, thuat_ngu)
```

Trong `cli.py`, hàm `cmd_translate`, dựng bảng rồi truyền vào:

```python
    thuat_ngu = glossary.doc_bang(proj / "glossary.txt")
```

ngay sau dòng dựng `system`, và đổi lời gọi:

```python
                res = translator.translate_chunk(con, provider, client, model,
                                                 system, cid, thuat_ngu)
```

- [ ] **Step 6: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 253 passed.

- [ ] **Step 7: Commit**

```bash
git add translator.py cli.py tests/test_kiem_tra.py
git commit -m "feat: kiểm chữ số và thuật ngữ đã khai

Spec mục 7 nói kiểm 'số và tên riêng'. Nửa sau không dùng được: 95%
đoạn chứa từ viết hoa và tên riêng thì được DỊCH, nên cảnh báo sẽ kêu ở
mọi đoạn. Thay bằng: kiểm chữ số nghiêm ngặt (50% đoạn có số, và số
phải sang nguyên vẹn), còn thuật ngữ thì chỉ kiểm những mục người dùng
đã khai trong glossary.txt."
```

---

## Task 4: Lệnh `edit`

**Files:**
- Modify: `cli.py`
- Create: `tests/test_edit.py`

**Interfaces:**
- Produces: lệnh `python cli.py edit <project> --block N [--set "<html>"]`.

- [ ] **Step 1: Viết test cho `edit`**

Tạo `tests/test_edit.py`:

```python
"""Sửa tay một đoạn rồi xuất lại — bản dịch nằm trong SQLite, không nằm trong file."""
import argparse

import pytest

import cli
import db
from helpers import run_init


def test_xem_mot_doan(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks").fetchone()[0]
    con.execute("UPDATE blocks SET dst_html='bản dịch cũ' WHERE id=?", (bid,))
    con.commit()

    cli.cmd_edit(argparse.Namespace(project=str(proj), block=bid, set=None))
    ra = capsys.readouterr().out
    assert "bản dịch cũ" in ra
    assert str(bid) in ra


def test_sua_mot_doan(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks").fetchone()[0]
    con.commit()

    cli.cmd_edit(argparse.Namespace(project=str(proj), block=bid,
                                    set="bản dịch mới"))
    con2 = db.connect(proj)
    assert con2.execute("SELECT dst_html FROM blocks WHERE id=?",
                        (bid,)).fetchone()[0] == "bản dịch mới"


def test_sua_xong_thi_go_co(source_epub, tmp_path):
    """Người dùng vừa sửa tay thì cảnh báo cũ không còn đúng nữa."""
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks").fetchone()[0]
    con.execute("UPDATE blocks SET flag='tag_mismatch' WHERE id=?", (bid,))
    con.commit()

    cli.cmd_edit(argparse.Namespace(project=str(proj), block=bid, set="đã sửa"))
    con2 = db.connect(proj)
    assert con2.execute("SELECT flag FROM blocks WHERE id=?",
                        (bid,)).fetchone()[0] is None


def test_doan_khong_ton_tai_bao_loi_ro(source_epub, tmp_path):
    """Review Focus 4."""
    proj = run_init(source_epub, tmp_path / "proj")
    with pytest.raises(SystemExit) as e:
        cli.cmd_edit(argparse.Namespace(project=str(proj), block=999999, set="x"))
    assert "999999" in str(e.value)


def test_xem_doan_chua_dich(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    bid = con.execute("SELECT MIN(id) FROM blocks").fetchone()[0]
    cli.cmd_edit(argparse.Namespace(project=str(proj), block=bid, set=None))
    assert "chưa dịch" in capsys.readouterr().out
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_edit.py -q`
Expected: FAIL với `AttributeError: module 'cli' has no attribute 'cmd_edit'`.

- [ ] **Step 3: Thêm `cmd_edit` vào `cli.py`**

Chèn sau `cmd_glossary`:

```python
# ------------------------------------------------------------------ edit

def cmd_edit(args):
    proj, con = open_project(args.project)
    r = con.execute(
        "SELECT id, page_no, kind, src_html, dst_html, flag FROM blocks WHERE id=?",
        (args.block,)).fetchone()
    if r is None:
        die(f"không có đoạn nào mang id {args.block}. Xem id bằng `inspect`.")

    if args.set is None:
        trang = r["page_no"] + 1 if r["page_no"] >= 0 else r["page_no"]
        print(f"block {r['id']} | trang {trang} | {r['kind']}"
              + (f" | cờ: {r['flag']}" if r["flag"] else ""))
        print(f"  gốc : {r['src_html']}")
        print(f"  dịch: {r['dst_html'] if r['dst_html'] else '(chưa dịch)'}")
        return

    # Người dùng vừa sửa tay thì cảnh báo máy gắn trước đó không còn đúng nữa.
    con.execute("UPDATE blocks SET dst_html=?, flag=NULL WHERE id=?",
                (args.set, args.block))
    con.commit()
    print(f"Đã sửa block {args.block}. Chạy `export` để xuất lại.")
```

Trong `main`, đăng ký sau parser `glossary`:

```python
    p = sub.add_parser("edit", help="xem hoặc sửa tay bản dịch của một đoạn")
    p.add_argument("project")
    p.add_argument("--block", type=int, required=True, help="id đoạn, xem bằng `inspect`")
    p.add_argument("--set", help="bản dịch mới; bỏ trống để chỉ xem")
    p.set_defaults(func=cmd_edit)
```

- [ ] **Step 4: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 258 passed.

- [ ] **Step 5: Commit**

```bash
git add cli.py tests/test_edit.py
git commit -m "feat: lệnh edit — sửa tay một đoạn rồi xuất lại

Bản dịch nằm trong SQLite chứ không nằm trong file xuất, nên sửa một
đoạn rồi export lại là xong, không phải dịch lại gì. Sửa tay thì gỡ cờ
máy đã gắn: người dùng vừa xem xong, cảnh báo cũ không còn đúng."
```

---

## Task 5: `status` mở rộng

**Files:**
- Modify: `cli.py`
- Create: `tests/test_status_mo_rong.py`

**Interfaces:**
- Consumes: cột `flag` với năm giá trị; cột `chunks.provider` / `model`.

- [ ] **Step 1: Viết test**

Tạo `tests/test_status_mo_rong.py`:

```python
"""`status` phải nói được: còn bao nhiêu, đáng ngờ chỗ nào, tốn bao nhiêu."""
import argparse

import cli
import db
from helpers import run_init


def chay(proj, capsys):
    cli.cmd_status(argparse.Namespace(project=str(proj)))
    return capsys.readouterr().out


def test_dem_co_theo_tung_loai(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    ids = [r[0] for r in con.execute("SELECT id FROM blocks ORDER BY id LIMIT 3")]
    for bid, co in zip(ids, ("tag_mismatch", "missing_number", "missing_number")):
        con.execute("UPDATE blocks SET flag=? WHERE id=?", (co, bid))
    con.commit()

    ra = chay(proj, capsys)
    assert "missing_number" in ra and "tag_mismatch" in ra
    assert "2" in ra, "phải đếm được 2 đoạn missing_number"


def test_tien_do_theo_trang(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    con.execute("UPDATE blocks SET dst_html='xong' WHERE page_no=0")
    con.commit()
    ra = chay(proj, capsys)
    assert "trang" in ra.lower()


def test_khong_co_co_nao_thi_khong_in_muc_do(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    ra = chay(proj, capsys)
    assert "đáng xem lại" not in ra


def test_uoc_tinh_chi_phi_ca_cuon_tu_phan_da_dich(source_epub, tmp_path, capsys,
                                                  monkeypatch):
    """Sau khi dịch thử, phải ngoại suy được tiền cho cả cuốn."""
    monkeypatch.setenv("PRICE_IN", "3")
    monkeypatch.setenv("PRICE_OUT", "15")
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]
    con.execute("UPDATE chunks SET status='done', in_tokens=1000, out_tokens=2000 "
                "WHERE id=?", (cid,))
    con.execute("UPDATE blocks SET dst_html='x' WHERE chunk_id=?", (cid,))
    con.commit()
    ra = chay(proj, capsys)
    assert "cả cuốn" in ra.lower()
```

- [ ] **Step 2: Chạy test để thấy nó hỏng**

Run: `.venv/bin/python -m pytest tests/test_status_mo_rong.py -q`
Expected: FAIL — `status` chưa đếm cờ theo loại, chưa in tiến độ theo trang, chưa ngoại suy chi phí.

- [ ] **Step 3: Mở rộng `cmd_status` trong `cli.py`**

Thay khối liệt kê đoạn bị gắn cờ:

```python
    flagged = con.execute(
        "SELECT id, page_no, flag, json_extract(layout, '$.href') AS href "
        "FROM blocks WHERE flag IS NOT NULL ORDER BY id").fetchall()
    if flagged:
        print(f"\n{len(flagged)} đoạn bị gắn cờ (nên xem lại):")
        for r in flagged[:10]:
            # EPUB định vị bằng href; PDF (Phase 3+) bằng số trang
            cho = r["href"] or f"trang {r['page_no']}"
            print(f"  block {r['id']} ({cho}): {r['flag']}")
        if len(flagged) > 10:
            print(f"  ... và {len(flagged) - 10} đoạn nữa")
```

bằng:

```python
    theo_loai = con.execute(
        "SELECT flag, COUNT(*) n FROM blocks WHERE flag IS NOT NULL "
        "GROUP BY flag ORDER BY n DESC").fetchall()
    if theo_loai:
        tong_co = sum(r["n"] for r in theo_loai)
        print(f"\n{tong_co} đoạn bị gắn cờ (nên xem lại):")
        for r in theo_loai:
            print(f"  {r['flag']:<16} {r['n']:>5} đoạn — {_giai_thich(r['flag'])}")
        vai = con.execute(
            "SELECT id, page_no, flag, json_extract(layout, '$.href') AS href "
            "FROM blocks WHERE flag IS NOT NULL ORDER BY id LIMIT 5").fetchall()
        print("  ví dụ:")
        for r in vai:
            cho = r["href"] or f"trang {r['page_no'] + 1}"
            print(f"    block {r['id']} ({cho}): {r['flag']}"
                  f"   — xem: python cli.py edit {args.project} --block {r['id']}")
```

Chèn thêm hàm giải thích và phần tiến độ theo trang, ngay trước `cmd_status`:

```python
GIAI_THICH_CO = {
    "empty": "mô hình trả về rỗng",
    "tag_mismatch": "số thẻ HTML không khớp bản gốc",
    "too_short": "bản dịch ngắn bất thường so với bản gốc",
    "missing_number": "bản gốc có chữ số mà bản dịch không có",
    "missing_term": "thuật ngữ đã khai trong glossary không thấy trong bản dịch",
    "overflow": "chữ không vừa khung, đã giữ nguyên bản gốc ở chỗ đó",
}


def _giai_thich(co: str) -> str:
    return GIAI_THICH_CO.get(co, "không rõ")
```

Và chèn vào `cmd_status`, ngay sau dòng in "Ký tự nguồn còn phải dịch":

```python
    trang = con.execute(
        "SELECT COUNT(DISTINCT page_no) FROM blocks WHERE page_no >= 0").fetchone()[0]
    trang_xong = con.execute(
        "SELECT COUNT(*) FROM (SELECT page_no FROM blocks WHERE page_no >= 0 "
        "GROUP BY page_no HAVING SUM(dst_html IS NULL) = 0)").fetchone()[0]
    if trang:
        print(f"Trang đã dịch xong hoàn toàn: {trang_xong:,}/{trang:,}")
```

Cuối cùng, ngoại suy chi phí cả cuốn. Thay khối in chi phí hiện có:

```python
        if p_in and p_out:
            cost = ((t["i"] + t["cr"] + t["cw"]) * float(p_in) + t["o"] * float(p_out)) / 1_000_000
            print(f"Chi phí tối đa ước tính: ${cost:,.2f} (giá USD/1M token từ PRICE_IN/PRICE_OUT; "
                  f"bỏ qua chênh lệch giá cache)")
```

bằng:

```python
        if p_in and p_out:
            cost = ((t["i"] + t["cr"] + t["cw"]) * float(p_in)
                    + t["o"] * float(p_out)) / 1_000_000
            print(f"Đã tiêu: ${cost:,.2f} (giá USD/1M token từ PRICE_IN/PRICE_OUT; "
                  f"bỏ qua chênh lệch giá cache)")
            da_dich = chars_all - chars_left
            if da_dich > 0 and chars_left > 0:
                # Ngoại suy theo SỐ KÝ TỰ đã dịch, không theo số chunk: chunk
                # to nhỏ không đều nên đếm chunk sẽ lệch.
                ca_cuon = cost * chars_all / da_dich
                print(f"Ước tính cả cuốn: ${ca_cuon:,.2f} "
                      f"(ngoại suy từ {da_dich:,}/{chars_all:,} ký tự đã dịch)")
```

- [ ] **Step 4: Chạy cả bộ**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 262 passed.

- [ ] **Step 5: Commit**

```bash
git add cli.py tests/test_status_mo_rong.py
git commit -m "feat: status đếm cờ theo loại, tiến độ theo trang, ngoại suy chi phí

Mỗi loại cờ kèm một câu giải thích và lệnh edit để xem ngay đoạn đó.
Chi phí cả cuốn ngoại suy theo số KÝ TỰ đã dịch chứ không theo số chunk,
vì chunk to nhỏ không đều."
```

---

## Task 6: Nghiệm thu — dịch thật 20 trang

**Đây là bước duy nhất của cả dự án tiêu token API. Tiền của người dùng, nên phải hỏi trước.**

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: toàn bộ Task 1-5.

- [ ] **Step 1: Chuẩn bị project và duyệt thuật ngữ — chưa tốn gì**

```bash
.venv/bin/python cli.py init ebook/astrology.pdf.pdf --dir /tmp/bt-p5 --force
.venv/bin/python cli.py glossary /tmp/bt-p5 --top 200
```

Expected: `init` báo ~10.400 đoạn / ~590 chunk. `glossary` ghi ra
`/tmp/bt-p5/glossary.candidates.txt` với 200 ứng viên, cái hay gặp nhất vài
trăm lần và cái cuối danh sách khoảng 45 lần.

Mở file đó ra xem. Nó có phải là thuật ngữ thật của cuốn sách không, hay toàn
từ vô nghĩa? Nếu toàn từ vô nghĩa thì quay lại Task 2 — bộ lọc chưa đủ.

- [ ] **Step 2: Soi cấu trúc và layout — vẫn chưa tốn gì**

```bash
.venv/bin/python cli.py inspect /tmp/bt-p5 --pages 150-155
.venv/bin/python cli.py export  /tmp/bt-p5 --pages 150-169 --dry-run --probe \
    -o /tmp/bt-p5/thu.pdf
```

Expected: `inspect` in ra thứ tự đọc của 6 trang. `export` báo `20 khổ`, cỡ chữ
trung vị quanh 98%, rất ít khối tràn khung.

- [ ] **Step 3: DỪNG LẠI VÀ HỎI NGƯỜI DÙNG**

Bước sau đây gọi API thật và tiêu tiền thật. Đưa cho người dùng con số trước
khi tiêu:

```bash
.venv/bin/python cli.py status /tmp/bt-p5
```

Nói với họ: 20 trang là khoảng 2,5% cuốn sách; theo ước tính thô ở `status` thì
cả cuốn rơi vào khoảng 18-20 đô, nên 20 trang vào khoảng 0,5 đô. Hỏi họ có
muốn chạy không, và **đợi họ trả lời**. Không tự chạy.

- [ ] **Step 4: Dịch thật 20 trang — chỉ sau khi người dùng đồng ý**

```bash
export ANTHROPIC_API_KEY=...        # người dùng tự đặt
.venv/bin/python cli.py translate /tmp/bt-p5 --pages 150-169
```

Expected: lệnh báo `Khoảng trang 150-169 -> thực dịch trang 150-171` (hoặc
tương tự — chunk vắt ngang trang nên vùng phủ rộng hơn một chút), rồi chạy
khoảng 14 chunk.

- [ ] **Step 5: Xem tiền thật và cờ thật**

```bash
export PRICE_IN=3 PRICE_OUT=15      # thay bằng giá thật của model đang dùng
.venv/bin/python cli.py status /tmp/bt-p5
```

Expected: in ra số token thật đã dùng, số tiền đã tiêu, và **ước tính cả cuốn
ngoại suy từ số ký tự đã dịch**. So con số đó với ước tính thô 18-20 đô lúc
lập kế hoạch Phase 2 — lệch nhiều thì con số nào đúng?

Nếu có đoạn bị gắn cờ, xem một cái:

```bash
.venv/bin/python cli.py edit /tmp/bt-p5 --block <id status vừa in>
```

- [ ] **Step 6: Xuất ra và ĐỌC**

```bash
.venv/bin/python cli.py export /tmp/bt-p5 --pages 150-169 -o /tmp/bt-p5/that.pdf
open /tmp/bt-p5/that.pdf
```

**Đây là lần đầu tiên trong cả dự án có bản dịch thật để đọc.** Kiểm bốn điều,
và ba trong đó chỉ mắt người trả lời được:

1. Tiếng Việt có tự nhiên không, hay dịch từng chữ.
2. Thuật ngữ chiêm tinh có nhất quán giữa các trang không.
3. Xưng hô và giọng văn có đúng như `style.md` đã ghi không.
4. Chữ có vừa khung không, ảnh có nguyên không (cái này script kiểm được).

Chỗ nào chưa ưng thì sửa `style.md` và `glossary.txt`, rồi dịch lại khoảng đó:

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0, '.')
import db
con = db.connect('/tmp/bt-p5')
con.execute(\"UPDATE chunks SET status='pending'\")
con.execute('UPDATE blocks SET dst_html=NULL, flag=NULL')
con.commit()
print('đã xoá bản dịch cũ, sẵn sàng dịch lại')"
.venv/bin/python cli.py translate /tmp/bt-p5 --pages 150-169
```

- [ ] **Step 7: Cập nhật README**

Thay phần `## Quy trình` bằng vòng làm việc đầy đủ:

```markdown
## Quy trình

```bash
# 1. Tạo project
python cli.py init sach.pdf

# 2. Gom thuật ngữ hay gặp, duyệt rồi dán sang glossary.txt
python cli.py glossary projects/sach --top 200

# 3. Sửa style.md (giọng văn, xưng hô) và glossary.txt

# 4. Soi xem tool hiểu sách thế nào — chưa tốn token
python cli.py inspect projects/sach --pages 1-20
python cli.py export  projects/sach --pages 1-20 --dry-run --probe

# 5. Dịch thử 20 trang rồi đọc
python cli.py translate projects/sach --pages 1-20
python cli.py export    projects/sach --pages 1-20
python cli.py status    projects/sach        # tiền thật + ước tính cả cuốn

# 6. Ưng thì dịch tiếp từng khúc
python cli.py translate projects/sach --pages 21-200

# 7. Sửa tay đoạn nào chưa ưng rồi xuất lại
python cli.py edit   projects/sach --block 1423
python cli.py edit   projects/sach --block 1423 --set "bản dịch mới"
python cli.py export projects/sach --pages 1-200
```

`status` đếm đoạn bị gắn cờ theo từng loại và in sẵn lệnh `edit` để xem ngay.
```

- [ ] **Step 8: Dọn và commit**

```bash
rm -rf /tmp/bt-p5
git add README.md
git commit -m "docs: vòng làm việc đầy đủ từ glossary tới sửa tay

Phase 5 xong: dịch theo khoảng trang, duyệt thuật ngữ trước, kiểm chữ số
và thuật ngữ đã khai, sửa tay một đoạn rồi xuất lại."
```

---

## Nghiệm thu Phase 5

1. `.venv/bin/python -m pytest tests/ -q` — 262 passed, không test nào gọi mạng.
2. `git log --oneline -- tests/golden/` vẫn chỉ có đúng một commit.
3. `translate --pages 150-169` trên sách thật chỉ dịch các chunk chạm khoảng đó, và báo vùng phủ thật.
4. `glossary --top 200` ra danh sách mà người dùng nhìn vào thấy đúng là thuật ngữ của cuốn sách.
5. `status` in được **tiền thật đã tiêu** và **ước tính cả cuốn** ngoại suy từ đó.
6. Có một bản dịch 20 trang thật để đọc, và người dùng đã đọc.
7. `grep -rn "pymupdf\|fitz" pdf_layout.py translator.py cli.py` ra rỗng.

Điều kiện 6 là điều kiện thật sự quan trọng: bốn phase trước chỉ chứng minh cái máy chạy đúng. Phase 5 là lần đầu tiên chứng minh nó dịch được.
