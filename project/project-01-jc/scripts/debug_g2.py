"""Focused G test: run the real exe, open the file dialog, select the batch
folder, and verify 10 rows via the acceptance script's own helpers."""
import subprocess
import sys
import time

import win32gui

import acceptance_all as acc


def main():
    subprocess.run(["taskkill", "/IM", "检测识别.exe", "/F"], capture_output=True)
    time.sleep(1)
    proc = subprocess.Popen([acc.EXE])
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
        raise SystemExit("no window")

    win.set_focus()
    time.sleep(0.5)
    acc.find_button(win, "选择文件").click_input()
    time.sleep(2)
    ok = acc.select_files_via_dialog(acc.BATCH_DIR)
    print("select_files_via_dialog:", ok)

    deadline = time.time() + 120
    last = -1
    while time.time() < deadline:
        rows = acc.table_rows(win)
        if rows != last:
            print("rows:", rows)
            last = rows
        if rows == 10:
            break
        time.sleep(0.5)
    print("final rows:", acc.table_rows(win))
    saw_prog = any(c.element_info.control_type == "ProgressBar"
                   for c in win.descendants())
    print("progress bar visible at end:", saw_prog)

    proc.terminate()
    subprocess.run(["taskkill", "/IM", "检测识别.exe", "/F"], capture_output=True)
    return 0 if acc.table_rows(win) == 10 else 1


if __name__ == "__main__":
    sys.exit(main())
