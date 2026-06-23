import os
import json
import yaml
import shutil
from pathlib import Path
from typing import List, Dict, Tuple
import xml.etree.ElementTree as ET
from collections import defaultdict
class BaseToYOLO:
    """基础转换类"""
    
    def __init__(self, input_path: str, output_path: str, keep_labels: List[str]):
        """
        初始化转换器
        
        Args:
            input_path: 输入数据集路径
            output_path: 输出数据集路径
            keep_labels: 要保留的标签列表（大小写敏感）
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.keep_labels = keep_labels
        
        # 创建标签映射（旧标签名 -> 新标签ID）
        self.label_map = {label: idx for idx, label in enumerate(keep_labels)}
        
        # 验证输入
        self._validate_input()
        
    def _validate_input(self):
        """验证输入数据集"""
        if not self.input_path.exists():
            raise FileNotFoundError(f"输入路径不存在: {self.input_path}")
        
        yaml_path = self.input_path / "dataset.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"缺少dataset.yaml文件: {yaml_path}")
        
        # 检查train和val目录
        train_path = self._find_split_path("train")
        val_path = self._find_split_path("val")
        
        if not train_path:
            raise FileNotFoundError("找不到train目录")
        if not val_path:
            raise FileNotFoundError("找不到val目录")
    
    def _find_split_path(self, split: str) -> Path:
        """
        查找数据集划分目录
        
        Args:
            split: 'train', 'val', 'test', 'valid'等
        
        Returns:
            找到的路径，找不到返回None
        """
        # 可能的目录名变种
        variants = [split, split.lower(), split.upper()]
        if split == "val":
            variants.extend(["valid", "Valid", "VALID"])
        
        for variant in variants:
            path = self.input_path / variant
            if path.exists():
                return path
        return None
    
    def _create_output_structure(self):
        """创建输出目录结构"""
        for split in ["train", "val"]:
            (self.output_path / "images" / split).mkdir(parents=True, exist_ok=True)
            (self.output_path / "labels" / split).mkdir(parents=True, exist_ok=True)
    
    def _normalize_bbox(self, bbox: List[float], img_width: int, img_height: int, 
                       format: str = "xywh") -> Tuple[float, float, float, float]:
        """
        将边界框转换为YOLO格式（归一化的中心点坐标）
        
        Args:
            bbox: 边界框坐标
            img_width: 图像宽度
            img_height: 图像高度
            format: 输入格式 'xywh' (x,y,w,h) 或 'xyxy' (x1,y1,x2,y2)
        
        Returns:
            (x_center, y_center, width, height) 归一化后的坐标
        """
        if format == "xyxy":
            x1, y1, x2, y2 = bbox
            x = x1
            y = y1
            w = x2 - x1
            h = y2 - y1
        else:  # xywh
            x, y, w, h = bbox
        
        # 归一化并转换为中心点格式
        x_center = (x + w / 2) / img_width
        y_center = (y + h / 2) / img_height
        width = w / img_width
        height = h / img_height
        
        return x_center, y_center, width, height
    
    def _update_dataset_yaml(self):
        """更新dataset.yaml文件"""
        yaml_path = self.output_path / "dataset.yaml"
        
        # 读取原始yaml
        input_yaml_path = self.input_path / "dataset.yaml"
        with open(input_yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # 更新类别信息
        data['nc'] = len(self.keep_labels)
        data['names'] = self.keep_labels
        
        # 更新路径
        data['train'] = 'images/train'
        data['val'] = 'images/val'
        
        # 移除test路径（如果有）
        if 'test' in data:
            del data['test']
        
        # 写入新yaml
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    
    def convert(self):
        """执行转换（子类实现）"""
        raise NotImplementedError("子类必须实现convert方法")