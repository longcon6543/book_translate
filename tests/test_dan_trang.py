"""Phần tính vị trí của reflow: hàm thuần, không PyMuPDF, không gọi mạng."""
import pytest

from render import dan_trang as dt


# ---- co_khoi (D3)

def test_than_bai_dung_mot_co_chung():
    assert dt.co_khoi("text", 7.3, 9.1) == 9.1
    assert dt.co_khoi("text", 14.0, 9.1) == 9.1


def test_tieu_de_kep_giua_than_va_gap_doi():
    assert dt.co_khoi("heading", 14.0, 9.1) == 14.0
    assert dt.co_khoi("heading", 6.0, 9.1) == 9.1
    assert dt.co_khoi("heading", 120.0, 9.1) == pytest.approx(18.2)


@pytest.mark.parametrize("kind", ["caption", "table", "formula"])
def test_loai_khac_kep_tu_0_8_than_toi_than(kind):
    assert dt.co_khoi(kind, 8.0, 10.0) == 8.0
    assert dt.co_khoi(kind, 3.1, 10.0) == pytest.approx(8.0), "dòng OCR cỡ vài pt (7b)"
    assert dt.co_khoi(kind, 12.0, 10.0) == 10.0


# ---- khung_ngang (D4)

def test_khoi_rong_keo_ra_du_khung():
    # khung chữ 22..328 rộng 306; khối rộng 200 >= 60%
    assert dt.khung_ngang(40, 240, 22, 328) == (22, 328)


def test_khoi_hep_giu_nguyen_be_rong_va_vi_tri():
    # rộng 100: dưới 60% nhưng trên 25% -> giữ nguyên
    assert dt.khung_ngang(125, 225, 22, 328) == (125, 225)


def test_khoi_hep_bi_day_vao_trong_khung():
    a, b = dt.khung_ngang(300, 400, 22, 328)
    assert (a, b) == (228, 328)


def test_khoi_qua_hep_duoc_noi_toi_thieu_quanh_tam_goc():
    """Review Focus 1: 236 khối harmonics rộng < 10% khung. Giữ vài pt là
    ép chữ Việt thành cột một chữ, cao hơn trang, kéo cả trang về dự phòng."""
    a, b = dt.khung_ngang(170, 180, 22, 328)
    toi_thieu = dt.TI_LE_KHOI_HEP_MIN * 306
    assert b - a == pytest.approx(toi_thieu)
    assert (a + b) / 2 == pytest.approx(175)


def test_khoi_qua_hep_o_mep_van_nam_trong_khung():
    a, b = dt.khung_ngang(320, 330, 22, 328)
    assert b == pytest.approx(328) and a >= 22


def test_khoi_be_rong_am_hoac_bang_khong_van_ra_khung_hop_le():
    a, b = dt.khung_ngang(200, 200, 22, 328)
    assert b - a == pytest.approx(dt.TI_LE_KHOI_HEP_MIN * 306)


# ---- xep_doc (D1 + D5 bước 1-2)

def test_con_cho_thi_nam_dung_do_cao_neo():
    assert dt.xep_doc([50, 200], [30, 30], 22, 525, 4) == [50, 200]


def test_khoi_truoc_dai_ra_day_khoi_sau_xuong():
    y = dt.xep_doc([50, 100], [80, 30], 22, 525, 4)
    assert y == [50, 134]


def test_khong_cap_nao_chong_nhau():
    neo, cao = [50, 60, 70, 80], [40, 40, 40, 40]
    y = dt.xep_doc(neo, cao, 22, 525, 4)
    for i in range(len(y) - 1):
        assert y[i] + cao[i] + 4 <= y[i + 1] + 1e-9


def test_thu_tu_dinh_tang_dan_dung_thu_tu_vao():
    y = dt.xep_doc([300, 50, 200], [20, 20, 20], 22, 525, 4)
    assert y == sorted(y)
    assert y[0] == 300, "neo khối đầu, khối sau không được chen lên trên"


