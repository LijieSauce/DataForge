"""
============================================================
小目标数据增强脚本 - 裁剪缩放贴背景
============================================================
用途：
    解决 YOLO 训练数据中目标偏大、实际业务目标偏小导致检测不出来的问题。
    思路：把原数据集中的目标全部裁出来，随机缩小后贴到全新背景图上，
         生成新的训练样本，让模型学到"该目标在小尺寸下的特征"。

输入：
    dataset/                  原始数据集（YOLO 格式）
    ├── images/
    │   ├── train/            训练集图片
    │   ├── val/              验证集图片
    │   └── test/             测试集图片
    └── labels/
        ├── train/            训练集标注 (.txt)
        ├── val/              验证集标注
        └── test/             测试集标注

    backgrounds/              背景图目录（无子目录，一堆图片）

输出：
    output/
    ├── images/               合成后的图片 (.jpg)
    └── labels/               合成后的标注 (.txt, YOLO 格式)
============================================================
"""

import cv2
import os
import random
from pathlib import Path
from glob import glob
import numpy as np

# ============================================================
# 配置区：根据实际情况修改下列参数
# ============================================================
DATASET_DIR    = r"E:\meter\dataset"          # 原始数据集根目录
BACKGROUND_DIR = r"E:\meter\xin\train\train"      # 背景图所在目录
OUTPUT_DIR     = "output_1"           # 合成结果输出目录

MIN_SIZE       = 35                 # 缩放后目标最小边长（像素），低于这个值不再缩
TARGETS_RANGE  = (1, 2)             # 每张背景贴的目标数量范围 [闭区间]

# 缩放档位概率分布（小:中:大 = 6:3:1）
# 小档：把目标缩到 [MIN_SIZE,  原min边/3]
# 中档：把目标缩到 [原min边/3, 原min边*2/3]
# 大档：把目标缩到 [原min边*2/3, 原min边]
PROB_SMALL  = 1
PROB_MEDIUM = 0
PROB_LARGE  = 0

IMG_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')   # 支持的图片格式

# ============================================================
# 第一步：从原始数据集中提取所有目标，形成"目标池"
# ============================================================
def load_targets(dataset_dir):
    """
    遍历 dataset/images/(train|val|test) 下所有图片，
    根据对应的 YOLO 标注文件把每个 bbox 区域裁剪出来，
    返回一个目标列表。

    返回：
        [
            {'img': numpy数组(裁剪后的目标), 'cls': 类别id},
            ...
        ]
    """
    targets = []

    # 三个子集都要遍历（train/val/test）
    for split in ('train', 'val', 'test'):
        img_dir = os.path.join(dataset_dir, 'images', split)
        lbl_dir = os.path.join(dataset_dir, 'labels', split)

        # 子目录可能不存在（比如有的数据集没 test）
        if not os.path.isdir(img_dir):
            continue

        # 遍历这个 split 下所有图片
        for img_path in sorted(os.listdir(img_dir)):
            # 跳过非图片文件
            if not img_path.lower().endswith(IMG_EXTS):
                continue

            full_img = os.path.join(img_dir, img_path)
            # 标注文件名：图片名同名 + .txt
            stem = Path(img_path).stem
            lbl_path = os.path.join(lbl_dir, stem + '.txt')

            # 没标注的图片直接跳过（无目标可裁）
            if not os.path.isfile(lbl_path):
                continue

            # 读图（cv2.imread 读不了中文路径时可以换成 np.fromfile + cv2.imdecode）
            img = cv2.imread(full_img)
            if img is None:
                print(f"[警告] 无法读取图片：{full_img}")
                continue
            h, w = img.shape[:2]

            # 逐行解析 YOLO 标注：class x_center y_center bw bh （都是归一化的）
            with open(lbl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) != 5:
                        continue  # 格式异常的行跳过

                    cls = int(parts[0])
                    xc, yc, bw, bh = map(float, parts[1:])

                    # 归一化坐标 -> 像素坐标
                    x1 = int((xc - bw / 2) * w)
                    y1 = int((yc - bh / 2) * h)
                    x2 = int((xc + bw / 2) * w)
                    y2 = int((yc + bh / 2) * h)

                    # 边界保护，防止越界裁剪
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(w, x2)
                    y2 = min(h, y2)

                    # 裁太小或者无效的跳过
                    if x2 - x1 < MIN_SIZE or y2 - y1 < MIN_SIZE:
                        continue

                    crop = img[y1:y2, x1:x2].copy()  # .copy() 避免引用大图占内存
                    if crop.size == 0:
                        continue

                    targets.append({'img': crop, 'cls': cls})

    return targets


