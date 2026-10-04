"""Dịch một chunk, dùng provider giả. Không gọi mạng."""
import pytest

import db
import translator
from helpers import run_init


class FakeFatal(Exception):
    pass


class FakeRetryable(Exception):
    pass


class FakeProvider:
    """Trả lời theo một danh sách kịch bản đã soạn sẵn."""

    NAME = "fake"
    DEFAULT_MODEL = "fake-1"
    SUPPORTS_CACHE = False

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []

    def make_client(self):
        return object()

    def is_fatal(self, exc):
        return isinstance(exc, FakeFatal)

    def is_retryable(self, exc):
        return isinstance(exc, FakeRetryable)

    def call(self, client, model, system, user, max_tokens):
        self.calls.append(user)
        item = self.scripts.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def echo_segments(user: str, wrap=lambda s: f"[VI] {s}"):
    """Dựng câu trả lời hợp lệ từ chính các <seg> trong prompt."""
    import re
    out = []
    for sid, body in re.findall(r'<seg id="(\d+)"[^>]*>(.*?)</seg>', user, re.S):
        out.append(f'<seg id="{sid}">{wrap(body)}</seg>')
    return "\n".join(out)


USAGE = {"input": 10, "output": 20, "cache_read": 0, "cache_write": 0}


@pytest.fixture
def project(source_epub, tmp_path):
    proj = run_init(source_epub, tmp_path / "proj")
    return proj, db.connect(proj)


def test_dich_thanh_cong_luu_vao_db(project):
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            return echo_segments(user), USAGE, "end_turn"

    p = P([])
    res = translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)

    assert res["status"] == "done"
    assert res["missing"] == 0
    rows = con.execute(
        "SELECT dst_html FROM blocks WHERE chunk_id=?", (cid,)).fetchall()
    assert all(r["dst_html"].startswith("[VI] ") for r in rows)


def test_thieu_doan_thi_thu_lai_roi_thanh_cong(project):
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]

    class P(FakeProvider):
        def __init__(self):
            super().__init__([])
            self.n = 0

        def call(self, client, model, system, user, max_tokens):
            self.n += 1
            if self.n == 1:
                segs = echo_segments(user).split("\n")
                return "\n".join(segs[:-1]), USAGE, "end_turn"   # bỏ sót đoạn cuối
            return echo_segments(user), USAGE, "end_turn"

    p = P()
    res = translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)
    assert res["status"] == "done"
    assert p.n == 2


def test_loi_nghiem_trong_thi_dung_han(project):
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]
    p = FakeProvider([FakeFatal("api key sai")])
    with pytest.raises(translator.FatalAPIError, match="api key sai"):
        translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)


def test_le_thang_html_thi_gan_co(project):
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            # bỏ hết thẻ inline -> check_translation phải bắt được
            import re
            out = []
            for sid, body in re.findall(r'<seg id="(\d+)"[^>]*>(.*?)</seg>', user, re.S):
                out.append(f'<seg id="{sid}">{re.sub(r"<[^>]+>", "", body)}</seg>')
            return "\n".join(out), USAGE, "end_turn"

    p = P([])
    res = translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)
    flags = [r["flag"] for r in con.execute(
        "SELECT flag FROM blocks WHERE chunk_id=? AND flag IS NOT NULL", (cid,))]
    assert "tag_mismatch" in flags
    assert res["flagged"] >= 1


def test_usage_thieu_truong_khong_lam_crash(project):
    """Provider bên thứ ba có thể không trả cache_read/cache_write."""
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            import providers
            return echo_segments(user), providers.normalize_usage({"output": 5}), "end_turn"

    p = P([])
    res = translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)
    assert res["status"] == "done"
    row = con.execute("SELECT * FROM chunks WHERE id=?", (cid,)).fetchone()
    assert row["cache_read"] == 0 and row["out_tokens"] == 5


