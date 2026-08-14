# spec-03：身份证字段提取

| 项 | 内容 |
|----|------|
| 所属阶段 | 阶段 3 |
| 对应 Skill | `stage-3-field-extraction` |
| 依赖 | 阶段 1（OcrResult）、阶段 2（可选用） |
| 对应 PRD | §2.1.1 字段提取/格式校验 |

## 1. 阶段目标

在 `src/processors/` 下实现 `IDCardProcessor`：从 OCR 文字块中提取**姓名、性别、公民身份号码**，并做格式校验（18 位、末位 X 统一大写）。预留 `BaseProcessor` 抽象，供后续发票等处理器复用。

## 2. 范围

**包含**：
- 处理器抽象基类
- IDCardProcessor 字段提取（姓名/性别/身份证号）
- 身份证号格式校验
- 字段缺失容错

**不包含**：UI、图片处理、OCR 调用（吃阶段 1 的结果）。

## 3. 数据模型 `src/processors/models.py`

```python
@dataclass
class CardResult:
    card_type: str            # 卡证类型："idcard"
    fields: dict[str, str]    # {"name":..., "gender":..., "id_number":...}
    missing: list[str]        # 缺失字段名列表
```

## 4. 接口规格 `src/processors/base.py` / `src/processors/idcard.py`

```python
class BaseProcessor(ABC):
    @abstractmethod
    def process(self, ocr_result: OcrResult) -> CardResult: ...

class IDCardProcessor(BaseProcessor):
    def process(self, ocr_result: OcrResult) -> CardResult: ...
```

处理器注册表 `src/processors/registry.py`：`card_type -> processor` 映射，供上层按需获取。

## 5. 字段提取规则

### 5.1 姓名 `name`
- 优先：找到含「姓名」关键词的文字块，取其右侧/后方的中文块。
- 兜底：按 OCR 坐标行匹配「姓名」所在行，提取该行中紧随的非标签文字。
- 校验：为中文组合（1~4 个汉字），否则记入 `missing`。

### 5.2 性别 `gender`
- 匹配关键词「男 / 女」，返回「男」或「女」。
- 未命中记入 `missing`。

### 5.3 身份证号 `id_number`
- 正则：`\d{17}[\dXx]`。
- 提取后校验：长度 18 位；末位 `x` → 统一转为大写 `X`。
- 多个候选命中时取置信度最高者。

### 5.4 格式校验 `validate_id_number(id_no) -> bool`
- 规则：18 位，末位为数字或大写 X，前 17 位为数字。
- 校验失败仅标记，**不阻断**流程，结果仍入表（方便用户手动改）。

## 6. 准确率要求

- 清晰正常身份证图：三字段提取准确率 ≥ 98%。
- 自测用 ≥ 20 张样例 OCR 结果（可脚本构造标注集），统计提取准确率并记录。

## 7. 自测规格

`scripts/test_idcard_processor.py`：
1. 构造含标准三字段的 OCR 文字块 → 断言三字段提取正确。
2. 构造末位小写 x 的身份证号 → 断言转大写 X。
3. 构造缺失姓名/性别的文字块 → 断言 `missing` 正确、不抛异常。
4. 竖排版身份证文字块样例 → 断言仍能提取。

## 8. 验收标准

| # | 验收项 | 判定 |
|---|--------|------|
| A-3-1 | 三字段提取正确，样例集准确率 ≥ 98% | ✅ |
| A-3-2 | 末位 x 统一转大写 X | ✅ |
| A-3-3 | 字段缺失返回空串 + 记入 `missing`，不崩溃 | ✅ |
| A-3-4 | 横版/竖版布局均能提取 | ✅ |
| A-3-5 | `registry` 可注册/获取处理器 | ✅ |

## 9. 交付物

- `src/processors/models.py`、`base.py`、`idcard.py`、`registry.py`
- `scripts/test_idcard_processor.py`
- 汇报：提取规则、准确率统计
