"""Full GUI acceptance against the frozen exe (PRD §5.2).

Launch sequence (one exe process, one relaunch):
  A. window + controls present
  B. clipboard paste -> 1 recognised row
  C. copy-all -> tab-separated Excel-ready text
  D. double-click edit a cell
  E. clear (confirm) -> 0 rows; close
  F. relaunch -> no residue (0 rows)
  G. file dialog -> batch 10 images -> progress bar shown -> 10 rows

Run: .venv\\Scripts\\python.exe scripts/acceptance_all.py
"""
import io
import re
import subprocess
import sys
import time

import win32clipboard
import win32con
import win32gui
from PIL import Image

EXE = r"d:\zjy\project\project_01_jc\dist\检测识别.exe"
SAMPLE = r"d:\zjy\project\project_01_jc\assets\samples\idcard_sample.jpg"
BATCH_DIR = r"C:\Users\13689\AppData\Local\Temp\jc_acceptance\batch"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def launch():
    subprocess.run(["taskkill", "/IM", "检测识别.exe", "/F"], capture_output=True)
    time.sleep(1)
    proc = subprocess.Popen([EXE])
    time.sleep(22)
    from pywinauto import Desktop
    desktop = Desktop(backend="uia")
    win = None
    for _ in range(40):
        wins = [w for w in desktop.windows()
                if w.window_text() == "检测识别" and w.is_visible()]
        if wins:
            win = wins[0]
            break
        time.sleep(1)
    if win is None:
        raise SystemExit("main window not found")
    win.set_focus()  # the console that runs this script otherwise steals focus
    time.sleep(0.5)
    return proc, win


def close_app(proc):
    subprocess.run(["taskkill", "/IM", "检测识别.exe", "/F"], capture_output=True)
    time.sleep(1)
    try:
        proc.wait(timeout=5)
    except Exception:
        pass


def find_button(win, title):
    for c in win.descendants(control_type="Button"):
        if c.window_text() == title:
            return c
    return None


def table_ctrl(win):
    for c in win.descendants(control_type="Table"):
        return c
    return None


def table_rows(win):
    """Authoritative row count from the bottom-bar '共 N 条结果' label.

    Counting UIA DataItems UNDERCOUNTS: QTableWidget is virtualised, so off-
    screen rows are never realised in the UIA tree (10 rows read as 8). The
    count label is the single source of truth; DataItems are only a fallback.
    """
    for c in win.descendants(control_type="Text"):
        m = re.match(r"共 (\d+) 条结果", c.window_text().strip())
        if m:
            return int(m.group(1))
    n = len([c for c in win.descendants(control_type="DataItem")])
    return n // 4 if n else 0


def wait_rows(win, expected, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if table_rows(win) == expected:
            return True
        time.sleep(0.5)
    return False


def put_image_clipboard(path):
    img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "BMP")
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, buf.getvalue()[14:])
    finally:
        win32clipboard.CloseClipboard()


def get_clipboard_text():
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        return ""
    finally:
        win32clipboard.CloseClipboard()


