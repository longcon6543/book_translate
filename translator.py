"""Dịch từng chunk bằng Claude API: prompt, gọi API, kiểm tra kết quả, lưu SQLite."""
import re
import time
from collections import Counter
from pathlib import Path

import providers

MAX_ATTEMPTS = 3        # số lần thử lại cho các đoạn thiếu/hỏng trong một chunk
MAX_TOKENS = 8192       # tiếng Việt tốn token hơn tiếng Anh; chunk ~6000 ký tự vẫn dư sức
CONTEXT_BLOCKS = 3      # số đoạn liền trước (kèm bản dịch) đưa vào làm ngữ cảnh

# Cờ KHUYẾN CÁO: bản dịch có thể vẫn đúng, chỉ là đáng liếc mắt qua. Số viết
# thành chữ ("năm một nghìn chín trăm mười bốn") là cách dịch đúng, và mô hình
# hỏi lại sẽ trả về đúng thứ đó lần nữa — thử lại chỉ tốn tiền. Nhận ngay, gắn
# cờ, để người đọc quyết. Các mã còn lại (empty, tag_mismatch, too_short) là
# hỏng cấu trúc thật, hỏi lại có thể cứu được nên vẫn hỏi lại.
CO_KHUYEN_CAO = frozenset({"missing_number", "missing_term"})

SEG_RE = re.compile(r'<seg\s+id="(\d+)"[^>]*>(.*?)</seg>', re.S)
TAG_RE = re.compile(r"<\s*([a-zA-Z][a-zA-Z0-9:_-]*)")   # chỉ thẻ mở
STRIP_TAGS_RE = re.compile(r"<[^>]+>")


class FatalAPIError(RuntimeError):
    pass


SYSTEM_TEMPLATE = """You are an expert English-to-Vietnamese book translator. \
You translate one part of a book at a time and must stay consistent with the style guide and glossary below.

## Input / output format
The user message contains segments like:
<seg id="12" tag="p">inner HTML of one paragraph</seg>

Reply with the same segments, same ids, same order, translated into Vietnamese:
<seg id="12">bản dịch tiếng Việt</seg>

Output ONLY <seg> elements. No commentary, no markdown fences, no wrapper tags.

## Rules
1. Translate every segment completely. Never skip, merge, split, summarize, reorder or add content.
2. Segment content is an HTML fragment. Keep ALL inline tags and their attributes exactly as in the source \
(<em>, <i>, <b>, <a href="...">, <span class="...">, <br/>, <sup>...). Use the same number of each tag. \
Only translate the text between tags, and place the tags around the corresponding Vietnamese words.
3. Never translate or change attribute values, URLs or ids. Keep HTML entities (&amp; &lt; &gt;) as in the source.
4. The text may come from an ebook conversion and contain small artifacts; infer the intended meaning from context.
5. Keep numbers, code, formulas and text that is already Vietnamese unchanged.
6. <previous_context> (if present) is only for continuity of names, tone and pronouns. Do not translate or repeat it.
7. Write natural, fluent Vietnamese as a professional literary translator would, not word-for-word.

## Style guide (from the user)
{style}

## Glossary (always use these translations)
{glossary}
"""


# ---------------------------------------------------------------- prompt

def load_glossary(path: Path) -> str:
    """glossary.txt: mỗi dòng `term = bản dịch`; dòng bắt đầu bằng # là chú thích."""
    lines = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            term, vi = (s.strip() for s in raw.split("=", 1))
            if term and vi:
                lines.append(f"- {term} -> {vi}")
    return "\n".join(lines) or "(none)"


def build_system(style: str, glossary: str) -> str:
    return SYSTEM_TEMPLATE.format(style=style.strip() or "(none)", glossary=glossary)


def _plain(s: str, limit: int = 600) -> str:
    return STRIP_TAGS_RE.sub("", s).strip()[-limit:]


