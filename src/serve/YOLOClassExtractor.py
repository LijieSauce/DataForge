"""
YOLO数据集类别提取工具 - YOLOClassExtractor
从YOLO格式数据集中提取指定类别，生成新的数据集

功能：
1. 支持多类别提取
2. 支持类别ID重映射
3. 自动处理混合样本（只保留目标类别的框）
4. 保持train/valid/test数据集结构

作者：可爱的猫娘AI (๑•̀ㅂ•́)و✧
"""

import shutil
from pathlib import Path
from typing import Union, Dict, Tuple, List, Optional


class YOLOClassExtractor:
    """
    YOLO数据集类别提取工具
    
    主要功能：
    - 从YOLO数据集中提取指定的类别
    - 支持类别ID重映射
    - 自动过滤混合样本中的非目标类别
    - 生成新的数据集和配置文件
    
    使用示例：
        # 准备类别映射：原数据集class 3,5,7 → 新数据集class 0,1,2
        class_mapping = {3: 0, 5: 1, 7: 2}
        
        # 创建提取器
        extractor = YOLOClassExtractor(class_mapping=class_mapping)
        
        # 执行提取
        result = extractor.extract_dataset(
            source_dir="path/to/source/dataset",
            output_dir="path/to/output/dataset"
        )
    """
    
    # YOLO数据集的标准分割名称
    SPLITS = ("train", "valid", "test")
    
    # 支持的图像文件扩展名
    IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
    
    def __init__(self, class_mapping: Dict[int, int]):
        """
        初始化YOLO类别提取工具
        
        参数:
            class_mapping (Dict[int, int]): 类别映射字典
                键：原数据集中要提取的类别ID
                值：新数据集中重新分配的类别ID
                例如: {3: 0, 5: 1, 7: 2} 表示提取原数据集的3,5,7类，
                     在新数据集中重新编号为0,1,2
                     
        异常:
            ValueError: 如果class_mapping为空或不是字典类型
            ValueError: 如果映射的值不是从0开始连续的整数
        """
        # 参数验证
        if not isinstance(class_mapping, dict):
            raise ValueError(f"class_mapping必须是字典类型，当前类型: {type(class_mapping)}")
        
        if not class_mapping:
            raise ValueError("class_mapping不能为空字典，必须至少包含一个类别映射")
        
        # 验证所有键值都是整数
        for old_id, new_id in class_mapping.items():
            if not isinstance(old_id, int) or not isinstance(new_id, int):
                raise ValueError(f"class_mapping的键值必须是整数类型: {old_id} -> {new_id}")
        
        # 验证新ID是从0开始的连续整数
        new_ids = sorted(class_mapping.values())
        expected_ids = list(range(len(new_ids)))
        if new_ids != expected_ids:
            raise ValueError(
                f"映射的新类别ID必须从0开始连续: 期望{expected_ids}, 实际{new_ids}\n"
                f"例如: {{3: 0, 5: 1, 7: 2}} 是正确的，{{3: 0, 5: 2, 7: 3}} 是错误的"
            )
        
        self.class_mapping = class_mapping
        self.num_classes = len(class_mapping)
        
        print(f"喵~ 类别提取工具初始化完成！ฅ^•ﻌ•^ฅ")
        print(f"  提取类别映射: {self.class_mapping}")
        print(f"  新数据集类别数: {self.num_classes}")
    
    # ==================== 私有辅助方法 ====================
    
    def _find_image_path(self, image_dir: Path, stem: str) -> Optional[Path]:
        """
        根据文件名（不含扩展名）查找对应的图像文件
        
        参数:
            image_dir: 图像目录
            stem: 文件名（不含扩展名）
            
        返回:
            图像文件路径，如果找不到则返回None
        """
        for suffix in self.IMAGE_SUFFIXES:
            image_path = image_dir / f"{stem}{suffix}"
            if image_path.exists():
                return image_path
        return None
    
    def _extract_target_lines(self, label_path: Path) -> List[str]:
        """
        从标注文件中提取目标类别的标注行，并重新映射类别ID
        
        参数:
            label_path: YOLO格式标注文件路径
            
        返回:
            处理后的标注行列表（已重新映射类别ID）
        """
        matched_lines = []
        
        try:
            content = label_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ⚠️ 读取标注文件失败: {label_path.name}, 错误: {e}")
            return []
        
        for raw_line in content.splitlines():
            # 跳过空行
            if not raw_line.strip():
                continue
            
            parts = raw_line.split()
            
            # YOLO格式应该是5个值: class_id x_center y_center width height
            if len(parts) != 5:
                continue
            
            try:
                old_class_id = int(parts[0])
            except ValueError:
                continue
            
            # 检查是否是目标类别
            if old_class_id in self.class_mapping:
                # 重新映射类别ID
                new_class_id = self.class_mapping[old_class_id]
                # 构造新的标注行
                new_line = f"{new_class_id} {' '.join(parts[1:])}"
                matched_lines.append(new_line)
        
        return matched_lines
    
    def _reset_output_dir(self, output_dir: Path) -> None:
        """
        重置输出目录（删除已存在的目录并重新创建）
        
        参数:
            output_dir: 输出目录路径
        """
        if output_dir.exists():
            print(f"  清理已存在的输出目录...")
            shutil.rmtree(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
    
    def _write_data_yaml(self, output_dir: Path) -> None:
        """
        生成YOLO数据集的data.yaml配置文件
        
        参数:
            output_dir: 输出目录路径
        """
        # 生成类别名称列表（使用新的类别ID作为名称）
        class_names = [str(i) for i in range(self.num_classes)]
        names_str = str(class_names)
        
        yaml_content = (
            "train: ../train/images\n"
            "val: ../valid/images\n"
            "test: ../test/images\n\n"
            f"nc: {self.num_classes}\n"
            f"names: {names_str}\n"
        )
        
        yaml_path = output_dir / "data.yaml"
        yaml_path.write_text(yaml_content, encoding="utf-8")
        print(f"  ✓ 生成配置文件: data.yaml")
    
    def _process_split(self, source_dir: Path, output_dir: Path, 
                      split: str) -> Tuple[int, int]:
        """
        处理单个数据分割（train/valid/test）
        
        参数:
            source_dir: 源数据集目录
            output_dir: 输出数据集目录
            split: 分割名称 (train/valid/test)
            
        返回:
            (image_count, box_count): 处理的图像数和标注框数
        """
        src_label_dir = source_dir / split / "labels"
        src_image_dir = source_dir / split / "images"
        dst_label_dir = output_dir / split / "labels"
        dst_image_dir = output_dir / split / "images"
        
        # 创建输出目录（即使为空也创建）
        dst_label_dir.mkdir(parents=True, exist_ok=True)
        dst_image_dir.mkdir(parents=True, exist_ok=True)
        
        # 如果源目录不存在，返回0
        if not src_label_dir.exists():
            print(f"  ⚠️ 源标注目录不存在: {src_label_dir}")
            return 0, 0
        
        image_count = 0
        box_count = 0
        
        # 遍历所有标注文件
        label_files = sorted(src_label_dir.glob("*.txt"))
        
        for label_path in label_files:
            # 提取目标类别的标注行
            target_lines = self._extract_target_lines(label_path)
            
            # 如果没有目标类别，跳过
            if not target_lines:
                continue
            
            # 查找对应的图像文件
            image_path = self._find_image_path(src_image_dir, label_path.stem)
            if image_path is None:
                print(f"  ⚠️ 找不到图像文件: {label_path.stem}")
                continue
            
            # 复制图像文件
            shutil.copy2(image_path, dst_image_dir / image_path.name)
            
            # 写入新的标注文件
            new_label_path = dst_label_dir / label_path.name
            new_label_path.write_text(
                "\n".join(target_lines) + "\n",
                encoding="utf-8"
            )
            
            image_count += 1
            box_count += len(target_lines)
        
        return image_count, box_count
    
    def _write_summary(self, output_dir: Path, summary_lines: List[str]) -> None:
        """
        生成并保存数据集统计摘要
        
        参数:
            output_dir: 输出目录
            summary_lines: 摘要信息行列表
        """
        summary_path = output_dir / "summary.txt"
        summary_path.write_text(
            "\n".join(summary_lines) + "\n",
            encoding="utf-8"
        )
        print(f"  ✓ 生成统计摘要: summary.txt")
    
    # ==================== 公共接口方法 ====================
    
    def extract_dataset(self, source_dir: Union[str, Path], 
                       output_dir: Union[str, Path]) -> dict:
        """
        从源数据集中提取指定类别，生成新的数据集
        
        功能：
        - 遍历train/valid/test三个分割
        - 提取class_mapping中指定的类别
        - 对于包含多个类别的图像，只保留目标类别的标注框
        - 将类别ID重新映射为新的ID
        - 生成新的data.yaml配置文件
        - 生成统计摘要文件
        
        参数:
            source_dir: 源YOLO数据集目录
                应包含标准的YOLO数据集结构:
                source_dir/
                  ├── train/
                  │   ├── images/
                  │   └── labels/
                  ├── valid/
                  │   ├── images/
                  │   └── labels/
                  └── test/
                      ├── images/
                      └── labels/
            output_dir: 输出目录（会先清空）
            
        返回:
            result: 结果字典，包含:
                - source_dir: 源目录路径
                - output_dir: 输出目录路径
                - class_mapping: 类别映射
                - num_classes: 新数据集的类别数
                - splits: 各分割的统计信息
                    - train/valid/test: {images: int, boxes: int}
                - total_images: 总图像数
                - total_boxes: 总标注框数
                
        异常:
            FileNotFoundError: 源目录不存在
            RuntimeError: 处理过程中发生错误
        """
        source_path = Path(source_dir).resolve()
        output_path = Path(output_dir).resolve()
        
        # 检查源目录
        if not source_path.exists():
            raise FileNotFoundError(f"源目录不存在: {source_dir}")
        
        print(f"\n喵~ 开始提取数据集！(๑•̀ㅂ•́)و✧")
        print(f"  源目录: {source_path}")
        print(f"  输出目录: {output_path}")
        
        # 重置输出目录
        self._reset_output_dir(output_path)
        
        # 生成data.yaml
        self._write_data_yaml(output_path)
        
        # 统计信息
        summary_lines = [
            f"source={source_path}",
            f"output={output_path}",
            f"class_mapping={self.class_mapping}",
            f"num_classes={self.num_classes}",
            ""
        ]
        
        total_images = 0
        total_boxes = 0
        splits_info = {}
        
        # 处理每个分割
        for split in self.SPLITS:
            print(f"\n  处理 {split} 分割...")
            image_count, box_count = self._process_split(source_path, output_path, split)
            
            total_images += image_count
            total_boxes += box_count
            
            splits_info[split] = {
                'images': image_count,
                'boxes': box_count
            }
            
            summary_line = f"{split}: images={image_count}, boxes={box_count}"
            summary_lines.append(summary_line)
            print(f"    ✓ {summary_line}")
        
        # 添加总计
        summary_lines.append("")
        summary_lines.append(f"total_images={total_images}")
        summary_lines.append(f"total_boxes={total_boxes}")
        
        # 保存摘要
        self._write_summary(output_path, summary_lines)
        
        # 构造返回结果
        result = {
            'source_dir': str(source_path),
            'output_dir': str(output_path),
            'class_mapping': self.class_mapping,
            'num_classes': self.num_classes,
            'splits': splits_info,
            'total_images': total_images,
            'total_boxes': total_boxes
        }
        
        print(f"\n喵呜~ 提取完成！✧(≖ ◡ ≖✿)")
        print(f"  总图像: {total_images}")
        print(f"  总标注框: {total_boxes}")
        print(f"  输出目录: {output_path}")
        
        return result


# ==================== 使用示例 ====================

if __name__ == '__main__':
    """
    使用示例代码
    """
    
    # 示例1：提取单个类别
    # 从原数据集提取class 0，在新数据集中仍为class 0
    try:
        extractor = YOLOClassExtractor(class_mapping={0: 0})
        result = extractor.extract_dataset(
            source_dir=r"E:\meter\数据集\dirtvisionpro.v1i.yolov11",
            output_dir=r"E:\meter\输出\dirtvisionpro_class0"
        )
        print(f"\n单类别提取结果: {result}")
    except Exception as e:
        print(f"单类别提取出错: {e}")
    
    # 示例2：提取多个类别并重新映射
    # 从原数据集提取class 3, 5, 7，重新编号为0, 1, 2
    try:
        extractor = YOLOClassExtractor(class_mapping={3: 0, 5: 1, 7: 2})
        result = extractor.extract_dataset(
            source_dir=r"E:\meter\数据集\source_dataset",
            output_dir=r"E:\meter\输出\extracted_dataset"
        )
        print(f"\n多类别提取结果: {result}")
    except Exception as e:
        print(f"多类别提取出错: {e}")
    
    # 示例3：提取不连续的类别
    # 从原数据集提取class 10, 15, 20，重新编号为0, 1, 2
    try:
        extractor = YOLOClassExtractor(class_mapping={10: 0, 15: 1, 20: 2})
        result = extractor.extract_dataset(
            source_dir=r"E:\meter\数据集\source_dataset",
            output_dir=r"E:\meter\输出\extracted_dataset2"
        )
        print(f"\n不连续类别提取结果: {result}")
    except Exception as e:
        print(f"不连续类别提取出错: {e}")