def test_loi_khong_phan_loai_duoc_van_den_tay_nguoi_dung(project):
    """Provider ném thứ nó không tự nhận là fatal hay retryable.

    Gặp thật: thiếu ANTHROPIC_API_KEY -> SDK ném TypeError, không phải APIError,
    nên cả hai hàm phân loại đều trả False và `raise` trần văng traceback giữa
    lúc đang dịch. Cùng lối thoát đó cũng nuốt IndexError khi máy chủ trả về
    choices rỗng.
    """
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]
    p = FakeProvider([TypeError("Could not resolve authentication method")])
    with pytest.raises(translator.FatalAPIError, match="authentication"):
        translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)


def test_usage_thieu_truong_that_su_khong_lam_crash(project):
    """Adapter bên thứ ba có thể quên chuẩn hoá và trả thẳng dict thiếu khoá.

    Bản test cũ tự gọi normalize_usage trong fake rồi mới trả về, nên nó chỉ
    kiểm tra rằng dict đã chuẩn hoá thì đã chuẩn hoá — đúng Review Focus #4 mà
    không hề phủ được.
    """
    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            return echo_segments(user), {"output": 5}, "end_turn"   # thiếu 3 khoá

    p = P([])
    res = translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)
    assert res["status"] == "done"
    row = con.execute("SELECT * FROM chunks WHERE id=?", (cid,)).fetchone()
    assert row["out_tokens"] == 5 and row["cache_read"] == 0


def test_bi_cat_do_het_token_thi_mach_nuoc_cho_nguoi_dung(project):
    """Gợi ý giảm --chunk-chars phải hiện với MỌI provider, không riêng Anthropic."""
    import providers

    proj, con = project
    cid = con.execute("SELECT MIN(id) FROM chunks").fetchone()[0]

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            return "", USAGE, providers.TRUNCATED

    p = P([])
    res = translator.translate_chunk(con, p, p.make_client(), "fake-1", "SYS", cid)
    assert res["status"] == "failed"
    assert "chunk-chars" in res["error"]


def test_translate_chi_dich_chunk_trong_khoang_trang(source_epub, tmp_path, capsys,
                                                    monkeypatch):
    """Dựng project rồi xin dịch một khoảng: chỉ những chunk chạm khoảng đó
    được gọi API, và lệnh phải báo vùng phủ thật."""
    import argparse

    import cli

    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    tong = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    assert tong >= 2, "EPUB mẫu phải có ít nhất 2 chunk để test có nghĩa"

    goi = []

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            goi.append(user)
            return echo_segments(user), USAGE, "end_turn"

    monkeypatch.setattr(cli.providers, "get", lambda ten: P([]))
    cli.cmd_translate(argparse.Namespace(
        project=str(proj), provider="fake", model="fake-1",
        limit=None, pages="1-1"))

    ra = capsys.readouterr().out
    assert "trang" in ra, "phải báo vùng trang đã dịch"
    con2 = db.connect(proj)
    xong = con2.execute("SELECT COUNT(*) FROM chunks WHERE status='done'").fetchone()[0]
    assert 0 < xong < tong, f"phải dịch một phần, không phải tất cả ({xong}/{tong})"


def test_translate_khoang_trang_khong_con_gi_thi_khong_goi_api(
        source_epub, tmp_path, capsys, monkeypatch):
    """Review Focus 1: khoảng rỗng thì nói rõ và KHÔNG tốn một lần gọi nào."""
    import argparse

    import cli

    proj = run_init(source_epub, tmp_path / "proj")
    goi = []

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            goi.append(user)
            return echo_segments(user), USAGE, "end_turn"

    monkeypatch.setattr(cli.providers, "get", lambda ten: P([]))

    # Ngoài sách: báo lỗi riêng, không gọi API.
    with pytest.raises(SystemExit) as e:
        cli.cmd_translate(argparse.Namespace(
            project=str(proj), provider="fake", model="fake-1",
            limit=None, pages="900-999"))
    assert "ngoài sách" in str(e.value)
    assert goi == [], "đã gọi API dù khoảng trang nằm ngoài sách"

    # Trong sách nhưng đã dịch hết: nói rồi về, cũng không gọi API.
    con = db.connect(proj)
    con.execute("UPDATE chunks SET status='done'")
    con.commit()
    cli.cmd_translate(argparse.Namespace(
        project=str(proj), provider="fake", model="fake-1",
        limit=None, pages="1-1"))
    assert goi == [], "đã gọi API dù khoảng trang không còn gì để dịch"
    assert "không có chunk nào" in capsys.readouterr().out.lower()


