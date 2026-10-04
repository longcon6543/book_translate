"""Chọn tầng ghi ra theo định dạng nguồn."""


class UnsupportedTarget(Exception):
    """Định dạng đầu ra chưa làm. Thông điệp dành cho người dùng cuối."""


def default_output_name(fmt: str, bilingual: bool) -> str:
    suffix = "bilingual" if bilingual else "vi"
    return f"output.{suffix}.{fmt}"


def write(fmt: str, project, con, out_path, *, bilingual: bool = False,
          mode=None, pages=None, dry_run: bool = False, probe: bool = False):
    """`mode=None` nghĩa là tự suy ra theo định dạng.

    Phải phân biệt được với việc người dùng NÊU RÕ một chế độ PDF cho project
    EPUB — đó mới là chỗ cần từ chối, vì cả overlay lẫn reflow đều đặt chữ
    theo toạ độ trang.
    """
    if mode is not None and mode not in ("overlay", "reflow"):
        raise UnsupportedTarget(f"chế độ '{mode}' không có. Chọn overlay hoặc reflow.")

    if fmt == "epub":
        if mode is not None:
            raise UnsupportedTarget(
                f"EPUB không có toạ độ trang nên không dùng được chế độ {mode}."
            )
        if pages or dry_run or probe:
            raise UnsupportedTarget(
                "EPUB không có toạ độ trang nên không dùng được --pages, "
                "--dry-run hay --probe."
            )
        from render import epub as adapter
        adapter.write(project, con, out_path, bilingual=bilingual)
        return None

    if fmt == "pdf":
        if mode == "reflow":
            from render import pdf_reflow as adapter
        else:
            from render import pdf_overlay as adapter
        return adapter.write(project, con, out_path, pages=pages,
                             dry_run=dry_run, probe=probe)

    raise UnsupportedTarget(f"chưa ghi ra được định dạng '{fmt}'.")
