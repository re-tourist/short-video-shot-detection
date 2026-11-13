import argparse
import json
import sys
from pathlib import Path

import cv2
from scenedetect import AdaptiveDetector, SceneManager, open_video


def process_video(video_path: Path, output_dir: Path, detector_name: str):
    shots_path = output_dir / "shots.json"
    shots_path.unlink(missing_ok=True)

    inference_seconds = None
    shots = []
    with open_video(video_path, backend="opencv") as video:
        if detector_name == "adaptive":
            manager = SceneManager()
            manager.add_detector(AdaptiveDetector())
            frame_count = manager.detect_scenes(video)
            scenes = manager.get_scene_list(start_in_scene=True)
        else:
            from transnet_detector import detect_transnet

            scenes, frame_count, inference_seconds = detect_transnet(video)
        if not frame_count:
            raise ValueError("未解码出任何视频帧")
        expected_duration = video.duration
        if expected_duration is not None and frame_count < expected_duration.frame_num:
            raise ValueError(
                f"视频未完整解码（{frame_count}/{expected_duration.frame_num} 帧）"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        for index, (start, end) in enumerate(scenes, start=1):
            start_seconds, end_seconds = start.seconds, end.seconds
            if end_seconds <= start_seconds:
                raise ValueError(f"镜头 {index} 的起止时间无效")
            video.seek((start_seconds + end_seconds) / 2)
            frame = video.read()
            if frame is False or not start <= video.position < end:
                raise ValueError(f"无法读取镜头 {index} 的预览帧")

            preview = f"shot_{index:04d}.jpg"
            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                raise OSError(f"无法编码预览图 {preview}")
            (output_dir / preview).write_bytes(encoded.tobytes())
            shots.append(
                {
                    "index": index,
                    "start_seconds": start_seconds,
                    "end_seconds": end_seconds,
                    "preview": preview,
                }
            )

    preview_names = {shot["preview"] for shot in shots}
    for old_preview in output_dir.glob("shot_*.jpg"):
        if old_preview.name not in preview_names:
            old_preview.unlink()

    result = {
        "video": video_path.name,
        "detector": detector_name,
        "duration_seconds": shots[-1]["end_seconds"],
        "shots": shots,
    }
    shots_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(shots), inference_seconds


def main() -> int:
    parser = argparse.ArgumentParser(description="批量检测 MP4 视频的镜头边界")
    parser.add_argument("--input-dir", type=Path, required=True, help="输入视频目录")
    parser.add_argument("--output-dir", type=Path, required=True, help="输出目录")
    parser.add_argument("--detector", choices=("adaptive", "transnetv2"), default="adaptive")
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        parser.error(f"输入目录不存在：{args.input_dir}")
    videos = sorted(
        path for path in args.input_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".mp4"
    )
    if not videos:
        parser.error(f"输入目录中没有 MP4 视频：{args.input_dir}")

    succeeded = failed = total_shots = 0
    for video_path in videos:
        try:
            count, inference_seconds = process_video(
                video_path, args.output_dir / video_path.stem, args.detector
            )
        except Exception as exc:
            failed += 1
            print(f"[失败] {video_path.name}：{str(exc).strip()}", file=sys.stderr, flush=True)
        else:
            succeeded += 1
            total_shots += count
            timing = (
                f"，推理 {inference_seconds:.3f} 秒（CPU）"
                if inference_seconds is not None else ""
            )
            print(f"[成功] {video_path.name}：{count} 个镜头{timing}", flush=True)

    print(f"汇总：成功 {succeeded}，失败 {failed}，共 {total_shots} 个镜头")
    return int(failed > 0)


if __name__ == "__main__":
    sys.exit(main())
