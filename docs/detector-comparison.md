# AdaptiveDetector 与 TransNet V2 对照

## 部署与运行

使用 Python 虚拟环境。在仓库根目录执行以下 PowerShell 命令。AdaptiveDetector 单独运行时只需安装 `requirements.txt`。

```powershell
python -m pip install torch==2.9.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-transnetv2.txt
New-Item -ItemType Directory -Force models | Out-Null
$rev = '85cef72af9a916bdfd7cc94a670c9cdfbf12d1ed'
Invoke-WebRequest "https://raw.githubusercontent.com/soCzech/TransNetV2/$rev/inference-pytorch/transnetv2_pytorch.py" -OutFile models/transnetv2_pytorch.py
python -m pip download --no-deps --index-url https://pypi.org/simple --dest models transnetv2-pytorch==1.0.5
@'
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

directory = Path("models")
wheel = directory / "transnetv2_pytorch-1.0.5-py3-none-any.whl"
if sha256(wheel.read_bytes()).hexdigest() != "9f8e72085526aaa95383d219b6750b1fa45b865fd10d840cafa12ef78ab3bf27":
    raise ValueError("Unexpected wheel SHA-256")
with ZipFile(wheel) as archive:
    member, = [name for name in archive.namelist()
               if Path(name).name == "transnetv2-pytorch-weights.pth"]
    (directory / Path(member).name).write_bytes(archive.read(member))
'@ | python -
python main.py --input-dir data --output-dir outputs/adaptive --detector adaptive
python main.py --input-dir data --output-dir outputs/transnetv2 --detector transnetv2
```

