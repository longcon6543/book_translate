"""Chế độ reflow. Không gọi mạng.

trang_theo_vi_tri: bộ dựng theo vị trí (R1 cũ) — nay là dự phòng cho trang
không dàn được. trang_reflow: dàn theo thứ tự, neo vị trí gốc (spec 8A).
"""
import pymupdf

from render import pdf_reflow

KHO = (334, 547)   # khổ trang harmonics, đo thật


def chu(page):
    """insert_htmlbox đặt dấu cách không ngắt; chuẩn hoá trước khi so."""
    return page.get_text().replace("\xa0", " ")


def trang_scan(chu_anh="English words baked into the scan"):
    """Giống một trang sách scan: ảnh phủ kín trang, chữ OCR nằm đè lên ảnh."""
    d = pymupdf.open()
    p = d.new_page(width=KHO[0], height=KHO[1])
    pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 60, 100), 0)
    pix.clear_with(180)
    p.insert_image(p.rect, pixmap=pix)
    p.insert_text((40, 80), chu_anh, fontsize=10)
    return d


def khoi(x0, y0, x1, y1, html, src="Original English text", id_=1, size=10.0,
         kind="text"):
    return {"id": id_, "bbox": pymupdf.Rect(x0, y0, x1, y1),
            "html": html, "src": src, "size": size, "kind": kind}


def test_tien_de_trang_scan_co_anh():
    """Nếu trang mẫu không có ảnh thì test R2 bên dưới xanh vô nghĩa."""
    assert trang_scan()[0].get_images(full=True)


def test_khong_mang_anh_nao_cua_trang_goc():
    """R2: chữ Anh của sách scan nằm TRONG ảnh. Chép ảnh sang là chép chữ Anh."""
    d = pdf_reflow.trang_theo_vi_tri(trang_scan(), 0, [khoi(40, 60, 300, 100, "Chữ Việt")])
    assert d[0].get_images(full=True) == []


def test_dung_kho_trang_goc():
    d = pdf_reflow.trang_theo_vi_tri(trang_scan(), 0, [khoi(40, 60, 300, 100, "Chữ Việt")])
    assert (d[0].rect.width, d[0].rect.height) == KHO


def test_chu_viet_nam_dung_khung_da_cho():
    """R1: đối chiếu trái-phải theo vị trí là công dụng chính của khổ đôi."""
    khung = pymupdf.Rect(40, 200, 300, 240)
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0, [khoi(*khung, "Xin chào bạn đọc")])
    thay = d[0].search_for("Xin")
    assert thay, "không thấy chữ Việt trên trang"
    tam = pymupdf.Point((thay[0].x0 + thay[0].x1) / 2, (thay[0].y0 + thay[0].y1) / 2)
    assert (khung + (-2, -2, 2, 2)).contains(tam), f"{thay[0]} lệch khỏi {khung}"


def test_trang_khong_co_khoi_nao_ra_trang_trang():
    """R5: overlay trả bản sao trang gốc; reflow ra trang trắng."""
    d = pdf_reflow.trang_theo_vi_tri(trang_scan(), 0, [])
    assert chu(d[0]).strip() == ""
    assert d[0].get_images(full=True) == []


def test_khung_y_am_duoc_kep_chu_khong_bi_mat():
    """R3: đo thật, 53/4.120 khối của harmonics có y âm."""
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0, [khoi(30, -3.0, 300, 40, "Tiêu đề chạy đầu trang")])
    assert "Tiêu đề" in chu(d[0])


def test_tran_o_bac_cuoi_thi_ve_chu_anh_goc_va_bao_tran():
    """R4: hết cách thì GIỮ — vẽ lại chữ Anh gốc vào đúng khung đó."""
    ghi = []
    dai = "Chữ Việt rất dài không thể nào vừa khung nhỏ này được. " * 30
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0, [khoi(10, 10, 110, 24, dai, src="Short")], ghi_nhan=ghi)
    assert "Short" in chu(d[0])
    assert "Chữ Việt rất dài" not in chu(d[0]), "bản tràn không được vẽ dở dang"
    assert ghi and ghi[0][2] is True, "khối tràn phải được báo để ghi cờ overflow"


def test_khoi_chua_dich_thi_hien_chu_anh():
    """Review Focus 1: trang dịch dở không có khoảng trắng im lặng."""
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0,
        [khoi(40, 60, 300, 100, "", src="Untranslated paragraph here")])
    assert "Untranslated paragraph" in chu(d[0])


def test_khung_han_ngoai_trang_bi_bo_qua():
    """Review Focus 4."""
    ghi = []
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0, [khoi(400, 100, 500, 200, "Ngoài trang")], ghi_nhan=ghi)
    assert chu(d[0]).strip() == ""
    assert ghi == []