def build_user(context: list, blocks: list, retry: bool = False) -> str:
    parts = []
    if retry:
        parts.append("NOTE: a previous attempt had missing or malformed segments. "
                     "Return every segment below, keeping all HTML tags identical to the source.\n")
    if context:
        parts.append("<previous_context>")
        for src, dst in context:
            parts.append(f"[EN] {_plain(src)}\n[VI] {_plain(dst)}")
        parts.append("</previous_context>\n")
    parts.append("<segments>")
    for b in blocks:
        parts.append(f'<seg id="{b["id"]}" tag="{b["tag"]}">{b["src_html"]}</seg>')
    parts.append("</segments>")
    return "\n".join(parts)


# ---------------------------------------------------------------- kiểm tra

def _text_len(s: str) -> int:
    return len(STRIP_TAGS_RE.sub("", s).strip())


_CHU_SO = re.compile(r"\d+")


def _so_trong(s: str) -> Counter:
    """Các cụm chữ số trong phần NỘI DUNG, bỏ qua thuộc tính thẻ."""
    return Counter(_CHU_SO.findall(STRIP_TAGS_RE.sub("", s)))


def check_translation(src: str, dst: str, thuat_ngu: dict = None):
    """None nếu ổn, hoặc mã lỗi.

    empty | tag_mismatch | too_short | missing_number | missing_term

    Kiểm chữ số thì đáng tin: số phải sang bản dịch nguyên vẹn, và đo thật cho
    thấy 50% số đoạn có chữ số.

    KHÔNG kiểm tên riêng nói chung. 95% số đoạn chứa từ viết hoa, mà tên riêng
    thì được DỊCH — sang tiếng Việt vẫn viết hoa nhưng không còn ký tự nào
    giống bản gốc. Cảnh báo kêu ở mọi đoạn thì bằng không có cảnh báo. Chỉ kiểm
    những thuật ngữ người dùng đã khai trong glossary.txt, tức đúng chỗ họ đã
    tuyên bố muốn dịch thành gì.
    """
    if not dst.strip():
        return "empty"
    if Counter(TAG_RE.findall(src.lower())) != Counter(TAG_RE.findall(dst.lower())):
        return "tag_mismatch"

    if _so_trong(src) - _so_trong(dst):
        return "missing_number"

    if thuat_ngu:
        than_src = STRIP_TAGS_RE.sub("", src)
        than_goc_dst = STRIP_TAGS_RE.sub("", dst)
        than_dst = than_goc_dst.lower()
    # Model trả về nguyên xi bản gốc là nó CỐ Ý giữ nguyên, và với sách này
    # phần lớn là mục lục tra cứu A-Z: dịch sang tiếng Việt sẽ phá thứ tự chữ
    # cái và làm mục lục vô dụng. Không có bản dịch thì câu "bản dịch đánh rơi
    # thuật ngữ" cũng không có nghĩa. Đo thật: luật cũ sinh 30 cờ trên 417
    # đoạn, 28 trong số đó nằm ở mục lục.
    if thuat_ngu and than_src.strip() != than_goc_dst.strip():
        for en, vi in thuat_ngu.items():
            # Khoá viết hoa thì khớp đúng hoa: "moon" là vệ tinh còn "Moon" là
            # Mặt Trăng, "mercury" là thuỷ ngân còn "Mercury" là Thuỷ Tinh. Đo
            # thật trên 22 trang sách cho thấy khớp bất kể hoa thường sinh
            # nhiễu là chính, mà nhiễu nhiều thì cờ thật bị chôn. Khoá người
            # dùng tự viết thường thì vẫn khớp bất kể hoa thường: họ có ý vậy.
            hoa = 0 if en[:1].isupper() else re.I
            if (re.search(rf"\b{re.escape(en)}\b", than_src, hoa)
                    and vi.lower() not in than_dst):
                return "missing_term"

    s, d = _text_len(src), _text_len(dst)
    if s > 80 and d < 0.4 * s:       # tiếng Việt thường dài hơn hoặc bằng tiếng Anh
        return "too_short"
    return None


def parse_response(text: str) -> dict:
    return {int(i): body.strip() for i, body in SEG_RE.findall(text)}


# ---------------------------------------------------------------- dịch một chunk

