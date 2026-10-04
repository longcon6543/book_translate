#!/usr/bin/env python3
"""booktrans - dịch sách EPUB Anh -> Việt bằng Claude (dùng cá nhân).

    python cli.py init sach.epub              # tạo project, tách đoạn, chia chunk
    python cli.py status projects/sach        # xem quy mô + ước tính token
    python cli.py translate projects/sach --limit 3   # dịch thử 3 chunk đầu
    python cli.py export projects/sach        # xuất EPUB tiếng Việt
"""
import argparse
import json
import os
import sqlite3
import shutil
import sys
from pathlib import Path

import blocks
import chunking
import db
import glossary
import ingest
import pdf_font
import providers
import render

DEFAULT_STYLE = """\
# Style guide - sửa file này cho hợp từng cuốn sách. Toàn bộ nội dung được đưa vào prompt.
- Thể loại: (điền vào: tiểu thuyết / phi hư cấu / kỹ thuật / tự lực ...)
- Văn phong: tự nhiên, mạch lạc, đúng ngữ pháp tiếng Việt; không dịch từng chữ; giữ sắc thái và nhịp văn của tác giả.
- Xưng hô: ngôi thứ nhất mặc định "tôi". (Ghi rõ cách xưng hô giữa các nhân vật chính ở đây, ví dụ: A gọi B là "anh", B gọi A là "em".)
- Tên riêng (người, địa danh, tổ chức): giữ nguyên tiếng Anh, trừ khi đã có tên tiếng Việt phổ biến.
- Thuật ngữ chuyên ngành: dịch sang tiếng Việt thông dụng; nếu chưa có từ chuẩn thì giữ nguyên tiếng Anh.
- Tên sách/phim/tác phẩm: giữ nguyên tiếng Anh, có thể thêm bản dịch trong ngoặc ở lần đầu nếu cần.
- Dấu câu: dùng dấu câu chuẩn tiếng Việt.
"""

DEFAULT_GLOSSARY = """\
# Mỗi dòng một mục:  term tiếng Anh = bản dịch (hoặc giữ nguyên)
# Ví dụ:
# Winterfell = Winterfell
# The Wall = Bức Tường
# machine learning = học máy
"""


def die(msg: str):
    sys.exit(f"Lỗi: {msg}")


def open_project(path: str):
    proj = Path(path)
    if not (proj / "project.db").exists():
        die(f"'{proj}' không phải project (thiếu project.db). Chạy `init` trước.")
    con = db.connect(proj)
    try:
        db.migrate(con)      # project Phase 1 được nâng cấp tại chỗ
    except (RuntimeError, sqlite3.Error) as e:
        die(str(e))
    return proj, con


# ------------------------------------------------------------------ init

