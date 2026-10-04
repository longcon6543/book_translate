"""Dò vùng hình vẽ trên ảnh trang sách scan. Hàm thuần: không PyMuPDF.

Trên trang scan, OCR đọc nét vẽ và ký hiệu của hình thành chữ rác ("K Ores"
cỡ tiêu đề). Hình có một dấu hiệu chữ không có: nét mực liền cao hơn nhiều
dòng chữ (đường kẻ, vòng tròn, bản đồ). Từ các nét đó, vùng nở ra nuốt ký
hiệu và nhãn nhỏ quanh hình, nhưng không bao giờ nuốt chú thích hay văn xuôi.

Đo thật trên sách scan 484 trang: 153 trang có vùng; 0 chú thích và 0 dòng văn
xuôi bị nuốt; bỏ 303 dòng rác (trung bình 4 ký tự). Hình chỉ gồm ký hiệu
không có nét vẽ thì không nhận được — chấp nhận có ý thức.

Spec: docs/superpowers/specs/2026-09-24-doc-sach-scan-design.md (E5, E6).
"""
import re

NGUONG_MUC = 50          # mực = tối hơn trung vị (nền giấy) ngần này mức xám
CAO_HAT = 25.0           # nét cao từ ngần này point là hạt nhân hình
GOP_HAT = 20.0           # hạt nhân cách nhau ngần này thì cùng một hình
SAT = 12.0               # vùng nuốt thành phần mực trong ngần này point
MEP_NGANG = 0.04         # hạt nhân trong dải mép này là bóng gáy sách
MEP_DOC = 0.03
MEP_NUOT = 0.02          # không nuốt thành phần chạm dải mép này
TI_LE_TRONG = 0.5        # dòng có ngần này diện tích trong vùng là của hình
VAN_XUOI_GIU = 40        # văn xuôi dài ngần này ký tự luôn giữ

# Cho phép ký hiệu trước "Figure": OCR hay đọc vạch lề trái thành "| " hay
# "© " (review 8B: dòng đầu một chú thích mất vì regex neo đầu dòng trượt).
_CHU_THICH = re.compile(r"^[^\w]*(Figure|Fig\.)\s+\d+", re.IGNORECASE)
# Dòng liền trên/dưới một dòng văn xuôi, cùng lề trái trong ngần này point,
# là dòng của cùng đoạn — dù nó ngắn (dòng cuối 2 từ) hay lẫn ký hiệu.
LECH_LE_DOAN = 4.0


