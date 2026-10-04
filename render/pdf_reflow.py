"""Chế độ reflow: dựng trang trắng mang chữ Việt, không chép gì từ trang gốc.

Dành cho sách scan, nơi chữ gốc là pixel trong ảnh nên overlay không xoá
được: đè chữ Việt lên là ra hai lớp chữ chồng nhau (đo thật: nửa dịch đậm
hơn nửa gốc 42% và 62%). Reflow không chép gì từ trang gốc — nửa trái của
khổ đôi đã mang nguyên bản gốc, kể cả hình, nên vùng hình ở nửa phải để
trống là đủ (spec R2). Nền trắng tự nó đã trống đúng kích thước.
"""
import json
import statistics

import pymupdf

import db
import pdf_font
import pdf_layout
from render import dan_trang, pdf_trang
from render.pdf_trang import _khung_dung, dat_chu, kep_khung


def _ve_bang_moi_gia(page, khung, html, size, kho) -> None:
    """Bậc cuối của R4: đặt được bằng mọi giá, co nhỏ tới đâu cũng được.

    Thang co dừng ở 70% vì dưới đó chữ khó đọc. Nhưng khi cả chữ Việt lẫn chữ
    Anh đều không vừa ở 70%, dừng ở đó là để khung TRẮNG — trong khi cờ
    overflow và trang --probe nói "đã giữ nguyên bản gốc". Review đo thật
    trên astrology trang 4-7: layout.size bị thổi lên 26-120pt nên cả tiêu đề
    sách biến khỏi nửa dịch; 42/53 khối y âm của harmonics cũng vậy. Chữ nhỏ
    vẫn hơn chữ mất, và overlay cũng giữ chữ gốc ở chỗ nó không đặt được.
    """
    gian_dong = pdf_layout.thang_co()[-1][1]
    page.insert_htmlbox(khung, html, css=pdf_font.dung_css(size, gian_dong),
                        archive=kho, scale_low=0)


# 8B E8: vùng hình (meta vung_hinh) vẽ thành ô "ảnh". Người dùng cho thu nhỏ.
CAO_O_TOI_THIEU = 30.0
TI_LE_O_ANH = 0.5
NHAN_ANH = "ảnh"


def chen_hinh(khoi: list, vung: list) -> list:
    """Danh sách khối mới có thêm ô hình, đặt theo độ cao để giữ thứ tự đọc."""
    out = list(khoi)
    for v in sorted(vung, key=lambda v: v[1]):
        muc = {"id": None, "kind": "hinh", "bbox": pymupdf.Rect(v),
               "html": "", "src": "", "size": 0.0}
        i = next((i for i, k in enumerate(out) if k["bbox"].y0 > v[1]),
                 len(out))
        out.insert(i, muc)
    return out


def _ve_o_anh(page, rect, kho, co) -> None:
    page.draw_rect(rect, color=(0.7, 0.7, 0.7), width=0.5)
    nhan = pymupdf.Rect(rect.x0, (rect.y0 + rect.y1) / 2 - co,
                        rect.x1, (rect.y0 + rect.y1) / 2 + co)
    page.insert_htmlbox(nhan, NHAN_ANH,
                        css=pdf_font.dung_css(co, 1.0)
                        + "*{text-align:center;color:#888888;}",
                        archive=kho, scale_low=0)