def cmd_init(args):
    src = Path(args.source)
    try:
        fmt = ingest.detect_format(src)
        ingest.ensure_supported(fmt)   # từ chối TRƯỚC khi tạo thư mục và copy
    except ingest.UnsupportedSource as e:
        die(str(e))

    proj = Path(args.dir) if args.dir else Path("projects") / src.stem
    db_path = proj / "project.db"
    if db_path.exists() and not args.force:
        die(f"{proj} đã có project. Dùng --force để tạo lại (sẽ xóa bản dịch cũ).")

    # ĐỌC XONG RỒI MỚI ĐỤNG VÀO ĐĨA. File hỏng chỉ lộ ra ở bước này; nếu để nó
    # lộ ra sau khi đã xoá project.db và đè source thì bản dịch đã trả tiền lẫn
    # file sách gốc đều mất trắng, không cách nào lấy lại.
    print(f"Đang đọc {src.name} ({fmt}) ...")
    try:
        data = ingest.load(src)
        if not data.blocks:
            raise ingest.UnsupportedSource(
                "không tìm thấy đoạn văn bản nào để dịch (sách toàn ảnh? DRM?).")
    except ingest.UnsupportedSource as e:
        die(str(e))
    except Exception as e:
        die(f"không đọc được {src.name}: {type(e).__name__}: {e}")

    da_co_truoc = proj.exists()
    proj.mkdir(parents=True, exist_ok=True)
    try:
        if db_path.exists():
            db_path.unlink()
        stored = proj / f"source.{fmt}"
        if src.resolve() != stored.resolve():      # init lại từ chính file đã lưu
            shutil.copy2(src, stored)
        for name, content in (("style.md", DEFAULT_STYLE), ("glossary.txt", DEFAULT_GLOSSARY)):
            if not (proj / name).exists():
                (proj / name).write_text(content, encoding="utf-8")
    except OSError as e:
        if not da_co_truoc:
            shutil.rmtree(proj, ignore_errors=True)
        die(f"không ghi được vào {proj}: {e}")

    con = db.connect(proj)
    db.migrate(con)
    for blk in data.blocks:
        blk.db_id = con.execute(blocks.INSERT_SQL, blk.as_row()).lastrowid

    groups = chunking.make_chunks(data.blocks, args.chunk_chars)
    for group in groups:
        cid = con.execute("INSERT INTO chunks(status) VALUES('pending')").lastrowid
        con.executemany("UPDATE blocks SET chunk_id=? WHERE id=?",
                        [(cid, blk.db_id) for blk in group])

    db.set_meta(con, "source_name", src.name)
    db.set_meta(con, "source_format", fmt)
    db.set_meta(con, "chunk_chars", args.chunk_chars)
    for khoa, gia_tri in data.meta.items():
        db.set_meta(con, khoa, json.dumps(gia_tri))
    con.commit()

    total = sum(len(b.src_html) for b in data.blocks)
    print(f"Xong: {len(data.blocks)} đoạn, {total:,} ký tự, {len(groups)} chunk.")
    print(f"Project: {proj}")
    print(f"Việc tiếp theo:\n  1. Sửa {proj / 'style.md'} và {proj / 'glossary.txt'}"
          f"\n  2. python cli.py status {proj}\n  3. python cli.py translate {proj} --limit 3")


# ------------------------------------------------------------------ status

GIAI_THICH_CO = {
    "empty": "mô hình trả về rỗng",
    "tag_mismatch": "số thẻ HTML không khớp bản gốc",
    "too_short": "bản dịch ngắn bất thường so với bản gốc",
    "missing_number": "bản gốc có chữ số mà bản dịch không có",
    "missing_term": "thuật ngữ đã khai trong glossary không thấy trong bản dịch",
    "overflow": "chữ không vừa khung, đã giữ nguyên bản gốc ở chỗ đó",
}


def _giai_thich(co: str) -> str:
    return GIAI_THICH_CO.get(co, "không rõ")


