"""Core GUI acceptance against the frozen exe (PRD §5.2).

Covers: window/controls present, clipboard-paste recognition, copy-to-Excel
(tab-separated), double-click edit, clear, close&reopen leaves no residue.

Run: .venv\\Scripts\\python.exe scripts/acceptance_core.py [--keep-open]
"""
import io
import subprocess
import sys
import time

import win32clipboard
from PIL import Image

EXE = r"d:\zjy\project\project_01_jc\dist\检测识别.exe"
SAMPLE = r"d:\zjy\project\project_01_jc\assets\samples\idcard_sample.jpg"
COLD_WAIT = 22  # exe cold start ~15s + slack

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def launch():
    # clean up stale onefile children from earlier runs, then launch fresh
    subprocess.run(["taskkill", "/IM", "检测识别.exe", "/F"],
                   capture_output=True)
    time.sleep(1)
    proc = subprocess.Popen([EXE])
    time.sleep(COLD_WAIT)
    from pywinauto import Desktop
    desktop = Desktop(backend="uia")
    wins = [w for w in desktop.windows()
            if w.window_text() == "检测识别" and w.is_visible()]
    if not wins:
        raise RuntimeError("main window 检测识别 not found")
    return proc, wins[0]


def put_image_clipboard(path):
    img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "BMP")
    dib = buf.getvalue()[14:]  # strip BITMAPFILEHEADER -> CF_DIB
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib)
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


def table_ctrl(win):
    for c in win.descendants(control_type="Table"):
        return c
    return None


def table_rows(win):
    """Row count of the results table (UIA 'Table'). None if not found."""
    t = table_ctrl(win)
    if t is None:
        return None
    try:
        return t.row_count()
    except Exception:
        return None


def wait_rows(win, expected, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        n = table_rows(win)
        if n == expected:
            return True
        time.sleep(0.5)
    return False


def find_button(win, title):
    for c in win.descendants(control_type="Button"):
        if c.window_text() == title:
            return c
    return None


def dump(win, tag):
    print(f"[DEBUG {tag}] controls:")
    for c in win.descendants():
        ct = c.element_info.control_type
        name = c.window_text()
        if name:
            print(f"    {ct}: {name!r}")
        else:
            print(f"    {ct}")


def close_app(proc, win):
    try:
        win.close()  # graceful WM_CLOSE
        proc.wait(timeout=10)
    except Exception:
        pass
    finally:
        # onefile bootloader can leave children; make sure it's gone
        subprocess.run(["taskkill", "/IM", "检测识别.exe", "/F"],
                       capture_output=True)
        time.sleep(1)


def main():
    keep_open = "--keep-open" in sys.argv

    # ---- launch 1 ----
    proc, win = launch()
    check("A-1 窗口出现", True, "title=检测识别")
    for txt in ("选择文件", "粘贴图片", "复制全部", "清空", "拖拽图片到此处开始识别"):
        found = any(c.window_text() == txt for c in win.descendants())
        check(f"A-2 控件[{txt}]", found)

    # ---- clipboard paste + recognise ----
    put_image_clipboard(SAMPLE)
    paste = find_button(win, "粘贴图片")
    paste.click_input()
    ok = wait_rows(win, 1, timeout=30)
    check("B-1 剪贴板粘贴识别出 1 行", ok)
    dump(win, "after-paste")  # inspect grid/status structure

    # ---- copy all -> tab-separated ----
    find_button(win, "复制全部").click_input()
    time.sleep(0.5)
    text = get_clipboard_text()
    lines = [l for l in text.split("\r\n") if l.strip()]
    fmt_ok = bool(lines) and all("\t" in l for l in lines)
    check("C-1 复制全部为制表符分列", fmt_ok,
          f"lines={len(lines)} first={lines[0] if lines else ''!r}")

    if keep_open:
        print("keeping window open; press Enter to exit")
        input()
        proc.terminate()
        return

    # ---- double-click edit ----
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
        row_h = 30
        x = trect.left + col_w * 1.5
        y = top + row_h / 2.0
        from pywinauto.mouse import double_click
        double_click(coords=(int(x), int(y)))
        time.sleep(0.5)
        # editor should be exposed as an Edit control now
        ed = None
        for c in win.descendants(control_type="Edit"):
            if c.is_visible():
                ed = c
                break
        if ed is None:
            check("D-2 双击进入编辑态", False)
        else:
            check("D-2 双击进入编辑态", True)
            ed.set_edit_text("测试姓名")
            ed.type_keys("{ENTER}")
            time.sleep(0.5)
            cells = [c.window_text()
                     for c in win.descendants(control_type="DataItem")]
            check("D-3 编辑后单元格更新", "测试姓名" in cells, f"cells={cells}")

    # ---- clear with confirm ----
    find_button(win, "清空").click_input()
    time.sleep(0.8)
    msg = None
    for w in _desktop_windows():
        if w.is_visible() and w.window_text() in ("清空", ""):
            pass
    # find any modal box and click its confirm button
    from pywinauto import Desktop
    desktop = Desktop(backend="uia")
    for w in desktop.windows():
        if not w.is_visible():
            continue
        btns = [c.window_text() for c in w.descendants(control_type="Button") if c.window_text()]
        if btns and w.window_text() == "清空":
            confirm = None
            for c in w.descendants(control_type="Button"):
                t = c.window_text()
                if t in ("Yes", "是", "确定", "Y", "Yes", "&Yes"):
                    confirm = c
                    break
            if confirm is None and btns:
                confirm = w.descendants(control_type="Button")[0]
            if confirm:
                confirm.click_input()
                msg = w.window_text()
            break
    time.sleep(0.8)
    n = table_rows(win)
    check("E-1 清空后表格 0 行", n in (None, 0), f"rows={n}")

    # ---- close & reopen: no residue ----
    close_app(proc, win)
    proc2, win2 = launch()
    n2 = table_rows(win2)
    check("F-1 重开无历史数据残留", n2 in (None, 0), f"rows={n2}")
    close_app(proc2, win2)

    # ---- summary ----
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n==== {passed}/{len(RESULTS)} passed ====")
    return 0 if passed == len(RESULTS) else 1


def _desktop_windows():
    from pywinauto import Desktop
    return Desktop(backend="uia").windows()


if __name__ == "__main__":
    sys.exit(main())
