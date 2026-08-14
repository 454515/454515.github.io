# 检测识别 项目进展记录

> 本文件用于跨会话恢复上下文。新对话开始前**先阅读本文件**（全局规则已约定）。
> 项目总控：[agent.md](./agent.md) ｜ 需求：[检测识别_PRD需求文档.md](./检测识别_PRD需求文档.md)
> 最近更新：2026-08-12（exe 打包 + 全量实测通过：发票识别 5 字段正确且缩图提速、exe 内粘贴识别复测通过、dist 内 git 库保留；`build_onefile.bat` 不再清空 dist 目录）

---

## 一、项目概览

Windows 本地桌面 OCR 工具：身份证识别（姓名/性别/公民身份号码）+ 发票识别（姓名/发票代码/发票号码/金额/开票时间），支持微信拖拽、文件选择、剪贴板粘贴、文件夹导入四种输入方式，批量识别，结果一键复制适配 Excel 分列。全程本地处理、数据不上传。

技术栈：PySide6 + PaddleOCR 3.7 + OpenCV + PyInstaller，Python 3.13.5。

## 二、已完成的事项

### 框架与文档（✅）
- `agent.md` 阶段总控（8 阶段）、`.claude/skills/` 8 个阶段 skill、`docs/specs/` 8 个 spec
- git 仓库已初始化（master，3 个提交），`.gitignore` 已排除 `.venv`、`assets/samples/`、`models/`
- Python 3.13.5 虚拟环境 `.venv` + `requirements.txt`

### 阶段 0：项目初始化（✅ spec-00 验收全过）
- `src/` 分层骨架：`ui/ core/ ocr/ processors/ utils/`
- `src/config.py` 全局配置、`src/app.py` 占位入口
- PaddleOCR 冒烟测试通过：例图识别 12 个文字块
- 例图 `assets/samples/idcard_sample.jpg`（用户提供，876×576，已 gitignore 敏感不入库）

### 阶段 1：OCR 引擎层（✅ spec-01 验收全过）
- `src/ocr/models.py`：`OcrWord` / `OcrResult` 统一数据模型
- `src/ocr/engine.py`：`OcrEngine`（惰性加载、线程安全初始化、损坏图容错、模块单例 `get_engine()`），引擎层不做任何缩放/矫正
- 性能：热态 **0.55~0.72s**（PRD 要求 ≤1.5s ✅）
- 测试：`scripts/test_ocr_engine.py`（自测）、`scripts/bench_ocr.py`（模型对比）

### 阶段 2：图像预处理与矫正（✅ spec-02 验收全过）
- `src/utils/preprocess_models.py`：`PreprocessResult`（image/rotation_angle/quad/found_card/error）
- `src/utils/preprocess.py`：管线入口 `preprocess_image()`，顺序 **尺寸归一化→方向校正→透视矫正→背景去除**；三个独立步骤 `correct_orientation` / `perspective_correct` / `extract_foreground`
- 尺寸归一化：仅放大不缩小，最长边到 `PREPROCESS_MAX_SIDE=1300`（`src/config.py`）
- 方向校正：四边形长边方向 + 号码行定位 0/180，返回 0/90/180/270；无四边形时 Hough 主方向兜底
- 透视矫正：Canny→轮廓→面积最大凸四边形→四点透视拉正；未检测到直通
- 容错：任何步骤失败降级原图直通、不抛异常；无法解码返回 error
- 自测：`scripts/test_preprocess.py`（合成卡片 0/90/180/270 + 倾斜 + 非身份证 + OCR 联调），**验收 A-2-1~A-2-5 全过**

### 阶段 3：身份证字段提取（✅ spec-03 验收全过）
- `src/processors/models.py`：`CardResult`（card_type/fields/missing）
- `src/processors/base.py`：`BaseProcessor` 抽象基类；`idcard.py`：`IDCardProcessor`
- 提取规则：姓名取「姓名」标签右下方最近中文块（横/竖排通用）；性别优先「性别」块内男/女；身份证号正则 `\d{17}[\dXx]` + 置信度最高 + 末位 x→X
- `src/processors/registry.py` + `__init__` 默认注册 idcard
- 自测：`scripts/test_idcard_processor.py`（标准/同块/小写x/缺失/竖排/20 张准确率 100%/registry/validate），**验收 A-3-1~A-3-5 全过**
- 真实样例完整链路验证：预处理→OCR→提取，三字段 `张建邺/男/321322200406170832` 全对、missing 空（预处理放大解决 OCR 原图漏检「男」）

