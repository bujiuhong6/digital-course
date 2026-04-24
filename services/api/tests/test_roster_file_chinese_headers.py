"""名单文件：中文表头（学号、姓名）与 xlsx 解析。"""

from __future__ import annotations

import io

import pytest

from app.routers.admin import _load_rows_from_file


def test_load_csv_chinese_headers() -> None:
    text = "学号,姓名\nA001,张三\nA002,李四\n"
    rows = _load_rows_from_file(text.encode("utf-8-sig"), "list.csv")
    assert rows == [("A001", "张三"), ("A002", "李四")]


def test_load_xlsx_chinese_headers() -> None:
    pytest.importorskip("openpyxl")
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["学号", "姓名"])
    ws.append(["B001", "王五"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    rows = _load_rows_from_file(buf.getvalue(), "r.xlsx")
    assert rows == [("B001", "王五")]
