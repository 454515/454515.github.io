# spec-00：项目初始化与环境搭建

| 项 | 内容 |
|----|------|
| 所属阶段 | 阶段 0 |
| 对应 Skill | `stage-0-init` |
| 依赖 | 无（项目起点） |
| 对应 PRD | §4 技术选型 |

## 1. 阶段目标

搭建可运行的项目地基：目录骨架、Python 虚拟环境、全部依赖安装到位，并用一张样例身份证图验证 PaddleOCR 引擎能完成真实识别（冒烟测试）。本阶段**不实现任何业务逻辑**。

## 2. 范围

**包含**：
- 项目目录骨架（含 `src/` 各分层包）
- 虚拟环境 `.venv` 与依赖清单 `requirements.txt`
- 配置模块 `src/config.py`（模型路径、常量）
- 程序入口 `src/app.py`（占位可运行）
- PaddleOCR 引擎可用性冒烟测试

**不包含**：任何识别、预处理、字段提取、UI 逻辑。

## 3. 技术方案

- 语言：Python 3.10+（64 位）
- 包管理：`venv` + `pip` + `requirements.txt`
- 依赖版本以安装时可用的最新稳定版为准，记录在汇报中

## 4. 目录结构与依赖清单

### 4.1 目录结构

```
src/
├── __init__.py
├── app.py               # 程序入口（占位）
├── config.py            # 全局配置：路径、模型路径、常量
├── ui/                  # 界面层（阶段 4 使用）
├── core/                # 业务逻辑层（阶段 6 使用）
├── ocr/                 # OCR 引擎层（阶段 1 使用）
├── processors/          # 字段提取层（阶段 3 使用）
└── utils/               # 工具层（阶段 2 使用）
```

各分层包先创建空包（含 `__init__.py`），后续阶段逐个填充。

### 4.2 依赖清单（requirements.txt）

```
PySide6
paddlepaddle
paddleocr
opencv-python
pyinstaller
```

> Paddle 安装若遇网络问题，使用 `-i https://pypi.tuna.tsinghua.edu.cn/simple` 镜像源。

### 4.3 模型目录（models/）

PaddleOCR 首次运行自动下载模型至 `~/.paddleocr/`。若网络受限，可手动放置模型到 `models/` 并在 `src/config.py` 配置。阶段 0 采用**自动下载**默认路径即可。

## 5. 冒烟测试规格

- 输入：1 张清晰的身份证样例图（`assets/samples/idcard_sample.jpg`，阶段 0 自备）
- 脚本：`scripts/smoke_test_ocr.py`
- 逻辑：加载 PaddleOCR → 识别样例图 → 打印识别到的文字块数量与前 3 条文字
- 通过标准：识别出 ≥ 1 条有效文字块，脚本正常退出

## 6. 验收标准

| # | 验收项 | 判定 |
|---|--------|------|
| A-0-1 | `python src/app.py` 可运行，输出占位信息，退出码 0 | ✅ |
| A-0-2 | `requirements.txt` 全部依赖在 `.venv` 中可导入 | ✅ |
| A-0-3 | 冒烟脚本识别样例图成功，输出文字块 | ✅ |
| A-0-4 | 目录结构与 4.1 一致 | ✅ |

## 7. 交付物

- `requirements.txt`、`src/` 骨架、`scripts/smoke_test_ocr.py`
- 汇报：依赖版本列表、冒烟测试输出、Paddle 模型下载/放置说明