### 阶段 4：UI 主界面框架（✅ spec-04 验收全过）
- `src/ui/`：`main_window.py`（MainWindow 组装）/ `drop_area.py` / `result_table.py` / `bottom_bar.py`
- 布局对照 PRD §2.2：顶部标签页（身份证可用、发票置灰 `setTabEnabled(1,False)`）→ 中央拖拽区（虚线占位）→ 选择文件/粘贴图片按钮 → 进度条（默认隐藏）→ 结果表格（序号/姓名/性别/身份证号，双击编辑）→ 底部操作栏（共 N 条/复制全部/清空）
- `MainWindow.add_demo_rows(rows: list[CardResult])` 模拟数据填充
- `src/app.py` 更新为启动主窗口（含 2 行演示数据）
- 自测：`scripts/test_ui_smoke.py`（offscreen，标签禁用/控件齐全/列序/填充/缩放），**验收 A-4-1~A-4-5 全过**

### 阶段 5：图片导入方式（✅ spec-05 验收全过）
- `src/core/import_queue.py`：`ImportQueue`（白名单 .jpg/.jpeg/.png/.bmp、abspath 去重、非图片入 `rejected`、文件夹递归+字母序）
- `src/ui/drop_area.py`：拖拽支持（dragEnter/dragLeave/drop）+ 高亮反馈（边框变色、提示「释放即可识别」）
- `src/ui/main_window.py`：`_import_paths`（文件/目录统一入口）、「选择文件」→ QFileDialog 多选、Ctrl+V 剪贴板图片 → 临时 PNG 入队、statusBar 导入反馈
- 自测：`scripts/test_import_stage5.py`（offscreen，入队顺序/文件夹递归/非图片拒绝/去重/拖拽高亮/剪贴板粘贴），**验收 A-5-1~A-5-5 全过**；阶段 4 test_ui_smoke 回归通过

## 三、关键决策

1. **禁用 oneDNN（必须，所有阶段遵守）**：paddlex 默认 `PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=True`，在 paddlepaddle 3.3.1 + Windows 上触发 `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support ... oneDNN` 崩溃。**任何代码在 import paddle/paddleocr 之前必须** `os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")`。已固化在 `engine.py` 与冒烟脚本。
2. **paddleocr 3.x API 变更**：`use_angle_cls` / `ocr(cls=True)` 已移除。用法：
   ```python
   ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                   use_textline_orientation=False, lang="ch",
                   text_detection_model_name=..., text_recognition_model_name=...)
   result = ocr.predict(img_path)   # 返回 list[OCRResult]
   res = result[0].json["res"]      # res["rec_texts"|"rec_scores"|"rec_polys"]
   ```
