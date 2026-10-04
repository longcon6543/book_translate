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
    """Mảnh bên phải đặt CAO hơn 1pt (chỉ số trên, cỡ chữ khác) — nếu đặt thấp
    hơn thì nó đứng sau dù code có gom dòng hay không, và test không thể đỏ."""
    trai = line(100, "trai", x0=67.0)
    phai = line(99, "phai", x0=300.0)      # cao hơn 1pt, vẫn là cùng một dòng
    assert [l.text for l in pdf_layout.sort_reading_order([phai, trai])] == ["trai", "phai"]


def test_gom_dong_khong_phu_thuoc_vao_vi_tri_tuyet_doi():
    """Làm tròn y tuyệt đối cho dung sai thật 0..3pt tuỳ chỗ. Reviewer dựng lại:
    561/1120 cặp sai, và trên sách thật là 294 cặp trên 28 trang."""
    sai = 0
    for y in range(60, 620):
        trai = line(float(y), "trai", x0=67.0)
        phai = line(float(y) - 1.5, "phai", x0=300.0)
        if [l.text for l in pdf_layout.sort_reading_order([phai, trai])] != ["trai", "phai"]:
            sai += 1
    assert sai == 0, f"{sai}/560 vị trí y bị sắp sai thứ tự"


def test_sap_theo_cot_truoc_roi_moi_den_do_cao():
    c0 = line(300, "cot0-duoi"); c0.col = 0
    c1 = line(100, "cot1-tren"); c1.col = 1
    ket = pdf_layout.sort_reading_order([c1, c0])
    assert [l.text for l in ket] == ["cot0-duoi", "cot1-tren"]


def test_danh_sach_rong():
    assert pdf_layout.sort_reading_order([]) == []


def test_sap_thu_tu_ton_trong_so_trang():
    """Dòng đầu trang sau không được nhảy lên trước dòng cuối trang trước.

    sort_reading_order sắp theo (col, y, x0); nếu thiếu page_no thì y=60 của
    trang 1 đứng trước y=600 của trang 0 — đảo ngược mạch sách.
    """
    a = line(600, "cuoi trang 0", page_no=0)
    b = line(60, "dau trang 1", page_no=1)
    ket = pdf_layout.sort_reading_order([b, a])
    assert [l.text for l in ket] == ["cuoi trang 0", "dau trang 1"]


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


def test_nuot_gach_noi_khong_lam_vo_the_inline():
    """Từ bị gạch nối nằm trong <i> — cắt bừa ký tự cuối là vỡ thẻ đóng."""
    a = line(100, "as-"); a.html = "<i>as-</i>"
    b = line(112, "trology"); b.html = "<i>trology</i>"
    p = pdf_layout.group_paragraphs([a, b])[0]
    assert p.html.count("<i>") == p.html.count("</i>")
    assert "</" in p.html and "<i>as-</" not in p.html


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


def test_header_lap_lai_bi_danh_dau_skip():
    ps = []
    for t in range(10):
        # y đổi theo trang: không khe nào lặp, nên chỉ luật VÂN TAY NỘI DUNG
        # mới cứu được test này. Trước đây luật chỗ đứng cũng làm nó xanh, nên
        # gỡ luật vân tay đi mà không test nào đỏ.
        ps.append(para("Chiem Tinh Hoc Can Ban", size=9.0, page_no=t,
                       y0=20.0 + (t % 5) * 4))
        ps.append(para(f"noi dung rieng cua trang {t} " * 8, page_no=t, y0=100.0,
                       n_lines=5))
    pdf_layout.mark_running(ps, 10)
    assert [p.kind for p in ps if p.bbox[1] < 40.0] == ["skip"] * 10
    assert all(p.kind != "skip" for p in ps if p.bbox[1] == 100.0)


