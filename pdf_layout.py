"""Dựng lại đoạn văn từ mảnh chữ rời của PDF.

Toàn bộ file này là hàm thuần trên cấu trúc dữ liệu: không import PyMuPDF,
không đụng đĩa, không đụng mạng. Nhờ vậy test chạy trong mili giây và Phase 4
(đè chữ lên trang) dùng lại được để tính chỗ đặt chữ.

Đơn vị toạ độ là point, gốc ở góc trên trái, y tăng xuống dưới.
"""
import html as _html
import math
import re
from dataclasses import dataclass

# Vùng thân bài: phần trang nằm giữa header và footer. Tỉ lệ đo thật trên
# ebook/astrology.pdf.pdf (khổ 666pt, header y~28, footer y~627) rồi quy về
# PHẦN TRĂM chiều cao trang — để tuyệt đối theo point thì trên khổ A4 (842pt)
# nó tuyên bố 227pt cuối trang là lề và xoá mất chữ thân bài thật.
CHIEU_CAO_MAU = 666.0
TI_LE_LE_TREN = 40.0 / CHIEU_CAO_MAU
TI_LE_LE_DUOI = 615.0 / CHIEU_CAO_MAU


def vung_than_bai(page_height: float = CHIEU_CAO_MAU) -> tuple:
    """(y trên, y dưới) của vùng thân bài cho một trang cao `page_height`."""
    return (page_height * TI_LE_LE_TREN, page_height * TI_LE_LE_DUOI)


VUNG_THAN_BAI = vung_than_bai()        # giữ tên cũ cho code đang dùng

# Hai dòng lệch nhau dưới ngần này point thì coi như cùng một dòng.
NGUONG_CUNG_DONG = 3.0


@dataclass
class Line:
    page_no: int
    bbox: tuple                 # (x0, y0, x1, y1)
    html: str                   # nội dung có <b>/<i>, đã escape
    text: str                   # nội dung thuần, chưa escape
    size: float                 # cỡ chữ trội nhất của dòng
    col: int = 0                # chỉ số cột, 0 là cột trái nhất
    ket_doan: bool = False      # 8B E4: dòng cuối một mục lục/chỉ mục


def _kieu(span) -> tuple:
    """(đậm, nghiêng) suy từ tên font. Tên font đáng tin hơn cờ bit của PDF."""
    ten = (span.get("font") or "").lower()
    return ("bold" in ten, "italic" in ten or "oblique" in ten)


def merge_spans(spans: list) -> tuple:
    """Ghép các mảnh của một dòng thành (html, text, size).

    Mảnh liền nhau cùng kiểu được gộp vào chung một thẻ, để không sinh ra
    <i>Alma</i><i>gest</i> — `check_translation` đếm thẻ nên chuyện đó làm
    mọi đoạn bị gắn cờ oan.
    """
    nhom = []                                   # [(đậm, nghiêng, [chuỗi])]
    for s in spans:
        t = s.get("text", "")
        if not t:
            continue
        k = _kieu(s)
        if nhom and nhom[-1][0] == k:
            nhom[-1][1].append(t)
        else:
            nhom.append((k, [t]))

    phan_html, phan_text = [], []
    for (dam, nghieng), phan in nhom:
        raw = "".join(phan)
        phan_text.append(raw)
        esc = _html.escape(raw, quote=False)
        if not esc.strip():                     # toàn khoảng trắng: không bọc thẻ
            phan_html.append(esc)
            continue
        if nghieng:
            esc = f"<i>{esc}</i>"
        if dam:
            esc = f"<b>{esc}</b>"
        phan_html.append(esc)

    text = "".join(phan_text)
    # Cỡ chữ của dòng lấy theo mảnh CÓ NHIỀU CHỮ NHẤT, không lấy lớn nhất:
    # chữ cái đầu chương cỡ 24pt không được kéo cả dòng thành tiêu đề.
    co = [(len(s.get("text", "").strip()), s.get("size", 0.0)) for s in spans
          if s.get("text", "").strip()]
    size = max(co)[1] if co else 0.0
    return "".join(phan_html), text, size