3. **模型选型 v6_tiny（唯一达标）**：禁用 oneDNN 后 CPU 实测 medium≈9.1s、small≈1.75s、v5_mobile≈3.2s、**v6_tiny≈0.65s**。配置在 `src/config.py`：`OCR_DET_MODEL="PP-OCRv6_tiny_det"`、`OCR_REC_MODEL="PP-OCRv6_tiny_rec"`。
4. **放大 1.5x 补偿质量**：v6_tiny 原图漏检「性别男」的「男」；放大到最长边约 1300px 后三字段完整，实测 1094ms 仍 ≤1.5s。**阶段 2 预处理第一步必须是「输入尺寸归一化」**（已写入 spec-02）。
5. **中文路径坑**：项目路径含中文（`D:\zjy\代码\...`），`cv2.imread/imwrite` 不支持中文路径，必须用 `cv2.imdecode(np.fromfile(path,dtype=np.uint8), ...)` 读取、`cv2.imencode(...).tofile(path)` 写入。**阶段 2 及后续所有 OpenCV 读写必须如此**。
6. **隐私红线**：`assets/samples/`（身份证例图）与 `.venv` 已 gitignore，不进版本库。
7. **依赖锁定**：paddlepaddle 3.3.1（cp313 wheel）、paddleocr 3.7.0、PySide6 6.11.1、opencv-python 5.0（实际 cv2 为 opencv-contrib-python 4.10.0.84）、pyinstaller 6.21.0。安装走清华镜像。
8. **方向校正 0/180 判定用「号码行定位」**：上下密度启发式对真实样例失效（正面上下密度几乎对称），改用**号码行**——身份证底部 18 位数字串是「窄横向连通域最多的一行」，行位置在上半→倒立转 180、在下半→正立。`_id_number_row_cy()` 在 `src/utils/preprocess.py`，窄 run 阈值 `< 0.9×行高`、少于 8 个窄 run 视为未找到（退回密度法兜底）。
9. **OCR 原图漏检「男」必须走预处理**：v6_tiny 对真实样例原图把「性别男」拆成 `性别`+`民族汉`、漏掉「男」，字段提取的 `gender` 会缺失；**必须预处理放大到 1300px 后再 OCR**（阶段 2 已固化），三字段才完整。UI 层（阶段 6）的识别流水线必须包含预处理。
10. **UI 后台识别禁用 QThread，用 threading.Thread**：实测 paddle 推理在 **QThread 线程里 16~30s/张**、在普通 python 线程 ~1s（与主线程持平）。`RecognitionService` 用 `threading.Thread(daemon=True)` 跑识别循环，信号照常跨线程队列回主线程（UI 层零改动）；`is_running()` 改查 `thread.is_alive()`。测试等待线程改用 `thread.join(timeout)`（QThread 的 `wait` 不存在）。
11. **paddle 冷态初始化必须在主线程**：有 QApplication 时，**任何非主线程**（QThread 或 python 线程）首次 import paddle / 创建 PaddleOCR 会卡死 >60s；主线程 3~4s 完成。`OcrEngine.warmup()` 强制在主线程 `_get_ocr()`；`MainWindow` 用 `QTimer.singleShot(0, ...)` 空闲时预热，`_start_recognition` 前再兜底同步一次（`_engine_ready` 标志）。预热后子线程只 predict，~1s/张。
12. **offscreen 测试别用 QTest.qWait 忙循环等真实识别**：主线程每 50ms 忙轮询会把 paddle 从 ~1s/张拖慢到 ~25s/张（真实 app.exec() 空闲时阻塞，不受影响）。真实验收脚本用 QEventLoop + `recognition_finished` 信号阻塞等待（`_wait_done` 用标志位区分完成/超时，不要用 `timer.isActive()` 判断——timer.stop() 后恒 False）。
13. **paddle 读不了中文路径下的模型（阶段 7 实测，推翻 spec-07 外置策略）**：paddlepaddle 底层 C++ 读取模型文件时，若路径含中文（`D:\zjy\代码\...`）报 `RuntimeError: parse error, attempting to parse an empty input`（inference.json 被读成空）。验证：模型放 ASCII 路径 `C:\Users\13689\AppData\Local\Temp\pdx_ascii` 加载成功。因此 **spec-07 §3.1「外置 models/ 目录」废弃**（用户 exe 放中文目录必挂），改为**模型内置进 exe**：`--add-data "models;models"`，onefile 解压到 ASCII 的 `%TEMP%\_MEIxxxx`，`src/config.py` 冻结时设 `PADDLE_PDX_CACHE_HOME=_MEIPASS/models` 离线加载；dev 环境不设（保留默认 `~/.paddlex` ASCII 缓存）。v6_tiny 模型仅 ~6.4MB，内置无体积压力。
14. **项目路径去中文（✅ 已完成）**：项目根 `D:\zjy\代码\project_01_检测识别` → `D:\zjy\project\project_01_jc`（"代码"→"project"、"检测识别"→"jc"）。由用户手动重命名完成，本文件现位于新路径，阶段 7 打包已在此继续。
15. **paddlex 的 ocr-core 依赖必须在打包时收齐 dist-info（阶段 7 实测，已修复）**：exe 内 warmup 报 `DependencyError: 'OCR' requires additional dependencies`——paddlex 用 `importlib.metadata` 检查 `require_extra("ocr")` 所需的 ocr-core 包 dist-info，而 `--collect-all paddleocr` 不会带它们。修复：spec 中对 `pyclipper / shapely / python_bidi / imagesize` 用 `collect_all`，对 `opencv-contrib-python / pypdfium2 / python-bidi` 用 `copy_metadata`（只收 dist-info，零体积成本）。**打包 exe 后必须实测识别**（仅启动成功 ≠ 识别可用）。
16. **现代文件对话框的列表是 `SHELLDLL_DefView`，不是 `ListBox`（阶段 7 验收实测）**：Win 11 的 IFileDialog 里 `ListBox` 控件是残留 overlay、`item_count()` 恒 0；真正的文件列表是 `SHELLDLL_DefView`。文件名框 `set_edit_text(路径)+Enter` **不导航**（焦点不在该框），导航要 **Ctrl+L 聚焦地址栏**再输入完整路径回车。全选用 Shell 视图聚焦后 Ctrl+A。
17. **方向校正 0/180 误判（阶段 7 实测，已修复）**：真实样例「卡片在浅灰背景上、不占满整图」时，`_is_upright` 的 OTSU+全局反转（`dark < half → 255-bw`）把浅灰背景反转成前景，身份证区域+背景粘成大带被 `row_h > 12%h` 跳过，号码行永远检测不到，**正立被误判倒立 180**。修复：`_is_upright` 优先用**暗字阈值** `threshold(gray,100,THRESH_BINARY_INV)` 提取黑字做号码行定位（浅灰背景≥~170 不会提取，背景不粘带），OTSU+反转降为兜底（覆盖深底白字）。验证：合成卡白/深底 0/90/180/270 全对、原样例 0/180 正确、新样例 `22c818...` 从误判 180 修正为 0 且三字段 `唐洪发/男/321123196506233817` 全对；test_preprocess / test_idcard_processor / test_ui_smoke / test_import_stage5 / test_stage6 **全回归通过**。90/270 的 landscape 判定（`_dominant_rotation`）是既有限制（当前实现对 real/new 的 rot90/270 就返回 180/0），非本次范围、未动。
18. **Qt 表格 UIA 虚拟化 + 验收自动化经验（阶段 7 实测）**：① QTableWidget 屏外行不实例化进 UIA 树，`descendants(control_type="DataItem")` 数行恒偏少（10 行读成 8）——**行数以底部标签「共 N 条结果」为权威**，DataItem 仅兜底。② Qt 表格双击编辑无法用合成双击触发（行被选中但编辑器不出现），**单击选中 + F2**（Qt 内建编辑当前单元格）+ `^a` 键入 Enter 可行；编辑器控件不在 UIA 树中，断言看 DataItem 文本。③ 跑验收的控制台进程会抢窗口焦点，**交互动作前先 `win.set_focus()`**（`launch()` 已固化）。
19. **粘贴与拖拽多文件（阶段 7 实测，已修复）**：① `QShortcut(QKeySequence.Paste)` 默认 `WindowShortcut`，表格/按钮抢焦点后 Ctrl+V 不触发——改为 `ApplicationShortcut`。② `_paste_clipboard` 原先只对 `hasImage()` 响应，微信多选复制/文件夹复制时剪贴板只有 `text/uri-list` 或微信专属 `x-xwechat-multiselect-copy` JSON，`hasImage()` 为 False 直接静默返回——新增两条 fallback：`hasUrls()` → URL 路径导入；微信 JSON → 解析文件路径导入；无图时在状态栏提示而非静默。③ **微信多选界面拖拽是微信客户端限制**：实测 dragEnter 的 mimeData `formats=[]` 完全空，微信多选选择界面根本不提供 OLE DnD 数据；改为「微信多选复制 → Ctrl+V」即可。
20. **PyInstaller 6.x onedir 真实布局（阶段 7 实测，config 零改动）**：① 6.x onedir 的 datas 全部落在 `exe同目录/_internal/`（`contents_directory` 默认值），**不是** exe 同目录根——模型实际在 `dist/jc/_internal/models/official_models/`。② **onedir 模式同样设置 `sys._MEIPASS`**（指向 `_internal`），config.py 的 `meipass` 分支（`_MEIPASS/models`）对 onedir 天然命中，无需改代码；注释「onedir 走 BASE_DIR/models」已过时但无害。③ **onedir spec 必须含 `COLLECT`**：只有 EXE 块（内嵌 binaries/datas、无 `exclude_binaries=True`）是 onefile 结构，产物是单文件而非目录；修复=EXE 加 `exclude_binaries=True` + `COLLECT(exe, a.binaries, a.datas, name='jc')`。④ onedir 展开体积约 782MB（onefile 283MB 为压缩后，解压同样 ~780MB），换取无解压冷启动 + 稳定模型路径；`jc.exe` 本体 39MB。⑤ `scripts/verify_onedir.py` 可在 dev 环境模拟 frozen onedir（设 `sys.frozen`/`sys._MEIPASS`=dist/jc/_internal），实测 config 路径解析 + 离线加载 + 三字段识别，规避「仅启动成功 ≠ 识别可用」。
21. **启动卡顿修复：warmup 移后台线程（2026-08-11，阶段 7 后）**：① 原 `singleShot(200)` 后主线程同步 `PaddleOCR(...)` 构造 3-4s，阻塞事件循环 → 启动后 UI 卡数秒。② `scripts/bench_subthread_warmup.py` 实测当前环境（去中文路径 + paddle 3.3.1 + PySide6 6.11 + onedir）：子线程首次 import paddle≈3.7s / import paddleocr≈3.0s / 创建实例≈0.5s 均不卡死——**关键决策 11 已失效**（疑因决策 14 去中文路径）。③ 修复：`main_window._warmup_engine` 改 `threading.Thread(daemon=True)` 后台加载 + `_warming_up` 防重入；`_start_recognition` 兜底改异步，识别线程靠 engine 的 `_lock` 等待加载完成。④ `scripts/measure_startup.py` 实测：窗口 2.48s 出现、首次 UIA 交互 **0.01s**。⑤ **待 z 实测 exe**：`scripts/verify_exe_recognize.py` 在 exe 上点击「粘贴图片」识别 60s 无结果，原因未定（可能 exe 内后台线程初始化与 dev 不一致 / 粘贴触发问题），**测试由 z 负责**。→ **2026-08-12 改回 onefile 重打包后复测通过**（见阶段 7 补充 3 与阶段 8）。