def test_ca_hai_thu_tieng_deu_tran_van_ve_chu_anh_khong_de_trang():
    """Review toàn nhánh, tái hiện trên astrology trang 4-7: tiêu đề sách biến
    khỏi nửa dịch. Cả chữ Việt lẫn chữ Anh đều tràn ở bậc 70% nên khung bị để
    TRẮNG, trong khi cờ overflow nói 'đã giữ nguyên bản gốc'."""
    ghi = []
    viet = "Chữ Việt rất dài không thể nào vừa khung nhỏ này được. " * 30
    anh = "English that does not fit either at seventy percent. " * 30
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0, [khoi(10, 10, 110, 24, viet, src=anh)], ghi_nhan=ghi)
    assert "English that" in chu(d[0]), "khung bị bỏ trắng"
    assert "Chữ Việt rất dài" not in chu(d[0])
    assert ghi and ghi[0][2] is True, "vẫn phải báo tràn để ghi cờ"


def test_co_chu_bi_thoi_len_van_khong_mat_tieu_de():
    """Nguyên nhân thật của lỗi trên: layout.size bị thổi lên 26-120pt."""
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0,
        [khoi(40, 60, 300, 100, "SÁCH CHIÊM TINH", src="THE ASTROLOGY BOOK",
              size=120.0)])
    assert "ASTROLOGY" in chu(d[0])


def test_khoi_chua_dich_tran_van_hien_chu_anh():
    anh = "Untranslated English far too long for this tiny box. " * 30
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0, [khoi(10, 10, 110, 24, "", src=anh)])
    assert "Untranslated English" in chu(d[0])


def test_khung_kep_con_dai_mong_van_co_chu():
    """Khối 424 của harmonics: bbox 305.6,-1.6,319.7,2.5, kẹp còn cao 2,5pt.
    Trước bản sửa nó bị để trắng dù được báo là 'đúng R4'."""
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0, [khoi(305.6, -1.6, 319.7, 2.5, "ao", src="ao ", size=6.2)])
    assert d[0].get_text().strip(), "dải 2,5pt vẫn phải mang chữ"


def test_vi_tri_khoi_chua_dich_khong_vao_ghi_nhan():
    """D7 (lỗi nhỏ 6a): khối chưa dịch tràn thì vẫn hiện chữ Anh, nhưng không
    được tính vào thống kê và không bị gắn cờ overflow — đo thật ~154 cờ giả
    trên harmonics nếu xuất khi chưa dịch."""
    ghi = []
    anh = "Untranslated English far too long for this tiny box. " * 30
    d = pdf_reflow.trang_theo_vi_tri(
        trang_scan(), 0, [khoi(10, 10, 110, 24, "", src=anh)], ghi_nhan=ghi)
    assert "Untranslated English" in chu(d[0])
    assert ghi == []


# ------------------------------------------------ trang_reflow (spec 8A)

THAN = 10.0


def dan(khoi_list, ghi=None, du_phong=None):
    return pdf_reflow.trang_reflow(trang_scan(), 0, khoi_list, ghi_nhan=ghi,
                                   than=THAN, du_phong=du_phong)


def dinh_chu(page, tu):
    """Độ cao đỉnh của lần xuất hiện đầu tiên của một từ đánh dấu."""
    thay = page.search_for(tu)
    assert thay, f"không thấy '{tu}' trên trang"
    return min(r.y0 for r in thay)


def day_chu(page, tu):
    return max(r.y1 for r in page.search_for(tu))


def test_dan_khong_mang_anh_va_dung_kho():
    """R2 + khổ trang."""
    d = dan([khoi(40, 60, 300, 100, "Chữ Việt")])
    assert d[0].get_images(full=True) == []
    assert (d[0].rect.width, d[0].rect.height) == KHO


def test_dan_trang_khong_co_khoi_ra_trang_trang():
    """R5 / D8."""
    d = dan([])
    assert chu(d[0]).strip() == ""
    assert d[0].get_images(full=True) == []


def test_dan_con_cho_thi_neo_dung_do_cao_goc():
    """D1: còn chỗ thì khối nằm ở độ cao gốc."""
    d = dan([khoi(40, 300, 300, 330, "Neoday ở đây")])
    assert abs(dinh_chu(d[0], "Neoday") - 300) < 6


def test_dan_khung_chong_nhau_ra_ba_dai_tach_roi_dung_thu_tu():
    """Review Focus 4 — nguyên nhân gốc của lỗi đè chữ: khung OCR chồng nhau."""
    dai = " thêm chữ cho dài ra" * 12
    d = dan([khoi(30, 100, 310, 140, "Aaaxx" + dai, id_=1),
             khoi(30, 105, 310, 145, "Bbbxx" + dai, id_=2),
             khoi(30, 110, 310, 150, "Cccxx" + dai, id_=3)])
    p = d[0]
    assert day_chu(p, "Aaaxx") <= dinh_chu(p, "Bbbxx")
    assert dinh_chu(p, "Aaaxx") < dinh_chu(p, "Bbbxx") < dinh_chu(p, "Cccxx")


