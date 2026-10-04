"""Phần dùng chung của hai chế độ xuất PDF khổ đôi: overlay và reflow.

Hai chế độ chỉ khác nhau đúng ở bộ dựng trang dịch — cách biến một trang gốc
thành một trang tiếng Việt. Mọi thứ còn lại (đặt chữ theo thang tự co, ghép
khổ đôi, trang báo cáo, ghi cờ overflow) nằm ở đây để hai chế độ không nói
hai kiểu.
"""
import html as _html
import json
import statistics
from pathlib import Path

import pymupdf

import db
import pdf_font
import pdf_layout
from render import UnsupportedTarget


def dat_chu(page, khung, html: str, size: float, kho) -> tuple:
    """Đặt `html` vào `khung`, đi theo thang tự co. Trả về (tỉ lệ, tràn).

    `insert_htmlbox` tự xuống dòng và tự co chữ; nó trả về (chỗ thừa, tỉ lệ) và
    dùng -1 làm chỗ thừa khi không vừa ở `scale_low` đã cho. Ta chỉ việc thử
    lần lượt các bậc và dừng ở bậc đầu tiên vừa.
    """
    if not html or not html.strip():
        return 1.0, False
    if khung.width <= 0 or khung.height <= 0:
        # Khung suy biến do bóc chữ lỗi. Bỏ qua có kiểm soát: một khung hỏng
        # không được làm hỏng cả lần xuất.
        return 0.0, True

    for scale_low, gian_dong in pdf_layout.thang_co():
        css = pdf_font.dung_css(size, gian_dong)
        thua, ti_le = page.insert_htmlbox(khung, html, css=css, archive=kho,
                                          scale_low=scale_low)
        if thua >= 0:
            return ti_le, False

    return pdf_layout.DAY_THANG, True


# Cỡ chữ của số trang in giữa khổ đôi.
CO_SO_TRANG = 7.0


def _khung_dung(khung, trang) -> bool:
    """Khung dùng được: có kích thước dương VÀ nằm trong trang.

    Khung nằm ngoài trang thì insert_htmlbox vẫn báo thành công mà chữ không ở
    đâu cả — mất nội dung im lặng, lại còn được tính là đặt thành công 100%.
    """
    if khung.width <= 0 or khung.height <= 0:
        return False
    return trang.contains(khung.tl) and khung.intersects(trang)


def kep_khung(khung, trang):
    """Phần giao của khung với trang. Không giao thì trả khung rỗng.

    Chỉ reflow gọi. Overlay LOẠI khối có khung ra ngoài trang và như thế là
    đúng, vì ảnh nền vẫn hiện chữ gốc ở chỗ đó. Reflow dựng trên nền trắng
    nên loại là mất nội dung im lặng — đo thật: 53/4.120 khối của một cuốn
    scan có góc trên-trái nằm trên mép trang, lệch chưa tới 5pt.

    Tự tính thay vì dùng Rect.intersect: với hai khung rời nhau thì
    intersect trả về một khung "không hợp lệ" mà tài liệu không nói rõ hình
    dạng. Khung rỗng Rect() thì _khung_dung chắc chắn loại.
    """
    x0, y0 = max(khung.x0, trang.x0), max(khung.y0, trang.y0)
    x1, y1 = min(khung.x1, trang.x1), min(khung.y1, trang.y1)
    if x1 <= x0 or y1 <= y0:
        return pymupdf.Rect()
    return pymupdf.Rect(x0, y0, x1, y1)


def ghep_kho_doi(src_doc, cap: list) -> "pymupdf.Document":
    """Khổ ngang rộng gấp đôi: trang gốc bên trái, trang dịch bên phải.

    `cap` là list (page_no, tài liệu một trang đã dịch), đúng thứ tự muốn xuất.
    Dán ở dạng vector bằng show_pdf_page nên chữ vẫn bôi đen và tìm kiếm được,
    ảnh vẫn nguyên độ nét, và hai bên dùng chung tài nguyên nên file không
    phình gấp đôi.
    """
    ra = pymupdf.open()
    for page_no, dich in cap:
        goc = src_doc[page_no].rect
        kho_ngang = ra.new_page(width=goc.width * 2, height=goc.height)
        kho_ngang.show_pdf_page(pymupdf.Rect(0, 0, goc.width, goc.height),
                                src_doc, page_no)
        kho_ngang.show_pdf_page(pymupdf.Rect(goc.width, 0, goc.width * 2, goc.height),
                                dich, 0)
        # Số trang gốc in giữa khổ để luôn biết đang ở đâu so với sách giấy.
        nhan = f"{page_no + 1}"
        rong = len(nhan) * CO_SO_TRANG * 0.6
        kho_ngang.insert_text((goc.width - rong / 2, goc.height - 6),
                              nhan, fontsize=CO_SO_TRANG)
    return ra


