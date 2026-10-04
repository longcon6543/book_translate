"""Đọc EPUB -> danh sách block cần dịch, và ghi bản dịch trở lại EPUB.

Nguyên tắc: chỉ thay *nội dung bên trong* các thẻ khối (p, h1-h6, li...),
giữ nguyên mọi thứ còn lại (ảnh, CSS, cấu trúc file) nên định dạng được giữ.

Hai hàm `extract_from_html` và `apply_to_html` là hàm thuần (chỉ dùng BeautifulSoup),
phần dùng ebooklib nằm ở nửa dưới file.
"""
import html

from bs4 import BeautifulSoup

import ebooklib
from ebooklib import epub

DC_NS = "http://purl.org/dc/elements/1.1/"

# Thẻ khối được coi là một "đoạn" để dịch. Chỉ lấy thẻ *lá* (không chứa thẻ khối con).
BLOCK_TAGS = [
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "blockquote", "figcaption", "dt", "dd", "td", "th", "caption", "div",
]
# Bỏ qua block nằm trong các thẻ này
SKIP_ANCESTORS = ["pre", "script", "style", "nav"]
# Thẻ mà bản song ngữ có thể chèn thêm một <p> nguồn ngay sau nó
SIBLING_OK = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "div", "figcaption"}

BILINGUAL_CSS = ".bt-src{color:#777;font-size:0.9em;font-style:italic;}"


# ---------------------------------------------------------------- hàm thuần (HTML)

def has_letters(text: str) -> bool:
    return any(c.isalpha() for c in text)


def parse_html(content) -> BeautifulSoup:
    return BeautifulSoup(content, "html.parser")


def iter_blocks(soup):
    """Duyệt các block lá theo thứ tự tài liệu.

    QUAN TRỌNG: extract và apply phải dùng đúng hàm này để `pos` khớp nhau.
    """
    for el in soup.find_all(BLOCK_TAGS):
        if el.find(BLOCK_TAGS) is not None:          # có thẻ khối con -> không phải lá
            continue
        if el.find_parent(SKIP_ANCESTORS) is not None:
            continue
        yield el


def extract_from_html(content) -> list:
    """Trả về [(pos, tag, inner_html)] cho các block có chữ."""
    soup = parse_html(content)
    out = []
    for pos, el in enumerate(iter_blocks(soup)):
        if not has_letters(el.get_text()):
            continue                                  # số trang, "* * *", ảnh trống...
        out.append((pos, el.name, el.decode_contents().strip()))
    return out


def _set_inner(el, inner_html: str) -> None:
    frag = BeautifulSoup(inner_html, "html.parser")
    el.clear()
    for child in list(frag.contents):
        el.append(child)


def _strip_ids(node) -> None:
    """Bản sao nguồn trong chế độ song ngữ không được trùng id/anchor."""
    for t in node.find_all(True):
        t.attrs.pop("id", None)
        if t.name == "a":
            t.attrs.pop("name", None)


def _add_source_copy(soup, el, orig_html: str) -> None:
    if el.name in SIBLING_OK:
        node = soup.new_tag("p", attrs={"class": "bt-src"})
        _set_inner(node, orig_html)
        _strip_ids(node)
        el.insert_after(node)
    else:  # li, td, th, dt, dd, caption: chèn vào trong chính thẻ để không vỡ cấu trúc
        span = soup.new_tag("span", attrs={"class": "bt-src"})
        _set_inner(span, orig_html)
        _strip_ids(span)
        el.append(soup.new_tag("br"))
        el.append(span)


def apply_to_html(content, translations: dict, bilingual: bool = False) -> bytes:
    """translations: {pos: inner_html_đã_dịch}. Trả về HTML mới (bytes)."""
    soup = parse_html(content)
    els = list(iter_blocks(soup))                     # chốt danh sách trước khi sửa cây
    changed = False
    for pos, el in enumerate(els):
        dst = translations.get(pos)
        if dst is None:
            continue
        orig_html = el.decode_contents()
        _set_inner(el, dst)
        if bilingual:
            _add_source_copy(soup, el, orig_html)
        changed = True

    if changed:
        if soup.html is not None:
            soup.html["lang"] = "vi"
            if soup.html.has_attr("xml:lang"):
                soup.html["xml:lang"] = "vi"
        if bilingual and soup.head is not None:
            style = soup.new_tag("style", attrs={"type": "text/css"})
            style.string = BILINGUAL_CSS
            soup.head.append(style)
    return str(soup).encode("utf-8")


# ---------------------------------------------------------------- phần ebooklib

def load_book(path):
    return epub.read_epub(str(path), options={"ignore_ncx": False})


def _is_content_doc(item) -> bool:
    if item.get_type() != ebooklib.ITEM_DOCUMENT:
        return False
    if isinstance(item, epub.EpubNav):
        return False
    if "nav" in (getattr(item, "properties", None) or []):
        return False
    return True


def ordered_documents(book) -> list:
    """Các file nội dung theo thứ tự đọc (spine), rồi đến file nằm ngoài spine."""
    docs, seen = [], set()
    for entry in book.spine:
        idref = entry[0] if isinstance(entry, (tuple, list)) else entry
        item = book.get_item_with_id(idref)
        if item is not None and _is_content_doc(item) and item.get_name() not in seen:
            docs.append(item)
            seen.add(item.get_name())
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        if _is_content_doc(item) and item.get_name() not in seen:
            docs.append(item)
            seen.add(item.get_name())
    return docs


def toc_entries(toc):
    """Duyệt phẳng mục lục (Link / Section / (Section, [con]))."""
    for entry in toc:
        if isinstance(entry, tuple):
            section, children = entry
            yield section
            yield from toc_entries(children)
        else:
            yield entry


def extract_blocks(book) -> list:
    """Trả về list[Block] đúng thứ tự dịch."""
    from blocks import Block          # tránh import vòng khi test riêng
    from db import PAGE_TITLE, PAGE_TOC

    rows = []
    for di, item in enumerate(ordered_documents(book)):
        href = item.get_name()
        for pos, tag, inner in extract_from_html(item.get_content()):
            rows.append(Block(page_no=di, pos=pos, tag=tag, src_html=inner,
                              layout={"href": href}))

    for i, entry in enumerate(toc_entries(book.toc)):
        title = (getattr(entry, "title", "") or "").strip()
        if has_letters(title):
            rows.append(Block(page_no=PAGE_TOC, pos=i, tag="toc",
                              src_html=html.escape(title, quote=False)))

    titles = book.get_metadata("DC", "title")
    if titles and has_letters(titles[0][0]):
        rows.append(Block(page_no=PAGE_TITLE, pos=0, tag="title",
                          src_html=html.escape(titles[0][0], quote=False)))
    return rows


def write_translated(book, out_path, doc_map: dict, toc_map: dict,
                     title: str = None, bilingual: bool = False) -> None:
    """doc_map: {href: {pos: dst_html}}, toc_map: {index: title}."""
    for item in ordered_documents(book):
        tr = doc_map.get(item.get_name())
        if tr:
            item.set_content(apply_to_html(item.get_content(), tr, bilingual))

    for i, entry in enumerate(toc_entries(book.toc)):
        if i in toc_map:
            entry.title = toc_map[i]

    book.language = "vi"
    book.metadata.setdefault(DC_NS, {})["language"] = [("vi", {})]
    if title:
        book.title = title
        book.metadata.setdefault(DC_NS, {})["title"] = [(title, {})]

    epub.write_epub(str(out_path), book)
