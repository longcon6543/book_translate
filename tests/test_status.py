"""`status` phải chạy được ở mọi trạng thái project, kể cả khi chưa dịch gì."""
import argparse

import cli
import db
from helpers import run_init


def run_status(proj, capsys):
    cli.cmd_status(argparse.Namespace(project=str(proj)))
    return capsys.readouterr().out


def test_project_chua_dich_gi(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    out = run_status(proj, capsys)
    assert "short.epub" in out
    assert "0/" in out or "0 " in out


def test_hien_provider_da_dung(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    con.execute("UPDATE chunks SET status='done', provider='anthropic', "
                "model='claude-sonnet-5', in_tokens=100, out_tokens=200 WHERE id=1")
    con.commit()
    out = run_status(proj, capsys)
    assert "anthropic" in out
    assert "claude-sonnet-5" in out


def test_khong_crash_khi_usage_toan_khong(source_epub, tmp_path, capsys):
    proj = run_init(source_epub, tmp_path / "proj")
    con = db.connect(proj)
    con.execute("UPDATE chunks SET status='done'")
    con.commit()
    out = run_status(proj, capsys)
    assert "Đoạn:" in out