def test_dan_khong_hai_khoi_nao_chong_nhau():
    """Spec mục 7: 0 cặp chồng. Đo trên khung chữ thực vẽ của từng khối."""
    ds = [khoi(30, 60 + 5 * i, 310, 90 + 5 * i, f"Moc{i}x " + "chữ Việt " * 25,
               id_=i) for i in range(5)]
    d = dan(ds)
    p = d[0]
    for i in range(4):
        # từ cuối của khối i nằm trên từ đầu của khối i+1
        assert dinh_chu(p, f"Moc{i}x") < dinh_chu(p, f"Moc{i + 1}x")
    tu = p.get_text("words")
    theo_khoi = {}
    for w in tu:
        theo_khoi.setdefault(w[5], []).append(w)   # block_no của PyMuPDF
    hop = [(min(w[1] for w in ws), max(w[3] for w in ws))
           for ws in theo_khoi.values()]
    hop.sort()
    for (a0, a1), (b0, b1) in zip(hop, hop[1:]):
        assert a1 <= b0 + 0.5, f"hai khối chồng: {a0:.1f}-{a1:.1f} và {b0:.1f}-{b1:.1f}"


def test_dan_neo_am_van_hien_chu():
    """Review Focus 2 ở mức trang."""
    d = dan([khoi(30, -3.0, 300, 40, "Tiêu đề chạy đầu trang")])
    assert "Tiêu đề" in chu(d[0])


def test_dan_trang_nhieu_chu_co_chung_mot_he_so():
    """D5: mọi khối cùng một s < 1, không rơi về dự phòng."""
    ghi, dp = [], []
    doan = "Đây là một câu tiếng Việt khá dài để lấp đầy trang dịch. " * 17
    d = dan([khoi(30, 40 + 150 * i, 310, 180 + 150 * i, doan, id_=i)
             for i in range(3)], ghi=ghi, du_phong=dp)
    assert dp == [], "trang này phải vừa ở một bậc co, không cần dự phòng"
    he_so = {round(t, 3) for _, t, _ in ghi}
    assert len(he_so) == 1, f"các khối co khác nhau: {he_so}"
    assert he_so.pop() < 1.0, "độ dài chữ chưa đủ để phải co — chỉnh độ dài"
    assert all(not tran for _, _, tran in ghi)


def test_dan_khong_vua_o_0_75_thi_du_phong():
    """D6: rơi về trang_theo_vi_tri, được đếm, và khối tràn vẫn báo tràn."""
    ghi, dp = [], []
    d = dan([khoi(30, 60, 310, 100, "Chữ Việt rất dài. " * 1500, id_=7)],
            ghi=ghi, du_phong=dp)
    assert dp == [0]
    assert ghi and ghi[0][0] == 7 and ghi[0][2] is True
    assert d[0].get_images(full=True) == []


def test_dan_khoi_chua_dich_hien_chu_anh_khong_vao_ghi_nhan():
    """D7 / Review Focus 3."""
    ghi = []
    d = dan([khoi(40, 60, 300, 100, "", src="Untranslated paragraph here")],
            ghi=ghi)
    assert "Untranslated paragraph" in chu(d[0])
    assert ghi == []


def test_dan_khoi_hep_giu_tam_ngang():
    """D4: tiêu đề hẹp căn giữa vẫn ở giữa."""
    d = dan([khoi(137, 60, 197, 80, "Chương", kind="heading", size=14.0)])
    thay = d[0].search_for("Chương")
    tam = (thay[0].x0 + thay[0].x1) / 2
    assert abs(tam - 167) < 40


def test_dan_hai_cot_khong_day_nhau_khong_phai_co():
    """Task 4 Ruling: chỉ mục 2 cột (harmonics 470-480) rơi dự phòng vì cột
    phải bị xếp xuống dưới cột trái. Hai cột phải dàn song song ở cỡ gốc."""
    ghi, dp = [], []
    doan = "Mục chỉ mục tiếng Việt khá dài, " * 22
    d = dan([khoi(30, 40, 160, 300, "Trai " + doan, id_=1),
             khoi(175, 40, 305, 300, "Phai " + doan, id_=2)],
            ghi=ghi, du_phong=dp)
    assert dp == []
    assert {round(t, 3) for _, t, _ in ghi} == {1.0}, "hai cột mà phải co chữ"
    assert abs(dinh_chu(d[0], "Phai") - 40) < 6, "cột phải bị đẩy xuống"


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