def test_chay_lai_van_ton_trong_dung_khoang_trang(source_epub, tmp_path,
                                                  capsys, monkeypatch):
    """Dừng giữa chừng rồi chạy lại phải tiếp đúng khoảng trang đó, không
    nhảy sang chunk ngoài khoảng."""
    import argparse

    import cli

    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    trong_khoang = {r["chunk_id"] for r in con.execute(
        "SELECT DISTINCT chunk_id FROM blocks WHERE page_no = 0")}

    da_goi = []

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            da_goi.append(user)
            return echo_segments(user), USAGE, "end_turn"

    monkeypatch.setattr(cli.providers, "get", lambda ten: P([]))
    lenh = argparse.Namespace(project=str(proj), provider="fake",
                              model="fake-1", limit=1, pages="1-1")
    cli.cmd_translate(lenh)                      # lượt 1: chỉ 1 chunk
    lenh.limit = None
    cli.cmd_translate(lenh)                      # lượt 2: phần còn lại

    con2 = db.connect(proj)
    xong = {r[0] for r in con2.execute(
        "SELECT id FROM chunks WHERE status='done'")}
    assert xong <= trong_khoang, (
        f"đã dịch chunk ngoài khoảng: {xong - trong_khoang}")


def test_co_khuyen_cao_khong_ton_them_luot_goi(project):
    """`missing_number`/`missing_term` là KHUYẾN CÁO, không phải hỏng cấu trúc.

    Số viết thành chữ ("năm một nghìn chín trăm mười bốn") là bản dịch đúng.
    Thử lại thì mô hình trả về đúng thứ đó lần nữa: tốn ba lượt gọi để ra cùng
    một kết quả, trên cuốn sách thật thì 50% số đoạn có chữ số.
    """
    import re

    proj, con = project
    cid = con.execute("SELECT MIN(chunk_id) FROM blocks "
                      "WHERE chunk_id IS NOT NULL").fetchone()[0]
    con.execute("UPDATE blocks SET src_html='He was born in 1914.' WHERE chunk_id=?",
                (cid,))
    con.commit()

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            self.calls.append(user)
            return (echo_segments(user, wrap=lambda s: re.sub(r"\d+", "", s)),
                    USAGE, "end_turn")

    p = P([])
    res = translator.translate_chunk(con, p, object(), "fake-1", "sys", cid)

    assert len(p.calls) == 1, f"cờ khuyến cáo đã tốn {len(p.calls)} lượt gọi"
    assert res["status"] == "done"
    assert res["flagged"] > 0
    co = {r[0] for r in con.execute(
        "SELECT DISTINCT flag FROM blocks WHERE chunk_id=? AND flag IS NOT NULL",
        (cid,))}
    assert co == {"missing_number"}


def test_hong_cau_truc_thi_van_thu_lai(project):
    """Ngược lại: thẻ lệch là hỏng thật — thử lại có thể cứu được, nên vẫn thử."""
    proj, con = project
    cid = con.execute("SELECT MIN(chunk_id) FROM blocks "
                      "WHERE chunk_id IS NOT NULL").fetchone()[0]
    con.execute("UPDATE blocks SET src_html='<em>hello there</em>' WHERE chunk_id=?",
                (cid,))
    con.commit()

    class P(FakeProvider):
        def call(self, client, model, system, user, max_tokens):
            self.calls.append(user)
            return (echo_segments(user, wrap=lambda s: "chào bạn"),
                    USAGE, "end_turn")

    p = P([])
    translator.translate_chunk(con, p, object(), "fake-1", "sys", cid)
    assert len(p.calls) == 3, "hỏng cấu trúc phải được thử lại đủ lượt"