# Chữ độn cho --dry-run: kéo dài chữ gốc thêm ~25% để mô phỏng tiếng Việt.
TI_LE_DON = 0.25


def _don_cho_dai_ra(html: str) -> str:
    """Nối thêm vài TỪ đầu của chính nó, để thử sức chứa mà không cần bản dịch.

    Cắt theo ký tự thì đứt giữa thẻ HTML ("<p>The <em" ), và với khối một chữ
    thì `max(1, ...)` thổi nó lên gấp ba — sinh ra tràn khung giả ở ô bảng, số
    trang và tiêu đề ngắn. Đo thật: 51 trong 55 cờ tràn của một lần dry-run là
    do độn, không phải do chữ thật.
    """
    tu = html.split()
    if len(tu) < 4:
        return html                      # quá ngắn: độn vào là bịa ra tràn giả
    n = max(1, int(len(tu) * TI_LE_DON))
    return html + " " + " ".join(tu[:n])


def _duong_nguon(project, con, fmt):
    ten = db.get_meta(con, "source_format", fmt)
    return Path(project) / f"source.{ten}"


def _chen_trang_bao_cao(ra, tk, tran, ti_le_all, kho):
    """Trang đầu file: soi ngay được layout có ổn không, không cần đọc hết.

    Phải đặt bằng chính font tiếng Việt đã nhúng. insert_text không khai font
    thì rơi về base-14, mà chính dự án này chứng minh font đó thiếu 17/25 chữ
    có dấu — trang báo cáo tự nó biến thành ô vuông.
    """
    trang = ra.new_page(width=ra[0].rect.width, height=ra[0].rect.height)
    duoi = [t for t in ti_le_all if t < 0.85]
    dong = [
        "BÁO CÁO DỰNG TRANG (--probe)",
        "",
        f"Khổ đã dựng: {tk['so_trang']}",
        f"Khối đã đặt chữ: {tk['so_khoi']}",
        f"Tỉ lệ cỡ chữ trung vị: {tk['co_trung_vi']:.0%}",
        f"Khối phải co dưới 85%: {len(duoi)}",
        f"Khối tràn khung: {tk['tran']}",
        "",
        "Tràn khung nghĩa là không vừa ngay cả ở đáy thang. Những khối đó giữ "
        "nguyên chữ gốc và được gắn cờ overflow; xem `status`.",
    ]
    if tran:
        dong.append("")
        dong += [f"tràn: trang {pno + 1}, block {bid}" for pno, bid in tran[:20]]

    noi = "<br/>".join(_html.escape(d, quote=False) or "&#160;" for d in dong)
    trang.insert_htmlbox(
        pymupdf.Rect(40, 40, trang.rect.width - 40, trang.rect.height - 40),
        noi, css=pdf_font.dung_css(11.0, 1.4), archive=kho)
    # move_page vô hiệu hoá đối tượng Page đang cầm, nên phải dời SAU khi
    # đã viết xong nội dung — dời trước là insert_htmlbox nổ NoneType.
    ra.move_page(ra.page_count - 1, 0)


