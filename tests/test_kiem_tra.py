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


def test_khoa_viet_hoa_chi_khop_cho_viet_hoa():
    """Đo thật trên sách: "Neptune's moon Triton" bị báo thiếu "Mặt Trăng".

    "moon" thường là vệ tinh, "Moon" mới là Mặt Trăng; "mercury" là thuỷ ngân,
    "Mercury" là Thuỷ Tinh. Khoá viết hoa mà khớp bất kể hoa thường thì trên
    909 trang sách thiên văn, nhiễu sẽ chôn vùi những cờ thật.
    """
    bang = {"Moon": "Mặt Trăng"}
    assert check_translation("Neptune's moon Triton is a KBO.",
                             "Triton, vệ tinh của Hải Vương Tinh, là một KBO.",
                             thuat_ngu=bang) is None


def test_khoa_viet_hoa_van_bat_khi_ban_goc_viet_hoa():
    """Đừng sửa quá tay: đúng chỗ cần bắt thì vẫn phải bắt."""
    bang = {"Moon": "Mặt Trăng"}
    assert check_translation("The Moon rules Cancer.",
                             "Thiên thể này cai quản Cự Giải.",
                             thuat_ngu=bang) == "missing_term"


def test_khoa_viet_thuong_van_khop_bat_ke_hoa_thuong():
    """Khoá người dùng viết thường là họ có ý nói mọi cách viết."""
    bang = {"natal chart": "bản đồ sao"}
    assert check_translation("Her Natal Chart shows this.",
                             "Điều này hiện ra rõ ràng.",
                             thuat_ngu=bang) == "missing_term"


def test_cac_luat_cu_van_chay():
    assert check_translation("<em>hi</em>", "") == "empty"
    assert check_translation("<em>hi there</em>", "chào") == "tag_mismatch"


def test_doan_giu_nguyen_ban_goc_khong_bi_bao_thieu_thuat_ngu():
    """Đo thật: 243/417 đoạn đã dịch là mục lục tra cứu A-Z, model cố ý giữ
    nguyên — dịch sang tiếng Việt sẽ phá thứ tự chữ cái và làm mục lục vô dụng.

    Giữ nguyên bản gốc thì câu "bản dịch đánh rơi thuật ngữ" không có nghĩa:
    không có bản dịch nào cả. Luật cũ sinh 30 cờ trên 417 đoạn, 28 trong số đó
    ở mục lục.
    """
    bang = {"Aquarius": "Bảo Bình"}
    muc_luc = "Aquarius 42 Aquinas, Thomas 19 Ara 7"
    assert check_translation(muc_luc, muc_luc, thuat_ngu=bang) is None


def test_giu_nguyen_ban_goc_van_bi_bat_neu_the_lech():
    """Đừng sửa quá tay: bỏ qua kiểm thuật ngữ thôi, các luật khác vẫn chạy."""
    assert check_translation("<em>Aquarius</em> 42", "Aquarius 42") == "tag_mismatch"


def test_dich_that_ma_roi_thuat_ngu_thi_van_bi_bat():
    """Chỉ đoạn GIỐNG HỆT mới được bỏ qua. Dịch thật mà rơi thuật ngữ vẫn bắt."""
    bang = {"Aquarius": "Bảo Bình"}
    assert check_translation("Aquarius rules the eleventh house.",
                             "Cung này cai quản nhà thứ mười một.",
                             thuat_ngu=bang) == "missing_term"
