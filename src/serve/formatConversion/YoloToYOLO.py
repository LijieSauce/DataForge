import os
import json
import yaml
import shutil
from pathlib import Path
from typing import List, Dict, Tuple
import xml.etree.ElementTree as ET
from collections import defaultdict
from .BaseToYOLO import BaseToYOLO

class YoloToYOLO(BaseToYOLO):
    """YOLO格式转YOLO格式（标准化和标签过滤）"""
    
    def convert(self):
        """执行YOLO到YOLO的转换"""
        self._create_output_structure()
        
        # 读取原始yaml获取类别映射
        input_yaml_path = self.input_path / "dataset.yaml"
        with open(input_yaml_path, 'r', encoding='utf-8') as f:
            input_yaml = yaml.safe_load(f)
        
        # 构建原始类别映射（ID -> 名称）
        if 'names' in input_yaml:
            if isinstance(input_yaml['names'], list):
                self.old_label_map = {idx: name for idx, name in enumerate(input_yaml['names'])}
            elif isinstance(input_yaml['names'], dict):
                self.old_label_map = input_yaml['names']
        else:
            raise ValueError("dataset.yaml中缺少names字段")
        
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
        """转换单个数据集划分"""
        if output_split is None:
            output_split = split
        
        split_path = self._find_split_path(split)
        if not split_path:
            return
        
        # 查找images和labels目录
        images_dir = split_path / "images"
        labels_dir = split_path / "labels"
        
        # 如果split目录下没有images/labels，可能split本身就是images或labels的父目录
        if not images_dir.exists():
            images_dir = split_path
        if not labels_dir.exists():
            # 尝试其他可能的位置
            labels_dir = split_path.parent / "labels" / split.name
            if not labels_dir.exists():
                labels_dir = split_path
        
        # 处理每个标注文件
        if labels_dir.exists():
            for label_file in labels_dir.glob("*.txt"):
                # 读取并转换标注
                yolo_lines = []
                with open(label_file, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) < 5:
                            continue
                        
                        old_class_id = int(parts[0])
                        
                        # 获取原始类别名称
                        if old_class_id not in self.old_label_map:
                            continue
                        
                        label_name = self.old_label_map[old_class_id]
                        
                        # 检查是否保留此类别
                        if label_name not in self.keep_labels:
                            continue
                        
                        new_class_id = self.label_map[label_name]
                        
                        # 保留原始坐标
                        coords = parts[1:5]
                        yolo_lines.append(f"{new_class_id} {' '.join(coords)}\n")
                
                # 如果没有保留的标注，跳过
                if not yolo_lines:
                    continue
                
                # 复制图像
                img_name = label_file.stem
                for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                    src_img = images_dir / f"{img_name}{ext}"
                    if src_img.exists():
                        dst_img = self.output_path / "images" / output_split / src_img.name
                        shutil.copy2(src_img, dst_img)
                        
                        # 写入标注文件
                        label_path = self.output_path / "labels" / output_split / label_file.name
                        with open(label_path, 'w') as f:
                            f.writelines(yolo_lines)
                        break