网络结构来自论文作者的 PyTorch 推理文件。作者的流程要求将 TensorFlow 权重转换为 PyTorch。本项目从固定版本的第三方 wheel 提取已转换权重，用 `torch.load(weights_only=True)` 加载并严格检查模型参数。 [作者推理代码](https://github.com/soCzech/TransNetV2/tree/85cef72af9a916bdfd7cc94a670c9cdfbf12d1ed/inference-pytorch) · [PyPI 分发文件及校验值](https://pypi.org/project/transnetv2-pytorch/1.0.5/#files)

本地实测文件的 SHA-256：

- 推理代码 `transnetv2_pytorch.py`：`f7c1d437465579a8ec28a5add19853d2cb2755248ea4a4207678210a609428e1`
- 转换权重 `transnetv2-pytorch-weights.pth`：`a313d0b3bebfa9a71914b375bfdf918a30b5c3b1e6be51972d35dd8078b442de`

TransNet V2 逐帧解码为 48×27 RGB，每个 100 帧窗口保留中间 50 帧的预测。单帧输出头的概率连续超过 0.5 时，在该段的首帧产生一个切点。视频起止作为外边界，所有转场帧均保留在连续镜头区间内。 [作者参考推理流程](https://github.com/soCzech/TransNetV2/blob/85cef72af9a916bdfd7cc94a670c9cdfbf12d1ed/inference/transnetv2.py)

已通过已安装的 PySceneDetect 0.7.3 Python API 确认，`AdaptiveDetector().min_scene_len` 为整数 15，表示 15 帧。这三条样片均为 15 FPS，相当于 1 秒。保留默认值。该阈值约束相邻检测切点，视频尾段仍可能短于 1 秒。

## 实测环境与匹配规则

Windows、Python 3.12.8、Intel Core i7-13700H、PyTorch 2.9.0+cpu、PySceneDetect 0.7.3、OpenCV 4.11.0.86、NumPy 2.5.4。实测复用了本机已有的 CPU 版 PyTorch，模型使用 4 个 PyTorch 计算线程。推理耗时为逐窗口张量转换、前向计算和取回概率的合计，排除模型加载、视频解码、预处理和预览图写入。

每个非首镜头的开始时间记为一个切点。三条样片均为 15 FPS，先将切点时间换算为最近的帧号，以 ±3 帧（±0.20 秒，含边界）做按时间顺序的一对一匹配。从两侧最早的未处理切点开始，若在容差内则配对并消费两点，否则将较早的点记为该算法独有。首尾外边界不参与匹配。

## 真实样片结果

| 视频 | Adaptive 镜头 | TransNet V2 镜头 | 匹配切点 | Adaptive 独有 | TransNet V2 独有 | TransNet V2 CPU 推理（秒） |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| sample-01.mp4 | 34 | 21 | 19 | 14 | 1 | 26.072 |
| sample-02.mp4 | 34 | 40 | 27 | 6 | 12 | 23.184 |
| sample-03.mp4 | 32 | 16 | 13 | 18 | 2 | 27.364 |
| 合计 | 100 | 77 | 59 | 38 | 15 | 76.620 |

两个真实样片批次各成功 3 条、失败 0 条，退出码均为 `0`。AdaptiveDetector 的三个 JSON 与第一阶段逐字节相同。两组 JSON 字段一致，所有区间从 0 秒连续覆盖至视频结束，末端与独立逐帧读取核对的时长相差小于 2 微秒。共 177 张 JPEG 均可解码。

TransNet V2 的混合输入验证中，损坏 MP4 无法打开，随后的一条有效视频仍输出 1 个镜头，批次退出码为 `1`。部署时 Hugging Face 直链下载中断，以上结果使用已校验的 PyPI wheel 内权重。

切点匹配计数只衡量两组预测在给定容差下的一致性。定量准确性评估需要完整的人工真值标注。

## 人工核验与标注方法

三条样片已完成整段回看和切分结果的人工定性核验，AdaptiveDetector 继续作为默认方案。详见 [README 的人工核验与结果分析](../README.md#人工核验与结果分析)。

在仓库根目录运行 `python review_cuts.py`。脚本读取 `data/` 下的 15 FPS 样片以及 `outputs/adaptive/`、`outputs/transnetv2/` 中对应的 JSON。打开 `outputs/cut-review/cut-review.csv`，其中有 53 个单侧预测和 59 个匹配点。重跑时可通过 `--output-dir outputs/cut-review-v2` 保留之前的填写记录。

1. 按 `priority` 顺序先看 sample-03 的 18 个 Adaptive 独有点、sample-02 的 12 个 TransNet V2 独有点、sample-01 的 14 个 Adaptive 独有点，再看余下 9 个单侧点和 59 个共同预测。帧号从 0 开始。匹配行以 Adaptive 帧定位，同时保留两侧预测帧。
2. 跳到 `time_seconds` 附近播放原视频，必要时逐帧确认。分歧行的 `comparison_image` 指向相对于 CSV 目录的辅助图，左侧为切点前一帧，右侧为切点帧。以原视频为准，在 `human_label` 填 `真实硬切`、`真实渐变`、`无切点` 或 `不确定`。在 `notes` 记录实际边界帧，渐变可记起止帧，并注明相似画面、短镜头、运动或闪光等现象。
3. 为查找双方共同漏检，完整观看三条视频，或选若干明确起止帧的连续区间，从头到尾标出其中所有真实切点，包括预测表未列出的点。可在同一份 CSV 追加一行，将两侧 `detected` 填 `False`、`match` 填 `missed_by_both`，并在备注记录核验区间。

硬切以新镜头首帧定位。若要将渐变纳入按帧匹配的统计，先统一渐变代表帧规则（例如转场中点），并保留起止帧供回看。只在已完整标注的连续区间内，按同一 ±3 帧容差分别匹配两个检测器与真值，计算 Precision、Recall 和 F1。只核查候选点时，记录已证实的误检和漏检案例。

现有核验 CSV 的 `human_label` 仍为空，逐帧真值标注和定量评估尚未完成。

## 交付回归

按上述两条批处理命令重跑三条样片，输出根目录改为 `outputs/task03-regression/` 下的对应检测器目录。每种检测器均成功 3 条、失败 0 条。六份 JSON 与上轮逐字节一致，区间连续，177 张镜头预览图均可解码。另核对了核查表的 112 行和 53 张可解码前后帧图，以及本地推理代码、权重的 SHA-256。