def cmd_status(args):
    proj, con = open_project(args.project)
    q = lambda sql, *a: con.execute(sql, a).fetchone()[0]

    n_blocks = q("SELECT COUNT(*) FROM blocks")
    n_done = q("SELECT COUNT(*) FROM blocks WHERE dst_html IS NOT NULL")
    chars_all = q("SELECT COALESCE(SUM(LENGTH(src_html)),0) FROM blocks")
    chars_left = q("SELECT COALESCE(SUM(LENGTH(src_html)),0) FROM blocks WHERE dst_html IS NULL")
    by_status = {r["status"]: r["n"] for r in
                 con.execute("SELECT status, COUNT(*) n FROM chunks GROUP BY status")}

    print(f"Sách: {db.get_meta(con, 'source_name')}")
    print(f"Đoạn: {n_done:,}/{n_blocks:,} đã dịch | Chunk: "
          f"{by_status.get('done', 0)} xong, {by_status.get('pending', 0)} chờ, {by_status.get('failed', 0)} lỗi")
    print(f"Ký tự nguồn còn phải dịch: {chars_left:,} / {chars_all:,}")

    trang = q("SELECT COUNT(DISTINCT page_no) FROM blocks WHERE page_no >= 0")
    trang_xong = q("SELECT COUNT(*) FROM (SELECT page_no FROM blocks "
                   "WHERE page_no >= 0 GROUP BY page_no "
                   "HAVING SUM(dst_html IS NULL) = 0)")
    if trang:
        print(f"Trang đã dịch xong hoàn toàn: {trang_xong:,}/{trang:,}")

    est_in = chars_left / 4       # ~4 ký tự/token với tiếng Anh (chưa tính system prompt lặp lại)
    print(f"Ước tính thô còn lại: ~{est_in:,.0f} token vào (nội dung), "
          f"token ra thường ~1.5-2.5x vì tiếng Việt tốn token hơn.")
    print("=> Hãy dịch thử vài chunk (--limit 3) rồi xem token thực tế bên dưới để nhân lên.")

    t = con.execute("SELECT COALESCE(SUM(in_tokens),0) i, COALESCE(SUM(out_tokens),0) o, "
                    "COALESCE(SUM(cache_read),0) cr, COALESCE(SUM(cache_write),0) cw FROM chunks").fetchone()
    if t["i"] or t["o"]:
        print(f"Đã dùng: {t['i']:,} vào (không cache) + {t['cr']:,} cache đọc + {t['cw']:,} cache ghi, "
              f"{t['o']:,} ra")
        p_in, p_out = os.environ.get("PRICE_IN"), os.environ.get("PRICE_OUT")
        if p_in and p_out:
            # Cache đọc thường rẻ bằng 1/10 giá vào, cache ghi đắt 1.25
            # lần. Style + glossary đi kèm MỌI chunk dưới dạng cache
            # đọc, nên gộp tất cả vào giá vào thì thổi phồng hẳn con số mà
            # người dùng dựa vào để quyết có dịch cả cuốn hay không.
            p_cr = float(os.environ.get("PRICE_CACHE_READ") or float(p_in) * 0.1)
            p_cw = float(os.environ.get("PRICE_CACHE_WRITE") or float(p_in) * 1.25)
            cost = (t["i"] * float(p_in) + t["cr"] * p_cr + t["cw"] * p_cw
                    + t["o"] * float(p_out)) / 1_000_000
            print(f"Đã tiêu: ${cost:,.2f} (giá USD/1M token từ PRICE_IN/PRICE_OUT, "
                  f"cache tính {p_cr:g}/{p_cw:g}; đổi bằng "
                  f"PRICE_CACHE_READ/PRICE_CACHE_WRITE)")
            da_dich = chars_all - chars_left
            if da_dich > 0 and chars_left > 0:
                # Ngoại suy theo SỐ KÝ TỰ đã dịch, không theo số chunk: chunk
                # to nhỏ không đều nên đếm chunk sẽ lệch.
                print(f"Ước tính cả cuốn: ${cost * chars_all / da_dich:,.2f} "
                      f"(ngoại suy từ {da_dich:,}/{chars_all:,} ký tự đã dịch)")
        else:
            print("(Đặt biến môi trường PRICE_IN và PRICE_OUT, đơn vị USD/1M token, để xem chi phí.)")

    used = con.execute(
        "SELECT provider, model, COUNT(*) n, "
        "COALESCE(SUM(in_tokens),0) i, COALESCE(SUM(out_tokens),0) o "
        "FROM chunks WHERE provider IS NOT NULL GROUP BY provider, model "
        "ORDER BY n DESC").fetchall()
    if used:
        print("Đã dịch bằng:")
        for r in used:
            print(f"  {r['provider']} / {r['model']}: {r['n']} chunk, "
                  f"vào {r['i']:,}, ra {r['o']:,}")

    theo_loai = con.execute(
        "SELECT flag, COUNT(*) n FROM blocks WHERE flag IS NOT NULL "
        "GROUP BY flag ORDER BY n DESC").fetchall()
    if theo_loai:
        tong_co = sum(r["n"] for r in theo_loai)
        print(f"\n{tong_co} đoạn bị gắn cờ (nên xem lại):")
        for r in theo_loai:
            print(f"  {r['flag']:<16} {r['n']:>5} đoạn — {_giai_thich(r['flag'])}")
        vai = con.execute(
            "SELECT id, page_no, flag, json_extract(layout, '$.href') AS href "
            "FROM blocks WHERE flag IS NOT NULL ORDER BY id LIMIT 5").fetchall()
        print("  ví dụ:")
        for r in vai:
            cho = r["href"] or f"trang {r['page_no'] + 1}"
            print(f"    block {r['id']} ({cho}): {r['flag']}")
            print(f"      xem: python cli.py edit {args.project} --block {r['id']}")

    failed = con.execute("SELECT id, error FROM chunks WHERE status='failed' ORDER BY id LIMIT 5").fetchall()
    for r in failed:
        print(f"chunk {r['id']} lỗi: {r['error']}")