## 四、未完成的待办

### 阶段 4：UI 主界面框架（✅）
- PySide6 主窗口：标签页（发票预留置灰）、拖拽区、按钮、进度条、表格（序号/姓名/性别/身份证号）、底部操作栏

### 阶段 5：图片导入方式（✅）
- 微信拖拽（单选✅ / 多选❌ 微信客户端限制）、文件选择、剪贴板粘贴（Ctrl+V + 按钮，支持标准位图/URL/微信多选JSON三种格式）、文件夹导入 + 拖拽高亮反馈

### 阶段 6：批量识别与结果管理（✅ 真实验收 A-6-1~A-6-6 全过）
- `src/core/recognition_service.py`：`RecognitionService(QObject)` + **后台线程**（threading.Thread，见关键决策 10）；信号 `progress_updated / image_started / result_ready / batch_finished`；逐张 预处理→OCR→字段提取，单张失败跳过并计数（spec-06 §3）
- `src/ui/main_window.py`：导入即自动识别（`_start_recognition` 快照队列并清空；单张隐藏进度条，批量显示 + 「正在识别第 N 张 / 共 M 张」）；**主线程 warmup 预加载模型**（关键决策 11）；结果入表（失败行三列显示「识别失败」）；复制全部/选中复制（制表符分隔、Excel 分列）；右键删除+重排、清空（带确认框）；识别中继续拖入 → 当前批完成后自动续批；`closeEvent` 停服务
- `src/ui/result_table.py`：`append_row / rows_data / selected_rows_data / renumber` + 右键菜单（删除/复制选中行）；序号列 str 化
- `src/app.py`：启动空窗口 + 状态栏提示，demo 行移除（识别由导入驱动）
- `scripts/test_stage6.py`：6 项自测全过（批量跳过计数 / stop 提前停 / 端到端含坏图 / 复制格式 / 双击编辑 / 删除重排+清空）
- 阶段 5 测试已适配导入→自动识别链路（UI 用例改注入 `_EchoEngine` + 断言表格行数）
- **真实端到端验收**：5 张样例 + 1 坏图 → 5 行 `张建邺/男/321322200406170832` + 1 行「识别失败」，statusBar「完成，失败 1 张」；单张热态 ~1.1s，批量（含进度条更新）~1.6s/张；test_ui_smoke / test_import_stage5 回归通过

