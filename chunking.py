"""Gom block liên tiếp thành chunk để gửi đi dịch.

Hàm thuần: không đụng DB, không đụng mạng, không đụng thư viện ngoài.
"""

DEFAULT_CHUNK_CHARS = 6000


def make_chunks(blocks: list, max_chars: int) -> list:
    """Gom các block liên tiếp thành chunk <= max_chars. Trả về list[list[Block]].

    Cắt chunk ở ba tình huống:
      - qua lại giữa trang thật và khối giả (mục lục, tên sách)
      - thêm block nữa là vượt max_chars
      - sang trang mới trong khi chunk đã đầy quá nửa
    """
    chunks, cur, size = [], [], 0
    for blk in blocks:
        n = len(blk.src_html)
        if cur:
            prev = cur[-1]
            doi_trang = blk.page_no != prev.page_no
            qua_khoi_gia = doi_trang and (blk.page_no < 0 or prev.page_no < 0)
            qua_to = size + n > max_chars
            trang_moi = doi_trang and size >= max_chars / 2
            if qua_khoi_gia or qua_to or trang_moi:
                chunks.append(cur)
                cur, size = [], 0
        cur.append(blk)
        size += n
    if cur:
        chunks.append(cur)
    return chunks


def chunks_cho_trang(trang_theo_chunk: dict, khoang: tuple) -> tuple:
    """Chọn mọi chunk CHẠM vào khoảng trang. Trả về (chunk_id đã sắp, vùng phủ).

    Không cắt chunk cho khớp khoảng. Đo thật trên sách mẫu: 55% chunk vắt
    ngang nhiều trang, nhưng chọn kiểu chồng lấn chỉ dư 0-2 trang. Cắt chunk
    ra để khớp chính xác sẽ phá mất ngữ cảnh ba đoạn liền trước mà
    `translate_chunk` dựa vào, đổi lấy 0-2 trang — không đáng.

    Vùng phủ trả về là vùng THẬT sẽ được dịch, không phải khoảng đã xin, để
    người dùng biết mình vừa trả tiền cho những trang nào.

    page_no âm là khối giả của EPUB (mục lục, tên sách); `--pages` nói về
    trang thật nên chúng không bao giờ được chọn theo đường này.
    """
    dau, cuoi = khoang
    chon = []
    for cid, trang in trang_theo_chunk.items():
        that = {p for p in trang if p >= 0}
        if any(dau <= p <= cuoi for p in that):
            chon.append(cid)

    if not chon:
        return [], None

    phu = {p for cid in chon for p in trang_theo_chunk[cid] if p >= 0}
    return sorted(chon), (min(phu), max(phu))
