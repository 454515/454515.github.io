# spec-05：图片导入方式

| 项 | 内容 |
|----|------|
| 所属阶段 | 阶段 5 |
| 对应 Skill | `stage-5-image-import` |
| 依赖 | 阶段 4（主窗口） |
| 对应 PRD | §2.1.2 图片导入（四种方式全 P0）、§2.2.2 拖拽反馈 |

## 1. 阶段目标

实现四种图片导入方式：**微信拖拽、文件选择、剪贴板粘贴（Ctrl+V）、文件夹导入**，外加拖拽反馈（边框高亮、文字变色）。导入的图片进入待识别队列（识别由阶段 6 接入）。

## 2. 范围

**包含**：
- 拖拽单/多张图片导入
- 拖拽文件夹导入（递归扫描 jpg/png）
- 「选择文件」按钮 + QFileDialog
- 剪贴板粘贴（Ctrl+V）
- 拖拽高亮反馈
- 导入队列管理（去重、非图片过滤、友好提示）

**不包含**：真实识别、进度条、复制/编辑（阶段 6）。

## 3. 导入队列 `src/core/import_queue.py`

```python
@dataclass
class ImportedImage:
    path: str
    filename: str   # 显示名

class ImportQueue:
    def add_images(self, paths: list[str]) -> list[str]: ...  # 返回过滤后接受的路径
    def add_folder(self, folder: str) -> list[str]: ...       # 递归扫描并加入
    def items(self) -> list[ImportedImage]: ...
    def clear(self) -> None: ...
```

**规则**：
- 扩展名白名单：`.jpg .jpeg .png .bmp`（大小写不敏感）。
- 去重：已存在的相同路径不重复加入。
- 过滤：白名单之外的（如 `.txt`）加入 `rejected` 列表用于提示，不崩溃。
- 排序：文件夹扫描结果按文件名字母序稳定入队。

## 4. 四种导入方式规格

### 4.1 微信拖拽（P0）
- 重写 `DropArea` 的 `dragEnterEvent` / `dropEvent`。
- 区分拖入内容：文件 URL 列表（`mimeData().urls()`）。
- 单 URL 为目录 → 走文件夹导入；为文件 → 按扩展名过滤加入队列。
- 微信图片可能是临时缓存路径，读取后直接进队列，不持久化。

### 4.2 文件选择（P0）
- 「选择文件」按钮 → `QFileDialog.getOpenFileNames`，过滤器含 jpg/png/bmp。
- 多选结果加入队列。

### 4.3 剪贴板粘贴（P0）
- 窗口激活（`keyPressEvent` 或窗口级快捷键）监听 `Ctrl+V`。
- 读取 `QApplication.clipboard()`：优先取图片 `mimeData().hasImage()`，将图片 `save()` 到临时目录后入队。
- 剪贴板非图片时不提示、静默忽略。

### 4.4 文件夹导入（P0）
- 拖入目录时递归遍历，收集所有白名单扩展名文件入队。

## 5. 拖拽反馈（P1）

- `dragEnterEvent` 期间：`DropArea` 边框高亮变色、提示文字变色（如「释放即可识别」）。
- 拖拽离开/放下：恢复默认样式。
- 样式用 QSS 实现（如 `border: 2px dashed #3a9; background: rgba(...)`）。

## 6. 容错与提示

- 导入非图片文件：友好提示（可弹 `QMessageBox` 或状态提示），不崩溃。
- 拖入损坏图片：允许进队列，识别阶段处理（阶段 6 的失败跳过逻辑兜底）。

## 7. 自测规格

1. 从资源管理器拖拽 2 张图片 → 入队成功，顺序正确。
2. 拖拽文件夹（含嵌套子目录 jpg/png）→ 全部入队，字母序。
3. 「选择文件」多选 → 入队成功。
4. Ctrl+V 粘贴剪贴板截图 → 入队成功。
5. 拖入 `.txt` 文件 → 被拒绝，友好提示，不崩溃。
6. 重复拖入同一张图 → 只入队一次。

## 8. 验收标准

| # | 验收项 | 判定 |
|---|--------|------|
| A-5-1 | 四种导入方式全部可用（P0） | ✅ |
| A-5-2 | 拖拽反馈高亮 + 文字变色生效 | ✅ |
| A-5-3 | 非图片/损坏文件提示友好、不崩溃 | ✅ |
| A-5-4 | 去重与排序规则生效 | ✅ |
| A-5-5 | 自测 6 项全部通过 | ✅ |

## 9. 交付物

- `src/ui/drop_area.py`（拖拽 + 高亮）、`src/core/import_queue.py`、按钮/粘贴逻辑接入 `main_window.py`
- 汇报：四种方式自测结果