### 阶段 7：打包与交付（✅ 目录模式 onedir，2026-08-11 最终版）
- ✅ `assets/icon.ico`：多尺寸 16/32/48/64/128/256（`scripts/make_icon.py` 纯 Pillow 绘制，无字体依赖）
- ✅ `models/official_models/`：从 `~/.paddlex/official_models/` 复制 v6_tiny_det/rec（约 6.4MB）
- ✅ `src/config.py` 适配 onedir：`_get_models_dir()` 区分 onefile（`_MEIPASS/models`）和 onedir（`BASE_DIR/models`，exe 同目录直读）
- ✅ `src/app.py`：`window.setWindowTitle("jc")` 覆盖默认中文窗口名
- ✅ 临时文件清理（PRD §3.3）：`recognition_service._recognize_one` 中间图 finally 删除；剪贴板粘贴文件记入 `_temp_files`，closeEvent 清理
- ✅ `jc.spec`：onedir 替换原 `检测识别.spec`，含 ocr-core 依赖补丁（`collect_all`/`copy_metadata`）。**修复：补 `exclude_binaries=True` + `COLLECT` 块**——原 spec 是 onefile 写法（EXE 内嵌 binaries/datas，无 COLLECT），首次构建产物实为单文件 `dist/jc.exe` 283MB 而非目录；修复后产出 `dist/jc/jc.exe`（39MB）+ `dist/jc/_internal/`（约 782MB，含全部 DLL/模型）
- ✅ `src/ui/main_window.py`：启动 warmup 延后至 `singleShot(200)`；`_copy_all`/`_copy_selected` 给身份证号加双引号防 Excel 科学计数法
- ✅ `src/ui/result_table.py`：`selectionBehavior` 改为 `SelectItems`，支持鼠标拖拽多选
- ✅ 回归：test_ui_smoke / test_stage6 / test_import_stage5 / test_preprocess / test_idcard_processor 全过
- ✅ 构建脚本：`scripts/build_onedir.bat`（双击打包）、`scripts/test_onedir.bat`（双击测试）
- ✅ **目录模式打包完成（2026-08-11）**：`dist/jc/jc.exe` + `dist/jc/_internal/`（总约 782MB）。`scripts/verify_onedir.py` 模拟 frozen onedir 环境验证——MODELS_DIR 解析 `_internal/models`、PADDLE_PDX_CACHE_HOME 正确、引擎离线加载（Using cached files，无联网）、样例三字段 `张建邺/男/321322200406170832` 全对
- ✅ **启动卡顿修复（2026-08-11）**：warmup 移后台线程（详见关键决策 21）。`scripts/measure_startup.py` 实测：窗口 2.48s 出现、首次 UIA 交互 **0.01s**（修复前主线程 warmup 阻塞数秒）。回归全过
- ✅ **exe 实测通过（2026-08-12）**：`verify_exe_recognize.py` 曾报旧 onedir exe 点击「粘贴图片」识别 60s 无结果（原因未定）。改回 onefile 重打包后，z 实测**全部通过**：发票识别 5 字段正确且缩图提速、exe 内粘贴图片识别正常、单击选中 Ctrl+C 复制到 Excel 身份证号完整显示、dist 内 git 库保留。
- 旧版 onefile `检测识别.spec` 已删除，dist 目录已清空