# ------------------------------------------------------------------ inspect

def parse_pages(spec):
    """'10-20' -> (9, 19). None -> None.

    Người dùng đếm trang từ 1 — như số in trên sách và như số `inspect` hiện —
    còn page_no trong DB đếm từ 0. Quy đổi ở đúng ranh giới này, nếu không
    trang đầu của sách không bao giờ với tới được.
    """
    if not spec:
        return None
    try:
        dau, _, cuoi = spec.partition("-")
        a = int(dau)
        b = int(cuoi) if cuoi else a
    except ValueError:
        die(f"--pages phải có dạng 10-20 hoặc 10, không phải '{spec}'.")
    if a < 1 or b < 1:
        die(f"--pages đếm từ 1, không nhận '{spec}'.")
    return (a - 1, b - 1)


def _rut_gon(s: str, gioi_han: int = 90) -> str:
    from bs4 import BeautifulSoup
    t = BeautifulSoup(s, "html.parser").get_text().strip()
    t = " ".join(t.split())
    return t if len(t) <= gioi_han else t[:gioi_han - 1] + "\u2026"


def cmd_inspect(args):
    proj, con = open_project(args.project)
    khoang = parse_pages(args.pages)

    sql = ("SELECT page_no, pos, tag, kind, src_html, bbox, cont_group "
           "FROM blocks")
    tham = ()
    if khoang:
        sql += " WHERE page_no BETWEEN ? AND ?"
        tham = khoang
    sql += " ORDER BY page_no, pos"

    rows = con.execute(sql, tham).fetchall()
    if not rows:
        print("không có đoạn nào trong khoảng này.")
        return

    trang_hien = None
    tong = 0
    for r in rows:
        if r["page_no"] != trang_hien:
            trang_hien = r["page_no"]
            # hiện số trang như người dùng thấy; page_no âm là mục lục/tên sách
            hien = trang_hien + 1 if trang_hien >= 0 else trang_hien
            print(f"\n--- trang {hien} ---")
        tong += len(r["src_html"])
        noi = _rut_gon(r["src_html"])
        nhom = f" ->nhóm {r['cont_group']}" if r["cont_group"] else ""
        print(f"  [{r['pos']:>2}] {r['kind']:<8} {r['tag']:<3}{nhom} | {noi}")

    trang = {r["page_no"] for r in rows}
    print(f"\n{len(rows)} đoạn trên {len(trang)} trang, {tong:,} ký tự nguồn.")
    print("Soi thứ tự đọc và phân loại ở trên. Chưa tốn token nào.")


# ------------------------------------------------------------------ glossary

def cmd_glossary(args):
    proj, con = open_project(args.project)
    doan = [r[0] for r in con.execute(
        "SELECT src_html FROM blocks WHERE kind != 'skip'")]
    ds = glossary.ung_vien(doan, top=args.top)
    if not ds:
        die("không trích được ứng viên nào (sách quá ngắn?).")

    ra = proj / "glossary.candidates.txt"
    glossary.ghi_ung_vien(ra, ds)
    print(f"Đã ghi {len(ds)} ứng viên vào {ra}")
    print(f"  hay gặp nhất: {ds[0][1]} lần | ít nhất trong danh sách: {ds[-1][1]} lần")
    print(f"Duyệt file đó, bỏ dấu # ở dòng bạn muốn khai, điền bản dịch, "
          f"rồi dán sang {proj / 'glossary.txt'}.")


