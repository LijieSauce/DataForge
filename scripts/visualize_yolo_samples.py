from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
import numpy as np


DATASET_DIR = Path(r"E:\meter\数据集\dirtvisionpro.v1i.yolov11")
OUTPUT_DIR = Path(r"E:\meter\输出\dirtvisionpro_label_preview")
SPLITS = ("train", "valid", "test")
DEFAULT_SAMPLES_PER_CLASS = 3
CLASS_IDS = (0, 1, 2)
CLASS_COLORS = {
    0: (255, 160, 0),
    1: (0, 200, 255),
    2: (80, 220, 80),
}


def read_image(image_path: Path) -> np.ndarray | None:
    data = np.fromfile(str(image_path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def save_image(image_path: Path, image: np.ndarray) -> None:
    image_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = image_path.suffix.lower()
    ext = ".png" if suffix not in {".jpg", ".jpeg", ".png"} else suffix
    success, encoded = cv2.imencode(ext, image)
    if not success:
        raise RuntimeError(f"无法编码图片: {image_path}")
    encoded.tofile(str(image_path))


def yolo_to_xyxy(record: list[str], width: int, height: int) -> tuple[int, int, int, int]:
    _, xc, yc, bw, bh = record
    xc = float(xc) * width
    yc = float(yc) * height
    bw = float(bw) * width
    bh = float(bh) * height

    x1 = max(0, int(round(xc - bw / 2)))
    y1 = max(0, int(round(yc - bh / 2)))
    x2 = min(width - 1, int(round(xc + bw / 2)))
    y2 = min(height - 1, int(round(yc + bh / 2)))
    return x1, y1, x2, y2


def collect_label_files(dataset_dir: Path, class_id: int) -> list[Path]:
    matches: list[Path] = []
    for split in SPLITS:
        label_dir = dataset_dir / split / "labels"
        if not label_dir.is_dir():
            continue
        for label_file in sorted(label_dir.glob("*.txt")):
            lines = label_file.read_text(encoding="utf-8").splitlines()
            if any(line.split() and int(line.split()[0]) == class_id for line in lines):
                matches.append(label_file)
    return matches


def find_image_path(label_file: Path) -> Path | None:
    image_dir = label_file.parent.parent / "images"
    stem = label_file.stem
    for suffix in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        image_path = image_dir / f"{stem}{suffix}"
        if image_path.exists():
            return image_path
    return None


def draw_annotations(image: np.ndarray, label_file: Path, focus_class: int) -> tuple[np.ndarray, int]:
    height, width = image.shape[:2]
    focus_count = 0

    for raw_line in label_file.read_text(encoding="utf-8").splitlines():
        parts = raw_line.split()
        if len(parts) != 5:
            continue

        class_id = int(parts[0])
        x1, y1, x2, y2 = yolo_to_xyxy(parts, width, height)
        color = CLASS_COLORS.get(class_id, (255, 255, 255))
        thickness = 3 if class_id == focus_class else 2
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)

        label = f"class {class_id}"
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        text_y1 = max(0, y1 - text_h - 10)
        text_y2 = text_y1 + text_h + 10
        text_x2 = min(width - 1, x1 + text_w + 12)
        cv2.rectangle(image, (x1, text_y1), (text_x2, text_y2), color, -1)
        cv2.putText(
            image,
            label,
            (x1 + 6, text_y2 - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )

        if class_id == focus_class:
            focus_count += 1

    return image, focus_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="随机抽样并可视化 YOLO 标注")
    parser.add_argument(
        "--samples-per-class",
        type=int,
        default=DEFAULT_SAMPLES_PER_CLASS,
        help="每个类别抽样的图片数量",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="预览图输出目录",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(42)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_lines: list[str] = []

    for class_id in CLASS_IDS:
        candidates = collect_label_files(DATASET_DIR, class_id)
        if not candidates:
            summary_lines.append(f"class {class_id}: 未找到样本")
            continue

        sample_count = min(args.samples_per_class, len(candidates))
        chosen = random.sample(candidates, sample_count)
        class_output_dir = output_dir / f"class_{class_id}"
        class_output_dir.mkdir(parents=True, exist_ok=True)

        saved_count = 0
        for index, label_file in enumerate(chosen, start=1):
            image_path = find_image_path(label_file)
            if image_path is None:
                continue

            image = read_image(image_path)
            if image is None:
                continue

            rendered, focus_count = draw_annotations(image, label_file, class_id)
            output_name = f"{index:02d}_{image_path.stem}_focus_{class_id}_n{focus_count}.jpg"
            save_image(class_output_dir / output_name, rendered)
            saved_count += 1

        summary_lines.append(f"class {class_id}: 生成 {saved_count} 张预览图")

    summary_path = output_dir / "summary.txt"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
