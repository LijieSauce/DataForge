
import os
import json
import yaml
import shutil
from pathlib import Path
from typing import List, Dict, Tuple
import xml.etree.ElementTree as ET
from collections import defaultdict
from serve.formatConversion.BaseToYOLO import BaseToYOLO

class VocToYOLO(BaseToYOLO):
    """Pascal VOC格式转YOLO格式"""
    
    def convert(self):
        """执行VOC到YOLO的转换"""
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
        """转换单个数据集划分"""
        if output_split is None:
            output_split = split
        
        split_path = self._find_split_path(split)
        if not split_path:
            return
        
        # 查找annotations和images目录
        annotations_dir = split_path / "annotations"
        images_dir = split_path / "images"
        
        if not annotations_dir.exists():
            annotations_dir = split_path / "Annotations"
        if not images_dir.exists():
            images_dir = split_path / "JPEGImages"
        
        if not annotations_dir.exists() or not images_dir.exists():
            print(f"⚠️ 警告: {split}目录结构不完整")
            return
        
        # 处理每个xml文件
        for xml_file in annotations_dir.glob("*.xml"):
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # 获取图像信息
            filename = root.find('filename').text
            size = root.find('size')
            img_width = int(size.find('width').text)
            img_height = int(size.find('height').text)
            
            # 转换标注
            yolo_lines = []
            for obj in root.findall('object'):
                label_name = obj.find('name').text
                
                # 检查是否保留此类别
                if label_name not in self.keep_labels:
                    continue
                
                new_class_id = self.label_map[label_name]
                
                # 获取边界框
                bndbox = obj.find('bndbox')
                xmin = float(bndbox.find('xmin').text)
                ymin = float(bndbox.find('ymin').text)
                xmax = float(bndbox.find('xmax').text)
                ymax = float(bndbox.find('ymax').text)
                
                # 转换为YOLO格式
                x_center, y_center, width, height = self._normalize_bbox(
                    [xmin, ymin, xmax, ymax], img_width, img_height, format="xyxy"
                )
                
                yolo_lines.append(
                    f"{new_class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n"
                )
            
            # 如果没有保留的标注，跳过这张图像
            if not yolo_lines:
                continue
            
            # 复制图像
            src_img = images_dir / filename
            if src_img.exists():
                dst_img = self.output_path / "images" / output_split / filename
                shutil.copy2(src_img, dst_img)
                
                # 写入标注文件
                label_filename = xml_file.stem + ".txt"
                label_path = self.output_path / "labels" / output_split / label_filename
                with open(label_path, 'w') as f:
                    f.writelines(yolo_lines)