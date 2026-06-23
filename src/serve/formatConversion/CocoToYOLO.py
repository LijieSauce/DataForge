import os
import json
import yaml
import shutil
from pathlib import Path
from typing import List, Dict, Tuple
import xml.etree.ElementTree as ET
from collections import defaultdict
from serve.formatConversion.BaseToYOLO import BaseToYOLO

class CocoToYOLO(BaseToYOLO):
    """COCO格式转YOLO格式"""
    
    def convert(self):
        """执行COCO到YOLO的转换"""
        self._create_output_structure()
        
        # 处理train和val
        for split in ["train", "val"]:
            self._convert_split(split)
        
        # 处理test（如果存在）
        test_path = self._find_split_path("test")
        if test_path:
            self._convert_split("test", output_split="val")
        
        # 更新yaml
        self._update_dataset_yaml()
        
        print(f"✨ 转换完成！输出路径: {self.output_path}")
    
    def _convert_split(self, split: str, output_split: str = None):
        """
        转换单个数据集划分
        
        Args:
            split: 输入划分名称
            output_split: 输出划分名称（默认与split相同）
        """
        if output_split is None:
            output_split = split
        
        split_path = self._find_split_path(split)
        if not split_path:
            return
        
        # 查找annotations json文件
        json_files = list(split_path.glob("*.json"))
        if not json_files:
            # 可能在父目录的annotations文件夹
            json_path = self.input_path / "annotations" / f"instances_{split}.json"
            if not json_path.exists():
                print(f"⚠️ 警告: 找不到{split}的json标注文件")
                return
        else:
            json_path = json_files[0]
        
        # 读取COCO json
        with open(json_path, 'r', encoding='utf-8') as f:
            coco_data = json.load(f)
        
        # 构建类别映射
        category_map = {}  # coco_cat_id -> label_name
        for cat in coco_data['categories']:
            category_map[cat['id']] = cat['name']
        
        # 构建图像ID到信息的映射
        image_map = {img['id']: img for img in coco_data['images']}
        
        # 按图像分组标注
        annotations_by_image = defaultdict(list)
        for ann in coco_data['annotations']:
            annotations_by_image[ann['image_id']].append(ann)
        
        # 处理每张图像
        for img_id, anns in annotations_by_image.items():
            img_info = image_map[img_id]
            img_filename = img_info['file_name']
            img_width = img_info['width']
            img_height = img_info['height']
            
            # 过滤并转换标注
            yolo_lines = []
            for ann in anns:
                cat_name = category_map[ann['category_id']]
                
                # 检查是否保留此类别
                if cat_name not in self.keep_labels:
                    continue
                
                new_class_id = self.label_map[cat_name]
                bbox = ann['bbox']  # COCO格式: [x, y, width, height]
                
                # 转换为YOLO格式
                x_center, y_center, width, height = self._normalize_bbox(
                    bbox, img_width, img_height, format="xywh"
                )
                
                yolo_lines.append(
                    f"{new_class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n"
                )
            
            # 如果没有保留的标注，跳过这张图像
            if not yolo_lines:
                continue
            
            # 复制图像
            src_img = split_path / "images" / img_filename if (split_path / "images").exists() else split_path / img_filename
            if not src_img.exists():
                # 尝试在images目录下查找
                src_img = self.input_path / "images" / split / img_filename
            
            if src_img.exists():
                dst_img = self.output_path / "images" / output_split / img_filename
                shutil.copy2(src_img, dst_img)
                
                # 写入标注文件
                label_filename = Path(img_filename).stem + ".txt"
                label_path = self.output_path / "labels" / output_split / label_filename
                with open(label_path, 'w') as f:
                    f.writelines(yolo_lines)