### 阶段 7 补充：onefile 单 exe + 复制修复（✅ 2026-08-12）
- ✅ **打包改回 onefile（单 exe）**：`jc.spec` 改为 `EXE(pyz, a.scripts, a.binaries, a.datas, [], name='jc')` 内嵌全部 binaries/datas，去掉 `exclude_binaries=True` + `COLLECT`；产物为单文件 `dist/jc.exe`。models 解压到 ASCII 的 `%TEMP%\_MEIxxxx`（中文 exe 目录安全，决策 13 依旧成立），`src/config.py` 零改动（`_MEIPASS` 分支天然命中）。
- ✅ **单击选中 + Ctrl+C 复制**：`result_table` selectionBehavior `SelectItems`→`SelectRows`（单击整行高亮、拖拽/Shift/Ctrl 多选整行）；`main_window` 新增 `QShortcut(QKeySequence.Copy)`→`_copy_selected`——不再需要双击进编辑态才能复制。
- ✅ **Excel 身份证号乱码修复**：复制收敛到 `_put_excel_clipboard` 双格式剪贴板——`text/html` 表格单元格带 `mso-number-format:\@`（Excel 强制按文本粘贴 18 位身份证号，杜绝科学计数法/尾数丢失）+ `text/plain` 制表符兜底（身份证列加引号）。
- ✅ **脚本**：新增 `scripts/build_onefile.bat` / `test_onefile.bat`（**修正 `cd /d %~dp0..`**——旧 onedir bat 写 `%~dp0` 会进 scripts/ 导致路径全错）；删除 onedir 版 build/test 与 `verify_onedir.py`（onedir 专属布局，不再适用）。
- ✅ **回归**：test_stage6（新增 SelectRows/Ctrl+C/HTML 格式断言）/ test_ui_smoke / test_import_stage5 全过；`jc.spec` py_compile 通过。
- ✅ **打包并实测通过（2026-08-12）**：`build_onefile.bat` 产出 `dist/jc.exe`，实测（a）单击选中行 + Ctrl+C → Excel 粘贴完整身份证号；（b）exe 内粘贴图片识别正常（旧 onedir 未定问题复测通过）。

### 阶段 7 补充 2：区域选择复制 + UPX 打包 + 打包分工（✅ 2026-08-12）
- ✅ **`build_onefile.bat` 不再清空 dist 目录（2026-08-12）**：原 `rmdir /s /q dist build` 会整个删除 dist——z 在 dist 里建了 git 库，被打包清掉。改为仅 `rmdir /s /q build` + `del dist\jc.exe`（PyInstaller `--noconfirm` 只覆盖自己的输出文件，不动 dist 里其他内容）。

- ✅ **问题 1 修复：拖动随意选中单元格**：`result_table` selectionBehavior 从 `SelectRows`（整行选择）改回 **`SelectItems`**（单元格级）——单击选中单元格、**鼠标拖动可随意选中任意矩形区域**、Shift/Ctrl 扩展多选；Ctrl+C 快捷键保留，无需双击进编辑态。Qt 限制：选中单元格内**部分文字**仍需双击编辑（仅影响部分文本复制，完整身份证号用单击+Ctrl+C 即可）。
- ✅ **问题 2 修复：单独复制身份证号不再乱码**：根因是 SelectRows 下无法单独选单元格 → 被迫双击编辑态复制 → Qt 内建纯文本剪贴板（无 HTML `mso-number-format`）→ Excel 按数字粘贴变科学计数法。修复：`selected_rows_data`（整行+全表头）改为 **`selected_cells_data`（选中区域+区域表头）**，`_copy_selected` 走区域 → `_put_excel_clipboard` 双格式（HTML `mso-number-format:\@` + TSV）→ 单独选中身份证单元格复制即身份证号列，Excel 按文本粘贴。右键菜单「复制选中行」→「复制选中区域」。
- ✅ **问题 3 加速：UPX 压缩生效**：系统原本没装 UPX（`upx=True` 空转，exe 283MB 未压缩）。已下载 **UPX 5.2.0** 至 `tools/upx/upx.exe`，`build_onefile.bat` 里 `set PATH=%cd%\tools\upx;%PATH%` 让 PyInstaller 自动启用压缩。重打包后 **`dist/jc.exe` 283MB → 217MB**（日志确认 UPX 生效：个别 CFG 保护的 Qt DLL 被 PyInstaller 自动跳过压缩，属正常）。启动解压数据量随之减少。
- ✅ **打包分工规则（已写入全局 CLAUDE.md「打包与测试分工」）**：打包执行 + 功能测试由 z 手动完成（双击 `scripts/build_onefile.bat` → 出 `dist/jc.exe`，`test_onefile.bat` 启动测试）；Claude 负责确认打包前置条件就绪（bat 可用 / `.venv` / `jc.spec` / `models` / `tools/upx/upx.exe` / icon）+ 回归测试 + progress.md 记录。本轮前置条件已逐项确认齐备（models 下 func_ret/locks/temp 为空目录，无体积影响）。
- ✅ **回归**：test_stage6（更新 SelectItems + 区域复制断言，覆盖「单独选中身份证单元格→剪贴板 HTML 含 ID」）/ test_ui_smoke / test_import_stage5 全过。
- ✅ **实测通过（2026-08-12）**：① 拖动随意选中单元格、单击选中 + Ctrl+C 正常；② 单独选中身份证号复制到 Excel 显示完整 18 位（非科学计数法）；③ 启动速度可接受；④ exe 内粘贴图片识别正常（旧问题复测通过）。

