"""Excel-safe clipboard helpers (spec-06 §6, stage-7 supplement).

put_excel_clipboard writes rows in two flavours at once:
- text/html: a table whose cells carry mso-number-format:\\@ so Excel pastes
  the 18-digit 身份证号 as TEXT, never scientific notation / lost digits.
- text/plain: tab-separated fallback (Notepad/WeChat), id quoted.

Shared by the table's copy buttons and the in-editor Ctrl+C handler.
"""
import html as _html

from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication


def put_excel_clipboard(rows: list[list[str]]) -> None:
    """Put rows on the clipboard; each row is a list of cell strings."""
    plain_lines = []
    for i, row in enumerate(rows):
        cells = [f'"{v}"' if i and c == 3 and v else v
                 for c, v in enumerate(row)]
        plain_lines.append("\t".join(cells))
    html_rows = "\n".join(
        "<tr>" + "".join(
            f'<td style="mso-number-format:\\@">{_html.escape(str(v))}</td>'
            for v in row
        ) + "</tr>"
        for row in rows
    )
    mime = QMimeData()
    mime.setText("\n".join(plain_lines))
    mime.setHtml(f"<table>{html_rows}</table>")
    QApplication.clipboard().setMimeData(mime)
