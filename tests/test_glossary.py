"""Trích ứng viên thuật ngữ. Hàm thuần: không DB, không mạng."""
import glossary


def test_dem_tu_viet_hoa_theo_tan_suat():
    doan = ["Sao Mars va Venus", "Mars lai xuat hien", "Mars lan nua"]
    ra = dict(glossary.ung_vien(doan))
    assert ra["Mars"] == 3
    assert ra["Venus"] == 1


def test_sap_theo_tan_suat_giam_dan():
    """Từ phải xuất hiện GIỮA câu ít nhất vài lần, nếu không luật 'chỉ viết
    hoa vì đứng đầu câu' loại nó đi — và đó là hành vi đúng."""
    doan = ["x Aaa y Bbb", "x Aaa y", "x Aaa y", "x Bbb y"]
    ra = glossary.ung_vien(doan)
    assert ra[0][0] == "Aaa" and ra[0][1] == 3


def test_bo_the_html_truoc_khi_dem():
    """Tên thẻ không được đếm thành thuật ngữ."""
    ra = dict(glossary.ung_vien(["sao <b>Mars</b> va <i>Venus</i> sang"]))
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
    """Tên mẫu phải toàn chữ cái: regex đòi ranh giới từ sau chuỗi chữ, nên
    'Term0' không khớp gì cả (sau 'Term' là chữ số, không phải ranh giới)."""
    ten = [f"Muc{chr(97 + i // 26)}{chr(97 + i % 26)}" for i in range(50)]
    doan = ["x " + " ".join(ten) + " y" for _ in range(3)]
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


def test_lenh_glossary_ghi_ra_file_ung_vien(source_epub, tmp_path, capsys):
    import argparse

    import cli
    from helpers import run_init

    proj = run_init(source_epub, tmp_path / "proj")
    cli.cmd_glossary(argparse.Namespace(project=str(proj), top=50))
    ra = (proj / "glossary.candidates.txt")
    assert ra.exists()
    noi = ra.read_text(encoding="utf-8")

    # "Chapter" KHÔNG có mặt, và đó là đúng: trong EPUB mẫu nó chỉ đứng đầu
    # tiêu đề và đầu mục lục, nên luật "chỉ viết hoa vì đứng đầu câu" loại nó.
    # Tiêu đề không phải thuật ngữ cần khai.
    assert "Chapter" not in noi
    # Còn từ nằm GIỮA tên sách thì có, kèm số lần xuất hiện.
    assert "Book = " in noi and "lần" in noi
    assert "glossary.candidates.txt" in capsys.readouterr().out


def test_lenh_glossary_khong_dung_khoi_skip(source_epub, tmp_path):
    """Header/footer là kind='skip'; chúng không phải thuật ngữ của sách."""
    import argparse

    import cli
    import db
    from helpers import run_init

    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    con.execute("UPDATE blocks SET src_html='x Zzzmarker y', kind='skip' "
                "WHERE id=(SELECT MIN(id) FROM blocks)")
    con.commit()
    cli.cmd_glossary(argparse.Namespace(project=str(proj), top=200))
    assert "Zzzmarker" not in (proj / "glossary.candidates.txt").read_text(
        encoding="utf-8")