# ------------------------------------------------------------------ edit

def cmd_edit(args):
    proj, con = open_project(args.project)
    r = con.execute(
        "SELECT id, page_no, kind, src_html, dst_html, flag FROM blocks WHERE id=?",
        (args.block,)).fetchone()
    if r is None:
        die(f"không có đoạn nào mang id {args.block}. Xem id bằng `inspect`.")

    if args.set is None:
        trang = r["page_no"] + 1 if r["page_no"] >= 0 else r["page_no"]
        print(f"block {r['id']} | trang {trang} | {r['kind']}"
              + (f" | cờ: {r['flag']}" if r["flag"] else ""))
        print(f"  gốc : {r['src_html']}")
        print(f"  dịch: {r['dst_html'] if r['dst_html'] else '(chưa dịch)'}")
        return

    if not args.set.strip():
        # `--set "$BIEN"` với biến chưa đặt sẽ ghi đè bản dịch đã trả tiền bằng
        # chuỗi rỗng. Block vẫn thoả `dst_html IS NOT NULL` nên `translate`
        # không dịch lại, `export` ra ô trống, và từ CLI không có đường nào
        # quay lại NULL. Chặn ở đây thay vì để mất chữ.
        die("--set rỗng sẽ xoá mất bản dịch mà không khôi phục được. "
            "Truyền nội dung thật, hoặc để nguyên nếu chỉ muốn xem.")

    # Người dùng vừa sửa tay thì cảnh báo máy gắn trước đó không còn đúng nữa.
    con.execute("UPDATE blocks SET dst_html=?, flag=NULL WHERE id=?",
                (args.set, args.block))
    con.commit()
    print(f"Đã sửa block {args.block}. Chạy `export` để xuất lại.")


# ------------------------------------------------------------------ translate

def kiem_khoang_trang(con, khoang) -> tuple:
    """Từ chối khoảng trang vô nghĩa. Trả về (dau, cuoi) đã kiểm.

    Ba tình huống khác hẳn nhau và từng bị gộp chung một câu: gõ nhầm
    `--pages 20-10` mà chỉ nghe "không có chunk nào" thì người dùng tưởng 10
    trang ấy đã dịch xong. `export` đã tách riêng từ Phase 4; `translate` và
    `reset` dùng lại đúng luật đó ở đây để ba lệnh không nói ba kiểu.
    """
    dau, cuoi = khoang
    if dau > cuoi:
        die(f"khoảng trang ngược: {dau + 1}-{cuoi + 1}.")
    het = con.execute(
        "SELECT MAX(page_no) FROM blocks WHERE page_no >= 0").fetchone()[0]
    so_trang = het + 1 if het is not None else 0
    if dau >= so_trang or cuoi < 0:
        die(f"khoảng trang {dau + 1}-{cuoi + 1} nằm ngoài sách "
            f"({so_trang} trang).")
    return dau, cuoi


# ------------------------------------------------------------------ reset