def sort_reading_order(lines: list) -> list:
    """Sắp theo cột, rồi theo chiều dọc, rồi trái sang phải.

    Bắt buộc: PyMuPDF trả block theo thứ tự nội bộ của file, và trên sách thật
    18/18 trang mẫu có block KHÔNG theo thứ tự dọc. Tin vào thứ tự thư viện
    trả về là đảo lộn nội dung cả cuốn sách.
    """
    if not lines:
        return []

    # Làm tròn y tuyệt đối cho dung sai thật 0..3pt tuỳ dòng rơi vào đâu so với
    # bội số của 3 — một chỉ số trên cao hơn 1,5pt có thể nhảy sang hàng khác.
    # Gom theo KHOẢNG CÁCH giữa các dòng liền nhau thì dung sai đúng bằng
    # NGUONG_CUNG_DONG ở mọi vị trí.
    tam = sorted(lines, key=lambda l: (l.page_no, l.col, l.bbox[1], l.bbox[0]))
    danh, chi_so, truoc = [], 0, None
    for l in tam:
        if truoc is not None and (l.page_no != truoc.page_no
                                  or l.col != truoc.col
                                  or l.bbox[1] - truoc.bbox[1] > NGUONG_CUNG_DONG):
            chi_so += 1
        danh.append((l.page_no, l.col, chi_so, l.bbox[0], l))
        truoc = l
    danh.sort(key=lambda x: x[:4])
    return [x[4] for x in danh]


# Cần ít nhất ngần này dòng mới dám kết luận sách nhiều cột.
TOI_THIEU_DONG_DE_DOAN_COT = 6
# Khe dọc phải rộng ít nhất ngần này phần của bề ngang trang.
KHE_COT_TOI_THIEU = 0.04
# Hai cột thật thì bên nào cũng phải gánh phần đáng kể LƯỢNG CHỮ. Đo bằng số
# dòng thì trang cuối chương (cột phải ngắn) bị coi là một cột rồi trộn xen kẽ
# hai cột thành đoạn vô nghĩa; đo bằng bề rộng thì vài mục căn phải ngắn vẫn bị
# loại (chúng rộng 13pt so với 333pt của thân bài) mà cột thưa dòng vẫn qua.
CAN_BANG_COT_TOI_THIEU = 0.10


def detect_columns(lines: list, page_width: float) -> None:
    """Gán `col` cho từng dòng. Sửa tại chỗ.

    Tìm một khe dọc mà KHÔNG dòng nào bắc ngang qua. Dòng bắc ngang (tiêu đề
    chạy suốt trang) được bỏ ra khỏi phép thử và gán về cột 0, nếu không nó tự
    xoá mất cái khe mà ta đang đi tìm.
    """
    for l in lines:
        l.col = 0
    if len(lines) < TOI_THIEU_DONG_DE_DOAN_COT:
        return

    rong_tb = sum(l.bbox[2] - l.bbox[0] for l in lines) / len(lines)
    hep = [l for l in lines if l.bbox[2] - l.bbox[0] < rong_tb * 1.5]
    if len(hep) < TOI_THIEU_DONG_DE_DOAN_COT:
        return

    # Quét thử từng vị trí chia; chọn vị trí mà không dòng hẹp nào bắc qua.
    trai_nhat = min(l.bbox[0] for l in hep)
    phai_nhat = max(l.bbox[2] for l in hep)
    ung_vien = []
    buoc = page_width / 100.0
    x = trai_nhat + buoc
    while x < phai_nhat:
        if not any(l.bbox[0] < x < l.bbox[2] for l in hep):
            ung_vien.append(x)
        x += buoc

    if not ung_vien:
        return

    # Gom các vị trí liền nhau thành khe; lấy khe rộng nhất.
    khe, cur = [], [ung_vien[0]]
    for a, b in zip(ung_vien, ung_vien[1:]):
        if b - a <= buoc * 1.5:
            cur.append(b)
        else:
            khe.append(cur)
            cur = [b]
    khe.append(cur)
    rong_nhat = max(khe, key=lambda k: k[-1] - k[0])
    if rong_nhat[-1] - rong_nhat[0] < page_width * KHE_COT_TOI_THIEU:
        return

    moc = (rong_nhat[0] + rong_nhat[-1]) / 2

    rong_trai = sum(l.bbox[2] - l.bbox[0] for l in hep if l.bbox[0] < moc)
    rong_phai = sum(l.bbox[2] - l.bbox[0] for l in hep if l.bbox[0] >= moc)
    tong = rong_trai + rong_phai
    if tong <= 0 or min(rong_trai, rong_phai) < tong * CAN_BANG_COT_TOI_THIEU:
        return                             # một bên quá ít chữ: không phải hai cột

    for l in lines:
        if l.bbox[2] - l.bbox[0] >= rong_tb * 1.5:
            l.col = 0                      # dòng vắt ngang: coi như cột đầu
        else:
            l.col = 1 if l.bbox[0] >= moc else 0