### 阶段 7 补充 3：单击即编辑选文字 + 编辑器内双格式复制（✅ 2026-08-12）
- ✅ **问题 1 终修：单击即编辑、文字全选、可直接拖动选**：z 实测补充 2 的 SelectItems 区域选择仍不符（Qt 非编辑态只能选"格子"，无法选"文字"，须双击进编辑框才能拖选）。按 z 确认的交互改为：`result_table.mousePressEvent` 左键点可编辑单元格 → `QTimer.singleShot(0)` 打开编辑器并 `selectAll()`——**单击文字立即全选高亮，按住即可拖选部分文字，无需双击**；序号列跳过；右键先 `commitData`+`closeEditor` 关编辑器再弹表格右键菜单（删除/复制选中区域），避免编辑器菜单抢占。
- ✅ **问题 2 终修：编辑器内 Ctrl+C 也走双格式**：根因是编辑态复制走 Qt 内建纯文本剪贴板（无 HTML `mso-number-format`）→ Excel 按数字粘贴变科学计数法/尾数丢失。修复：新增 `src/ui/clipboard.py::put_excel_clipboard(rows)`（HTML `mso-number-format:\@` + TSV 双格式，从 main_window 抽出共用）；`result_table` 新增 `_CopySafeTextDelegate`（createEditor 装 eventFilter 拦截 Ctrl+C → `put_excel_clipboard([[selected_text]])` 后吞掉默认复制）。单元格/区域复制（`_copy_all`/`_copy_selected`）与编辑器复制共用同一双格式实现。
- ✅ **回归**：test_stage6 新增第 7 项断言（QTest 单击→编辑器出现且 `selectedText()==NAME`、编辑器内 Ctrl+C → 剪贴板 HTML 含 `mso-number-format:\@` + NAME）；test_stage6 / test_ui_smoke / test_import_stage5 全过。
- ✅ **重新打包并实测通过（2026-08-12）**：① 单击结果行单元格 → 文字全选高亮、可直接拖动选文字；② 选中身份证号按 Ctrl+C → Excel 完整 18 位（非科学计数法）；③ 启动速度可接受；④ exe 内粘贴图片识别正常（旧问题复测通过）。

### 阶段 8：发票识别（✅ 2026-08-12，打包实测通过）
- ✅ **轻量文档预处理 `preprocess_document`**（`src/utils/preprocess.py`）：仅解码（unicode-safe）+ 只放大不缩小。**实测身份证全管线对整页票据有害**：误判 90° 旋转 + 透视裁剪破坏版面，OCR 全乱码；原图直接 OCR 效果好。发票必须跳过方向校正/透视矫正/背景去除。
- ✅ **`InvoiceProcessor`**（`src/processors/invoice.py`，card_type="invoice"）：锚点提取 5 字段。样张（江苏省医疗收费票据）映射：`姓名←交款人`、`发票代码←票据代码(32060226)`、`发票号码←票据号码(0000243741)`、`金额←(小写)4,180.76`（z 确认取小写数字）、`开票时间←开票日期(2026-08-12)`。同块剥离 + 邻近块几何兜底；同时兼容增值税票措辞（发票代码/发票号码/价税合计/开票时间/购方名称）；金额大写兜底、日期归一 YYYY-MM-DD。
- ✅ **UI 复用 `RecognitionPage`**（`src/ui/recognition_page.py`）：把 main_window 单页识别逻辑整体抽出（拖拽区/按钮/进度/表格/底栏/导入/识别/结果管理），按文档类型参数化。`MainWindow` 瘦身为薄壳：双标签页（身份证识别 / 发票识别）均启用、各自独立工作区；全局 Ctrl+C/Ctrl+V 派发到激活页；**测试兼容别名**（result_table 等指向 idcard 页）→ 三个旧测试零改动。
- ✅ **列头参数化**：`ResultTable(columns=None)`（默认身份证列）；列与字段 key 常量入 `src/config.py`（`ID_CARD_COLUMNS/FIELDS`、`INVOICE_COLUMNS/FIELDS`）。
- ✅ **回归全过**：新增 `scripts/test_invoice.py` 8 项（同块/分离块/缺失/增值税措辞/日期归一/版面不变/真实样张 E2E/UI 标签+列头）；test_stage6 / test_ui_smoke（更新发票标签启用+列头断言）/ test_import_stage5 / test_idcard_processor / test_preprocess 全过。
- ✅ **真实样张 E2E 全对**：`唐洪发 / 32060226 / 0000243741 / 4,180.76 / 2026-08-12`，missing 空。offscreen 完整流程（后台预热+服务识别+QEventLoop 阻塞等待）5.6s 出表全对。
- ✅ `.gitignore` 加 `发票样张/`（医疗票据属敏感数据，沿用身份证样张先例）。
- ✅ **打包实测通过（2026-08-12）**：`build_onefile.bat` 重打包后，切到「发票识别」标签拖入样张 → 5 字段正确且缩图提速；旧遗留「exe 内粘贴识别 60s 无结果」一并复测通过。
- ✅ **发票速度优化（2026-08-12，已实施）**：调研见 `scripts/bench_invoice_scale.py`（样张 1280×1707 原图直出 3.67s，缩到 1300px=2.56s 快约 30%、5 字段全对；1100px 起错字丢字段，1300px 为安全下限）。实施：`config.py` 加 `PREPROCESS_DOC_MAX_SIDE=1300`；`preprocess.py` 新增 `_fit_to_max_side`（只缩小不放大，长边超限才缩）并让 `preprocess_document` 改用它（原用 `_resize_to_max_side` 只放大不缩小，大图以全分辨率喂 OCR）。身份证链路不受影响（走 `preprocess_image`，卡片本就放大）。test_invoice（缩图断言更新为「长边 ≤1300」+ 真实样张 E2E 5 字段全对）/ test_preprocess（身份证主链路零回归）全过。
- 📌 **踩坑记录**：offscreen 下 `QTest.qWait` 忙轮询会让子线程 paddle predict 卡死 >60s（决策 12 已知坑，非真实 bug；真实 app.exec() 空闲阻塞不受影响）；等待真实识别用 QEventLoop + 信号阻塞（本次完整流程验证 5.6s 通过）。另：用 `time.sleep` 等 `_engine_ready` 不会触发 QTimer 预热（事件循环不跑，singleShot 不 fire），需用 QEventLoop 或 app.processEvents。