def cmd_reset(args):
    """Xoá bản dịch của một khoảng trang để dịch lại bằng model khác.

    `translate` chỉ lấy đoạn có `dst_html IS NULL`, nên không có lệnh này thì
    bản dịch của model đầu tiên bị đóng đinh vĩnh viễn — lần dùng thật đầu
    tiên mới lộ ra chỗ thiếu ấy.

    Xoá thứ đã trả tiền nên mặc định KHÔNG xoá: chạy không có --yes thì chỉ
    báo cáo. Và không có --pages thì từ chối hẳn, vì `reset` trần mà xoá sạch
    cả cuốn là tai hoạ không hoàn lại được.
    """
    proj, con = open_project(args.project)

    if not getattr(args, "pages", None):
        die("reset phải có --pages. Không có nó thì lệnh này xoá sạch bản dịch "
            "cả cuốn, nên phải ghi rõ khoảng trang muốn xoá.")

    dau, cuoi = kiem_khoang_trang(con, parse_pages(args.pages))

    doan = [r["id"] for r in con.execute(
        "SELECT id FROM blocks WHERE page_no BETWEEN ? AND ? "
        "AND dst_html IS NOT NULL", (dau, cuoi))]
    if not doan:
        print(f"Không có đoạn nào đã dịch trong khoảng trang {dau + 1}-{cuoi + 1}.")
        return

    cho = ",".join("?" * len(doan))
    chunk = [r[0] for r in con.execute(
        f"SELECT DISTINCT chunk_id FROM blocks WHERE id IN ({cho}) "
        f"AND chunk_id IS NOT NULL", doan)]
    cho_c = ",".join("?" * len(chunk))
    tok = con.execute(
        f"SELECT COALESCE(SUM(in_tokens),0) i, COALESCE(SUM(out_tokens),0) o "
        f"FROM chunks WHERE id IN ({cho_c})", chunk).fetchone()

    if not args.yes:
        print(f"Sẽ xoá bản dịch của {len(doan)} đoạn trên trang "
              f"{dau + 1}-{cuoi + 1} ({len(chunk)} chunk).")
        print(f"  bỏ đi lượt dịch đã tiêu {tok['i']:,} token vào + "
              f"{tok['o']:,} token ra")
        print("Không hoàn lại được. Thêm --yes nếu chắc chắn.")
        return

    con.execute(f"UPDATE blocks SET dst_html=NULL, flag=NULL WHERE id IN ({cho})",
                doan)
    # Để chunk ở 'done' thì `translate` bỏ qua và việc xoá thành vô nghĩa.
    # Xoá luôn số token: `translate` CỘNG THÊM vào, nên giữ số cũ sẽ khiến cùng
    # một đoạn chữ mang token của hai lượt dịch và `status` ngoại suy cả cuốn
    # đắt gấp đôi. Đổi lại, khoản đã tiêu cho lượt cũ không còn trong sổ — nên
    # nó được in ra ngay trên đây.
    con.execute(f"UPDATE chunks SET status='pending', error=NULL, in_tokens=0, "
                f"out_tokens=0, cache_read=0, cache_write=0 WHERE id IN ({cho_c})",
                chunk)
    con.commit()
    print(f"Đã xoá bản dịch của {len(doan)} đoạn trên trang {dau + 1}-{cuoi + 1}.")
    print(f"Dịch lại: python cli.py translate {args.project} "
          f"--pages {dau + 1}-{cuoi + 1} --model <model mới>")


# ------------------------------------------------------------------ translate

