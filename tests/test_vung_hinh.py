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


def test_hai_vung_no_ra_chong_nhau_thi_gop_lam_mot():
    """Nghiệm thu 8B: hai hạt nhân cách nhau > 20pt cùng nuốt một ký hiệu ở
    giữa, nở thành hai vùng chồng nhau — 31 trang harmonics có vùng trùng lặp
    (trang 145: 4 vùng giống hệt), ô 'ảnh' xếp chồng dọc làm trang tràn."""
    buf, r, c = anh()
    ve(buf, r, 40, 40, 42, 100)
    ve(buf, r, 72, 40, 74, 100)
    ve(buf, r, 52, 60, 62, 66)
    assert vh.tim_vung(tp_cua(buf, r, c), [], r, c) == [(40, 40, 74, 100)]


# ---- review toàn nhánh 8B (Important): E6 bỏ mất chữ thật cạnh hình

def test_chu_thich_co_ky_hieu_dau_dong_van_la_chu_thich():
    """Trang 331: OCR đặt một ký hiệu + dấu cách trước 'Figure' (vạch lề
    trái) — regex neo đầu dòng trượt, dòng đầu chú thích bị bỏ."""
    assert vh.la_chu_thich("| Figure 12.3 The chart")
    assert vh.la_chu_thich("© Fig. 2 the chart")
    assert not vh.la_chu_thich("see Figure 2")


def test_dong_cuoi_doan_ngan_duoi_van_xuoi_duoc_bao_ve():
    """Trang 235: dòng cuối đoạn 2 từ ngay dưới dòng văn xuôi — không đủ tiêu
    chuẩn 'văn xuôi', bị vùng hình nuốt, câu mất đuôi."""
    dong = [((20, 99, 190, 109), "a full line of real prose goes here"),
            ((20, 111, 70, 121), "ended here.")]
    assert (20, 111, 70, 121) in vh.dong_bao_ve(dong)


def test_dong_lan_ky_hieu_ngay_tren_van_xuoi_duoc_bao_ve():
    dong = [((20, 87, 120, 97), "Q/M = ©"),
            ((20, 99, 190, 109), "a full line of real prose goes here")]
    assert (20, 87, 120, 97) in vh.dong_bao_ve(dong)


def test_dong_lech_le_trai_khong_ke_thua_bao_ve():
    """Nhãn trong hình nằm dưới đoạn văn nhưng lệch lề trái: không phải dòng
    tiếp của đoạn."""
    dong = [((20, 99, 190, 109), "a full line of real prose goes here"),
            ((80, 111, 110, 121), "K Ores")]
    assert (80, 111, 110, 121) not in vh.dong_bao_ve(dong)


def test_vung_khong_nuot_dong_cuoi_doan_ngan():
    buf, r, c = anh()
    ve(buf, r, 90, 125, 92, 200)               # nét hình
    ve(buf, r, 80, 113, 88, 120)               # chữ của dòng cuối đoạn ngắn
    dong = [((20, 99, 190, 109), "a full line of real prose goes here"),
            ((20, 111, 95, 121), "ended here.")]
    assert vh.tim_vung(tp_cua(buf, r, c), dong, r, c) == [(90, 125, 92, 200)]