def _get_context(con, first_block) -> list:
    if first_block["page_no"] < 0:                   # mục lục / tên sách: không cần ngữ cảnh
        return []
    rows = con.execute(
        "SELECT src_html, dst_html FROM blocks "
        "WHERE id < ? AND page_no >= 0 AND dst_html IS NOT NULL "
        "ORDER BY id DESC LIMIT ?",
        (first_block["id"], CONTEXT_BLOCKS),
    ).fetchall()
    return [(r["src_html"], r["dst_html"]) for r in reversed(rows)]


def translate_chunk(con, provider, client, model: str, system: str, chunk_id: int,
                    thuat_ngu: dict = None) -> dict:
    """Dịch các block chưa có bản dịch trong chunk.

    `provider` là module (hoặc object) theo giao kèo ở providers/__init__.py.
    Trả về {status, error, flagged, usage, missing}.
    """
    rows = con.execute(
        "SELECT * FROM blocks WHERE chunk_id=? ORDER BY id", (chunk_id,)
    ).fetchall()
    todo = {b["id"]: b for b in rows if b["dst_html"] is None}
    context = _get_context(con, rows[0])

    best_effort = {}          # bid -> (dst, problem): bản dịch lỗi nhưng dùng được nếu hết cách
    gan_co_ngay = 0           # nhận luôn kèm cờ khuyến cáo, không thử lại
    usage = dict(input=0, output=0, cache_read=0, cache_write=0)
    error = None
    attempts = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if not todo:
            break
        attempts += 1
        user = build_user(context, list(todo.values()), retry=attempt > 1)
        try:
            text, u, stop = provider.call(client, model, system, user, MAX_TOKENS)
        except Exception as e:
            if provider.is_fatal(e):
                con.rollback()
                raise FatalAPIError(f"{type(e).__name__}: {e}") from e
            if not provider.is_retryable(e):
                # Provider không nhận là fatal cũng không nhận là thử lại được.
                # Gặp thật khi thiếu khoá API: SDK ném TypeError. `raise` trần ở
                # đây văng traceback giữa lúc đang dịch, nên gói lại để
                # cmd_translate in ra thành câu cho người đọc.
                con.rollback()
                raise FatalAPIError(f"{type(e).__name__}: {e}") from e
            error = f"{type(e).__name__}: {e}"
            time.sleep(min(30, 5 * attempt))
            continue

        for k in usage:
            usage[k] += u.get(k) or 0   # adapter lạ có thể trả thiếu khoá

        for bid, dst in parse_response(text).items():
            b = todo.get(bid)
            if b is None:
                continue                                      # id lạ -> bỏ qua
            problem = check_translation(b["src_html"], dst, thuat_ngu)
            if problem is None:
                con.execute("UPDATE blocks SET dst_html=?, flag=NULL WHERE id=?", (dst, bid))
                del todo[bid]
            elif problem in CO_KHUYEN_CAO:
                con.execute("UPDATE blocks SET dst_html=?, flag=? WHERE id=?",
                            (dst, problem, bid))
                del todo[bid]
                gan_co_ngay += 1
            else:
                best_effort[bid] = (dst, problem)

        if todo:
            error = f"lần {attempt}: còn {len(todo)} đoạn thiếu/lỗi" + \
                    (" (bị cắt do hết token, hãy giảm --chunk-chars)"
                     if stop == providers.TRUNCATED else "")

    flagged = gan_co_ngay
    for bid, (dst, problem) in best_effort.items():           # hết lượt: nhận bản tốt nhất, gắn cờ
        if bid in todo and dst.strip():
            con.execute("UPDATE blocks SET dst_html=?, flag=? WHERE id=?", (dst, problem, bid))
            del todo[bid]
            flagged += 1

    status = "done" if not todo else "failed"
    con.execute(
        "UPDATE chunks SET status=?, attempts=attempts+?, error=?, provider=?, model=?, "
        "in_tokens=in_tokens+?, out_tokens=out_tokens+?, cache_read=cache_read+?, "
        "cache_write=cache_write+? WHERE id=?",
        (status, attempts, None if status == "done" else error,
         getattr(provider, "NAME", None), model,
         usage["input"], usage["output"], usage["cache_read"], usage["cache_write"],
         chunk_id),
    )
    con.commit()
    return dict(status=status, error=error, flagged=flagged, usage=usage, missing=len(todo))
