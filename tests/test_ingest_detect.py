"""Nhận diện bằng nội dung file, không bao giờ bằng phần mở rộng.

Đây là lỗi đã thật sự xảy ra: một file PDF được copy thành source.epub và cả
pipeline chết ở tầng sâu với thông báo vô nghĩa.
"""
import zipfile

import pytest

import ingest


def test_epub_that_duoc_nhan_dien(source_epub):
    assert ingest.detect_format(source_epub) == "epub"


def test_pdf_mang_duoi_epub_van_bi_nhan_ra(tmp_path):
    fake = tmp_path / "sach.epub"
    fake.write_bytes(b"%PDF-1.6\r\n%\xe2\xe3\xcf\xd3\r\n")
    assert ingest.detect_format(fake) == "pdf"


def test_file_rong_bao_loi_ro(tmp_path):
    empty = tmp_path / "rong.epub"
    empty.write_bytes(b"")
    with pytest.raises(ingest.UnsupportedSource, match="rỗng"):
        ingest.detect_format(empty)


def test_zip_khong_phai_epub_bao_loi_ro(tmp_path):
    z = tmp_path / "taptin.epub"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("hello.txt", "xin chao")
    with pytest.raises(ingest.UnsupportedSource, match="EPUB"):
        ingest.detect_format(z)


def test_file_khong_ton_tai(tmp_path):
    with pytest.raises(ingest.UnsupportedSource, match="không thấy"):
        ingest.detect_format(tmp_path / "khong-co.epub")


def test_file_la_bao_loi_ro(tmp_path):
    odd = tmp_path / "sach.epub"
    odd.write_bytes(b"Xin chao, day la van ban thuong.")
    with pytest.raises(ingest.UnsupportedSource, match="không phải PDF hay EPUB"):
        ingest.detect_format(odd)


def test_pdf_nay_da_duoc_ho_tro():
    assert "pdf" in ingest.SUPPORTED_FORMATS
    assert "epub" in ingest.SUPPORTED_FORMATS


def test_load_epub_tra_ve_block(source_epub):
    result = ingest.load(source_epub)
    assert result.fmt == "epub"
    assert result.source_name == "short.epub"
    tags = [b.tag for b in result.blocks]
    assert "h1" in tags and "p" in tags and "li" in tags
    assert all(b.kind == "text" for b in result.blocks if b.page_no >= 0)
    assert any(b.layout.get("href") == "c1.xhtml" for b in result.blocks)