def test_neo_am_kep_vao_dinh_khung():
    """Review Focus 2: 53 khối harmonics có y0 âm."""
    assert dt.xep_doc([-3, 100], [20, 20], 22, 525, 4) == [22, 100]


def test_neo_tran_day_thi_day_nguoc_tu_day():
    # neo khối 2 ở 480, cao 60 -> đáy 540 > 525; đẩy ngược: khối 2 lên 465,
    # khối 1 vẫn vừa ở neo 200.
    y = dt.xep_doc([200, 480], [100, 60], 22, 525, 4)
    assert y == [200, 465]


def test_mot_khoi_tran_day_khong_keo_ca_trang_len_dinh():
    """Review toàn nhánh (Important): 27/468 trang harmonics bị dồn khít từ
    đỉnh chỉ vì một dòng chân trang neo dưới lề — khối dời tới 300pt, trang
    dịch mất gióng hàng với trang gốc dù còn thừa chỗ."""
    y = dt.xep_doc([100, 200, 300, 515], [40, 40, 40, 20], 22, 525, 4)
    assert y == [100, 200, 300, 505]


def test_day_nguoc_chi_nang_vua_du():
    # khối 3 phải lên 485 (525-40); khối 2 phải lên 485-4-40 = 441 dù neo 460
    y = dt.xep_doc([100, 460, 510], [40, 40, 40], 22, 525, 4)
    assert y == [100, 441, 485]


def test_neo_duoi_day_khung_van_duoc_dat_trong_khung():
    """Review Focus 2: khối neo dưới đáy khung không được mất."""
    y = dt.xep_doc([50, 600], [20, 20], 22, 525, 4)
    assert y == [50, 505]


def test_don_khit_van_tran_thi_tra_none():
    assert dt.xep_doc([50, 60], [300, 300], 22, 525, 4) is None


def test_khong_co_khoi_nao():
    assert dt.xep_doc([], [], 22, 525, 4) == []


# ---- xep_doc nhiều cột (Task 4 Ruling: chỉ đẩy dưới khối chồng theo chiều ngang)

def test_khoi_khong_chong_ngang_thi_khong_day_nhau():
    """Chỉ mục 2 cột (harmonics trang 470-480, dò cột không bắt được): cột phải
    không được bị đẩy xuống dưới cột trái."""
    ngang = [(22, 170), (22, 170), (180, 328), (180, 328)]
    y = dt.xep_doc([50, 60, 50, 60], [200, 200, 200, 200], 22, 525, 4, ngang)
    assert y == [50, 254, 50, 254]


def test_khoi_chong_ngang_mot_phan_van_bi_day():
    ngang = [(22, 200), (150, 328)]
    y = dt.xep_doc([50, 60], [100, 30], 22, 525, 4, ngang)
    assert y == [50, 154]


def test_nhieu_cot_khong_cap_nao_chong():
    ngang = [(22, 170), (180, 328), (100, 250), (22, 328)]
    neo, cao = [50, 55, 60, 65], [40, 40, 40, 40]
    y = dt.xep_doc(neo, cao, 22, 525, 4, ngang)
    for i in range(4):
        for j in range(i):
            if ngang[i][0] < ngang[j][1] and ngang[j][0] < ngang[i][1]:
                assert y[j] + cao[j] + 4 <= y[i] + 1e-9


def test_nhieu_cot_tran_day_xet_moi_cot():
    """Đáy trang phải xét cả cột nào xuống thấp nhất, không chỉ khối cuối."""
    ngang = [(22, 170), (22, 170), (180, 328)]
    y = dt.xep_doc([50, 300, 50], [240, 240, 30], 22, 525, 4, ngang)
    # neo: cột trái 50, 300 -> đáy 540 > 525; đẩy ngược cột trái: 285, rồi
    # 285-4-240 = 41; cột phải không bị kéo theo.
    assert y == [41, 285, 50]
