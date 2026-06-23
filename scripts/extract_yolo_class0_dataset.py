from __future__ import annotations

import argparse
import shutil
from pathlib import Path


DEFAULT_SOURCE = Path(r"E:\meter\数据集\dirtvisionpro.v1i.yolov11")
DEFAULT_OUTPUT = Path(r"E:\meter\输出\dirtvisionpro_class0")
SPLITS = ("train", "valid", "test")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
TARGET_CLASS_ID = "0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract YOLO samples containing class 0 into a new dataset."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Source YOLO dataset directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output dataset directory.",
    )
    return parser.parse_args()


def find_image_path(image_dir: Path, stem: str) -> Path | None:
    for suffix in IMAGE_SUFFIXES:
        image_path = image_dir / f"{stem}{suffix}"
        if image_path.exists():
            return image_path
    return None


def collect_class0_lines(label_path: Path) -> list[str]:
    matched: list[str] = []
    for raw_line in label_path.read_text(encoding="utf-8").splitlines():
        parts = raw_line.split()
        if len(parts) != 5:
            continue
        if parts[0] == TARGET_CLASS_ID:
            matched.append(" ".join(parts))
    return matched


def reset_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def write_data_yaml(output_dir: Path) -> None:
    yaml_text = (
        "train: ../train/images\n"
        "val: ../valid/images\n"
        "test: ../test/images\n\n"
        "nc: 1\n"
        "names: ['0']\n"
    )
    (output_dir / "data.yaml").write_text(yaml_text, encoding="utf-8")


def process_split(source_dir: Path, output_dir: Path, split: str) -> tuple[int, int]:
    src_label_dir = source_dir / split / "labels"
    src_image_dir = source_dir / split / "images"
    dst_label_dir = output_dir / split / "labels"
    dst_image_dir = output_dir / split / "images"

    dst_label_dir.mkdir(parents=True, exist_ok=True)
    dst_image_dir.mkdir(parents=True, exist_ok=True)

    image_count = 0
    box_count = 0

    for label_path in sorted(src_label_dir.glob("*.txt")):
        class0_lines = collect_class0_lines(label_path)
        if not class0_lines:
            continue

        image_path = find_image_path(src_image_dir, label_path.stem)
        if image_path is None:
            continue

        shutil.copy2(image_path, dst_image_dir / image_path.name)
        (dst_label_dir / label_path.name).write_text(
            "\n".join(class0_lines) + "\n",
            encoding="utf-8",
        )

        image_count += 1
        box_count += len(class0_lines)

    return image_count, box_count


def write_summary(output_dir: Path, summary_lines: list[str]) -> None:
    (output_dir / "summary.txt").write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    source_dir = args.source.resolve()
    output_dir = args.output.resolve()

    reset_output_dir(output_dir)
    write_data_yaml(output_dir)

    summary_lines: list[str] = [
        f"source={source_dir}",
        f"output={output_dir}",
        "class_id=0",
        "label_mode=keep_only_class_0_lines",
    ]

    total_images = 0
    total_boxes = 0

    for split in SPLITS:
        image_count, box_count = process_split(source_dir, output_dir, split)
        total_images += image_count
        total_boxes += box_count
        summary_lines.append(f"{split}: images={image_count}, boxes={box_count}")

    summary_lines.append(f"total_images={total_images}")
    summary_lines.append(f"total_boxes={total_boxes}")
    write_summary(output_dir, summary_lines)

    print(f"Done: {output_dir}")
    for line in summary_lines[4:]:
        print(line)


if __name__ == "__main__":
    main()