def thanh_phan(xam: bytes, rong: int, cao: int, ti_le: float) -> list:
    """Khung (point) của mọi thành phần mực liên thông 4 hướng.

    `ti_le` là số point trên một pixel. Ngưỡng mực tính theo trung vị độ xám
    (nền giấy) chứ không cố định: giấy ố mỗi trang một màu.
    """
    n = rong * cao
    mau = sorted(xam[::7])
    nguong = mau[len(mau) // 2] - NGUONG_MUC
    da_xet = bytearray(n)
    out = []
    for i in range(n):
        if xam[i] >= nguong or da_xet[i]:
            continue
        ngan = [i]
        da_xet[i] = 1
        x0 = x1 = i % rong
        y0 = y1 = i // rong
        while ngan:
            j = ngan.pop()
            x, y = j % rong, j // rong
            if x < x0: x0 = x
            if x > x1: x1 = x
            if y < y0: y0 = y
            if y > y1: y1 = y
            for k in (j - 1, j + 1, j - rong, j + rong):
                if 0 <= k < n and not da_xet[k] and xam[k] < nguong \
                        and abs(k % rong - x) <= 1:
                    da_xet[k] = 1
                    ngan.append(k)
        out.append((x0 * ti_le, y0 * ti_le, (x1 + 1) * ti_le, (y1 + 1) * ti_le))
    return out


def la_chu_thich(text: str) -> bool:
    return bool(_CHU_THICH.match(text))


def la_van_xuoi(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    tu = [w for w in t.split() if sum(c.isalpha() for c in w) >= 2]
    chu = sum(c.isalpha() or c == " " for c in t) / len(t)
    return chu >= 0.8 and (len(t) >= 25 or len(tu) >= 3)


def _gan(a, b, d) -> bool:
    return (a[0] - d <= b[2] and b[0] - d <= a[2]
            and a[1] - d <= b[3] and b[1] - d <= a[3])


def _hop(a, b) -> tuple:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _trong(l, r) -> float:
    """Tỉ lệ diện tích khung l nằm trong khung r."""
    x0, y0 = max(l[0], r[0]), max(l[1], r[1])
    x1, y1 = min(l[2], r[2]), min(l[3], r[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0) / max(1e-6, (l[2] - l[0]) * (l[3] - l[1]))


def dong_bao_ve(dong: list) -> list:
    """Khung các dòng vùng hình không được nuốt: văn xuôi, chú thích, và các
    dòng tiếp của chú thích (dòng cuối chú thích thường ngắn, không đủ dài để
    là 'văn xuôi' — đo thật: thiếu luật này là 13 chú thích lọt vào vùng)."""
    bao_ve = [k for k, t in dong if la_van_xuoi(t) or la_chu_thich(t)]
    # Dòng tiếp của đoạn văn xuôi (review 8B: dòng cuối đoạn 2 từ và dòng lẫn
    # ký hiệu chiêm tinh bị vùng hình nuốt, câu mất đuôi). Chỉ một bước từ
    # dòng văn xuôi thật, không lan tiếp — lan tiếp là kéo cả nhãn hình vào.
    van_xuoi = [k for k, t in dong if la_van_xuoi(t)]
    for k, _ in dong:
        if k in bao_ve:
            continue
        for v in van_xuoi:
            cao = v[3] - v[1]
            if abs(k[0] - v[0]) <= LECH_LE_DOAN and (
                    -2 <= k[1] - v[3] <= 0.8 * cao
                    or -2 <= v[1] - k[3] <= 0.8 * cao):
                bao_ve.append(k)
                break
    chu_thich = [k for k, t in dong if la_chu_thich(t)]
    doi = True
    while doi:
        doi = False
        for k, _ in dong:
            if k in chu_thich:
                continue
            if any(0 <= k[1] - c[3] <= 0.8 * (c[3] - c[1])
                   and k[0] < c[2] and c[0] < k[2] for c in chu_thich):
                chu_thich.append(k)
                if k not in bao_ve:
                    bao_ve.append(k)
                doi = True
    return bao_ve


def tim_vung(tp: list, dong: list, rong_trang: float, cao_trang: float) -> list:
    """Vùng hình trên một trang: list khung (x0, y0, x1, y1) theo point.

    `tp` là kết quả thanh_phan; `dong` là list (khung, chữ) của dòng OCR.
    """
    bao_ve = dong_bao_ve(dong)
    hat = [c for c in tp
           if c[3] - c[1] >= CAO_HAT
           and c[0] > MEP_NGANG * rong_trang and c[2] < (1 - MEP_NGANG) * rong_trang
           and c[1] > MEP_DOC * cao_trang and c[3] < (1 - MEP_DOC) * cao_trang]
    vung = []
    for c in hat:
        for i, v in enumerate(vung):
            if _gan(v, c, GOP_HAT):
                vung[i] = _hop(v, c)
                break
        else:
            vung.append(c)

    def duoc_nuot(c) -> bool:
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        if any(l[0] <= cx <= l[2] and l[1] <= cy <= l[3] for l in bao_ve):
            return False
        return (c[0] >= MEP_NUOT * rong_trang
                and c[2] <= (1 - MEP_NUOT) * rong_trang)

    doi = True
    while doi:
        doi = False
        for i in range(len(vung)):
            for c in tp:
                v = vung[i]
                if c[0] >= v[0] and c[1] >= v[1] and c[2] <= v[2] and c[3] <= v[3]:
                    continue
                if _gan(v, c, SAT) and duoc_nuot(c):
                    vung[i] = _hop(v, c)
                    doi = True

    # Hai hạt nhân xa nhau cùng nuốt một ký hiệu thì nở ra trùm lên nhau. Đo
    # thật: 31 trang có vùng trùng lặp (một trang 4 vùng giống hệt) — ô "ảnh"
    # bị vẽ lặp và xếp chồng dọc làm trang tràn. Gộp vùng chạm nhau lại.
    gop = True
    while gop:
        gop = False
        for i in range(len(vung)):
            for j in range(i + 1, len(vung)):
                if _gan(vung[i], vung[j], 0):
                    vung[i] = _hop(vung[i], vung.pop(j))
                    gop = True
                    break
            if gop:
                break

    # Cắt mép tại dòng được bảo vệ chạm vùng: một nét hình chồng lên dòng chú
    # thích ngay dưới hình kéo mép vùng xuống quá dòng đó.
    ra = []
    for x0, y0, x1, y1 in vung:
        for l in bao_ve:
            if l[0] >= x1 or l[2] <= x0 or _trong(l, (x0, y0, x1, y1)) <= 0:
                continue
            if (l[1] + l[3]) / 2 > (y0 + y1) / 2:
                y1 = min(y1, l[1] - 0.5)
            else:
                y0 = max(y0, l[3] + 0.5)
        if y1 - y0 >= CAO_HAT:
            ra.append((x0, y0, x1, y1))
    return ra


def loc_dong_trong_hinh(dong: list, vung: list) -> list:
    """True = giữ dòng. Dòng nằm phần lớn trong vùng hình là rác OCR của hình,
    trừ chú thích và văn xuôi dài (luôn giữ)."""
    giu = []
    for k, t in dong:
        trong = max((_trong(k, v) for v in vung), default=0.0)
        if trong < TI_LE_TRONG:
            giu.append(True)
        else:
            giu.append(la_chu_thich(t)
                       or (la_van_xuoi(t) and len(t.strip()) >= VAN_XUOI_GIU))
    return giu
