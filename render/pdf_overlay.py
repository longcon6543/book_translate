"""Chế độ overlay: đè chữ Việt lên bản sao trang gốc, rồi ghép khổ đôi.

Chỉ đúng cho text-PDF, nơi chữ gốc là đối tượng văn bản nên xoá được. Sách
scan có chữ là pixel trong ảnh — xoá không được, đè lên là ra hai lớp chữ;
dùng pdf_reflow. Phần dùng chung của hai chế độ nằm ở pdf_trang.py.
"""
import pymupdf

import pdf_font
from render import pdf_trang
# Dùng lại từ pdf_trang, không chép: trang_dich gọi chúng, và test hiện có
# truy cập qua pdf_overlay.<tên>.
from render.pdf_trang import _khung_dung, dat_chu, ghep_kho_doi  # noqa: F401


def xoa_chu(page, khung_list) -> None:
    """Xoá chữ trong các khung, GIỮ NGUYÊN ảnh nằm dưới.

    `images=PDF_REDACT_IMAGE_NONE` là bắt buộc, không phải tuỳ chọn. Đo thật:
    apply_redactions() mặc định xoá chữ xong khoét trắng 100% vùng ảnh bên
    dưới; với cờ này thì 0%. Chú thích đè lên hình là chuyện thường trong sách,
    nên bỏ cờ là khoét lỗ khắp cuốn.
    """
    if not khung_list:
        return
    for khung in khung_list:
        page.add_redact_annot(khung)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)


def trang_dich(src_doc, page_no: int, khoi: list, kho=None,
               ghi_nhan=None) -> "pymupdf.Document":
    """Tài liệu một trang: bản sao trang gốc, chữ Anh thay bằng chữ Việt.

    `khoi` là list dict {bbox, html, size, id?}. `ghi_nhan`, nếu truyền vào, sẽ
    nhận thêm một tuple (id, tỉ lệ, tràn) cho mỗi khối đã đặt.

    Trang không có khối nào thì trả về bản sao nguyên vẹn — trang chưa dịch
    phải hiện bản gốc, không phải trang trắng.

    Trả về tài liệu mới; người gọi có trách nhiệm đóng.
    """
    if kho is None:
        kho = pdf_font.dung_archive(pdf_font.chon_bo_font())

    d = pymupdf.open()
    d.insert_pdf(src_doc, from_page=page_no, to_page=page_no)
    page = d[0]

    hop_le = [k for k in khoi
              if _khung_dung(k["bbox"], page.rect) and k["html"].strip()]
    if not hop_le:
        return d

    # Thử đặt trên một trang nháp TRƯỚC, rồi mới xoá chữ gốc của những khối đặt
    # được. Xoá trước rồi mới biết không đặt nổi là để lại LỖ TRỐNG: chữ Anh
    # mất mà chữ Việt không có. Spec mục 6 bậc 7 nói "hết cách thì GIỮ", không
    # phải "hết cách thì bỏ".
    nhap = pymupdf.open()
    nhap.insert_pdf(src_doc, from_page=page_no, to_page=page_no)
    ket = [(k,) + dat_chu(nhap[0], k["bbox"], k["html"], k["size"], kho)
           for k in hop_le]
    nhap.close()

    dat_duoc = [k for k, _, bi_tran in ket if not bi_tran]
    xoa_chu(page, [k["bbox"] for k in dat_duoc])
    for k in dat_duoc:
        dat_chu(page, k["bbox"], k["html"], k["size"], kho)

    if ghi_nhan is not None:
        for k, ti_le, bi_tran in ket:
            ghi_nhan.append((k.get("id"), ti_le, bi_tran))
    return d


def write(project, con, out_path, *, pages=None,
          dry_run=False, probe=False) -> dict:
    """Xuất PDF khổ đôi chế độ overlay."""
    return pdf_trang.write(project, con, out_path, trang_dich, pages=pages,
                           dry_run=dry_run, probe=probe)
