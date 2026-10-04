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
    """Khung cao 16pt: đo thật cho thấy bóp giãn dòng thôi chưa đủ, phải thu
    cỡ chữ. Khung 30pt như kế hoạch viết ban đầu thì bậc 2 của thang (giãn dòng
    0.95) đã vừa rồi, nên test không ép được đường nó tuyên bố kiểm."""
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    ti_le, tran = pdf_overlay.dat_chu(page, pymupdf.Rect(10, 10, 290, 26),
                                      "Một đoạn văn tiếng Việt khá dài " * 4,
                                      10.0, kho)
    assert 0 < ti_le < 1.0, f"phải co lại, nhưng ti_le={ti_le}"
    assert tran is False
    dat = page.get_text().replace("\xa0", " ").strip()
    assert len(dat) > 100, "co lại thì phải đặt ĐỦ chữ, không được cắt cụt"
    doc.close()


def test_bao_vua_thi_chu_that_su_duoc_dat_du():
    """insert_htmlbox trả thua=-1 khi KHÔNG đặt được chữ nào (đo thật: 0/128
    ký tự). Nếu nó báo vừa mà lại cắt cụt thì cả thang tự co vô nghĩa."""
    doc, page = trang_trang()
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())
    noi = "Một đoạn văn tiếng Việt khá dài " * 4
    ti_le, tran = pdf_overlay.dat_chu(page, pymupdf.Rect(10, 10, 290, 26),
                                      noi, 10.0, kho)
    assert tran is False
    dat = page.get_text().replace("\xa0", " ").strip()
    assert len(dat) >= len(noi) - 2, f"đặt thiếu: {len(dat)}/{len(noi)}"
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
