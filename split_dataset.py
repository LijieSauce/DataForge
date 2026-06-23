#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将平铺的 output 目录结构转换为 dataset 风格的 train/val/test 分层结构。

用法：python split_dataset.py
"""

import os
import random
import shutil
from pathlib import Path

# ============================================================
# 🔧 常量配置区 —— 按需修改
# ============================================================

# 源目录（平铺结构：images/ 和 labels/ 下直接放文件）
SOURCE_DIR = Path(r"E:\meter\输出\dataset7")

# 源 images 子目录名
SOURCE_IMAGES = "images"

# 源 labels 子目录名
SOURCE_LABELS = "labels"

# 图片扩展名（支持多种，会按顺序匹配）
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")

# 标签扩展名
LABEL_EXTENSION = ".txt"


# 目标子目录名（在 SOURCE_DIR 下创建）
TARGET_IMAGES = "images"  # images 的目标根（其下创建 train/val/test）
TARGET_LABELS = "labels"  # labels 的目标根

# 分割比例（train, val, test），三者之和应为 1.0
SPLIT_RATIOS = {
    "train": 0.7,
    "val":   0.3,
}

# 随机种子（设为 None 则每次运行结果不同）
RANDOM_SEED = 42

# 是否使用符号链接而非移动文件（Windows 下通常不建议）
USE_SYMLINK = False

# 是否强制覆盖已有目标文件
OVERWRITE = False

# 是否确认后才执行（True = 先预览再确认）
DRY_RUN = False

# ============================================================
# 逻辑代码
# ============================================================

def collect_pairs(src_dir: Path, images_dir: str, labels_dir: str,
                   img_exts: tuple, lbl_ext: str) -> list[tuple[str, Path, Path]]:
    """
    收集 images 和 labels 配对的文件。
    返回 [(basename, img_path, lbl_path), ...]
    """
    img_dir = src_dir / images_dir
    lbl_dir = src_dir / labels_dir

    if not img_dir.exists():
        raise FileNotFoundError(f"源图片目录不存在: {img_dir}")
    if not lbl_dir.exists():
        raise FileNotFoundError(f"源标签目录不存在: {lbl_dir}")

    pairs = []
    missing_labels = []

    for img_path in sorted(img_dir.iterdir()):
        if not img_path.is_file():
            continue
        # 匹配扩展名
        matched_ext = None
        for ext in img_exts:
            if img_path.suffix.lower() == ext.lower():
                matched_ext = ext
                break
        if matched_ext is None:
            continue

        basename = img_path.stem  # 不含扩展名的文件名
        lbl_path = lbl_dir / f"{basename}{lbl_ext}"

        if lbl_path.exists():
            pairs.append((basename, img_path, lbl_path))
        else:
            missing_labels.append(basename)

    if missing_labels:
        print(f"⚠️  有 {len(missing_labels)} 个图片缺少对应标签，已跳过")

    return pairs


def split_items(items: list, ratios: dict, seed: int | None) -> dict[str, list]:
    """随机打乱并按比例分割。"""
    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.Random()

    shuffled = list(items)  # 浅拷贝
    rng.shuffle(shuffled)

    total = len(shuffled)
    splits = {}
    start = 0

    split_names = list(ratios.keys())
    for i, name in enumerate(split_names):
        if i == len(split_names) - 1:
            # 最后一份拿剩余所有，防止浮点误差丢文件
            end = total
        else:
            end = start + round(total * ratios[name])
        splits[name] = shuffled[start:end]
        start = end

    return splits


def move_or_link(src: Path, dst: Path, use_symlink: bool, overwrite: bool):
    """移动或创建符号链接。"""
    if dst.exists():
        if overwrite:
            dst.unlink()
        else:
            raise FileExistsError(f"目标已存在: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if use_symlink:
        os.symlink(src.resolve(), dst.resolve())
    else:
        shutil.move(str(src), str(dst))


def main():
    # --- 收集 ---
    print("🔍 正在扫描文件...")
    pairs = collect_pairs(SOURCE_DIR, SOURCE_IMAGES, SOURCE_LABELS,
                          IMAGE_EXTENSIONS, LABEL_EXTENSION)
    print(f"   找到 {len(pairs)} 对图片+标签")

    if not pairs:
        print("❌ 没有找到可用的文件对，退出。")
        return

    # --- 分割 ---
    print("🎲 正在随机分割...")
    splits = split_items(pairs, SPLIT_RATIOS, RANDOM_SEED)
    for name, items in splits.items():
        print(f"   {name}: {len(items)} 对 ({len(items)/len(pairs)*100:.1f}%)")

    # 校验
    total_split = sum(len(v) for v in splits.values())
    if total_split != len(pairs):
        print(f"⚠️  分割总数 ({total_split}) 与源文件数 ({len(pairs)}) 不一致！")

    # --- 干跑预览 ---
    if DRY_RUN:
        print("\n📋 [DRY RUN] 预览模式，不会实际移动文件：")
        for name, items in splits.items():
            print(f"  [{name}] {len(items)} 对 → {SOURCE_DIR / TARGET_IMAGES / name}/")
        print("\n✅ 预览完成。将 DRY_RUN 改为 False 后重新运行即可执行。")
        return

    # --- 执行移动 ---
    print(f"\n🚚 正在{'创建符号链接' if USE_SYMLINK else '移动'}文件...")
    errors = []
    for split_name, items in splits.items():
        img_target_dir = SOURCE_DIR / TARGET_IMAGES / split_name
        lbl_target_dir = SOURCE_DIR / TARGET_LABELS / split_name
        for basename, img_src, lbl_src in items:
            try:
                move_or_link(img_src, img_target_dir / img_src.name, USE_SYMLINK, OVERWRITE)
                move_or_link(lbl_src, lbl_target_dir / lbl_src.name, USE_SYMLINK, OVERWRITE)
            except Exception as e:
                errors.append((basename, e))

    # --- 清理空的源子目录 ---
    old_img_dir = SOURCE_DIR / SOURCE_IMAGES
    old_lbl_dir = SOURCE_DIR / SOURCE_LABELS
    # 只删 train/val/test 之外的残留空目录
    for d in (old_img_dir, old_lbl_dir):
        if d.exists():
            # 如果目录本身是目标目录的一部分（原地转换），跳过
            pass

    # --- 结果 ---
    if errors:
        print(f"\n⚠️  有 {len(errors)} 个文件搬移失败：")
        for basename, err in errors[:10]:
            print(f"   - {basename}: {err}")
        if len(errors) > 10:
            print(f"   ... 还有 {len(errors) - 10} 个")
    else:
        print("\n🎉 全部完成，零错误！")

    # 打印最终结构
    print("\n📁 最终目录结构：")
    for name in splits:
        img_count = len(list((SOURCE_DIR / TARGET_IMAGES / name).iterdir()))
        lbl_count = len(list((SOURCE_DIR / TARGET_LABELS / name).iterdir()))
        print(f"   {TARGET_IMAGES}/{name}: {img_count} 个")
        print(f"   {TARGET_LABELS}/{name}: {lbl_count} 个")


if __name__ == "__main__":
    main()
