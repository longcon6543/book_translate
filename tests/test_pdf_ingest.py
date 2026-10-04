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


import pytest

import ingest


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
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page(width=522, height=666)
    p = tmp_path / "scan.pdf"
    doc.save(str(p)); doc.close()

    # Trang trắng: không lớp chữ, không ảnh scan để OCR (Phase C). Thông báo
    # không được hứa OCR khi không có gì để OCR.
    with pytest.raises(ingest.UnsupportedSource, match="không có trang ảnh"):
        ingest.load(p)


def test_pdf_co_mat_khau_bao_ro(tmp_path):
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


def _anh(doc, page, x0, y0, x1, y1):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 32, 32))
    pix.set_rect(pix.irect, (180, 120, 60))
    page.insert_image(pymupdf.Rect(x0, y0, x1, y1), pixmap=pix)


def test_trang_chi_co_anh_khong_lam_vo(tmp_path):
    """Block ảnh KHÔNG có khoá "lines" — bỏ guard `type != 0` là KeyError.
    Sách thật có 114 block ảnh mà không test nào chạm tới chúng."""
    doc = pymupdf.open()
    p0 = doc.new_page(width=522, height=666)
    for i in range(4):
        p0.insert_text((67, 120 + i * 12), f"dong {i} noi dung day du", fontsize=10)
    p1 = doc.new_page(width=522, height=666)
    _anh(doc, p1, 100, 100, 300, 300)
    p = tmp_path / "anh.pdf"
    doc.save(str(p)); doc.close()

    kq = ingest.load(p)
    assert {b.page_no for b in kq.blocks} == {0}, "trang toàn ảnh không được sinh block"
    assert all(b.src_html.strip() for b in kq.blocks)


def test_anh_lan_voi_chu_tren_cung_mot_trang(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page(width=522, height=666)
    _anh(doc, page, 300, 90, 460, 250)
    for i in range(4):
        page.insert_text((67, 120 + i * 12), f"dong {i} noi dung day du", fontsize=10)
    p = tmp_path / "lan.pdf"
    doc.save(str(p)); doc.close()

    kq = ingest.load(p)
    assert kq.blocks and all(b.src_html.strip() for b in kq.blocks)


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
    _anh(doc, doc.new_page(width=522, height=666), 0, 0, 522, 333)
    _anh(doc, doc.new_page(width=522, height=666), 0, 0, 522, 666)
    doc.new_page(width=522, height=666)
    # new_page() vô hiệu hoá mọi Page tạo trước nó (đo thật, PyMuPDF 1.28.2):
    # cầm Page cũ qua lần tạo trang sau là ra "page is None". Lấy lại theo số.
    nua, kin, trang = doc[0], doc[1], doc[2]
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


def test_trang_scan_dong_than_bai_khong_bi_nuot_vao_tieu_de_chay(tmp_path):
    """Nghiệm thu Phase 7 đo thật: group_paragraphs gộp dòng tiêu đề chạy ở lề
    với dòng thân bài ngay dưới thành MỘT đoạn; đoạn đó ngắn và bắt đầu ở lề
    nên mark_running gắn skip cả đoạn — chữ thân bài biến mất (một tên chương
    trong mục lục, dữ liệu một lá số). Trang scan phải gom đoạn riêng từng vùng."""
    doc = pymupdf.open()
    for i in range(5):
        _anh(doc, doc.new_page(width=522, height=666), 0, 0, 522, 666)
    for i in range(5):
        page = doc[i]                          # new_page() làm Page cũ vô hiệu
        page.insert_text((67, 20), "RUNNING HEAD", fontsize=10)
        page.insert_text((67, 55), f"body text on page {i} kept", fontsize=10)
    p = tmp_path / "dau.pdf"
    doc.save(str(p))
    doc.close()
    chu = " ".join(b.src_html for b in ingest.load(p).blocks)
    for i in range(5):
        assert f"body text on page {i} kept" in chu, f"mất chữ thân bài trang {i}"


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


def test_la_trang_scan_dung_khoi_co_san_khong_hoi_lai_khung_anh(monkeypatch):
    """Tăng tốc init: get_image_rects tốn ~61s trên sách scan 484 trang, trong
    khi get_text('dict') mà _doc_trang đã đọc mang sẵn khung từng ảnh."""
    doc = pymupdf.open()
    _anh(doc, doc.new_page(width=522, height=666), 0, 0, 522, 333)
    _anh(doc, doc.new_page(width=522, height=666), 0, 0, 522, 666)
    doc.new_page(width=522, height=666)
    _anh(doc, doc.new_page(width=522, height=666), -40, -40, 562, 706)
    cu = [pdf_text._la_trang_scan(doc[i]) for i in range(4)]
    assert cu == [False, True, False, True], "tiền đề: đường cũ phải phân biệt được"

    def cam(*a, **k):
        raise AssertionError("không được hỏi lại get_image_rects")
    monkeypatch.setattr(pymupdf.Page, "get_image_rects", cam)
    moi = [pdf_text._la_trang_scan(doc[i], doc[i].get_text("dict")["blocks"])
           for i in range(4)]
    assert moi == cu


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

    def __call__(self, anh, **kw):
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
    # Khớp đúng thông báo mới: thông báo cũ ("chưa tự chạy OCR") cũng có chữ
    # OCR nên match="OCR" xanh cả khi chưa có lượt OCR.
    with pytest.raises(ingest.UnsupportedSource, match="OCR không đọc ra chữ nào"):
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


def test_trang_scan_dat_xoay_90_van_la_trang_scan(tmp_path, monkeypatch):
    """Review Phase C: khung ảnh (dict lẫn get_image_rects) theo toạ độ CHƯA
    xoay, page.rect theo hướng hiển thị — trang /Rotate 90 chỉ phủ 67%, sách
    scan chụp ngang bị báo 'PDF trắng' và không được OCR."""
    doc = pymupdf.open()
    for _ in range(2):
        doc.new_page(width=600, height=400)
    for i in range(2):
        _anh(doc, doc[i], 0, 0, 600, 400)
        doc[i].set_rotation(90)
    f = tmp_path / "xoay.pdf"
    doc.save(str(f)); doc.close()
    d = pymupdf.open(f)
    assert all(pdf_text._la_trang_scan(d[i]) for i in range(2))
    assert all(pdf_text._la_trang_scan(d[i], d[i].get_text("dict")["blocks"])
               for i in range(2))
    d.close()
    dong = [_kq_pt(30, 80, 370, 90, "fake ocr line on a rotated scan page")]
    monkeypatch.setattr(ocr_mod, "tao_engine", lambda: EngineGia(dong))
    assert "rotated scan page" in " ".join(b.src_html for b in ingest.load(f).blocks)
