"""`inspect` cho xem tool hiểu cuốn sách thế nào, trước khi tiêu tiền dịch."""
import argparse

import pytest

import cli
from helpers import build_pdf, run_init, trang_mot_doan


def run_inspect(proj, capsys, pages=None):
    cli.cmd_inspect(argparse.Namespace(project=str(proj), pages=pages))
    return capsys.readouterr().out


@pytest.fixture
def proj_pdf(tmp_path):
    src = build_pdf(tmp_path / "m.pdf", [
        [{"text": "Chuong Mot", "x": 67, "y": 80, "size": 14}] + trang_mot_doan(120, 4),
        trang_mot_doan(80, 3, tien_to="hai"),
        trang_mot_doan(80, 3, tien_to="ba"),
    ])
    return run_init(src, tmp_path / "proj")


def test_in_ra_tung_doan_theo_thu_tu(proj_pdf, capsys):
    out = run_inspect(proj_pdf, capsys)
    assert "trang 1" in out and "trang 2" in out
    assert out.index("trang 1") < out.index("trang 2")


def test_hien_phan_loai(proj_pdf, capsys):
    out = run_inspect(proj_pdf, capsys)
    assert "heading" in out


def test_loc_theo_khoang_trang(proj_pdf, capsys):
    out = run_inspect(proj_pdf, capsys, pages="3-3")
    assert "trang 3" in out
    assert "trang 1" not in out and "trang 2" not in out


def test_khoang_trang_sai_dinh_dang_bao_loi_ro(proj_pdf, capsys):
    with pytest.raises(SystemExit) as e:
        run_inspect(proj_pdf, capsys, pages="linh tinh")
    assert "--pages" in str(e.value)


def test_khoang_trang_khong_co_trang_nao(proj_pdf, capsys):
    out = run_inspect(proj_pdf, capsys, pages="900-999")
    assert "không có đoạn nào" in out


def test_in_ra_tong_ket_de_uoc_luong(proj_pdf, capsys):
    out = run_inspect(proj_pdf, capsys)
    assert "ký tự" in out
