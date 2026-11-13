from functools import lru_cache
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
import torch

MODEL_DIR = Path(__file__).resolve().parent / "models"


@lru_cache(maxsize=1)
def load_model():
    source = MODEL_DIR / "transnetv2_pytorch.py"
    weights = MODEL_DIR / "transnetv2-pytorch-weights.pth"
    if not source.is_file() or not weights.is_file():
        raise FileNotFoundError("请按 README 下载 TransNet V2 推理代码和权重到 models/ 目录")

    from models.transnetv2_pytorch import TransNetV2
    torch.set_num_threads(min(4, torch.get_num_threads()))
    model = TransNetV2()
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
    return model.eval().to(memory_format=torch.channels_last_3d)


def detect_transnet(video):
    frames, positions = [], []
    while (frame := video.read()) is not False:
        small = cv2.resize(frame, (48, 27), interpolation=cv2.INTER_LINEAR)
        frames.append(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        positions.append(video.position)

    frame_count = len(frames)
    expected_duration = video.duration
    if not frame_count or (
        expected_duration is not None and frame_count < expected_duration.frame_num
    ):
        return [], frame_count, None

    model = load_model()
    padded = np.pad(
        np.stack(frames), ((25, 25 + (-frame_count % 50)), (0, 0), (0, 0), (0, 0)),
        mode="edge",
    )
    predictions = []
    started = perf_counter()
    with torch.inference_mode():
        for offset in range(0, frame_count, 50):
            window = torch.from_numpy(padded[offset : offset + 100]).unsqueeze(0)
            logits, _ = model(window)
            predictions.append(logits[0, 25:75, 0].sigmoid().numpy())
    inference_seconds = perf_counter() - started

    # Place one cut at the first frame of each above-threshold run.
    # Leading positives do not create a cut at the beginning of the video.
    transitions = np.concatenate(predictions)[:frame_count] > 0.5
    cut_indices = np.flatnonzero(transitions[1:] & ~transitions[:-1]) + 1
    boundaries = [positions[0], *(positions[i] for i in cut_indices), positions[-1] + 1]
    return list(zip(boundaries, boundaries[1:])), frame_count, inference_seconds