def write(project, con, out_path, dung_trang, *, pages=None,
          dry_run=False, probe=False) -> dict:
    """Xuất PDF khổ đôi. Trả về thống kê để `export` in ra và `--probe` dùng.

    `dung_trang` là bộ dựng trang dịch của chế độ đang dùng — chỗ DUY NHẤT
    hai chế độ khác nhau. Ký: (src_doc, page_no, khoi, kho, ghi_nhan) ->
    tài liệu một trang.
    """
    nguon = pymupdf.open(str(_duong_nguon(project, con, "pdf")))
    kho = pdf_font.dung_archive(pdf_font.chon_bo_font())

    cot = ("SELECT id, page_no, pos, bbox, layout, kind, "
           "       COALESCE(dst_html, '') dst, src_html "
           "FROM blocks WHERE bbox IS NOT NULL")
    tham = ()
    if pages:
        cot += " AND page_no BETWEEN ? AND ?"
        tham = pages
    cot += " ORDER BY page_no, pos"

    theo_trang = {}
    for r in con.execute(cot, tham):
        noi_dung = _don_cho_dai_ra(r["src_html"]) if dry_run else r["dst"]
        goc = r["src_html"] or ""
        # Khối chưa dịch vẫn phải tới bộ dựng trang: overlay tự bỏ qua nó
        # (chữ gốc còn nguyên trên bản sao trang), reflow thì vẽ chữ Anh vào
        # — trên nền trắng mà bỏ qua là để lại khoảng trống im lặng.
        if not noi_dung.strip() and not goc.strip():
            continue
        x0, y0, x1, y1 = (float(v) for v in r["bbox"].split(","))
        lay = json.loads(r["layout"] or "{}")
        theo_trang.setdefault(r["page_no"], []).append(
            {"id": r["id"], "bbox": pymupdf.Rect(x0, y0, x1, y1),
             "html": noi_dung, "src": goc,
             "size": float(lay.get("size") or 10.0),
             "kind": r["kind"] or "text"})

    if pages:
        dau, cuoi = pages
        if dau > cuoi:
            nguon.close()
            raise UnsupportedTarget(
                f"khoảng trang ngược: {dau + 1}-{cuoi + 1}.")
        if dau >= nguon.page_count or cuoi < 0:
            n = nguon.page_count
            nguon.close()
            raise UnsupportedTarget(
                f"khoảng trang {dau + 1}-{cuoi + 1} nằm ngoài sách ({n} trang).")
        dau, cuoi = max(0, dau), min(nguon.page_count - 1, cuoi)
    else:
        dau, cuoi = 0, nguon.page_count - 1

    cap, ti_le_all, tran = [], [], []
    for pno in range(dau, cuoi + 1):
        ket = []
        d = dung_trang(nguon, pno, theo_trang.get(pno, []), kho, ghi_nhan=ket)
        for bid, ti_le, bi_tran in ket:
            ti_le_all.append(ti_le)
            if bi_tran:
                tran.append((pno, bid))
        cap.append((pno, d))

    ra = ghep_kho_doi(nguon, cap)
    tk = {"so_trang": len(cap), "so_khoi": len(ti_le_all),
          "tran": len(tran),
          "co_trung_vi": statistics.median(ti_le_all) if ti_le_all else 1.0}
    if probe:
        _chen_trang_bao_cao(ra, tk, tran, ti_le_all, kho)

    # garbage=4 là bắt buộc: insert_htmlbox nhúng cả file font MỖI LẦN GỌI,
    # tức mỗi khối một bản. Với garbage=3 thì 20 trang ra 75MB (98% là font
    # lặp) và cả cuốn 925 trang không chạy xong trong 37 phút.
    ra.save(str(out_path), garbage=4, deflate=True)
    ra.close()
    for _, d in cap:
        d.close()
    nguon.close()

    # Cờ overflow ghi vào cột flag để `status` đếm được. Ba điều bắt buộc:
    #  - dry-run KHÔNG ghi gì: chữ ở đó là chữ Anh độn thêm, cờ sinh ra là giả;
    #  - dọn cờ overflow CŨ trong khoảng vừa dựng, nếu không sửa bản dịch cho
    #    ngắn lại rồi xuất lại vẫn thấy cờ cũ;
    #  - chỉ đụng vào cờ 'overflow'. Cột flag dùng chung với translator
    #    (tag_mismatch / too_short) — đè lên là xoá mất cảnh báo chất lượng.
    if not dry_run:
        con.execute(
            "UPDATE blocks SET flag=NULL "
            "WHERE flag='overflow' AND page_no BETWEEN ? AND ?", (dau, cuoi))
        for _, bid in tran:
            # Chỉ ghi khi ô cờ đang trống hoặc đã là overflow. Cờ chất lượng
            # của translator nói về bản dịch ĐÚNG hay SAI, quan trọng hơn cờ
            # layout — và số khối tràn vẫn được đếm trong thống kê và --probe.
            con.execute("UPDATE blocks SET flag='overflow' "
                        "WHERE id=? AND (flag IS NULL OR flag='overflow')", (bid,))
        con.commit()
    return tk