# Phase 8B E2: dò hai cột trên trang scan bằng bằng chứng từng hàng.
TOI_THIEU_DONG_HAI_COT = 12
LECH_HANG = 3.0
TI_LE_HANG_TACH = 0.6
VUNG_KHE = (0.3, 0.7)
BAC_QUA_TOI_DA = 2
TI_LE_BAC_QUA = 0.05


def _gom_hang(lines: list) -> list:
    hang = []
    for l in sorted(lines, key=lambda l: l.bbox[1]):
        if hang and abs(l.bbox[1] - hang[-1][0].bbox[1]) <= LECH_HANG:
            hang[-1].append(l)
        else:
            hang.append([l])
    return hang


def tim_khe_hai_cot(lines: list, page_width: float,
                    page_height: float = CHIEU_CAO_MAU) -> "float | None":
    """x của khe giữa hai cột, hoặc None. Chỉ dùng cho trang sách scan.

    detect_columns đòi khe mà KHÔNG dòng hẹp nào bắc qua; OCR chỉ mục để 1-2
    mảnh lấn khe nên cả trang thành một cột, rồi ghép mảnh nối mục cột trái
    với mục cột phải. Nới luật đó thì trang hình (mảnh rác giả làm cột) và
    trang Ghi chú một cột bị chia sai — đo thật: 10 trang. Bằng chứng đúng
    của hai cột là HÀNG: phần lớn hàng có chữ ở cả hai bên khe. Đo thật: 14/14
    trang chỉ mục; ngoài chỉ mục chỉ còn các bảng in nhiều cột.
    """
    tren, duoi = vung_than_bai(page_height)
    than = [l for l in lines if tren <= l.bbox[1] <= duoi]
    if len(than) < TOI_THIEU_DONG_HAI_COT:
        return None
    hang = _gom_hang(than)
    cho_phep = max(BAC_QUA_TOI_DA, math.ceil(TI_LE_BAC_QUA * len(than)))
    trai, phai = VUNG_KHE[0] * page_width, VUNG_KHE[1] * page_width

    tot = None
    for x in sorted({l.bbox[2] + 0.5 for l in than}):
        if not trai <= x <= phai:
            continue
        if sum(1 for l in than if l.bbox[0] < x < l.bbox[2]) > cho_phep:
            continue
        tach = sum(1 for h in hang
                   if any(l.bbox[2] <= x for l in h)
                   and any(l.bbox[0] >= x for l in h)
                   and not any(l.bbox[0] < x < l.bbox[2] for l in h))
        if tot is None or tach > tot[0]:
            tot = (tach, x)
    if tot is None or tot[0] < TI_LE_HANG_TACH * len(hang):
        return None
    return tot[1]


# Dòng sau thụt vào hơn dòng trước ngần này point thì coi là mở đoạn mới.
NGUONG_THUT_DAU_DONG = 6.0
# Khoảng cách dọc lớn hơn giãn dòng thường nhân hệ số này thì tách đoạn.
HE_SO_TACH_DOAN = 1.6

_GACH_NOI_CUOI = re.compile(r"([a-zà-ỹ])-$", re.IGNORECASE)
# Gạch nối cuối chuỗi HTML, có thể nằm trước một loạt thẻ đóng: "<i>as-</i>".
_GACH_NOI_HTML = re.compile(r"-(\s*(?:</[a-zA-Z]+>)*)$")


@dataclass
class Para:
    page_no: int
    lines: list
    html: str
    text: str
    size: float
    bbox: tuple
    kind: str = "text"
    cont_group: int = None