## 五、全局验收标准（PRD §5.2，自动化 A-G：16/16 全过）
1. 微信拖拽识别 2. 四种导入方式 3. 批量10张进度条 4. 复制粘贴Excel分列 5. 双击编辑 6. 断网运行 7. 无数据残留
> A-G 自动化覆盖了 1(改剪贴板/文件对话框) 2 3 4 5 7；微信拖拽(1)与断网(6)需人工或特殊方案，见阶段 7 待办。

## 六、环境与常用命令

```powershell
# Python 解释器
.\.venv\Scripts\python.exe

# 运行/测试
python src\app.py                                    # 骨架入口
python scripts\smoke_test_ocr.py                     # OCR 冒烟
python scripts\test_ocr_engine.py                    # 引擎自测
python scripts\bench_ocr.py v6_tiny                  # 模型基准（v6_medium/v6_small/v6_tiny/v5_mobile）
python scripts\test_preprocess.py                    # 预处理自测（含 OCR 联调）
python scripts\test_idcard_processor.py              # 字段提取自测
python scripts\test_ui_smoke.py                      # UI 框架自测（offscreen）
python scripts\test_import_stage5.py                 # 导入方式自测（offscreen）
python scripts\test_stage6.py                        # 阶段6 批量识别+结果管理自测（offscreen）
python src\app.py                                    # 启动 GUI 主窗口
```

- 模型缓存：`C:\Users\13689\.paddlex\official_models\`（v6_tiny_det/rec 已下载，medium/small/v5_mobile 也已缓存）
- 例图：`assets/samples/idcard_sample.jpg`（876×576，`张建邺/男/321322200406170832`）

## 七、git 提交历史
| hash | 说明 |
|------|------|
| 02b53cf | 阶段0：骨架、venv、依赖、冒烟测试 |
| 35ba4ba | 阶段0：进度表 + spec-01 环境约束 |
| 0621a39 | 阶段1：OcrEngine（v6_tiny、惰性加载、unicode-safe）、性能 0.65s |
| 7b41f47 | 阶段2：预处理管线（归一化/方向校正/透视矫正/裁剪）、验收 A-2 全过 |
| 8fbebfa | docs：progress.md 记录阶段2 hash |
| 4bb2eff | 阶段3：IDCardProcessor 三字段提取、验收 A-3 全过 |
| b090d80 | docs：progress.md 记录阶段3 hash |
| c0a3af5 | 阶段4：PySide6 主窗口框架、验收 A-4 全过 |
| 31884f4 | 阶段5：四种图片导入 + 拖拽高亮、验收 A-5 全过 |
| 743a8bc | 阶段6：批量识别 + 结果管理、验收 A-6 全过（threading.Thread + 主线程 warmup 解决 QThread/paddle 卡死与冷加载） |
| 46b14f7 | 启动优化（warmup 延后 200ms）、Excel 身份证号加引号防科学计数法、表格拖拽多选 |
| （未提交） | onedir 打包改造：`jc.spec`、`src/config.py` onedir 路径、`src/app.py` 窗口名 jc、`scripts/build_onedir.bat` / `test_onedir.bat`，构建待执行 |
