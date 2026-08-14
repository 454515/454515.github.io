# spec-02：图像预处理与矫正

| 项 | 内容 |
|----|------|
| 所属阶段 | 阶段 2 |
| 对应 Skill | `stage-2-image-preprocess` |
| 依赖 | 阶段 1（联调用） |
| 对应 PRD | §2.1.1 方向校正/透视矫正/背景去除 |

## 1. 阶段目标

在 `src/utils/` 下实现图片预处理管线，为 OCR 提供最利于识别的图片。核心三项：**方向校正**、**透视矫正**、**背景去除**。

## 2. 范围

**包含**：
- 方向校正（旋转 0/90/180/270）
- 透视矫正（四边形检测 + 拉正）
- 背景去除（裁剪身份证区域）
- 统一管线入口

**不包含**：调用 OCR、文字识别逻辑。

## 3. 功能规格

### 3.1 数据模型 `src/utils/preprocess_models.py`

```python
@dataclass
class PreprocessResult:
    image: np.ndarray          # 处理后的 BGR 图片
    rotation_angle: int        # 校正旋转角度：0/90/180/270
    quad: list | None          # 检测到的身份证四边形四点，None 表示未检测到
    found_card: bool           # 是否检测到身份证区域
    error: str | None          # None 表示成功
```

### 3.2 管线入口 `src/utils/preprocess.py`

```python
def preprocess_image(image_path: str) -> PreprocessResult: ...
```

调用顺序：**输入尺寸归一化 → 方向校正 → 透视矫正 → 背景去除（裁剪）**。

> **输入尺寸归一化**（阶段 1 实测结论）：PP-OCRv6_tiny 原图可能漏检小字
> （如「性别男」中的「男」），把输入放大到 **最长边约 1300px（约 1.5x）** 后
> 字段恢复完整，且识别仍 ≤1.5s。此步骤为预处理管线第一步，放大倍数按
> `max_side / max(原图宽高)` 计算，仅放大不缩小。

### 3.3 各步骤规格

#### 3.3.1 方向校正 `correct_orientation(image) -> (rotated_image, angle)`
- 原理：优先用边缘/轮廓长边方向分析 + 文本方向兜底，返回 0/90/180/270。
- 保证：任意角度输入，输出正面朝上。

#### 3.3.2 透视矫正 `perspective_correct(image) -> (corrected, quad, found)`
- 流程：灰度 → 高斯模糊 → 边缘检测（Canny）→ 轮廓查找 → 取面积最大、近似为四边形的轮廓作为身份证边框。
- 规则：未找到有效四边形时 `found=False`，原图直通，不强行矫正。
- 输出：四点透视变换拉正，身份证边缘尽量水平。

#### 3.3.3 背景去除 `extract_foreground(image, quad) -> cropped`
- 仅当 `found=True` 时按四边形裁剪出身份证区域。
- 失败兜底：裁剪失败则返回原图，不阻断后续流程。

### 3.4 容错规则

- 图片无法解码：返回 `error` 非空。
- 管线任何一步失败：降级为「原图直通」，`error=None` 但 `found_card=False`，**不抛异常**，确保 OCR 总有机会执行。

## 4. 自测规格

`scripts/test_preprocess.py`，准备 4 张样例图：
1. 正向清晰图 → 预期 `found_card=True`、方向不变。
2. 旋转 90°/180° 图 → 预期校正回正向。
3. 倾斜/仰拍图 → 预期透视矫正后边缘水平。
4. 非身份证图（如风景照）→ 预期不崩溃，`found_card` 可能为 False。

将管线输出与 OCR 引擎联调一次：预处理后识别结果不劣于原图识别。

## 5. 验收标准

| # | 验收项 | 判定 |
|---|--------|------|
| A-2-1 | 任意角度图输出正向朝上（4 张样例自测通过） | ✅ |
| A-2-2 | 倾斜/仰拍图透视矫正后身份证边缘基本水平 | ✅ |
| A-2-3 | 非身份证图不崩溃，`found_card` 正确标记 | ✅ |
| A-2-4 | 管线任何失败均降级直通，不抛异常 | ✅ |
| A-2-5 | 与 OCR 联调：预处理后识别不劣化 | ✅ |

## 6. 交付物

- `src/utils/preprocess.py`、`src/utils/preprocess_models.py`、`scripts/test_preprocess.py`
- 汇报：各步骤实现原理、自测效果（可附样例图）
