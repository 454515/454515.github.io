# spec-01：OCR 引擎层

| 项 | 内容 |
|----|------|
| 所属阶段 | 阶段 1 |
| 对应 Skill | `stage-1-ocr-engine` |
| 依赖 | 阶段 0（引擎可用） |
| 对应 PRD | §4.2 OCR 引擎层、§3.1 性能 |

## 1. 阶段目标

在 `src/ocr/` 下封装 PaddleOCR，向上层提供**通用的、与具体卡证类型无关**的识别接口。上层只依赖本层接口，不直接接触 PaddleOCR。

## 2. 范围

**包含**：
- `OcrEngine` 类（加载 / 识别 / 释放）
- 统一结果数据模型 `OcrResult` / `OcrWord`
- 异常与错误处理
- 引擎惰性加载、全局唯一实例

**不包含**：图片预处理、字段提取、任何身份证业务逻辑。

## 3. 接口规格

### 3.1 `src/ocr/models.py` — 数据模型

```python
@dataclass
class OcrWord:
    text: str          # 识别文本
    confidence: float  # 置信度 0~1
    box: list          # 四点坐标 [[x,y],[x,y],[x,y],[x,y]]
    # 注：PaddleOCR 识别结果中的 [box, text, score]

@dataclass
class OcrResult:
    words: list[OcrWord]   # 按识别顺序排列的文字块
    image_path: str        # 源图片路径
    elapse_ms: float       # 识别耗时（毫秒）
    error: str | None      # None 表示成功，否则为错误描述
```

### 3.2 `src/ocr/engine.py` — 引擎封装

```python
class OcrEngine:
    def __init__(self, config) -> None: ...      # 仅保存配置，不加载模型
    def recognize(self, image_path: str) -> OcrResult: ...  # 首次调用时加载模型
    def close(self) -> None: ...                 # 释放模型资源
```

**规则**：
- **惰性加载**：`recognize()` 首次被调用时才初始化 PaddleOCR 实例；`import` 与 `__init__` 不加载模型。
- **全局唯一**：引擎实例由模块级单例提供，避免重复加载模型。
- **线程安全**：`recognize()` 需能在工作线程中调用（阶段 6 的识别线程会用到）；内部不加持锁的共享状态。
- **错误处理**：图片不存在 / 无法解码 / Paddle 异常时，`recognize()` 返回 `OcrResult.error` 非空，**不抛裸异常**。
- **识别参数**：`lang='ch'`、`use_angle_cls=True`（启用方向分类，配合阶段 2 的预处理兜底）。
- **性能**：普通 CPU 环境单张识别耗时 ≤ 1.5s（实测记录，图片为阶段 0 样例）。

### 3.3 环境要求（阶段 0 实测结论，必须遵守）

在 `import paddle` / `import paddleocr` **之前**，必须设置环境变量：

```python
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
```

原因：paddlex 默认启用 oneDNN（`PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT` 默认 `True`），而
paddlepaddle 3.3.1 在 Windows 上触发 oneDNN 指令 bug
（`NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support ... oneDNN`），
文本检测推理必然失败。实测禁用后正常。

位置：`engine.py` 模块顶层、任何 paddle 导入之前用 `os.environ.setdefault` 设置，
不依赖外部环境。冒烟脚本 `scripts/smoke_test_ocr.py` 已采用同样做法。

另外注意 paddleocr 3.x API 变更：
- `use_angle_cls` / `cls=True` 已移除，改用 `use_doc_orientation_classify` /
  `use_doc_unwarping` / `use_textline_orientation`，推理用 `predict()` 而非 `ocr()`。
- 为满足性能要求，引擎应禁用文档矫正与方向分类
  （`use_doc_unwarping=False, use_doc_orientation_classify=False, use_textline_orientation=False`），
  方向校正由阶段 2 预处理管线负责。

### 3.4 模型选型与性能实测（阶段 1 结论）

在禁用 oneDNN 的 CPU（本机）上，对 876×576 样例图实测热态耗时：

| 模型变体 | 热态耗时 | words | 结论 |
|----------|---------|-------|------|
| PP-OCRv6_medium | ~9.1s | 12 | 超预算 |
| PP-OCRv6_small | ~1.75s | 10 | 超预算 |
| **PP-OCRv6_tiny** | **~0.55-0.72s** | 11 | ✅ 唯一达标 |
| PP-OCRv5_mobile | ~3.2s | 12 | 超预算 |

**决策**：默认使用 `PP-OCRv6_tiny_det` + `PP-OCRv6_tiny_rec`（`src/config.py` 中
`OCR_DET_MODEL` / `OCR_REC_MODEL`，引擎构造可覆盖）。

**质量补偿（重要）**：tiny 在原图上可能漏检小字（实测漏「男」），将输入放大到
**1.5x（约 1314×864）** 后「性别男」等字段恢复完整，实测 1094ms 仍 ≤ 1.5s。
因此阶段 2 预处理管线必须加入**输入尺寸归一化（放大至最长边约 1300px）**，
引擎层保持纯净（不做缩放）。

## 4. 自测规格

`scripts/test_ocr_engine.py`：
1. 首次 `recognize()` 前断言模型未加载（不触发网络/磁盘加载日志）。
2. 对阶段 0 样例图 `recognize()`，断言 `error is None` 且 `words` 非空。
3. 对损坏图片（如空文件）`recognize()`，断言 `error` 非空、不抛异常。
4. 打印单张 `elapse_ms`。

## 5. 验收标准

| # | 验收项 | 判定 |
|---|--------|------|
| A-1-1 | `OcrEngine` 提供加载/识别/释放三动作，接口如 §3.2 | ✅ |
| A-1-2 | 识别返回 `OcrResult`，上层不接触 PaddleOCR 类型 | ✅ |
| A-1-3 | 惰性加载生效：导入与构造不加载模型 | ✅ |
| A-1-4 | 自测脚本 4 项全部通过 | ✅ |
| A-1-5 | 实测单张识别 ≤ 1.5s（记录数值） | ✅ |

## 6. 交付物

- `src/ocr/models.py`、`src/ocr/engine.py`、`scripts/test_ocr_engine.py`
- 汇报：接口定义、实测耗时、异常处理说明
