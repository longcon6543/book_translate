"""Ghi lại vân tay của hành vi HIỆN TẠI.

Chạy một lần ở Task 1 để đóng băng hành vi Phase 1. Sau đó CHỈ chạy lại khi bạn
cố ý đổi đầu ra của đường EPUB — và khi đó phải giải thích được vì sao trong
thông điệp commit.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import db
from helpers import build_epub, fingerprint, run_init, seed_translations
from test_golden_epub import GOLDEN_DIR, export


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = build_epub(tmp / "short.epub")
        for bilingual, name in ((False, "epub_fingerprint.txt"),
                                (True, "epub_fingerprint_bilingual.txt")):
            proj = run_init(src, tmp / f"proj_{name}")
            seed_translations(db.connect(proj))
            (GOLDEN_DIR / name).write_text(fingerprint(export(proj, bilingual)),
                                           encoding="utf-8")
            print("đã ghi", name)


if __name__ == "__main__":
    main()
