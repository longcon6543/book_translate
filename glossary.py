"""Thuật ngữ: trích ứng viên từ bản gốc, và đọc bảng người dùng đã khai.

Hàm thuần — không DB, không mạng, không đụng đĩa trừ hai hàm đọc/ghi file.

`translator.py` đọc glossary để dựng prompt, và `check_translation` đọc nó để
kiểm bản dịch. Hai chỗ dùng chung một cách đọc thì cách đọc đó phải nằm riêng.
"""
import collections
import re
from pathlib import Path

# Từ chức năng tiếng Anh: viết hoa vì đứng đầu câu, không phải vì là tên riêng.
# Đo thật trên sách mẫu: 29/200 ứng viên đầu bảng thuộc loại này.
TU_CHUC_NANG = frozenset("""
the this that these those there then thus they their them and but for from with
which when where while what who whom whose however therefore because since
although though after before during until unless about above below between each
every some many most much more less other another such same both either neither
all any one two three four five six seven eight nine ten first second third his
her its our your not nor only very also just even still yet once upon under over
into onto through without within toward towards against among along around behind
beyond if it is as at by be been being are was were has have had can could should
would may might must shall will do does did done say says said see seen look
looks new old now here how why than too own per via
""".split())

# Ứng viên phải dài hơn ngần này để không vơ phải viết tắt và chữ cái đầu mục.
DAI_TOI_THIEU = 3
# Từ có hơn ngần này phần số lần xuất hiện nằm ở đầu câu thì chỉ viết hoa vì
# vị trí, không phải vì là tên riêng. Đo thật: 31/200 ứng viên đầu bảng.
TI_LE_DAU_CAU = 0.9

_THE = re.compile(r"<[^>]+>")
_TU_HOA = re.compile(r"\b[A-Z][a-zA-Z'-]{%d,}\b" % (DAI_TOI_THIEU - 1))
_KET_CAU = ".!?"


def ung_vien(doan, top: int = 200) -> list:
    """[(từ, số lần)] xếp theo tần suất giảm dần, đã lọc nhiễu.

    Mặc định 200: đo thật trên sách mẫu, sau khi lọc thì ứng viên thứ 200 vẫn
    xuất hiện 45 lần trong 900 trang — vẫn là thuật ngữ đáng khai. Lấy sâu hơn
    (>=20 lần là 568 từ) thì quá nhiều để duyệt bằng mắt.
    """
    dem = collections.Counter()
    dau_cau = collections.Counter()

    for h in doan:
        t = _THE.sub("", h)
        for m in _TU_HOA.finditer(t):
            tu = m.group()
            dem[tu] += 1
            truoc = t[:m.start()].rstrip()
            if not truoc or truoc[-1] in _KET_CAU:
                dau_cau[tu] += 1

    sach = [(tu, n) for tu, n in dem.items()
            if tu.lower() not in TU_CHUC_NANG
            and dau_cau[tu] / n <= TI_LE_DAU_CAU]
    sach.sort(key=lambda x: (-x[1], x[0]))
    return sach[:top]


def doc_bang(nguon) -> dict:
    """`glossary.txt` -> {tiếng Anh: bản dịch}.

    Mỗi dòng `term = bản dịch`; dòng bắt đầu bằng # là chú thích. Dòng hỏng bị
    bỏ qua lặng lẽ — file này người dùng gõ tay, một dòng sai không được làm
    hỏng cả lần dịch.
    """
    if hasattr(nguon, "read"):
        dong = nguon.read().splitlines()
    else:
        duong = Path(nguon)
        if not duong.exists():
            return {}
        dong = duong.read_text(encoding="utf-8").splitlines()

    bang = {}
    for raw in dong:
        raw = raw.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        en, vi = (s.strip() for s in raw.split("=", 1))
        if en and vi:
            bang[en] = vi
    return bang


def ghi_ung_vien(duong_dan, ds: list) -> None:
    """Ghi file ứng viên để người dùng duyệt rồi dán vào glossary.txt.

    Mọi dòng đều là chú thích: dán nguyên file vào glossary.txt cũng không
    khai nhầm gì — người dùng phải tự bỏ dấu # của dòng nào họ muốn giữ.
    """
    dong = [
        "# Ứng viên thuật ngữ, xếp theo số lần xuất hiện.",
        "# Bỏ dấu # ở đầu dòng nào bạn muốn khai, rồi điền bản dịch sau dấu =",
        "# rồi dán sang glossary.txt.",
        "",
    ]
    dong += [f"# {tu} =            # {n} lần" for tu, n in ds]
    Path(duong_dan).write_text("\n".join(dong) + "\n", encoding="utf-8")