def test_so_trang_thay_doi_van_bi_skip():
    """Số trang khác nhau từng trang nhưng vẫn là footer."""
    ps = []
    for t in range(10):
        ps.append(para(str(100 + t), size=9.0, page_no=t,
                       y0=620.0 + (t % 5) * 4))          # y đổi theo trang
        ps.append(para(f"than bai trang {t} " * 10, page_no=t, y0=100.0, n_lines=5))
    pdf_layout.mark_running(ps, 10)
    assert [p.kind for p in ps if p.bbox[1] > 615.0] == ["skip"] * 10


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


def test_dau_ket_cau_moi_la_thu_quyet_dinh_co_noi_hay_khong():
    """Chữ hoa đầu dòng KHÔNG còn là căn cứ — xem ruling Task 9.

    Dòng trước kết câu thì không nối, dù dòng sau viết thường; dòng trước còn
    dang dở thì nối, dù dòng sau viết hoa.
    """
    a = para("da ket thuc han.", page_no=0, y0=600.0)
    b = para("con day la doan moi", page_no=1, y0=60.0)
    pdf_layout.link_continuations([a, b])
    assert a.cont_group is None

    c = para("con dang do", page_no=0, y0=600.0)
    d = para("Mars tiep tuc y do.", page_no=1, y0=60.0)
    pdf_layout.link_continuations([c, d])
    assert c.cont_group is not None and c.cont_group == d.cont_group


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


# ---- sửa sau nghiệm thu trên sách thật (Task 9 Step 7) ----

def test_vai_dong_can_phai_khong_bien_thanh_hai_cot():
    """Sách MỘT cột có mấy mục căn phải ngắn: khe trống giữa chúng và thân bài
    không phải ranh giới cột. Trên sách thật, lỗi này làm 351/911 trang bị
    tách cột nhầm và 214 trang sai thứ tự đọc."""
    than = [line(100 + i * 12, "than bai", x0=67.0, x1=400.0) for i in range(12)]
    can_phai = [line(100 + i * 60, "12", x0=457.0, x1=470.0) for i in range(2)]
    lines = than + can_phai
    pdf_layout.detect_columns(lines, 522.0)
    assert {l.col for l in lines} == {0}, "một bên quá thưa thì không phải hai cột"


def test_hai_cot_that_su_van_duoc_nhan_ra():
    """Sửa trên không được làm hỏng trường hợp hai cột thật."""
    trai = [line(100 + i * 12, "trai", x0=50.0, x1=240.0) for i in range(8)]
    phai = [line(100 + i * 12, "phai", x0=280.0, x1=470.0) for i in range(8)]
    lines = trai + phai
    pdf_layout.detect_columns(lines, 522.0)
    assert {l.col for l in phai} == {1}


