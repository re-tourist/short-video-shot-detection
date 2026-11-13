# Short Video Shot Detection

短视频镜头边界检测工具，支持 PySceneDetect AdaptiveDetector 和 TransNet V2。

本项目用于 AI 应用开发岗位的技术测试，目标是在有限开发时间内，实现准确性可验证、能够批量运行的镜头切分程序。

## 1. 项目目标

输入若干短视频，自动识别镜头边界，并输出：

- 每个镜头的起止时间。
- 每个镜头的一张预览图。
- 结构化切分结果。
- 单视频处理失败的错误信息。

程序应支持一次运行处理多个视频，且单个视频失败不影响其他视频。

本项目只处理镜头边界检测（Shot Boundary Detection），不涉及进一步的语义片段划分或视频重新组合。

## 2. 技术方案

两个检测器可独立运行。

| 方案                 | 实现                           | 用途               |
| -------------------- | ------------------------------ | ------------------ |
| Traditional Baseline | PySceneDetect AdaptiveDetector | 已实现，采用默认检测参数 |
| Deep Learning        | TransNet V2 (PyTorch)          | 预训练模型，使用 CPU 推理 |

**选型原则：**

1. 优先使用现有成熟实现，不重新训练模型。
2. 两个算法独立输出，使用相同标准验证。
3. 根据真实测试结果选择最终默认检测器。
4. 暂不使用 AutoShot 或复杂融合算法。

## 3. 项目结构

当前目录结构：

- `main.py`：批处理入口及主要逻辑。
- `requirements.txt`：运行依赖。
- `transnet_detector.py`、`requirements-transnetv2.txt`：TransNet V2 接入及额外依赖。
- `review_cuts.py`：从两组检测结果生成本地人工核查材料。
- `.gitignore`：排除本地环境、视频及运行产物。
- `AGENTS.md`：AI 辅助开发规则。
- `data/`：本地输入视频，不提交。
- `outputs/`：镜头结果与预览图，不提交。

## 4. 运行方法

使用 Python 3.10 或以上版本，已在 Windows / Python 3.12.8 验证。建议在虚拟环境中安装依赖。

```bash
python -m pip install -r requirements.txt
```

将视频放入 `data/`，例如 `sample-01.mp4`、`sample-02.mp4`、`sample-03.mp4`。

在仓库根目录运行。

```bash
python main.py --input-dir data --output-dir outputs/adaptive --detector adaptive
```

运行 TransNet V2 前，按[部署与对照记录](docs/detector-comparison.md)安装 PyTorch 并准备 `models/` 下的推理代码和权重。

```bash
python main.py --input-dir data --output-dir outputs/transnetv2 --detector transnetv2
```

程序按文件名顺序处理输入目录第一层的 `.mp4` 文件，扩展名不区分大小写。每条视频的结果位于 `<输出目录>/<视频文件名去掉扩展名>/`，其中 `shots.json` 记录镜头区间，`shot_0001.jpg` 等文件保存各镜头时间中点附近的帧。使用不同的输出目录可保留两组结果。

例如，一条时长 60 秒的视频有三个镜头时，`outputs/adaptive/sample-01/shots.json` 如下。

```json
{
  "video": "sample-01.mp4",
  "detector": "adaptive",
  "duration_seconds": 60.0,
  "shots": [
    {"index": 1, "start_seconds": 0.0, "end_seconds": 20.0, "preview": "shot_0001.jpg"},
    {"index": 2, "start_seconds": 20.0, "end_seconds": 40.0, "preview": "shot_0002.jpg"},
    {"index": 3, "start_seconds": 40.0, "end_seconds": 60.0, "preview": "shot_0003.jpg"}
  ]
}
```

时间单位为秒。镜头使用左闭右开区间 `[start_seconds, end_seconds)`，相邻镜头共用同一个边界。无切点的视频会输出一个覆盖全片的镜头。`preview` 是相对于 `shots.json` 所在目录的路径。

程序在终端报告每条视频的镜头数或失败原因，最后汇总成功数、失败数及成功视频的总镜头数。全部成功时退出码为 `0`，有单视频失败时继续跑完批次并返回 `1`，输入目录不存在或没有 MP4 时返回 `2`。

## 5. 结果验证

三条样片中，AdaptiveDetector 检出 100 个镜头，TransNet V2 检出 77 个。两组区间均完整连续，预览图均可解码。见[双算法对照](docs/detector-comparison.md)和[基线结果](docs/baseline-results.md)。

运行 `python review_cuts.py` 可在 `outputs/cut-review/` 生成核查表和 53 张分歧切点前后帧图。按[人工核验说明](docs/detector-comparison.md#人工核验)填写标签，并观看完整连续区间以发现共同漏检。

## 6. 开发状态

- 已完成 PySceneDetect 基线及真实样片工程验证。
- 两种检测器可运行，核查材料已生成。CLI 暂沿用 `adaptive` 默认值，最终选型待人工核验。

## 7. 设计取舍与已知限制

本项目优先考虑快速交付和可复现性，不引入模型训练、大规模超参数搜索或复杂融合机制。

传统检测器可能对渐变转场和相似镜头切换不敏感。可变帧率视频的末帧时长和中点定位依赖 OpenCV 后端，实际精度仍待验证。

实际验证发现的问题与最终算法选择依据，将在完成实验后补充。

## 8. AI 辅助开发说明

项目使用 Codex 辅助开发，主要规则见 `AGENTS.md`。

- **Keep It Simple** 使用独立脚本读取现有 JSON，用 OpenCV 导出相邻帧，复用现有依赖。
- **Verify What Matters** 把预测分歧整理成人工核查清单，并要求观看连续区间来发现共同漏检。
- **Keep Delivery Reproducible** 固定推理代码版本、记录权重校验值，并用 Git 忽略规则排除私有视频、权重和核查产物。

## 9. 素材使用说明

测试视频仅用于本次招聘测试，不公开上传原始视频及可还原其内容的预览图等派生素材。

公开仓库仅包含代码、配置及适宜公开的说明文档。
