"""Chọn và nhúng bộ font có đủ dấu tiếng Việt.

Chỗ duy nhất trong dự án biết đường dẫn file font.

Đây là chỗ hỏng thì hỏng toàn bộ: font Latin thiếu dấu không báo lỗi gì, nó chỉ
vẽ ô vuông, và người dùng phát hiện sau khi đã dịch xong cả cuốn. Nên module
này thà dừng hẳn còn hơn lùi về một font "gần đúng".

Đo thật: toàn bộ font dựng sẵn của PyMuPDF (helv, tiro, cour) thiếu 17/25 ký tự
tiếng Việt có dấu. Máy thử nghiệm không có font giấy phép mở nào đủ dấu, nên
mặc định trỏ vào font hệ thống macOS và đường dẫn phải cấu hình được.
"""
import os
from dataclasses import dataclass

import pymupdf

# Những chữ mà font Latin hay thiếu nhất: nguyên âm có hai dấu, và chữ Đ.
KY_TU_THU = "ặữổỹằẵợựỡẫĐđỨƯờáàảãạêôơưêế"

# Biến môi trường để trỏ font khác: ba đường dẫn, ngăn bằng dấu hai chấm.
BIEN_MOI_TRUONG = "BOOKTRANS_FONT"

_MAC = "/System/Library/Fonts/Supplemental/"
UU_TIEN_MAC_DINH = [
    (_MAC + "Times New Roman.ttf", _MAC + "Times New Roman Bold.ttf",
     _MAC + "Times New Roman Italic.ttf"),
    (_MAC + "Georgia.ttf", _MAC + "Georgia Bold.ttf", _MAC + "Georgia Italic.ttf"),
    (_MAC + "Arial Unicode.ttf",) * 3,
]
# Windows: Times New Roman / Arial có sẵn, đủ dấu tiếng Việt.
_WIN = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts") + os.sep
UU_TIEN_MAC_DINH += [
    (_WIN + "times.ttf", _WIN + "timesbd.ttf", _WIN + "timesi.ttf"),
    (_WIN + "arial.ttf", _WIN + "arialbd.ttf", _WIN + "ariali.ttf"),
]
# Linux: DejaVu / Liberation là gói font phổ biến nhất của các bản phân phối.
_DJV = "/usr/share/fonts/truetype/dejavu/"
_LIB = "/usr/share/fonts/truetype/liberation/"
UU_TIEN_MAC_DINH += [
    (_DJV + "DejaVuSerif.ttf", _DJV + "DejaVuSerif-Bold.ttf",
     _DJV + "DejaVuSerif-Italic.ttf"),
    (_LIB + "LiberationSerif-Regular.ttf", _LIB + "LiberationSerif-Bold.ttf",
     _LIB + "LiberationSerif-Italic.ttf"),
]


class ThieuFont(Exception):
    """Không có font dùng được. Thông điệp dành cho người dùng cuối."""


@dataclass
class BoFont:
    ten: str
    thuong: str
    dam: str
    nghieng: str


def thieu_glyph(duong_dan) -> list:
    """Những ký tự trong KY_TU_THU mà font này KHÔNG vẽ được."""
    try:
        f = pymupdf.Font(fontfile=str(duong_dan))
    except Exception as e:
        raise ThieuFont(
            f"{os.path.basename(str(duong_dan))} không đọc được như một file "
            f"font: {e}"
        ) from e
    # has_glyph trả về MÃ glyph; thiếu thì là 0. Đừng so với False — `0 is False`
    # là False trong Python, và phép thử sẽ im lặng bỏ sót mọi ký tự thiếu.
    return [c for c in KY_TU_THU if not f.has_glyph(ord(c))]