def cmd_translate(args):
    import translator

    proj, con = open_project(args.project)

    # Chọn việc TRƯỚC khi dựng client. Cả ba đường ra dưới đây đều không tốn
    # một lượt gọi nào, nên không có lý do bắt người dùng phải có khoá API mới
    # nghe được "khoảng trang này dịch xong rồi".
    total_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    chua_xong = [r["id"] for r in con.execute(
        "SELECT id FROM chunks WHERE status != 'done' ORDER BY id")]

    khoang = parse_pages(getattr(args, "pages", None))
    if khoang:
        dau, cuoi = kiem_khoang_trang(con, khoang)
        trang_theo_chunk = {}
        for r in con.execute(
            "SELECT chunk_id, page_no FROM blocks WHERE chunk_id IS NOT NULL"
        ):
            trang_theo_chunk.setdefault(r["chunk_id"], set()).add(r["page_no"])
        trong_khoang, phu = chunking.chunks_cho_trang(trang_theo_chunk, khoang)
        todo = [c for c in chua_xong if c in set(trong_khoang)]
        if not todo:
            print(f"Không có chunk nào cần dịch trong khoảng trang "
                  f"{dau + 1}-{cuoi + 1}: đã dịch xong rồi.")
            return
        # Vùng phủ THẬT, không phải khoảng đã xin: chunk vắt ngang trang kéo
        # theo vài trang ngoài khoảng, và người dùng đang trả tiền cho chúng.
        print(f"Khoảng trang {dau + 1}-{cuoi + 1} "
              f"-> thực dịch trang {phu[0] + 1}-{phu[1] + 1}.")
    else:
        todo = chua_xong

    if not todo:
        print("Không còn chunk nào cần dịch. Chạy `export` để xuất file.")
        return

    try:
        provider = providers.get(args.provider)
    except ValueError as e:
        die(str(e))

    model = args.model or provider.DEFAULT_MODEL
    if not model:
        die(f"provider '{args.provider}' không có model mặc định. Truyền --model.")

    style_path = proj / "style.md"
    style = style_path.read_text(encoding="utf-8") if style_path.exists() else ""
    system = translator.build_system(style, translator.load_glossary(proj / "glossary.txt"))
    # Cùng file glossary.txt: vào prompt để mô hình dùng, và vào check_translation
    # để kiểm xem mô hình có dùng thật không.
    thuat_ngu = glossary.doc_bang(proj / "glossary.txt")
    try:
        client = provider.make_client()
    except Exception as e:
        die(f"không khởi tạo được provider '{args.provider}': {e}")
    if args.limit:
        todo = todo[:args.limit]

    print(f"Provider: {provider.NAME} | Model: {model} | Dịch {len(todo)} chunk "
          f"(tổng {total_chunks}). Ctrl+C để dừng, chạy lại sẽ tiếp tục.")
    ok = failed = 0
    try:
        for n, cid in enumerate(todo, 1):
            size = con.execute(
                "SELECT COUNT(*), SUM(LENGTH(src_html)) FROM blocks WHERE chunk_id=?",
                (cid,)).fetchone()
            print(f"[{n}/{len(todo)}] chunk {cid} ({size[0]} đoạn, {size[1]:,} ký tự) ... ",
                  end="", flush=True)
            try:
                res = translator.translate_chunk(con, provider, client, model,
                                                 system, cid, thuat_ngu)
            except translator.FatalAPIError as e:
                print("LỖI NGHIÊM TRỌNG")
                die(f"{e}\nKiểm tra API key, tên model (--model), số dư tài khoản.")
            u = res["usage"]
            extra = f", {res['flagged']} đoạn gắn cờ" if res["flagged"] else ""
            if res["status"] == "done":
                ok += 1
                print(f"ok (vào {u['input'] + u['cache_read'] + u['cache_write']:,}, "
                      f"ra {u['output']:,}{extra})")
            else:
                failed += 1
                print(f"THẤT BẠI, còn {res['missing']} đoạn: {res['error']}")
    except KeyboardInterrupt:
        print("\nĐã dừng. Tiến độ đã lưu; chạy lại lệnh translate để tiếp tục.")
    print(f"Xong phiên này: {ok} chunk ok, {failed} lỗi. Xem `status` để biết chi tiết.")


# ------------------------------------------------------------------ export