def trang_theo_vi_tri(src_doc, page_no: int, khoi: list, kho=None,
                      ghi_nhan=None, *, than: float = 9.0) -> "pymupdf.Document":
    """Tài liệu một trang trắng đúng khổ trang gốc, chữ đặt đúng khung gốc.

    Bộ dựng của Phase 6 (R1). Từ Phase 8A chỉ còn là dự phòng: trang_reflow
    gọi nó cho trang không dàn được ở hệ số co 0,75.

    Cùng giao kèo với pdf_overlay.trang_dich để pdf_trang.write gọi được cả
    hai. `khoi` là list dict {id, bbox, html, src, size}.

    Trả về tài liệu mới; người gọi có trách nhiệm đóng.
    """
    if kho is None:
        kho = pdf_font.dung_archive(pdf_font.chon_bo_font())

    goc = src_doc[page_no].rect
    d = pymupdf.open()
    page = d.new_page(width=goc.width, height=goc.height)

    for k in khoi:
        if k.get("kind") == "hinh":
            o = kep_khung(k["bbox"], page.rect)
            if _khung_dung(o, page.rect):
                _ve_o_anh(page, o, kho, than)
            continue
        src = k.get("src", "")
        ban_dich = k["html"].strip()
        # Khối chưa dịch thì hiện chữ Anh, như overlay vẫn làm: trên nền trắng
        # mà bỏ qua là để lại khoảng trống im lặng ở chỗ chưa dịch.
        html = k["html"] if ban_dich else src
        if not html.strip():
            continue
        # R3: kẹp chứ không loại. Overlay loại được vì ảnh nền còn hiện chữ ở
        # chỗ đó; ở đây loại là mất nội dung.
        khung = kep_khung(k["bbox"], page.rect)
        if not _khung_dung(khung, page.rect):
            continue
        ti_le, bi_tran = dat_chu(page, khung, html, k["size"], kho)
        if bi_tran:
            # R4: hết cách thì GIỮ chữ Anh gốc. insert_htmlbox không vẽ gì khi
            # không vừa, nên khung đó đang trống.
            con_tran = True
            if ban_dich and src.strip():
                _, con_tran = dat_chu(page, khung, src, k["size"], kho)
            if con_tran:
                _ve_bang_moi_gia(page, khung, src if src.strip() else html,
                                 k["size"], kho)
        # D7: khối chưa dịch hiện chữ Anh nhưng không vào thống kê — tràn của
        # nó là tràn của chữ Anh, gắn cờ overflow cho nó là cờ giả.
        if ghi_nhan is not None and ban_dich:
            ghi_nhan.append((k.get("id"), ti_le, bi_tran))
    return d


def _thu_bac(muc, khung, than, s, kho):
    """Một bậc của thang D5: đo chiều cao từng khối ở hệ số s rồi xếp dọc.

    Trả về list (rect, css) theo thứ tự `muc`, hoặc None khi không vừa. Đo
    trên tài liệu nháp riêng: vẽ lên trang thật rồi mới biết không vừa là để
    lại chữ thừa.
    """
    nhap = pymupdf.open()
    trang_nhap = nhap.new_page(width=khung.x1 + dan_trang.LE,
                               height=khung.y1 + dan_trang.LE)
    ngang, cao, css_ds = [], [], []
    try:
        for k, html, _ in muc:
            if k.get("kind") == "hinh":
                # Ô ảnh: bề rộng gốc kẹp vào khung (không nới như D4), cao nửa
                # hình gốc, tối thiểu CAO_O_TOI_THIEU; không cần đo.
                x0 = max(k["bbox"].x0, khung.x0)
                x1 = min(k["bbox"].x1, khung.x1)
                if x1 - x0 < 1:
                    x0, x1 = khung.x0, khung.x1
                h = max(CAO_O_TOI_THIEU, TI_LE_O_ANH * k["bbox"].height) * s
                if h > khung.height:
                    return None
                ngang.append((x0, x1))
                cao.append(h)
                css_ds.append("")
                continue
            co = dan_trang.co_khoi(k.get("kind", "text"), k["size"], than) * s
            css = pdf_font.dung_css(co, dan_trang.GIAN_DONG)
            x0, x1 = dan_trang.khung_ngang(k["bbox"].x0, k["bbox"].x1,
                                           khung.x0, khung.x1)
            do = pymupdf.Rect(x0, khung.y0, x1, khung.y1)
            thua, _ = trang_nhap.insert_htmlbox(do, html, css=css,
                                                archive=kho, scale_low=1)
            if thua < 0:
                return None                 # một khối đã cao hơn cả khung
            ngang.append((x0, x1))
            cao.append(do.height - thua)
            css_ds.append(css)
    finally:
        nhap.close()

    khoang = dan_trang.TI_LE_KHOANG * than * s
    y = dan_trang.xep_doc([k["bbox"].y0 for k, _, _ in muc], cao,
                          khung.y0, khung.y1, khoang, ngang)
    if y is None:
        return None
    # Khung vẽ cao hơn chữ đúng một khoảng: insert_htmlbox cần chút dư để
    # không làm tròn thành "không vừa", và khối sau bắt đầu ở đúng chỗ đó
    # nên vẫn không chồng.
    return [(pymupdf.Rect(x0, yi, x1, yi + h + (0 if k.get("kind") == "hinh"
                                                 else khoang)), css)
            for (k, _, _), (x0, x1), yi, h, css in zip(muc, ngang, y, cao, css_ds)]


