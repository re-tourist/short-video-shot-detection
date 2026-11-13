"""Build a local review packet from the two detector runs on the 15 FPS samples."""

import argparse
import csv
import json
from pathlib import Path

import cv2

FPS = 15
TOLERANCE = 3
PRIORITY = {
    ("sample-03", "adaptive_only"): 1,
    ("sample-02", "transnetv2_only"): 2,
    ("sample-01", "adaptive_only"): 3,
}


def read_cuts(detector, video):
    path = Path("outputs") / detector / video.stem / "shots.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    if (result["video"], result["detector"]) != (video.name, detector):
        raise ValueError(f"Unexpected video or detector in {path}")
    return [round(shot["start_seconds"] * FPS) for shot in result["shots"][1:]]


def match_cuts(adaptive, transnet):
    i = j = 0
    while i < len(adaptive) and j < len(transnet):
        a, t = adaptive[i], transnet[j]
        if abs(a - t) <= TOLERANCE:
            yield a, t, "matched"
            i += 1
            j += 1
        elif a < t:
            yield a, None, "adaptive_only"
            i += 1
        else:
            yield None, t, "transnetv2_only"
            j += 1
    yield from ((a, None, "adaptive_only") for a in adaptive[i:])
    yield from ((None, t, "transnetv2_only") for t in transnet[j:])


def save_comparisons(video, output, pairs):
    cuts = [a if a is not None else t for a, t, kind in pairs if kind != "matched"]
    wanted = {frame for cut in cuts for frame in (cut - 1, cut)}
    capture = cv2.VideoCapture(str(video))
    frames = {}
    try:
        if not capture.isOpened() or capture.get(cv2.CAP_PROP_FPS) != FPS:
            raise ValueError(f"Expected a readable {FPS} FPS video: {video}")
        for index in range(max(wanted, default=-1) + 1):
            if not capture.grab():
                raise ValueError(f"Cannot read frame {index} from {video}")
            if index in wanted:
                ok, frame = capture.retrieve()
                if not ok:
                    raise ValueError(f"Cannot decode frame {index} from {video}")
                width = round(360 * frame.shape[1] / frame.shape[0])
                frames[index] = cv2.resize(frame, (width, 360), interpolation=cv2.INTER_AREA)
    finally:
        capture.release()

    for cut in cuts:
        panels = [frames[index].copy() for index in (cut - 1, cut)]
        for label, index, panel in zip(("Before", "At cut"), (cut - 1, cut), panels):
            cv2.rectangle(panel, (0, 0), (panel.shape[1], 28), (0, 0, 0), -1)
            cv2.putText(panel, f"{label} #{index}", (5, 20), cv2.FONT_HERSHEY_SIMPLEX,
                        0.48, (255, 255, 255), 1, cv2.LINE_AA)
        ok, image = cv2.imencode(".jpg", cv2.hconcat(panels))
        if not ok:
            raise ValueError(f"Cannot encode comparison for {video} at frame {cut}")
        (output / f"cut_{video.stem}-{cut:05d}.jpg").write_bytes(image.tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/cut-review"))
    output = parser.parse_args().output_dir
    if output.exists():
        parser.error("Choose a new output directory to preserve existing annotations.")
    output.mkdir(parents=True)
    images = output / "frames"
    images.mkdir()

    rows = []
    for video in sorted(Path("data").glob("*.mp4")):
        pairs = list(match_cuts(read_cuts("adaptive", video), read_cuts("transnetv2", video)))
        save_comparisons(video, images, pairs)
        for a, t, kind in pairs:
            cut = a if a is not None else t
            priority = PRIORITY.get((video.stem, kind), 5 if kind == "matched" else 4)
            rows.append((priority, video.name, cut, f"{cut / FPS:.6f}",
                         a is not None, t is not None, a, t, kind,
                         f"frames/cut_{video.stem}-{cut:05d}.jpg" if kind != "matched" else "",
                         "", ""))

    with (output / "cut-review.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("priority", "video", "frame", "time_seconds", "adaptive_detected",
                         "transnetv2_detected", "adaptive_frame", "transnetv2_frame",
                         "match", "comparison_image", "human_label", "notes"))
        writer.writerows(sorted(rows))


if __name__ == "__main__":
    main()
