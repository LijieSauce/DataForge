import os
import math
import random
import shutil
import uuid
from pathlib import Path

# 每个文件夹对应 (路径, 比例)
SOURCE_DIRS = [
    (r"E:\meter\数据集\玻璃", 1.0),
    (r"E:\meter\xin\JPEGImages", 0),
    (r"E:\meter\xin\Image_Classification", 0),
]

OUTPUT_IMAGES = r"E:\meter\dataset4\images"
OUTPUT_LABELS = r"E:\meter\dataset4\labels"
TOTAL_COUNT = 1000
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def collect_images(d):
    images = []
    for root, _, files in os.walk(d):
        for f in files:
            if Path(f).suffix.lower() in IMAGE_EXTS:
                images.append(os.path.join(root, f))
    return images


def clear_dir(d):
    for f in Path(d).glob("*"):
        f.unlink()


def main():
    os.makedirs(OUTPUT_IMAGES, exist_ok=True)
    os.makedirs(OUTPUT_LABELS, exist_ok=True)
    clear_dir(OUTPUT_IMAGES)
    clear_dir(OUTPUT_LABELS)

    selected = []
    for dir_path, ratio in SOURCE_DIRS:
        count = math.ceil(TOTAL_COUNT * ratio)
        images = collect_images(dir_path)
        print(f"{dir_path}  共 {len(images)} 张，目标抽取 {count} 张")
        if len(images) < count:
            print(f"  警告：图片不足，全部选取 {len(images)} 张")
            selected.extend(images)
        else:
            selected.extend(random.sample(images, count))

    print(f"\n合计选取 {len(selected)} 张，开始复制...")

    for i, src in enumerate(selected, 1):
        ext = Path(src).suffix.lower()
        name = str(uuid.uuid4())
        shutil.copy2(src, os.path.join(OUTPUT_IMAGES, name + ext))
        open(os.path.join(OUTPUT_LABELS, name + ".txt"), "w").close()

        if i % 100 == 0:
            print(f"进度：{i}/{len(selected)}")

    print(f"完成！已生成 {len(selected)} 张图片及对应空白标注到 E:\\meter\\output1")


if __name__ == "__main__":
    main()