def trang_reflow(src_doc, page_no: int, khoi: list, kho=None,
                 ghi_nhan=None, *, than: float,
                 du_phong=None) -> "pymupdf.Document":
    """Tài liệu một trang trắng: khối dàn theo thứ tự, neo độ cao gốc (8A).

    Cùng giao kèo với pdf_overlay.trang_dich cộng hai tham số từ khoá:
    `than` là cỡ thân bài cả cuốn, `du_phong` nhận page_no của trang phải
    rơi về trang_theo_vi_tri (D6). `khoi` là list dict
    {id, bbox, html, src, size, kind}.
    """
    if kho is None:
        kho = pdf_font.dung_archive(pdf_font.chon_bo_font())

    goc = src_doc[page_no].rect
    le = dan_trang.LE
    khung = pymupdf.Rect(le, le, goc.width - le, goc.height - le)

    muc = []
    for k in khoi:
        if k.get("kind") == "hinh":
            muc.append((k, "", False))
            continue
        da_dich = bool(k["html"].strip())
        # D7: chưa dịch thì hiện chữ Anh — khoảng trắng im lặng tệ hơn.
        html = k["html"] if da_dich else k.get("src", "")
        if html.strip():
            muc.append((k, html, da_dich))

    d = pymupdf.open()
    page = d.new_page(width=goc.width, height=goc.height)
    if not muc:
        return d                                # D8 / R5

    for s in dan_trang.THANG_S:
        dat = _thu_bac(muc, khung, than, s, kho)
        if dat is not None:
            break
    else:
        d.close()
        if du_phong is not None:
            du_phong.append(page_no)
        return trang_theo_vi_tri(src_doc, page_no, khoi, kho, ghi_nhan, than=than)

    for (k, html, da_dich), (rect, css) in zip(muc, dat):
        if k.get("kind") == "hinh":
            _ve_o_anh(page, rect, kho, than * s)
            continue
        page.insert_htmlbox(rect, html, css=css, archive=kho, scale_low=1)
        if ghi_nhan is not None and da_dich:
            ghi_nhan.append((k.get("id"), s, False))
    return d


def co_than(con) -> float:
    """D3: cỡ thân bài cả cuốn = trung vị layout.size của khối kind='text'."""
    co = []
    for (lay,) in con.execute("SELECT layout FROM blocks WHERE kind='text'"):
        size = json.loads(lay or "{}").get("size")
        if size:
            co.append(float(size))
    return statistics.median(co) if co else 10.0


def write(project, con, out_path, *, pages=None,
          dry_run=False, probe=False) -> dict:
    """Xuất PDF khổ đôi chế độ reflow. tk có thêm 'trang_du_phong'."""
    du_phong = []
    than = co_than(con)
    hinh = json.loads(db.get_meta(con, "vung_hinh") or "{}")

    def dung(src_doc, page_no, khoi, kho=None, ghi_nhan=None):
        return trang_reflow(src_doc, page_no,
                            chen_hinh(khoi, hinh.get(str(page_no), [])),
                            kho, ghi_nhan, than=than, du_phong=du_phong)

    tk = pdf_trang.write(project, con, out_path, dung, pages=pages,
                         dry_run=dry_run, probe=probe)
    tk["trang_du_phong"] = len(du_phong)
    return tk
