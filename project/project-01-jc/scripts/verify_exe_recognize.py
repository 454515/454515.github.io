# -*- coding: utf-8 -*-
"""End-to-end verify on the frozen exe: background warmup + clipboard-paste
recognition. Proves the sub-thread PaddleOCR init works inside the exe and
the full import->recognize->table path still functions.

Usage: .venv\\Scripts\\python.exe scripts/verify_exe_recognize.py
"""
import io
import subprocess
import sys
import time

import win32clipboard
from PIL import Image
from pywinauto import Desktop

EXE = r"d:\zjy\project\project_01_jc\dist\jc\jc.exe"
SAMPLE = r"d:\zjy\project\project_01_jc\assets\samples\idcard_sample.jpg"

# Put the sample into the clipboard as CF_DIB (same as acceptance_core).
img = Image.open(SAMPLE).convert("RGB")
buf = io.BytesIO()
img.save(buf, "BMP")
dib = buf.getvalue()[14:]  # strip BITMAPFILEHEADER -> CF_DIB
win32clipboard.OpenClipboard()
try:
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib)
finally:
    win32clipboard.CloseClipboard()

subprocess.run(["taskkill", "/IM", "jc.exe", "/F"], capture_output=True)
time.sleep(1)
proc = subprocess.Popen([EXE])
pid = proc.pid
desktop = Desktop(backend="uia")

win = None
t0 = time.perf_counter()
while time.perf_counter() - t0 < 40:
    for w in desktop.windows():
        try:
            if w.process_id() == pid and w.is_visible():
                win = w
                break
        except Exception:  # noqa: BLE001 - stale element mid-launch
            pass
    if win:
        break
    time.sleep(0.3)
if not win:
    print("FAIL: main window not found within 40s")
    sys.exit(1)
print(f"window found in {time.perf_counter() - t0:.1f}s (still responsive)")

# Let the background warmup finish (or reveal if it stalls inside the exe).
time.sleep(12)

paste = next(
    (c for c in win.descendants(control_type="Button")
     if c.window_text() == "粘贴图片"),
    None,
)
if paste is None:
    print("FAIL: 粘贴图片 button not found")
    for c in win.descendants():
        ct = c.element_info.control_type
        name = c.window_text()
        print(f"    {ct}: {name!r}" if name else f"    {ct}")
    subprocess.run(["taskkill", "/IM", "jc.exe", "/F"], capture_output=True)
    sys.exit(1)
paste.click_input()  # triggers clipboard paste -> background recognition

deadline = time.perf_counter() + 60
rows = 0
while time.perf_counter() < deadline:
    try:
        t = next((c for c in win.descendants(control_type="Table")), None)
        if t is not None:
            rows = t.row_count()
            if rows:
                print(f"result table rows={rows}")
                break
    except Exception:  # noqa: BLE001 - UIA probe can flake mid-recognition
        pass
    time.sleep(0.5)
else:
    print("FAIL: no result rows within 60s (recognition via background warmup failed)")
    subprocess.run(["taskkill", "/IM", "jc.exe", "/F"], capture_output=True)
    sys.exit(1)

subprocess.run(["taskkill", "/IM", "jc.exe", "/F"], capture_output=True)
print("PASS: exe recognized sample via clipboard paste (background warmup ok)")
