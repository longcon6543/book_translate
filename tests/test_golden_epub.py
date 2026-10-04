"""Lưới an toàn: đường EPUB phải cho ra đúng kết quả cũ sau mọi lần refactor.

Test này KHÔNG kiểm tra chất lượng dịch. Nó kiểm tra rằng việc tách tầng ở
Phase 2 không làm đổi một byte nào của file xuất ra.
"""
from pathlib import Path

import db
from helpers import fingerprint, run_init, seed_translations

GOLDEN_DIR = Path(__file__).parent / "golden"


def export(proj: Path, bilingual: bool) -> Path:
    import argparse

    import cli
    out = proj / ("out.bi.epub" if bilingual else "out.vi.epub")
    cli.cmd_export(argparse.Namespace(
        project=str(proj), output=str(out), bilingual=bilingual,
        mode=None, pages=None, dry_run=False, probe=False))
    return out


def test_epub_don_ngu_khop_van_tay(source_epub, tmp_path):
    proj = run_init(source_epub, tmp_path / "proj")
    seed_translations(db.connect(proj))
    expected = (GOLDEN_DIR / "epub_fingerprint.txt").read_text(encoding="utf-8")
    assert fingerprint(export(proj, False)) == expected


def test_epub_song_ngu_khop_van_tay(source_epub, tmp_path):
    proj = run_init(source_epub, tmp_path / "proj")
    seed_translations(db.connect(proj))
    expected = (GOLDEN_DIR / "epub_fingerprint_bilingual.txt").read_text(encoding="utf-8")
    assert fingerprint(export(proj, True)) == expected


def test_doan_chi_co_so_khong_duoc_tach_ra_dich(source_epub, tmp_path):
    """`<p>42</p>` không có chữ cái nên `has_letters` phải loại nó."""
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    srcs = [r[0] for r in con.execute("SELECT src_html FROM blocks")]
    assert "42" not in srcs
