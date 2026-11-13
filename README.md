# Short Video Shot Detection

## 一、设计思路

将短视频切分为连续镜头，为后续素材打标、检索和重新组合提供时间边界与预览图。默认使用 PySceneDetect 的 AdaptiveDetector 作为轻量基线，可选用预训练 TransNet V2（PyTorch CPU）做对照。两个检测器独立运行，共用 OpenCV 解码和输出流程，使用现成模型与默认参数。

**真实案例与工程验证。** 官方样片 `sample-01.mp4` 使用 AdaptiveDetector 检出 34 个镜头，前三段为 0–2.333333、2.333333–4.4、4.4–5.8 秒。三条样片在两种检测器下均处理成功，分别输出 100 和 77 个镜头。逐条验证了区间从 0 秒连续覆盖至视频结束，以及每个镜头的 JPEG 可解码。混入损坏 MP4 后，其余视频仍生成结果。

**人工评测与已知问题。** 样片为 15 FPS，AdaptiveDetector 默认最短切点间隔 15 帧（1 秒），会限制密集切点的检出。双算法在 ±3 帧下有 53 个单侧预测，已整理成核查材料，误检、漏检和准确性待人工标注确认。详见[基线实验](docs/baseline-results.md)和[算法对照与人工核查](docs/detector-comparison.md)。

**AI 辅助开发。** [AGENTS.md](AGENTS.md) 的三条规则在交付中有直接作用。

- **Keep It Simple** 复用成熟检测器和同一输出流程，切点核查直接读取已有 JSON。
- **Verify What Matters** 用真实视频检查覆盖范围和预览图，混入损坏文件验证批处理隔离。
- **Keep Delivery Reproducible** 固定依赖和上游代码版本，记录权重校验值，并排除本地素材及运行产物。

## 二、部署运行

使用 Python 3.10 或以上版本，已在 Windows / Python 3.12.8 实测。建议在虚拟环境中安装依赖。将三条 MP4 放在 `data/` 第一层，扩展名不区分大小写。在仓库根目录执行以下命令。

```bash
python -m pip install -r requirements.txt
python main.py --input-dir data --output-dir outputs/adaptive --detector adaptive
```

运行 TransNet V2 前，按[部署说明](docs/detector-comparison.md#部署与运行)安装 CPU 版 PyTorch，并将指定推理代码和权重放入 `models/`。

```bash
python main.py --input-dir data --output-dir outputs/transnetv2 --detector transnetv2
```

每条视频在输出目录下创建一个同名子目录，包含 `shots.json` 和各镜头中点附近的 JPEG。时间单位为秒，区间左闭右开，`preview` 相对于 JSON 所在目录。批次结束后汇总结果，全部成功返回 `0`，有视频失败返回 `1`，输入目录无效或没有 MP4 返回 `2`。

以下是 `outputs/adaptive/sample-01/shots.json` 的真实摘录，镜头数组仅列前三项。

```json
{
  "video": "sample-01.mp4",
  "detector": "adaptive",
  "duration_seconds": 160.333334,
  "shots": [
    {"index": 1, "start_seconds": 0.0, "end_seconds": 2.333333, "preview": "shot_0001.jpg"},
    {"index": 2, "start_seconds": 2.333333, "end_seconds": 4.4, "preview": "shot_0002.jpg"},
    {"index": 3, "start_seconds": 4.4, "end_seconds": 5.8, "preview": "shot_0003.jpg"}
  ]
}
```
