---
name: stage-0-init
description: 阶段 0：项目初始化与环境搭建。创建项目骨架、虚拟环境、安装依赖，验证 PaddleOCR 引擎可用。仅在进入阶段 0 时调用。
---

# 阶段 0：项目初始化与环境搭建

## 目标
搭建可运行的项目骨架：目录结构、Python 虚拟环境、全部依赖安装到位，并验证 OCR 引擎能完成一次真实识别（冒烟测试），为后续阶段打好地基。

## 前置条件
- 已阅读 [agent.md](../../../agent.md) 第 4、5 节（开发原则、阶段总览）。
- 本机已安装 Python 3.10+（64 位）。

## 执行步骤

1. **读 spec**：先完整阅读 [spec-00-项目初始化.md](../../../docs/specs/spec-00-项目初始化.md)，按其「目录结构」「依赖清单」执行。
2. **创建虚拟环境**：在项目根目录执行 `python -m venv .venv`。
3. **安装依赖**：激活虚拟环境后按 spec 的 requirements 安装（PySide6、paddlepaddle、paddleocr、opencv-python、pyinstaller 等）。
4. **创建源码骨架**：按 spec 目录结构创建 `src/` 下各模块空包，每个包放 `__init__.py`。
5. **创建配置与入口**：建立 `src/app.py`（仅打印占位信息，验证包可导入即可）、`src/config.py`（模型路径等配置常量）。
6. **冒烟测试**：运行 spec 定义的冒烟脚本，用一张身份证样例图验证 PaddleOCR 能识别出文字。
7. **验收**：对照 spec「验收标准」逐条自检。

## 完成标准
- [ ] `python src/app.py` 可运行，不报错。
- [ ] 冒烟测试输出 PaddleOCR 识别到的文字块，引擎可用。
- [ ] 目录结构与 spec 一致。
- [ ] 已向用户汇报：依赖版本、冒烟测试结果、注意事项（如 Paddle 安装镜像）。

## 注意事项
- PaddleOCR 首次运行会自动下载模型，若网络受限请预先手动放置模型到 `models/` 目录并配置 `src/config.py`。
- 安装 paddlepaddle 遇到镜像问题时，可提示使用国内镜像源安装。
- 不要在阶段 0 实现任何业务逻辑，只搭地基。