# ============================================================
# 第二步：随机缩放（按概率分布偏向小尺寸）
# ============================================================
def random_scale(crop):
    """
    根据概率分布对目标进行随机缩放。
    缩放策略：以"短边"为基准，按比例同步缩放，避免拉伸变形。

    输入：原始目标 numpy 数组
    输出：缩放后的目标 numpy 数组
    """
    h, w = crop.shape[:2]
    min_side = min(h, w)        # 用短边作为缩放基准
    
    # 如果原图就接近最小尺寸，直接返回（没缩放空间了）
    if min_side <= MIN_SIZE:
        return crop

    # 按概率选择缩放档位
    r = random.random()
    if r < PROB_SMALL:
        # 小档：最大幅度缩小
        lo, hi = MIN_SIZE, max(MIN_SIZE + 1, min_side // 3)
    elif r < PROB_SMALL + PROB_MEDIUM:
        # 中档：中等缩放
        lo = max(MIN_SIZE, min_side // 3)
        hi = max(lo + 1, min_side * 2 // 3)
    else:
        # 大档：基本不缩或微缩
        lo = max(MIN_SIZE, min_side * 2 // 3)
        hi = max(lo + 1, min_side)

    # 在选定的档位区间内取一个新短边长度
    new_min_side = random.randint(lo, hi)

    # 计算缩放比例并对宽高同步缩放
    scale = new_min_side / min_side
    new_w = max(MIN_SIZE, int(round(w * scale)))
    new_h = max(MIN_SIZE, int(round(h * scale)))

    # INTER_AREA 在缩小图像时效果最好（更清晰、不易出锯齿）
    return cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_AREA)


# ============================================================
# 第三步：把目标贴到背景图的随机位置
# ============================================================
def paste_target(bg, target, existing_boxes, max_try=20):
    """
    把目标贴到背景的随机位置，尽量避免和已贴目标重叠。

    参数：
        bg              : 背景图（会被原地修改）
        target          : 缩放后的目标
        existing_boxes  : 已经贴过的目标 bbox 列表 [(x1,y1,x2,y2), ...]
        max_try         : 找不重叠位置的最大尝试次数

    返回：
        成功时：(x1, y1, x2, y2) 像素坐标
        失败时：None（背景太小贴不下）
    """
    bg_h, bg_w = bg.shape[:2]
    t_h, t_w = target.shape[:2]

    # 背景比目标还小，没法贴
    if t_w >= bg_w or t_h >= bg_h:
        return None

    # 多试几次，尽量找不重叠的位置
    for _ in range(max_try):
        x1 = random.randint(0, bg_w - t_w)
        y1 = random.randint(0, bg_h - t_h)
        x2, y2 = x1 + t_w, y1 + t_h

        # 检查是否与已贴目标重叠
        overlap = False
        for ex1, ey1, ex2, ey2 in existing_boxes:
            if not (x2 <= ex1 or x1 >= ex2 or y2 <= ey1 or y1 >= ey2):
                overlap = True
                break

        if not overlap:
            # 直接覆盖（硬贴，不做羽化）
            bg[y1:y2, x1:x2] = target
            return (x1, y1, x2, y2)

    # 实在找不到不重叠的位置，那就允许重叠也贴一下（避免目标白白浪费）
    x1 = random.randint(0, bg_w - t_w)
    y1 = random.randint(0, bg_h - t_h)
    x2, y2 = x1 + t_w, y1 + t_h
    bg[y1:y2, x1:x2] = target
    return (x1, y1, x2, y2)


# ============================================================
# 主流程
# ============================================================
def main():
    # 准备输出目录
    out_img_dir = os.path.join(OUTPUT_DIR, 'images')
    out_lbl_dir = os.path.join(OUTPUT_DIR, 'labels')
    os.makedirs(out_img_dir, exist_ok=True)
    os.makedirs(out_lbl_dir, exist_ok=True)

    # ----- 1. 加载所有目标到目标池 -----
    print("[1/3] 正在从原始数据集裁剪目标...")
    targets = load_targets(DATASET_DIR)
    print(f"      目标池总数：{len(targets)}")
    if not targets:
        print("[错误] 目标池为空，请检查数据集路径和标注文件")
        return

    # ----- 2. 加载背景图列表 -----
    print("[2/3] 正在扫描背景图...")
    bg_paths = []
    for ext in IMG_EXTS:
        bg_paths.extend(glob(os.path.join(BACKGROUND_DIR, '*' + ext)))
        bg_paths.extend(glob(os.path.join(BACKGROUND_DIR, '*' + ext.upper())))
    bg_paths = sorted(set(bg_paths))
    print(f"      背景图总数：{len(bg_paths)}")
    if not bg_paths:
        print("[错误] 背景图目录为空，请先放图进去")
        return

    # ----- 3. 开始合成 -----
    print("[3/3] 开始合成...")

    # 打乱目标池，避免同一张原图的目标连续被使用
    random.shuffle(targets)

    target_idx = 0      # 目标池消费指针
    bg_idx = 0          # 背景图遍历指针（用完循环利用）
    output_count = 0    # 已生成图片数量

    while target_idx < len(targets):
        # 取背景图（循环利用）
        bg_path = bg_paths[bg_idx % len(bg_paths)]
        bg_idx += 1

        bg = cv2.imread(bg_path)
        if bg is None:
            print(f"[警告] 跳过损坏背景：{bg_path}")
            continue
        bg = bg.copy()  # 不污染原始背景文件

        # 决定这张背景图贴几个目标（1~2个），且不能超过剩余目标数
        n = random.randint(*TARGETS_RANGE)
        n = min(n, len(targets) - target_idx)

        labels = []                # 这张图的所有YOLO标注
        existing_boxes = []        # 已贴目标的像素坐标，用于检测重叠
        bg_h, bg_w = bg.shape[:2]

        for _ in range(n):
            t = targets[target_idx]
            target_idx += 1

            # 随机缩放
            scaled = random_scale(t['img'])

            # 贴上去
            box = paste_target(bg, scaled, existing_boxes)
            if box is None:
                # 背景比目标还小，这个目标这次没贴上，跳过即可
                continue

            x1, y1, x2, y2 = box
            existing_boxes.append(box)

            # 像素坐标 -> YOLO 归一化坐标
            xc = (x1 + x2) / 2 / bg_w
            yc = (y1 + y2) / 2 / bg_h
            nw = (x2 - x1) / bg_w
            nh = (y2 - y1) / bg_h
            labels.append(f"{t['cls']} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")

        # 至少贴上了一个目标才输出
        if labels:
            out_name = f"synth_{output_count:06d}"
            cv2.imwrite(os.path.join(out_img_dir, out_name + '.jpg'), bg)
            with open(os.path.join(out_lbl_dir, out_name + '.txt'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(labels))
            output_count += 1

            # 进度提示（每500张打一次）
            if output_count % 500 == 0:
                print(f"      已生成 {output_count} 张，目标池剩余 {len(targets) - target_idx}")

    print(f"\n[完成] 共生成 {output_count} 张合成图，全部保存在 {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
