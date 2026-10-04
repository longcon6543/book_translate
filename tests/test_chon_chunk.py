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