def _tu_moi_truong(gia_tri=None, ngan=None):
    """Bộ font người dùng đặt qua biến môi trường. Dấu tách theo hệ điều hành
    (os.pathsep): ':' trên macOS/Linux, ';' trên Windows — tách bằng ':' thì
    'C:\\...' bị cắt ngay sau ổ đĩa."""
    if gia_tri is None:
        gia_tri = os.environ.get(BIEN_MOI_TRUONG)
    if ngan is None:
        ngan = os.pathsep
    if not gia_tri:
        return []
    phan = [p for p in gia_tri.split(ngan) if p]
    if len(phan) == 1:
        phan = phan * 3
    if len(phan) != 3:
        raise ThieuFont(
            f"{BIEN_MOI_TRUONG} phải là 1 hoặc 3 đường dẫn ngăn bằng '{ngan}' "
            f"(thường{ngan}đậm{ngan}nghiêng), đang có {len(phan)}."
        )
    return [tuple(phan)]


def chon_bo_font(uu_tien=None) -> BoFont:
    """Bộ font đầu tiên vừa tồn tại vừa đủ dấu. Không có thì ném ThieuFont.

    Nếu người dùng đã nêu rõ font qua biến môi trường thì CHỈ thử font đó.
    Lặng lẽ lùi về font hệ thống khi font họ chọn hỏng là biến lời hứa "từ
    chối font thiếu dấu" thành lời nói dối — họ tưởng đang dùng font mình
    chọn, và không có thông báo nào cho biết là không.
    """
    if uu_tien is not None:
        danh_sach = list(uu_tien)
    else:
        danh_sach = _tu_moi_truong() or UU_TIEN_MAC_DINH

    thieu_duong, thieu_dau = [], []
    for bo in danh_sach:
        thuong, dam, nghieng = (bo * 3)[:3] if len(bo) == 1 else bo
        khong_co = [p for p in (thuong, dam, nghieng) if not os.path.exists(p)]
        if khong_co:
            thieu_duong.extend(khong_co)
            continue
        # Kiểm CẢ BA mặt chữ: chỉ kiểm mặt thường là để lọt cả cuốn in đậm
        # bằng ô vuông.
        thieu = next(((d, t) for d in (thuong, dam, nghieng)
                      for t in [thieu_glyph(d)] if t), None)
        if thieu:
            thieu_dau.append(thieu)
            continue
        return BoFont(ten=os.path.basename(thuong), thuong=thuong,
                      dam=dam, nghieng=nghieng)

    if thieu_dau:
        duong, thieu = thieu_dau[0]
        raise ThieuFont(
            f"font {os.path.basename(duong)} thiếu {len(thieu)} ký tự tiếng "
            f"Việt ({''.join(thieu[:8])}...). Dùng font khác qua biến môi "
            f"trường {BIEN_MOI_TRUONG}."
        )
    raise ThieuFont(
        f"không thấy file font nào: {', '.join(thieu_duong[:3])}. "
        f"Trỏ font khác qua biến môi trường {BIEN_MOI_TRUONG}."
    )


def dung_archive(bo: BoFont) -> "pymupdf.Archive":
    kho = pymupdf.Archive()
    kho.add(bo.thuong, "r.ttf")
    kho.add(bo.dam, "b.ttf")
    kho.add(bo.nghieng, "i.ttf")
    return kho


def dung_css(size: float, line_height: float = 1.0) -> str:
    """CSS cho insert_htmlbox.

    PHẢI khai font-size. Mặc định của insert_htmlbox là 12pt trong khi thân bài
    sách mẫu là 10pt; bỏ qua chỗ này là mọi phép đo tràn khung phồng lên 20%.
    """
    return (
        "@font-face{font-family:viet;src:url(r.ttf);}"
        "@font-face{font-family:viet;src:url(b.ttf);font-weight:bold;}"
        "@font-face{font-family:viet;src:url(i.ttf);font-style:italic;}"
        "*{font-family:viet;"
        f"font-size:{size:.2f}px;"
        f"line-height:{line_height};"
        "margin:0;padding:0;}"
    )