def cmd_export(args):
    proj, con = open_project(args.project)
    fmt = db.get_meta(con, "source_format", "epub")

    n_missing = con.execute(
        "SELECT COUNT(*) FROM blocks WHERE dst_html IS NULL").fetchone()[0]
    if n_missing:
        print(f"Lưu ý: còn {n_missing} đoạn chưa dịch, sẽ giữ nguyên tiếng Anh "
              f"trong file xuất.")

    out = Path(args.output) if args.output else \
        proj / render.default_output_name(fmt, args.bilingual)
    try:
        tk = render.write(fmt, proj, con, out, bilingual=args.bilingual,
                          mode=args.mode, pages=parse_pages(args.pages),
                          dry_run=args.dry_run, probe=args.probe)
    except (render.UnsupportedTarget, pdf_font.ThieuFont) as e:
        die(str(e))
    print(f"Đã xuất: {out}")
    if tk:
        print(f"  {tk['so_trang']} khổ, {tk['so_khoi']} khối, cỡ chữ trung vị "
              f"{tk['co_trung_vi']:.0%}, {tk['tran']} khối tràn khung.")
        if tk.get("trang_du_phong"):
            print(f"  {tk['trang_du_phong']} trang dự phòng: không dàn vừa ở "
                  f"cỡ chữ 75% nên giữ bố cục theo vị trí.")


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description="Dịch sách Anh -> Việt (EPUB, PDF, sách scan) bằng mô hình AI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="tạo project từ file sách (EPUB hoặc PDF; sách scan chưa có chữ thì tự OCR)")
    p.add_argument("source", help="đường dẫn file sách")
    p.add_argument("--dir", help="thư mục project (mặc định: projects/<tên file>)")
    p.add_argument("--chunk-chars", type=int, default=chunking.DEFAULT_CHUNK_CHARS,
                   help=f"kích thước chunk tính theo ký tự (mặc định {chunking.DEFAULT_CHUNK_CHARS})")
    p.add_argument("--force", action="store_true", help="tạo lại project đã tồn tại")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("status", help="xem tiến độ, ước tính, đoạn bị gắn cờ")
    p.add_argument("project")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("inspect", help="xem tool hiểu cuốn sách thế nào (không tốn token)")
    p.add_argument("project")
    p.add_argument("--pages", help="khoảng trang, ví dụ 1-20")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("glossary", help="gom thuật ngữ hay gặp để duyệt trước khi dịch")
    p.add_argument("project")
    p.add_argument("--top", type=int, default=200,
                   help="số ứng viên (mặc định 200)")
    p.set_defaults(func=cmd_glossary)

    p = sub.add_parser("edit", help="xem hoặc sửa tay bản dịch của một đoạn")
    p.add_argument("project")
    p.add_argument("--block", type=int, required=True, help="id đoạn, xem bằng `inspect`")
    p.add_argument("--set", help="bản dịch mới; bỏ trống để chỉ xem")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("reset", help="xoá bản dịch một khoảng trang để dịch lại")
    p.add_argument("project")
    p.add_argument("--pages", required=True,
                   help="khoảng trang cần xoá, ví dụ 150-169 (bắt buộc)")
    p.add_argument("--yes", action="store_true",
                   help="xác nhận xoá thật; không có cờ này thì chỉ báo cáo")
    p.set_defaults(func=cmd_reset)

    p = sub.add_parser("translate", help="dịch các chunk còn lại (có thể dừng và chạy lại)")
    p.add_argument("project")
    p.add_argument("--provider",
                   default=os.environ.get("BOOKTRANS_PROVIDER", providers.DEFAULT_PROVIDER),
                   help=f"mặc định {providers.DEFAULT_PROVIDER}. "
                        f"Có: {', '.join(providers.names())}")
    p.add_argument("--model", help="mặc định theo provider")
    p.add_argument("--limit", type=int, help="chỉ dịch N chunk (để chạy thử)")
    p.add_argument("--pages", help="chỉ dịch các chunk chạm khoảng trang, ví dụ 1-20")
    p.set_defaults(func=cmd_translate)

    p = sub.add_parser("export", help="xuất bản dịch: EPUB tiếng Việt, hoặc PDF khổ đôi song ngữ")
    p.add_argument("project")
    p.add_argument("-o", "--output")
    p.add_argument("--bilingual", action="store_true", help="xen kẽ bản gốc dưới mỗi đoạn")
    p.add_argument("--mode", choices=("overlay", "reflow"),
                   help="overlay: đè chữ lên trang gốc (mặc định cho PDF, hợp với "
                        "PDF có chữ). reflow: dựng trang mới theo thứ tự đoạn, "
                        "hình thành ô 'ảnh' (dùng cho sách scan)")
    p.add_argument("--pages", help="khoảng trang, ví dụ 1-20")
    p.add_argument("--dry-run", action="store_true",
                   help="đè chính chữ gốc kèm chữ độn — kiểm layout, không tốn token")
    p.add_argument("--probe", action="store_true",
                   help="thêm trang báo cáo dựng trang ở đầu file")
    p.set_defaults(func=cmd_export)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
