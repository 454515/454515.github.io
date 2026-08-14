# -*- coding: utf-8 -*-
"""Measure exe startup responsiveness (window found + first UIA interaction).

Key metric: time from window appearing to a successful UIA query. With the
OLD main-thread warmup, PaddleOCR init (~3-7s) blocks the UI event loop, so
this interaction stalls for seconds; with background warmup it returns fast.

Usage: .venv\\Scripts\\python.exe scripts/measure_startup.py
"""
import subprocess
import sys
import time

from pywinauto import Desktop

EXE = r"d:\zjy\project\project_01_jc\dist\jc\jc.exe"

subprocess.run(["taskkill", "/IM", "jc.exe", "/F"], capture_output=True)
time.sleep(1)

t0 = time.perf_counter()
proc = subprocess.Popen([EXE])
pid = proc.pid
desktop = Desktop(backend="uia")

win, found = None, None
deadline = t0 + 40
while time.perf_counter() < deadline:
    for w in desktop.windows():
        try:
            if w.process_id() == pid and w.is_visible():
                win, found = w, time.perf_counter()
                break
        except Exception:  # noqa: BLE001 - stale UIA element mid-launch
            pass
    if win:
        break
    time.sleep(0.3)

if not win:
    print("FAIL: main window not found within 40s")
    sys.exit(1)
print(f"window found at {found - t0:.2f}s after launch")

# Let singleShot(200) fire, then probe UI. Old main-thread warmup would be
# blocking the event loop right now; background warmup keeps the UI live.
time.sleep(0.8)
t1 = time.perf_counter()
try:
    text = win.window_text()
    _ = [c for c in win.descendants(control_type="Edit")]  # heavier UIA probe
except Exception as exc:  # noqa: BLE001
    print(f"interaction failed: {exc}")
    subprocess.run(["taskkill", "/IM", "jc.exe", "/F"], capture_output=True)
    sys.exit(1)
t2 = time.perf_counter()
print(f"first UIA interaction took {t2 - t1:.2f}s (window responsive)"
      f"  title={text!r}")
print(f"RESULT: interaction={t2 - t1:.2f}s")

subprocess.run(["taskkill", "/IM", "jc.exe", "/F"], capture_output=True)