def test_header_doi_theo_chuong_van_bi_bat():
    """Tên chương chạy đầu trang chỉ lặp trong phạm vi một chương, không lặp
    trên 60% cả cuốn. Trên sách thật, 871 đoạn header lọt lưới vì luật cũ."""
    ten = ["Cac Cung Hoang Dao", "Cac Hanh Tinh", "Cac Nha", "Cac Goc Chieu"]
    ps = []
    for t in range(40):
        ten_chuong = ten[t // 10]                 # đổi mỗi 10 trang, khác nhau bằng CHỮ
        ps.append(para(ten_chuong, size=9.0, page_no=t,
                       y0=20.0 + (t % 5) * 4))          # y đổi theo trang
        ps.append(para(f"than bai trang {t} " * 10, page_no=t, y0=100.0, n_lines=5))
    pdf_layout.mark_running(ps, 40)
    header = [p for p in ps if p.bbox[1] < 40.0]
    assert all(p.kind == "skip" for p in header), \
        f"còn {sum(1 for p in header if p.kind != 'skip')}/40 header chưa bị bắt"


def test_chu_xuat_hien_vai_trang_le_te_khong_bi_coi_la_header():
    """Một câu ngắn tình cờ nằm rìa trang ở vài trang rải rác không phải header."""
    ps = []
    for t in range(40):
        if t % 13 == 0:
            ps.append(para("cau ngan tinh co", size=9.0, page_no=t, y0=28.0))
        ps.append(para(f"than bai trang {t} " * 10, page_no=t, y0=100.0, n_lines=5))
    pdf_layout.mark_running(ps, 40)
    assert all(p.kind != "skip" for p in ps if p.bbox[1] == 28.0)


def test_trang_sau_mo_bang_danh_tu_rieng_van_duoc_noi():
    """Sách đầy tên hành tinh và cung hoàng đạo viết hoa. Luật cũ chặn theo
    chữ hoa làm chỉ 104/899 cặp trang được nối trên sách thật."""
    a = para("mot cau van con dang do noi ve", page_no=0, y0=600.0)
    b = para("Mars va Venus trong cung nay.", page_no=1, y0=60.0)
    pdf_layout.link_continuations([a, b])
    assert a.cont_group is not None and a.cont_group == b.cont_group


def test_chu_nho_hon_mot_chut_van_la_than_bai():
    """9pt trên nền 10pt là chữ thân bài cỡ nhỏ, không phải chú thích ảnh.
    Luật cũ gán 1147 đoạn thành caption, và caption bị loại khỏi nối trang."""
    ps = [para("noi dung " * 20, size=10.0, n_lines=8),
          para("mot doan chu nho hon mot chut nhung van la than bai", size=9.0)]
    pdf_layout.classify(ps)
    assert ps[1].kind == "text"


def test_running_head_doi_chu_tung_trang_van_bi_bat():
    """Sách tra cứu ghi mục từ của chính trang đó lên đầu trang, nên chữ KHÔNG
    BAO GIỜ lặp. Trên sách thật còn sót 566 đoạn kiểu này sau khi đã sửa luật
    cửa sổ. Dấu hiệu thật là chỗ đứng: cùng một khe ngoài vùng thân bài bị
    chiếm trên phần lớn số trang.
    """
    def muc_tu(i):
        # chỉ gồm CHỮ CÁI: _van_tay bỏ chữ số, nên nếu dùng số thì 40 trang sẽ
        # gộp thành một vân tay và luật cũ bắt được — test sẽ xanh giả.
        return "muc " + "".join(chr(97 + (i * j + j) % 26) for j in range(1, 7))

    ps = []
    for t in range(40):
        ps.append(para(muc_tu(t), size=9.0, page_no=t, y0=28.0))
        ps.append(para(f"than bai trang {t} " * 10, page_no=t, y0=100.0, n_lines=5))
    pdf_layout.mark_running(ps, 40)
    dau_trang = [p for p in ps if p.bbox[1] == 28.0]
    assert all(p.kind == "skip" for p in dau_trang), \
        f"còn {sum(1 for p in dau_trang if p.kind != 'skip')}/40 running head chưa bắt"


def test_luat_cho_dung_khong_duoc_dung_cho_vung_than_bai():
    """Chốt lại điều spec cảnh báo: dòng thân bài cũng lặp vị trí vì sách xếp
    lưới đều. Luật chỗ đứng chỉ áp dụng NGOÀI vùng thân bài."""
    ps = [para(f"cau van dai binh thuong o trang {t}, du dai de khong bi coi la "
               f"header ngan", page_no=t, y0=571.0) for t in range(40)]
    pdf_layout.mark_running(ps, 40)
    assert all(p.kind != "skip" for p in ps)


def test_vung_than_bai_phai_theo_chieu_cao_trang():
    """VUNG_THAN_BAI là số tuyệt đối lấy từ sách cao 666pt. Trên A4 (842pt) nó
    tuyên bố 227pt cuối trang — 27% chiều cao — là lề, nên luật chỗ đứng xoá
    mất chữ thân bài thật. Reviewer dựng lại được: 20/20 trang A4 mất chữ.
    """
    cao = 842.0                                    # A4
    ps = []
    for t in range(20):
        # đoạn ngắn nằm ở 1/4 dưới trang A4 — vẫn thừa chỗ phía dưới, là thân bài
        ps.append(para(f"ket luan cua trang {chr(97 + t)}", page_no=t, y0=735.0))
        ps.append(para(f"than bai trang {t} " * 10, page_no=t, y0=100.0, n_lines=5))
    pdf_layout.mark_running(ps, 20, page_height=cao)
    duoi = [p for p in ps if p.bbox[1] == 735.0]
    assert all(p.kind != "skip" for p in duoi), \
        f"xoá mất {sum(1 for p in duoi if p.kind == 'skip')}/20 đoạn thân bài A4"


def test_header_van_bi_bat_tren_trang_a4():
    """Sửa trên không được làm luật mất tác dụng ở khổ khác."""
    ps = []
    for t in range(20):
        ps.append(para(f"muc tu {chr(97 + t)}{chr(98 + t)}", size=9.0,
                       page_no=t, y0=30.0))
        ps.append(para(f"than bai trang {t} " * 10, page_no=t, y0=120.0, n_lines=5))
    pdf_layout.mark_running(ps, 20, page_height=842.0)
    assert all(p.kind == "skip" for p in ps if p.bbox[1] == 30.0)


def test_cot_phai_thua_dong_o_cuoi_chuong_van_la_cot():
    """Trang cuối chương của sách hai cột có cột phải ngắn. Luật cân bằng theo
    SỐ DÒNG làm hai cột sập lại và trộn xen kẽ thành đoạn vô nghĩa."""
    trai = [line(100 + i * 12, f"T{i}", x0=50.0, x1=240.0) for i in range(20)]
    phai = [line(100 + i * 12, f"P{i}", x0=280.0, x1=470.0) for i in range(6)]
    lines = trai + phai
    pdf_layout.detect_columns(lines, 522.0)
    assert {l.col for l in phai} == {1}, "cột phải thưa dòng bị sập vào cột trái"
    ket = [l.text for l in pdf_layout.sort_reading_order(lines)]
    assert ket[:3] == ["T0", "T1", "T2"], f"trộn xen kẽ: {ket[:6]}"


def test_luat_can_bang_van_chan_duoc_muc_can_phai_ngan():
    """Sửa trên không được làm sống lại lỗi 351 trang tách cột nhầm."""
    than = [line(100 + i * 12, "than bai", x0=67.0, x1=400.0) for i in range(12)]
    can_phai = [line(100 + i * 60, "12", x0=457.0, x1=470.0) for i in range(2)]
    lines = than + can_phai
    pdf_layout.detect_columns(lines, 522.0)
    assert {l.col for l in lines} == {0}


def test_tieu_de_in_dam_viet_hoa_cung_co_la_tieu_de():
    """Sách tra cứu in mục từ 10.2pt đậm viết hoa trên nền 10.0pt — tỉ lệ 1.02
    nên luật chỉ-theo-cỡ-chữ bỏ sót 811 đoạn trên sách thật."""
    p_body = para("noi dung " * 20, size=10.0, n_lines=8)
    p_head = para("ACCIDENTAL DIGNITY", size=10.2)
    p_head.html = "<b>ACCIDENTAL DIGNITY</b>"
    pdf_layout.classify([p_body, p_head])
    assert p_head.kind == "heading"


def test_chu_dam_giua_cau_khong_bien_ca_doan_thanh_tieu_de():
    p_body = para("noi dung " * 20, size=10.0, n_lines=8)
    p = para("mot cau co mot tu in dam o giua va viet thuong", size=10.0)
    p.html = "mot cau co mot tu <b>in dam</b> o giua va viet thuong"
    pdf_layout.classify([p_body, p])
    assert p.kind == "text"


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


def test_ghep_manh_danh_sach_rong():
    assert pdf_layout.ghep_manh_cung_hang([]) == []


def test_khong_ghep_o_le_tren_va_le_duoi():
    """Nghiệm thu Phase 7 đo thật: ghép ở lề làm tiêu đề chạy dính mảnh rác OCR
    khác nhau từng trang, thoát khỏi mark_running — khối ở lề trên tăng từ 180
    lên 474, thêm 6.346 ký tự tiêu đề vào DB để đem đi dịch. Lề trang chỉ chứa
    tiêu đề chạy, chân trang, số trang: không có đoạn văn nào để chia sai."""
    dau = [line(10, "running head", x0=67, x1=200), line(10, "50", x0=208, x1=220)]
    chan = [line(630, "footer text", x0=67, x1=200), line(630, "51", x0=208, x1=220)]
    assert len(pdf_layout.ghep_manh_cung_hang(dau, page_height=666.0)) == 2
    assert len(pdf_layout.ghep_manh_cung_hang(chan, page_height=666.0)) == 2


def test_le_tinh_theo_chieu_cao_trang_that():
    """Cùng luật với mark_running: lề tính theo khổ trang thật. Sách scan khổ
    547pt có lề trên ở y < 32,9 chứ không phải 40."""
    ls = [line(35, "body text starts high", x0=67, x1=200),
          line(35, "tail", x0=208, x1=230)]
    assert len(pdf_layout.ghep_manh_cung_hang(ls, page_height=547.0)) == 1
    assert len(pdf_layout.ghep_manh_cung_hang(ls, page_height=666.0)) == 2


def test_tach_theo_vung_chia_le_tren_than_bai_le_duoi():
    """Cùng luật lề với mark_running: y0 < lề trên, y0 > lề dưới."""
    tren, than, duoi = pdf_layout.tach_theo_vung(
        [line(100, "than 1"), line(10, "dau"), line(630, "chan"), line(200, "than 2")],
        page_height=666.0)
    assert [l.text for l in tren] == ["dau"]
    assert [l.text for l in than] == ["than 1", "than 2"]
    assert [l.text for l in duoi] == ["chan"]


def test_tach_theo_vung_danh_sach_rong():
    assert pdf_layout.tach_theo_vung([], page_height=547.0) == ([], [], [])


def test_gom_doan_theo_vung_dung_gian_dong_cua_ca_trang():
    """Review toàn nhánh Phase 7, đo trên sách scan thật: gom đoạn riêng từng
    vùng làm khoảng cách dòng 'bình thường' tính trên vài dòng của vùng đó. Ở
    lề trên thường chỉ có một khoảng (rác OCR -> số trang), nó thành 'bình
    thường' nên không bao giờ tách; rác dính số trang, thoát mark_running, và
    10 số trang bị đem đi dịch."""
    tren = [line(0, "xq", x0=400, x1=420), line(28, "50", x0=67, x1=80)]
    than = [line(100 + 12 * i, f"body line {i}") for i in range(4)]
    # Tiền đề: chỉ đưa riêng lề trên cho group_paragraphs là dính thành một đoạn.
    assert len(pdf_layout.group_paragraphs(tren)) == 1
    doan = pdf_layout.gom_doan_theo_vung(tren + than, page_height=666.0)
    o_le = [p for p in doan if p.bbox[1] < 40]
    assert len(o_le) == 2, "rác và số trang phải là hai đoạn, như khi gom cả trang"
    assert [p.text for p in doan if p.bbox[1] >= 40] == [
        "body line 0 body line 1 body line 2 body line 3"]


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


def test_cot_so_trang_co_manh_ocr_doc_sai_van_duoc_noi():
    """Nghiệm thu 8B: mục lục thật có số trang bị OCR đọc sai ("5a8" thay cho
    285) nằm trong cột số — luật "cột toàn số" không bao giờ đúng, 0 mảnh nào
    được nối. Đo thật: cột số mục lục 75-88% là số; cột phải chỉ mục 0-13%."""
    ls = (_hang_muc(100, "Chuong mot", "12", col_so=1)
          + _hang_muc(112, "Chuong hai", "34", col_so=1)
          + _hang_muc(124, "Chuong ba", "56", col_so=1)
          + _hang_muc(136, "Chuong bon", "5a8", col_so=1))
    ra = pdf_layout.noi_so_trang(ls, 548)
    assert "Chuong mot 12" in [l.text for l in ra]
    assert sum(l.ket_doan for l in ra) == 3