def select_files_via_dialog(folder, expected=10):
    """Open the native file dialog, navigate to `folder`, select all, open.

    Win11 common-dialog quirks (measured, see progress.md decision 16 + G-2):
    - the real file list is a UIA List '项目视图'; ListBox / SysListView32 do
      not exist / are inert overlays.
    - navigation must go through the address bar (Ctrl+L + full path + Enter);
      the filename box does NOT navigate.
    - maximise the dialog first so every item is realised before Ctrl+A (a
      default-sized dialog drops items at open time).
    - Ctrl+A, then verify the selection count before opening.
    """
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    from pywinauto.mouse import click as mclick

    dlg = _find_dialog()
    for _ in range(10):
        if dlg is not None:
            break
        time.sleep(0.5)
        dlg = _find_dialog()
    if dlg is None:
        print("  G: no dialog found")
        return False
    win32gui.ShowWindow(dlg, win32con.SW_MAXIMIZE)
    time.sleep(2.5)
    win32gui.SetForegroundWindow(dlg)
    uw = Application(backend="uia").connect(handle=dlg, timeout=10).window(handle=dlg)
    uw.set_focus()
    time.sleep(0.3)
    items = []
    for attempt in range(5):
        send_keys("^l")
        time.sleep(0.4)
        send_keys(folder, with_spaces=True)
        time.sleep(0.3)
        send_keys("{ENTER}")
        time.sleep(2.0)
        lst = [c for c in uw.descendants(control_type="List")
               if c.window_text() == "项目视图"]
        items = lst[0].children() if lst else []
        print(f"  G nav attempt {attempt}: {len(items)} items")
        if len(items) == expected:
            break
    if len(items) != expected:
        print("  G: expected", expected, "items, abort")
        return False
    r = items[0].rectangle()
    mclick(coords=((r.left + r.right) // 2, (r.top + r.bottom) // 2))
    time.sleep(0.5)
    send_keys("^a")
    time.sleep(0.8)
    sel = sum(1 for it in items if it.is_selected())
    print("  G selected:", sel)
    if sel < expected:
        return False
    send_keys("{ENTER}")
    time.sleep(0.5)
    return True


def _find_dialog():
    hwnds = []

    def _cb(h, acc):
        if win32gui.GetClassName(h) == "#32770" and \
                win32gui.GetWindowText(h) == "选择图片":
            acc.append(h)
    win32gui.EnumWindows(_cb, hwnds)
    return hwnds[0] if hwnds else None


def data_items(win):
    return [c.window_text() for c in win.descendants(control_type="DataItem")]


def main():
    # ---- launch 1 ----
    proc, win = launch()
    check("A-1 窗口出现", True)
    for txt in ("选择文件", "粘贴图片", "复制全部", "清空"):
        check(f"A-2 控件[{txt}]", find_button(win, txt) is not None)

    # ---- B: clipboard paste (retry — clipboard read + window focus are flaky) ----
    ok = False
    for attempt in range(3):
        put_image_clipboard(SAMPLE)
        time.sleep(0.5)
        win.set_focus()
        time.sleep(0.3)
        find_button(win, "粘贴图片").click_input()
        if wait_rows(win, 1, timeout=25):
            ok = True
            break
    check("B-1 剪贴板粘贴识别出 1 行", ok)
    if ok:
        cells = data_items(win)
        check("B-2 三字段正确",
              "张建邺" in cells and "男" in cells and
              "321322200406170832" in cells, f"cells={cells}")

    # ---- C: copy all -> tab separated ----
    find_button(win, "复制全部").click_input()
    time.sleep(0.5)
    text = get_clipboard_text()
    lines = [l for l in text.replace("\r\n", "\n").split("\n") if l.strip()]
    ok = bool(lines) and all("\t" in l for l in lines)
    check("C-1 复制全部为制表符分列", ok, f"lines={len(lines)} first={lines[0] if lines else ''!r}")

    # ---- D: single-click a cell + EditKeyPressed input edits it ----
    table = table_ctrl(win)
    if table is None:
        check("D-1 找到结果表格", False)
    else:
        trect = table.rectangle()
        hdr = None
        for c in win.descendants(control_type="Header"):
            hdr = c
            break
        top = hdr.rectangle().bottom if hdr else trect.top + 25
        col_w = trect.width() / 4.0
        x = int(trect.left + col_w * 1.5)
        y = int(top + 15)
        from pywinauto.mouse import click
        click(coords=(x, y))  # select the row + set the current cell
        time.sleep(0.4)
        from pywinauto.keyboard import send_keys
        send_keys("{F2}")  # Qt edits the current cell on F2 (editor is not a UIA Edit)
        time.sleep(0.5)
        send_keys("^a")    # select the existing text, then type the replacement
        send_keys("TestName")
        time.sleep(0.3)
        send_keys("{ENTER}")
        time.sleep(0.5)
        check("D-2 编辑单元格生效", "TestName" in data_items(win),
              f"cells={data_items(win)}")

    # ---- E: clear + confirm ----
    find_button(win, "清空").click_input()
    time.sleep(0.8)
    from pywinauto import Desktop
    desktop = Desktop(backend="uia")
    clicked = False
    YES_TEXTS = ("Yes", "是", "确定", "Y", "&Yes", "是(Y)", "Yes(&Y)")
    for w in desktop.windows():
        if not w.is_visible():
            continue
        try:
            btns = [c for c in w.descendants(control_type="Button")]
        except Exception:
            continue
        for c in btns:
            if c.window_text() in YES_TEXTS:
                c.click_input()
                clicked = True
                break
        if clicked:
            break
    check("E-1 清空确认框出现并确认", clicked)
    time.sleep(0.8)
    check("E-2 清空后表格 0 行", table_rows(win) in (0, None))

    close_app(proc)

    # ---- F: relaunch, no residue ----
    proc2, win2 = launch()
    check("F-1 重开无历史数据残留", table_rows(win2) in (0, None))

    # ---- G: batch 10 via file dialog ----
    win2.set_focus()
    time.sleep(0.5)
    find_button(win2, "选择文件").click_input()
    time.sleep(2)
    ok = select_files_via_dialog(BATCH_DIR)
    check("G-1 文件对话框选择批量文件", ok)
    # watch for the progress bar during the batch
    saw_progress = False
    deadline = time.time() + 90
    while time.time() < deadline:
        if any(c.element_info.control_type == "ProgressBar"
               for c in win2.descendants()):
            saw_progress = True
        if table_rows(win2) == 10:
            break
        time.sleep(0.5)
    check("G-2 批量识别 10 行", table_rows(win2) == 10)
    check("G-3 批量时进度条可见", saw_progress)
    if table_rows(win2) == 10:
        cells = data_items(win2)  # visible rows only (Qt virtualises the rest)
        check("G-4 10 行结果三字段完整",
              "张建邺" in cells and "男" in cells and
              "321322200406170832" in cells, f"visible cells={len(cells)}")

    close_app(proc2)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n==== {passed}/{len(RESULTS)} passed ====")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
