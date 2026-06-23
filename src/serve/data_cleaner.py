"""
数据清洗工具 - 用于手动筛选数据集图片
操作说明：
- 按 A/a：保留当前图片和标注
- 按 D/d：删除当前图片和标注
- 按 Q/q 或 ESC：退出程序
"""

import os
import shutil
import cv2
import numpy as np
from pathlib import Path


REANNOTATION_IMAGE_DIR = r"E:\meter\输出\目标1"


def read_image(path):
    """兼容中文路径的图片读取"""
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def get_all_images(dataset_path):
    """获取数据集中所有图片路径"""
    images = []
    image_extensions = ['.jpg', '.jpeg', '.png']

    # 遍历 train 和 val 目录
    for subset in ['train', 'val']:
        image_dir = dataset_path / 'images' / subset
        if image_dir.exists():
            for file in image_dir.iterdir():
                if file.suffix.lower() in image_extensions:
                    images.append({
                        'image_path': file,
                        'subset': subset,
                        'name': file.name
                    })

    # 按文件名排序
    images.sort(key=lambda x: x['name'])
    return images


def get_label_path(image_info, dataset_path):
    """获取对应的标注文件路径"""
    image_path = image_info['image_path']
    subset = image_info['subset']

    # 将图片扩展名替换为.txt，并修改路径到labels目录
    label_name = image_path.stem + '.txt'
    label_path = dataset_path / 'labels' / subset / label_name

    return label_path


def read_label_lines(label_path):
    """读取 YOLO 标注文件内容"""
    if not label_path.exists():
        return []

    for encoding in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            with open(label_path, 'r', encoding=encoding) as f:
                return [line.strip() for line in f if line.strip()]
        except UnicodeDecodeError:
            continue
    return []


def draw_yolo_labels(image, label_path):
    """在图片上绘制 YOLO 标注框和类别文字"""
    display_img = image.copy()
    h, w = display_img.shape[:2]
    lines = read_label_lines(label_path)

    if not lines:
        cv2.putText(display_img, 'No label', (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        return display_img

    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            continue

        try:
            cls_id = parts[0]
            xc, yc, bw, bh = map(float, parts[1:])
        except ValueError:
            continue

        x1 = int((xc - bw / 2) * w)
        y1 = int((yc - bh / 2) * h)
        x2 = int((xc + bw / 2) * w)
        y2 = int((yc + bh / 2) * h)

        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(0, min(w - 1, x2))
        y2 = max(0, min(h - 1, y2))

        if x2 <= x1 or y2 <= y1:
            continue

        color = (0, 255, 0)
        cv2.rectangle(display_img, (x1, y1), (x2, y2), color, 2)

        label = f"cls:{cls_id}"
        (text_w, text_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
        )
        text_y = max(20, y1 - 8)
        box_y1 = max(0, text_y - text_h - baseline)
        box_y2 = min(h - 1, text_y + baseline)
        box_x2 = min(w - 1, x1 + text_w + 8)

        cv2.rectangle(display_img, (x1, box_y1), (box_x2, box_y2), color, -1)
        cv2.putText(display_img, label, (x1 + 4, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    return display_img


def delete_files(image_info, dataset_path):
    """删除图片和对应的标注文件"""
    image_path = image_info['image_path']
    label_path = get_label_path(image_info, dataset_path)

    # 删除图片
    if image_path.exists():
        image_path.unlink()
        print(f"  已删除图片: {image_path.name}")

    # 删除标注文件（如果存在）
    if label_path.exists():
        label_path.unlink()
        print(f"  已删除标注: {label_path.name}")
    else:
        print(f"  注意: 未找到对应的标注文件")


def build_unique_target_path(target_dir, file_name):
    """生成不覆盖已有文件的目标路径"""
    target_path = target_dir / file_name
    if not target_path.exists():
        return target_path

    stem = target_path.stem
    suffix = target_path.suffix
    counter = 1
    while True:
        candidate = target_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def move_image_for_reannotation(image_info):
    """移动图片到待重标注目录，仅处理图片文件"""
    image_path = image_info['image_path']

    if not REANNOTATION_IMAGE_DIR.strip():
        print("  注意: 待重标注输出目录为空，请先在脚本顶部填写 REANNOTATION_IMAGE_DIR")
        return False

    target_dir = Path(REANNOTATION_IMAGE_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = build_unique_target_path(target_dir, image_path.name)

    shutil.move(str(image_path), str(target_path))
    print(f"  已移动图片到待重标注目录: {target_path}")
    return True


def main():
    # 数据集路径
    dataset_path = Path(r'E:\meter\输出\表计_1')

    if not dataset_path.exists():
        print(f"错误: 数据集路径不存在 - {dataset_path}")
        return

    # 获取所有图片
    print("正在扫描图片...")
    images = get_all_images(dataset_path)
    total = len(images)

    if total == 0:
        print("未找到任何图片！")
        return

    print(f"找到 {total} 张图片")
    print("\n操作说明：")
    print("  A/a - 保留当前图片")
    print("  D/d - 删除当前图片和标注")
    print("  S/s - 移动当前图片到待重标注目录")
    print("  Q/q 或 ESC - 退出程序")
    print("\n开始清洗...\n")

    # 遍历所有图片
    current_index = 0
    deleted_count = 0
    kept_count = 0
    relabel_count = 0

    while current_index < total:
        image_info = images[current_index]
        image_path = image_info['image_path']
        subset = image_info['subset']

        # 读取图片（兼容中文路径）
        img = read_image(image_path)

        if img is None:
            print(f"警告: 无法读取图片 {image_path}")
            current_index += 1
            continue

        # 显示进度和文件名
        progress = f"第 {current_index + 1}/{total} 张 - {subset}/{image_info['name']}"
        print(f"\r{progress}", end='', flush=True)

        # 在图片上叠加标注和进度信息
        label_path = get_label_path(image_info, dataset_path)
        display_img = draw_yolo_labels(img, label_path)
        cv2.putText(display_img, progress, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # 显示图片
        cv2.imshow('Data Cleaner', display_img)

        # 等待按键
        while True:
            key = cv2.waitKey(0) & 0xFF

            # 保留 (A/a)
            if key in [ord('a'), ord('A')]:
                kept_count += 1
                print(f" -> 保留")
                break

            # 删除 (D/d)
            elif key in [ord('d'), ord('D')]:
                print(f" -> 删除")
                delete_files(image_info, dataset_path)
                deleted_count += 1
                break

            # 待重标注 (S/s)
            elif key in [ord('s'), ord('S')]:
                print(f" -> 移动到待重标注目录")
                if move_image_for_reannotation(image_info):
                    relabel_count += 1
                    break

            # 退出 (Q/q/ESC)
            elif key in [ord('q'), ord('Q'), 27]:  # 27 是 ESC 的键码
                print(f"\n\n退出程序")
                print(f"统计: 保留 {kept_count} 张, 删除 {deleted_count} 张, 待重标注 {relabel_count} 张")
                cv2.destroyAllWindows()
                return

            # 其他按键无反应，继续等待

        current_index += 1

    # 全部处理完成
    cv2.destroyAllWindows()
    print(f"\n\n清洗完成！")
    print(f"统计: 保留 {kept_count} 张, 删除 {deleted_count} 张, 待重标注 {relabel_count} 张")


if __name__ == '__main__':
    main()