def _giãn_dòng_thường(lines: list) -> float:
    """Trung vị khoảng cách dọc giữa các dòng liền nhau trong cùng trang."""
    khoang = [b.bbox[1] - a.bbox[1]
              for a, b in zip(lines, lines[1:])
              if b.page_no == a.page_no and 0 < b.bbox[1] - a.bbox[1] < 60]
    if not khoang:
        return 12.0
    khoang.sort()
    return khoang[len(khoang) // 2]


def _nối(truoc: str, sau: str) -> tuple:
    """Nối hai dòng. Trả về (chuỗi đã nối, chế độ nối).

    BA trường hợp, không phải hai:
      "nuot" — gạch nối do xếp chữ: bỏ gạch, ghép liền ("as-" + "trology").
      "dinh" — gạch nối của từ ghép thật: GIỮ gạch, vẫn ghép liền, không thêm
               dấu cách ("Anh-" + "Viet" -> "Anh-Viet", không phải "Anh- Viet").
      "cach" — dòng thường: ghép bằng một dấu cách.

    Phân biệt "nuot" với "dinh" bằng chữ đầu của dòng sau: từ bị xếp chữ cắt
    đôi thì phần sau viết thường, còn từ ghép thật thường có vế sau viết hoa.
    """
    if _GACH_NOI_CUOI.search(truoc):
        if sau[:1].islower():
            return truoc[:-1] + sau, "nuot"
        return truoc + sau, "dinh"
    return truoc + " " + sau, "cach"


def _nối_html(truoc: str, sau: str, che_do: str) -> str:
    """Nối phần HTML theo cùng chế độ mà `_nối` đã chọn cho phần chữ.

    Khi nuốt gạch nối phải bỏ đúng dấu gạch chứ không phải ký tự cuối chuỗi:
    dấu gạch có thể nằm trước một loạt thẻ đóng, như "<i>as-</i>".
    """
    if che_do == "nuot":
        return _GACH_NOI_HTML.sub(r"\1", truoc) + sau
    if che_do == "dinh":
        return truoc + sau
    return truoc + " " + sau


# Ghép mảnh cùng hàng — chỉ dùng cho trang sách scan (ingest/pdf_text.py quyết).
# Đo thật trên sách scan: ngưỡng 2,0x bắt 1.037/1.292 chỗ cùng hàng và 227/280
# chỗ cắt ngang câu; quá 2x thì lẫn ô bảng, chú thích nằm cạnh nhau. Không áp
# cho text-PDF: ở đó chỗ cùng hàng có khe ~3x và là ô bảng, cột mục lục ĐÚNG.
NGUONG_KHE_CUNG_HANG = 2.0
TI_LE_CHONG_CUNG_HANG = 0.6


def _cung_hang(a, b) -> bool:
    chong = min(a.bbox[3], b.bbox[3]) - max(a.bbox[1], b.bbox[1])
    thap = min(a.bbox[3] - a.bbox[1], b.bbox[3] - b.bbox[1])
    return thap > 0 and chong > TI_LE_CHONG_CUNG_HANG * thap


def _ghep_hai_dong(a, b):
    # Cỡ chữ trội lấy theo mảnh nhiều chữ hơn, như merge_spans: OCR hay gán cỡ
    # chữ thổi lên cho mảnh ngắn, lấy max là thổi theo cả dòng.
    chinh = a if len(a.text) >= len(b.text) else b
    return Line(page_no=a.page_no,
                bbox=(min(a.bbox[0], b.bbox[0]), min(a.bbox[1], b.bbox[1]),
                      max(a.bbox[2], b.bbox[2]), max(a.bbox[3], b.bbox[3])),
                html=a.html.rstrip() + " " + b.html.lstrip(),
                text=a.text.rstrip() + " " + b.text.lstrip(),
                size=chinh.size, col=a.col)


def tach_theo_vung(lines: list, page_height: float = CHIEU_CAO_MAU) -> tuple:
    """(lề trên, thân bài, lề dưới), cùng luật lề với mark_running, giữ thứ tự.

    Chỉ dùng cho trang sách scan. group_paragraphs không biết lề: dòng tiêu đề
    chạy và dòng thân bài ngay dưới cùng lề trái thì bị gộp thành MỘT đoạn.
    mark_running quyết định loại hay giữ CẢ đoạn theo vị trí dòng đầu, nên đoạn
    gộp đó ngắn và bắt đầu ở lề thì bị gắn skip — chữ thân bài mất theo. Đo
    thật trên sách scan: một tên chương trong mục lục, dữ liệu một lá số; và
    code cũ đã sẵn làm mất một đoạn trích dẫn theo đúng cách này. Gom đoạn
    riêng từng vùng thì đoạn ở lề chỉ còn chữ ở lề.
    """
    tren, duoi = vung_than_bai(page_height)
    return ([l for l in lines if l.bbox[1] < tren],
            [l for l in lines if tren <= l.bbox[1] <= duoi],
            [l for l in lines if l.bbox[1] > duoi])


def ghep_manh_cung_hang(lines: list, page_height: float = CHIEU_CAO_MAU,
                        khe_toi_da: float = NGUONG_KHE_CUNG_HANG) -> list:
    """Ghép các mảnh chữ OCR nằm cùng một hàng thành một dòng.

    OCR cắt một hàng chữ thành hai mảnh. group_paragraphs thấy mảnh đuôi nằm xa
    về bên phải, tưởng là dòng thụt đầu đoạn, nên đẩy nó sang đoạn SAU: đoạn
    trước mất vài chữ cuối, đoạn sau mở đầu bằng chữ lạc, và model dịch một câu
    cụt. Ghép lại trước khi gom đoạn thì chữ về đúng đoạn.

    Hai dòng liền nhau (theo thứ tự đọc) được ghép khi: cùng trang, cùng cột,
    cùng hàng, dòng sau nằm bên phải dòng trước, và khe ngang không quá
    `khe_toi_da` lần cỡ chữ dòng trước. Trả về list Line mới; không sửa đầu vào.

    KHÔNG ghép ở lề trên và lề dưới — cùng luật lề với mark_running. Lề chỉ
    chứa tiêu đề chạy, chân trang, số trang, và mark_running cần chúng còn
    nguyên mảnh ngắn để nhận ra chúng lặp lại. Đo thật trên sách scan: ghép
    cả ở lề làm tiêu đề dính mảnh rác OCR khác nhau từng trang, khối ở lề
    trên lọt vào DB tăng từ 180 lên 474.
    """
    tren, duoi = vung_than_bai(page_height)
    out = []
    for l in sort_reading_order(lines):
        truoc = out[-1] if out else None
        if (truoc is not None
                and l.page_no == truoc.page_no and l.col == truoc.col
                and tren <= truoc.bbox[1] <= duoi and tren <= l.bbox[1] <= duoi
                and _cung_hang(truoc, l)
                and l.bbox[0] >= truoc.bbox[2] - 2
                and l.bbox[0] - truoc.bbox[2] <= khe_toi_da * truoc.size):
            out[-1] = _ghep_hai_dong(truoc, l)
        else:
            out.append(l)
    return out


# Phase 8B E3/E4: số trang của mục lục/chỉ mục nằm tách khỏi hàng chữ của nó.
_SO_TRANG = re.compile(r"^(\d{1,3}|[ivxlc]{1,6})$", re.IGNORECASE)
TOI_THIEU_HANG_MUC_LUC = 3
# Cột có QUÁ ngần này phần mảnh chỉ là số là cột số trang của mục lục. Không
# đòi 100%: OCR đọc sai vài số trang ("5a8"). Đo thật: cột số mục lục 75-88%,
# cột phải chỉ mục 0-13%.
TI_LE_COT_SO_TRANG = 0.5


def noi_so_trang(lines: list, page_height: float = CHIEU_CAO_MAU) -> list:
    """Nối mảnh chỉ có số trang vào dòng chữ cùng hàng bên trái nó.

    Chỉ dùng cho trang sách scan, SAU ghép mảnh. Đo thật: mục lục sách scan có
    21 mảnh số trang nằm tách thành cột riêng; dịch ra thì số trang lạc khỏi
    mục. Chỉ nối trong cùng cột — trừ khi phần lớn cột của mảnh số là mảnh số
    (cột số trang mục lục, TI_LE_COT_SO_TRANG). Trang có từ TOI_THIEU_HANG_MUC_LUC hàng đã nối là
    mục lục/chỉ mục: mỗi dòng đã nối là cuối một đoạn. Ít hơn thì chỉ nối —
    thân bài có số lẻ loi, tách đoạn ở đó là cắt câu. Trả về list Line mới.
    """
    tren, duoi = vung_than_bai(page_height)

    def o_than(l):
        return tren <= l.bbox[1] <= duoi

    def la_so(l):
        return bool(_SO_TRANG.match(l.text.strip()))

    cot_toan_so = set()
    for c in {l.col for l in lines}:
        cung_cot = [l for l in lines if l.col == c]
        if sum(la_so(l) for l in cung_cot) > TI_LE_COT_SO_TRANG * len(cung_cot):
            cot_toan_so.add(c)
    out = list(lines)
    da_noi = []
    for s in sorted([l for l in lines if o_than(l) and la_so(l)],
                    key=lambda l: (l.bbox[1], l.bbox[0])):
        ban = [m for m in out if m is not s and o_than(m) and not la_so(m)
               and (m.col == s.col or s.col in cot_toan_so)
               and m.bbox[2] <= s.bbox[0] + 1 and _cung_hang(m, s)]
        if not ban:
            continue
        m = max(ban, key=lambda m: m.bbox[2])
        moi = _ghep_hai_dong(m, s)
        # So theo danh tính: Line là dataclass nên == so từng trường, hai dòng
        # trùng chữ và khung (rác OCR lặp) sẽ bị index/remove nhầm.
        out = [moi if x is m else x for x in out if x is not s]
        da_noi = [x for x in da_noi if x is not m] + [moi]
    if len(da_noi) >= TOI_THIEU_HANG_MUC_LUC:
        for l in da_noi:
            l.ket_doan = True
    return out



def group_paragraphs(lines: list, gian: float = None) -> list:
    """Gom dòng liền nhau thành đoạn văn.

    Tách đoạn khi: sang trang khác, khoảng cách dọc vượt giãn dòng thường,
    hoặc dòng sau thụt vào so với dòng trước.
    """
    if not lines:
        return []

    lines = sort_reading_order(lines)
    # `gian` truyền vào khi chỉ gom MỘT PHẦN trang (gom_doan_theo_vung): giãn
    # dòng phải đo trên cả trang, không trên vài dòng của phần đó.
    if gian is None:
        gian = _giãn_dòng_thường(lines)
    nhom, cur = [], [lines[0]]

    for truoc, sau in zip(lines, lines[1:]):
        cach = sau.bbox[1] - truoc.bbox[1]
        doi_trang = sau.page_no != truoc.page_no
        xa_qua = cach > gian * HE_SO_TACH_DOAN
        thut_vao = sau.bbox[0] - truoc.bbox[0] > NGUONG_THUT_DAU_DONG
        if doi_trang or xa_qua or thut_vao or truoc.ket_doan:
            nhom.append(cur)
            cur = []
        cur.append(sau)
    nhom.append(cur)

    out = []
    for group in nhom:
        text = group[0].text
        html = group[0].html
        for l in group[1:]:
            text, che_do = _nối(text, l.text)
            html = _nối_html(html, l.html, che_do)
        out.append(Para(
            page_no=group[0].page_no,
            lines=group,
            html=html,
            text=text,
            size=max(l.size for l in group),
            bbox=(min(l.bbox[0] for l in group), min(l.bbox[1] for l in group),
                  max(l.bbox[2] for l in group), max(l.bbox[3] for l in group)),
        ))
    return out


def gom_doan_theo_vung(lines: list, page_height: float = CHIEU_CAO_MAU) -> list:
    """Gom đoạn riêng lề trên / thân bài / lề dưới, với giãn dòng của CẢ trang.

    Chỉ dùng cho trang sách scan (xem tach_theo_vung vì sao phải tách vùng).
    Giãn dòng phải đo một lần trên cả trang: review đo trên sách scan thật —
    đo riêng từng vùng thì lề trên thường chỉ có MỘT khoảng cách (rác OCR tới
    số trang), khoảng đó thành "bình thường" nên không bao giờ tách; rác dính
    số trang, thoát mark_running, và 10 số trang bị đem đi dịch.
    """
    gian = _giãn_dòng_thường(sort_reading_order(lines))
    out = []
    for vung in tach_theo_vung(lines, page_height):
        out.extend(group_paragraphs(vung, gian=gian))
    return out


# Tiêu đề: to hơn cỡ trội của trang ngần này lần, VÀ ngắn.
HE_SO_TIEU_DE = 1.15
DAI_TOI_DA_TIEU_DE = 80
# Caption: nhỏ hơn cỡ trội ngần này lần. Để 0.9 thì 9pt trên nền 10pt lọt vào
# (1147 đoạn trên sách mẫu) — mà đó là chữ thân bài cỡ nhỏ, và caption bị loại
# khỏi link_continuations nên kéo theo hỏng cả việc nối trang.
HE_SO_CAPTION = 0.85
# Bảng / công thức: tỉ lệ ký tự số hoặc ký tự toán vượt ngưỡng này.
TI_LE_SO_LA_BANG = 0.30
TI_LE_TOAN_LA_CONG_THUC = 0.08
DAI_TOI_DA_BANG = 120

# Mục từ sách tra cứu in đậm viết hoa nhưng cỡ chữ gần như không đổi (10.2 trên
# nền 10.0), nên luật chỉ-theo-cỡ bỏ sót 811 đoạn trên sách mẫu.
_BOC_DAM = re.compile(r"^<b>(.*)</b>$", re.S)
TI_LE_HOA_TIEU_DE = 0.85

_KY_TU_TOAN = set("=+\u00d7\u00f7\u00b1\u2213\u2264\u2265\u2260\u2211\u220f\u221a\u222b\u00b0\u2032\u2033")


def _la_tieu_de_dam(p) -> bool:
    """Cả đoạn nằm trong một thẻ <b>, ngắn, và gần như toàn chữ hoa."""
    if not _BOC_DAM.match((p.html or "").strip()):
        return False
    t = p.text.strip()
    if not t or len(t) > DAI_TOI_DA_TIEU_DE:
        return False
    chu = [c for c in t if c.isalpha()]
    return bool(chu) and sum(c.isupper() for c in chu) / len(chu) >= TI_LE_HOA_TIEU_DE


def _co_troi(paras: list) -> float:
    """Cỡ chữ chiếm nhiều ký tự nhất — tức cỡ của thân bài."""
    theo_co = {}
    for p in paras:
        theo_co[p.size] = theo_co.get(p.size, 0) + len(p.text)
    return max(theo_co.items(), key=lambda kv: kv[1])[0] if theo_co else 10.0


def classify(paras: list) -> None:
    """Gán `kind` cho từng đoạn. Sửa tại chỗ.

    Cỡ trội được tính RIÊNG TỪNG TRANG: một trang in toàn chữ nhỏ không được
    biến cả trang thành caption.
    """
    theo_trang = {}
    for p in paras:
        theo_trang.setdefault(p.page_no, []).append(p)

    for cung_trang in theo_trang.values():
        troi = _co_troi(cung_trang)
        for p in cung_trang:
            t = p.text.strip()
            if not t:
                p.kind = "text"
                continue

            chu_so = sum(c.isdigit() for c in t)
            toan = sum(c in _KY_TU_TOAN for c in t)

            if toan / len(t) >= TI_LE_TOAN_LA_CONG_THUC:
                p.kind = "formula"
            elif chu_so / len(t) >= TI_LE_SO_LA_BANG and len(t) <= DAI_TOI_DA_BANG:
                p.kind = "table"
            elif _la_tieu_de_dam(p):
                p.kind = "heading"
            elif p.size >= troi * HE_SO_TIEU_DE and len(t) <= DAI_TOI_DA_TIEU_DE:
                p.kind = "heading"
            elif p.size <= troi * HE_SO_CAPTION:
                p.kind = "caption"
            else:
                p.kind = "text"


# Cần ít nhất ngần này trang mới dám kết luận có header/footer.
TOI_THIEU_TRANG_DE_DO_LAP = 4
# Header/footer được xét theo CỬA SỔ trang, không theo cả cuốn: tên chương chạy
# đầu trang chỉ lặp trong phạm vi một chương. Trên sách mẫu, luật "60% cả cuốn"
# để lọt 871 đoạn header.
CUA_SO_TRANG = 10
TI_LE_TRONG_CUA_SO = 0.6
# Dưới ngần này lần lặp thì không đủ bằng chứng, dù cửa sổ có hẹp tới đâu.
TOI_THIEU_LAN_LAP = 4

# Sách tra cứu ghi mục từ của chính trang đó lên đầu trang, nên CHỮ không bao
# giờ lặp — trên sách mẫu còn sót 566 đoạn kiểu này. Dấu hiệu thật là chỗ đứng:
# cùng một khe bị chiếm trên phần lớn số trang. Chỉ an toàn vì luật này chỉ
# chạy trên các đoạn ĐÃ ngắn và ĐÃ nằm ngoài vùng thân bài.
TI_LE_TRANG_CO_KHE = 0.6
DO_CAO_KHE = 6.0
# Header/footer là chữ ngắn.
DAI_TOI_DA_LAP = 60

_CHU_SO = re.compile(r"\d+")


def _van_tay(text: str) -> str:
    """Bỏ chữ số đi: số trang đổi từng trang nhưng vẫn là cùng một footer."""
    return _CHU_SO.sub("#", text.strip().lower())


def _khe(p) -> int:
    """Khe dọc mà đoạn này chiếm, gom các y gần nhau về cùng một số."""
    return round(p.bbox[1] / DO_CAO_KHE)


def _lap_trong_cua_so(trang: set) -> bool:
    """Vân tay có lặp dày đặc trong BẤT KỲ cửa sổ CUA_SO_TRANG trang nào không?

    Tên chương chạy đầu trang lặp trên vài chục trang liền rồi đổi; đếm trên cả
    cuốn thì không bao giờ đạt ngưỡng, đếm theo cửa sổ thì đạt ngay.
    """
    ds = sorted(trang)
    if len(ds) < TOI_THIEU_LAN_LAP:
        return False
    can = max(TOI_THIEU_LAN_LAP, int(CUA_SO_TRANG * TI_LE_TRONG_CUA_SO))
    for i, dau in enumerate(ds):
        trong_cua_so = sum(1 for q in ds[i:] if q < dau + CUA_SO_TRANG)
        if trong_cua_so >= can:
            return True
    return False


def mark_running(paras: list, so_trang: int,
                 page_height: float = CHIEU_CAO_MAU) -> None:
    """Đánh dấu header/footer là `skip`. Sửa tại chỗ.

    KHÔNG dò bằng vị trí lặp lại. Sách xếp chữ theo lưới đều nên dòng thân bài
    cũng rơi đúng cùng độ cao trên hầu hết các trang — đo thật trên sách mẫu
    thấy các dòng ở y=55, 571, 583, 595 xuất hiện trên 15-18/18 trang. Dò bằng
    vị trí là xoá nhầm nội dung thật.

    Ba điều kiện cùng lúc: nội dung (sau khi bỏ chữ số) lặp trên phần lớn số
    trang, chữ ngắn, và nằm ngoài vùng thân bài.
    """
    if so_trang < TOI_THIEU_TRANG_DE_DO_LAP or not paras:
        return

    tren, duoi = vung_than_bai(page_height)
    ria = [p for p in paras
           if (p.bbox[1] < tren or p.bbox[1] > duoi) and len(p.text.strip()) <= DAI_TOI_DA_LAP]

    trang_theo_van_tay = {}
    for p in ria:
        trang_theo_van_tay.setdefault(_van_tay(p.text), set()).add(p.page_no)

    lap = {vt for vt, trang in trang_theo_van_tay.items()
           if _lap_trong_cua_so(trang)}

    # Luật thứ hai: khe bị chiếm trên phần lớn số trang, bất kể chữ có lặp không.
    trang_theo_khe = {}
    for p in ria:
        trang_theo_khe.setdefault(_khe(p), set()).add(p.page_no)
    khe_lap = {k for k, trang in trang_theo_khe.items()
               if len(trang) >= so_trang * TI_LE_TRANG_CO_KHE}

    for p in ria:
        if _van_tay(p.text) in lap or _khe(p) in khe_lap:
            p.kind = "skip"


_KET_CAU = set(".!?\u201d\u2019")        # chấm, than, hỏi, ngoặc kép/đơn đóng


def link_continuations(paras: list) -> None:
    """Nối các đoạn bị cắt ngang trang thành cùng một `cont_group`.

    Đo thật trên sách mẫu: 11/18 trang có đoạn nối sang trang sau, trong đó 2
    trang cắt ngang giữa một từ bằng gạch nối. Đây là chuyện thường, không
    phải ngoại lệ.

    Chỉ xét các đoạn `text`: tiêu đề, caption, bảng, công thức và header/footer
    không bao giờ nối. Đoạn `skip` cũng không được cắt mạch — footer nằm giữa
    hai nửa của một đoạn là chuyện bình thường.
    """
    thuc = [p for p in paras if p.kind == "text"]
    nhom_ke = 0

    for truoc, sau in zip(thuc, thuc[1:]):
        if sau.page_no <= truoc.page_no:
            continue                                  # cùng trang: không phải nối trang
        t = truoc.text.rstrip()
        s = sau.text.lstrip()
        if not t or not s:
            continue
        if t[-1] in _KET_CAU:
            continue                                  # đã kết câu: đoạn mới
        # KHÔNG xét chữ hoa đầu dòng: sách đầy danh từ riêng viết hoa (tên hành
        # tinh, cung hoàng đạo), luật đó chặn mất 795/899 cặp trang đáng nối.
        # Dấu kết câu ở dòng trước là bằng chứng đủ và đáng tin hơn.

        if truoc.cont_group is None:
            nhom_ke += 1
            truoc.cont_group = nhom_ke
        sau.cont_group = truoc.cont_group


# ---- thang tự co khi chữ Việt không vừa khung chữ Anh ----
#
# Tiếng Việt dài hơn tiếng Anh, nhưng đo thật trên 269 đoạn thân bài của sách
# mẫu (cỡ chữ khớp bản gốc) thì trung vị vẫn giữ được 98%, 91% số đoạn giữ được
# từ 85% trở lên, và đoạn tệ nhất là 74%. Thang này vì thế còn dư chỗ.
#
# Spec mục 6 có một bậc "cho tràn xuống lề nếu dưới khung là chỗ trống". Bỏ đi:
# đo thật cho thấy không đoạn nào phải xuống dưới 74% nên bậc đó không bao giờ
# được dùng, trong khi nó đòi biết khung dưới có trống không và sai thì đè lên
# đoạn kế tiếp.
DAY_THANG = 0.70

THANG_CO = (
    (1.00, 1.00),     # cỡ gốc, giãn dòng gốc
    (1.00, 0.95),     # bóp giãn dòng trước — ít gây chú ý hơn thu cỡ chữ
    (0.85, 0.95),
    (0.75, 0.95),
    (DAY_THANG, 0.95),
)


def thang_co() -> tuple:
    """Các bậc (tỉ lệ cỡ chữ tối thiểu, giãn dòng) thử lần lượt, vừa là dừng."""
    return THANG_CO


def co_chap_nhan_duoc(ti_le: float) -> bool:
    """`insert_htmlbox` trả -1 khi không vừa ở tỉ lệ đã cho."""
    return ti_le >= DAY_THANG
