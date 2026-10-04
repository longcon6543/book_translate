"""Phần tính vị trí của chế độ reflow: dàn khối theo thứ tự, neo độ cao gốc.

Hàm thuần, không đụng PyMuPDF: nhận số, trả số. Phần đo chiều cao chữ và vẽ
nằm ở pdf_reflow. Tách ra vì đây là toàn bộ phần logic khó, và test bằng số
thì nhanh và chính xác hơn đọc ngược chữ trên trang.

Spec: docs/superpowers/specs/2026-09-24-dan-trang-theo-thu-tu-design.md
"""

# D2: lề bốn phía. Người dùng cho nới lề; cột chữ gốc harmonics rộng ~277pt,
# khung chữ với lề này rộng 306pt. Đo thử: lề 18 và 36 đều cho trung vị 100%.
LE = 22.0
# D5: hệ số co chung cho cả trang, thử lần lượt, vừa là dừng. Dưới 0,75 chữ
# khó đọc — trang đó rơi về bố cục theo vị trí.
THANG_S = (1.00, 0.95, 0.90, 0.85, 0.80, 0.75)
# Khoảng cách giữa hai khối, tính theo cỡ thân bài.
TI_LE_KHOANG = 0.4
# D4: khối rộng từ ngần này bề rộng khung trở lên thì kéo ra đủ khung.
TI_LE_KHOI_RONG = 0.6
# D4: khối hẹp không được hẹp hơn ngần này bề rộng khung. Đo thật: 236 khối
# harmonics rộng dưới 10% khung — giữ nguyên thì chữ Việt thành cột một chữ.
TI_LE_KHOI_HEP_MIN = 0.25
# Giãn dòng đã dùng khi đo thử (spec mục 2).
GIAN_DONG = 1.2


def co_khoi(kind: str, size: float, than: float) -> float:
    """D3: cỡ chữ theo loại khối. `than` là cỡ thân bài của cả cuốn."""
    if kind == "text":
        return than
    if kind == "heading":
        return min(max(size, than), 2 * than)
    return min(max(size, 0.8 * than), than)


def khung_ngang(x0: float, x1: float, trai: float, phai: float) -> tuple:
    """D4: khoảng ngang của khối trong khung chữ [trai, phai]."""
    rong_khung = phai - trai
    rong = x1 - x0
    if rong >= TI_LE_KHOI_RONG * rong_khung:
        return trai, phai
    toi_thieu = TI_LE_KHOI_HEP_MIN * rong_khung
    if rong < toi_thieu:
        tam = (x0 + x1) / 2
        x0, rong = tam - toi_thieu / 2, toi_thieu
    a = min(max(x0, trai), phai - rong)
    return a, a + rong


def _chong_ngang(a: tuple, b: tuple) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def xep_doc(neo: list, cao: list, tren: float, duoi: float,
            khoang: float, ngang: "list | None" = None) -> "list | None":
    """D1 + D5 bước 1-2: độ cao đỉnh của từng khối, hoặc None nếu không vừa.

    Bước 1 neo: mỗi khối ở max(neo, đáy mọi khối TRƯỚC nó có chồng theo chiều
    ngang + khoảng). Hai khối chồng ngang thì khối sau luôn nằm dưới khối
    trước nên không bao giờ đè; khối không chồng ngang (cột khác) thì không
    đẩy nhau — chỉ mục 2 cột mà dò cột không bắt được vẫn dàn được.

    Bước 2 đẩy ngược từ đáy khi bước 1 vượt đáy: đi từ khối cuối lên, mỗi
    khối chỉ nâng vừa đủ để nó và các khối SAU nó chồng ngang còn vừa khung.
    Khối không cần nâng giữ nguyên neo — một dòng chân trang neo dưới lề không
    kéo cả trang lên đỉnh. Bước này hỏng đúng khi có một chuỗi khối chồng
    ngang dài hơn khung, cũng là lúc dồn khít từ đỉnh hỏng, nên không cần
    bước dồn khít riêng.

    `ngang` là list (x0, x1) từng khối; None = mọi khối chồng nhau (một cột).
    """
    if not cao:
        return []
    if ngang is None:
        ngang = [(0.0, 1.0)] * len(cao)
    n = len(cao)

    y = []
    for i in range(n):
        dinh = max(neo[i], tren)
        for j in range(i):
            if _chong_ngang(ngang[i], ngang[j]):
                dinh = max(dinh, y[j] + cao[j] + khoang)
        y.append(dinh)
    if max(yi + h for yi, h in zip(y, cao)) <= duoi + 1e-6:
        return y

    for i in range(n - 1, -1, -1):
        tran_tren = duoi - cao[i]
        for k in range(i + 1, n):
            if _chong_ngang(ngang[i], ngang[k]):
                tran_tren = min(tran_tren, y[k] - khoang - cao[i])
        y[i] = min(y[i], tran_tren)
    if min(y) >= tren - 1e-6:
        return y
    return None
