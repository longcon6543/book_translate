"""Gom block thành chunk. Hàm thuần, không đụng DB, không đụng mạng."""
from blocks import Block
from chunking import make_chunks


def b(page_no, chars, pos=0):
    return Block(page_no=page_no, pos=pos, tag="p", src_html="x" * chars)


def test_gom_den_khi_day_chunk():
    chunks = make_chunks([b(0, 40), b(0, 40), b(0, 40)], max_chars=100)
    assert [len(c) for c in chunks] == [2, 1]


def test_khong_tron_trang_that_voi_muc_luc():
    """page_no âm là mục lục và tên sách — phải nằm chunk riêng."""
    chunks = make_chunks([b(0, 10), b(-1, 10), b(-2, 10)], max_chars=1000)
    assert len(chunks) == 3


def test_sang_trang_moi_thi_cat_khi_chunk_da_kha_day():
    chunks = make_chunks([b(0, 60), b(1, 10)], max_chars=100)
    assert [len(c) for c in chunks] == [1, 1]


def test_sang_trang_moi_nhung_chunk_con_rong_thi_khong_cat():
    chunks = make_chunks([b(0, 10), b(1, 10)], max_chars=100)
    assert [len(c) for c in chunks] == [2]


def test_danh_sach_rong():
    assert make_chunks([], max_chars=100) == []


def test_mot_block_to_hon_ca_chunk_van_di_mot_minh():
    chunks = make_chunks([b(0, 500), b(0, 10)], max_chars=100)
    assert [len(c) for c in chunks] == [1, 1]


def test_as_row_dung_thu_tu_va_khong_gom_db_id():
    blk = Block(page_no=7, pos=2, tag="p", src_html="xin chao",
                layout={"href": "c1.xhtml"})
    blk.db_id = 99
    row = blk.as_row()
    assert row[0] == 7 and row[1] == 2 and row[2] == "p" and row[3] == "text"
    assert row[4] == "xin chao"
    assert row[7] == '{"href":"c1.xhtml"}'
    assert 99 not in row          # db_id là chuyện của Python, không phải của cột
    assert len(row) == 9
