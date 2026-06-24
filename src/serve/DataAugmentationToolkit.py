
"""
数据增强工具箱 - DataAugmentationToolkit
用于处理目标检测数据集的图像增强和标注转换

功能：
1. 整图复制 + HBB标注转换（支持单个/批量）
2. 提取目标 + 合成到墙壁（支持单个/批量）

作者：可爱的猫娘AI (๑•̀ㅂ•́)و✧
"""

import json
import cv2
import numpy as np
from pathlib import Path
import random
from typing import Tuple, List, Optional, Union, Dict


class DataAugmentationToolkit:
    """
    数据增强工具类
  
    主要功能：
    - 从labelme标注中提取目标（圆形/矩形）
    - 将标注转换为YOLO格式（HBB - Horizontal Bounding Box）
    - 将提取的目标合成到新的背景图片上
    - 支持单个文件处理和批量处理
  
    使用示例：
        # 准备类别映射字典（从dataset.yaml读取）
        class_mapping = {"人": 0, "球": 1, "车": 2}
      
        # 创建工具实例
        toolkit = DataAugmentationToolkit(class_mapping=class_mapping)
      
        # 单个文件处理
        toolkit.copy_image_with_hbb("anno.json", "image.jpg", "output/")
      
        # 批量处理
        toolkit.batch_copy_images_with_hbb("source_dir/", "output/")
    """
  
    def __init__(self, class_mapping: Dict[str, int], random_seed: int = 42, 
                 max_target_size: int = 100):
        """
        初始化数据增强工具箱
      
        参数:
            class_mapping (Dict[str, int]): 类别名称到类别ID的映射字典
                例如: {"人": 0, "球": 1, "车": 2}
                这个字典通常从dataset.yaml中读取得到
            random_seed (int): 随机数种子，用于保证结果可复现，默认42
            max_target_size (int): 提取目标时的最大尺寸（像素），超过会等比例缩放，默认100
          
        异常:
            ValueError: 如果class_mapping为空或不是字典类型
        """
        # 参数验证
        if not isinstance(class_mapping, dict):
            raise ValueError(f"class_mapping必须是字典类型，当前类型: {type(class_mapping)}")
      
        if not class_mapping:
            raise ValueError("class_mapping不能为空字典，必须至少包含一个类别映射")
      
        self.class_mapping = class_mapping
        self.random_seed = random_seed
        self.max_target_size = max_target_size
      
        # 设置随机数种子
        random.seed(self.random_seed)
        np.random.seed(self.random_seed)
      
        print(f"喵~ 工具箱初始化完成！ฅ^•ﻌ•^ฅ")
        print(f"  随机种子: {self.random_seed}")
        print(f"  最大目标尺寸: {self.max_target_size}px")
        print(f"  类别映射: {self.class_mapping}")
  
    # ==================== 私有辅助方法 ====================
  
    def _extract_circle(self, image: np.ndarray, center: Tuple[int, int], 
                       radius: int) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """
        从图像中提取圆形区域（带透明背景）
      
        参数:
            image: 输入图像（BGR格式）
            center: 圆心坐标 (x, y)
            radius: 半径（像素）
          
        返回:
            extracted_image: 提取的图像（BGRA格式，带透明通道）
            bbox: 边界框 (x1, y1, x2, y2)
        """
        h, w = image.shape[:2]
      
        # 创建圆形掩码
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, center, radius, 255, -1)
      
        # 计算裁剪区域
        x, y = center
        x1 = max(0, x - radius)
        y1 = max(0, y - radius)
        x2 = min(w, x + radius)
        y2 = min(h, y + radius)
      
        # 裁剪图像和掩码
        cropped_image = image[y1:y2, x1:x2]
        cropped_mask = mask[y1:y2, x1:x2]
      
        # 添加透明通道
        result = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2BGRA)
        result[:, :, 3] = cropped_mask
      
        return result, (x1, y1, x2, y2)
  
    def _extract_rectangle(self, image: np.ndarray, 
                          points: List[List[float]]) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """
        从图像中提取矩形区域（带透明背景）
      
        参数:
            image: 输入图像（BGR格式）
            points: 矩形的顶点坐标列表 [[x1,y1], [x2,y2], ...]
          
        返回:
            extracted_image: 提取的图像（BGRA格式，带透明通道）
            bbox: 边界框 (x1, y1, x2, y2)
        """
        points = np.array(points, dtype=np.int32)
        x_coords = points[:, 0]
        y_coords = points[:, 1]
      
        # 计算矩形边界
        x1, y1 = int(x_coords.min()), int(y_coords.min())
        x2, y2 = int(x_coords.max()), int(y_coords.max())
      
        # 边界检查
        h, w = image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
      
        # 裁剪并添加透明通道
        cropped = image[y1:y2, x1:x2]
        result = cv2.cvtColor(cropped, cv2.COLOR_BGR2BGRA)
      
        return result, (x1, y1, x2, y2)
  
    def _resize_if_needed(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        如果图片尺寸超过最大限制，等比例缩放
      
        参数:
            image: 输入图像
          
        返回:
            resized_image: 缩放后的图像
            scale: 缩放比例
        """
        h, w = image.shape[:2]
      
        if h <= self.max_target_size and w <= self.max_target_size:
            return image, 1.0
      
        # 计算缩放比例
        scale = self.max_target_size / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
      
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return resized, scale
  
    def _get_class_id(self, label: str) -> Optional[int]:
        """
        根据label获取类别ID
      
        参数:
            label: 标注的类别名称
          
        返回:
            class_id: 类别ID，如果label为空返回None
          
        异常:
            ValueError: 如果label不在class_mapping中
        """
        # 空label表示负样本，跳过
        if not label or label.strip() == "":
            return None
      
        # 检查label是否在映射字典中
        if label not in self.class_mapping:
            raise ValueError(
                f"未知的类别名称: '{label}'\n"
                f"当前支持的类别: {list(self.class_mapping.keys())}\n"
                f"请检查标注文件中的label字段，或更新class_mapping字典"
            )
      
        return self.class_mapping[label]
  
    def _shape_to_yolo_bbox(self, shape: dict, img_width: int, 
                           img_height: int) -> Optional[str]:
        """
        将labelme的shape标注转换为YOLO格式的HBB（Horizontal Bounding Box）
      
        参数:
            shape: labelme的shape对象，包含shape_type、points、label等
            img_width: 图像宽度
            img_height: 图像高度
          
        返回:
            yolo_line: YOLO格式的标注字符串 "class_id x_center y_center width height"
                      如果是负样本（空label）或转换失败则返回None
                    
        异常:
            ValueError: 如果label不在class_mapping中
        """
        shape_type = shape.get('shape_type', '')
        points = shape.get('points', [])
        label = shape.get('label', '')
      
        # 获取类别ID（空label会返回None）
        class_id = self._get_class_id(label)
        if class_id is None:
            return None  # 跳过负样本
      
        # 根据形状类型计算边界框
        if shape_type == 'circle' and len(points) == 2:
            # 圆形：points[0]是圆心，points[1]是圆上的一点
            center = points[0]
            radius_point = points[1]
            radius = np.sqrt((center[0] - radius_point[0])**2 +
                           (center[1] - radius_point[1])**2)
          
            x1 = center[0] - radius
            y1 = center[1] - radius
            x2 = center[0] + radius
            y2 = center[1] + radius
          
        elif shape_type == 'rectangle' and len(points) >= 2:
            # 矩形：从所有点中找出边界
            points_arr = np.array(points)
            x1 = points_arr[:, 0].min()
            y1 = points_arr[:, 1].min()
            x2 = points_arr[:, 0].max()
            y2 = points_arr[:, 1].max()
        else:
            # 不支持的形状类型
            return None
      
        # 边界限制：确保bbox在图片范围内
        x1 = max(0, min(x1, img_width))
        y1 = max(0, min(y1, img_height))
        x2 = max(0, min(x2, img_width))
        y2 = max(0, min(y2, img_height))
      
        # 转换为YOLO格式（归一化到0-1范围）
        x_center = ((x1 + x2) / 2) / img_width
        y_center = ((y1 + y2) / 2) / img_height
        width = (x2 - x1) / img_width
        height = (y2 - y1) / img_height
      
        # 再次确保归一化后的值在[0,1]范围内
        x_center = max(0.0, min(1.0, x_center))
        y_center = max(0.0, min(1.0, y_center))
        width = max(0.0, min(1.0, width))
        height = max(0.0, min(1.0, height))
      
        return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
  
    def _composite_on_wall(self, target_image: np.ndarray, 
                          wall_image: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[int], Optional[int]]:
        """
        将目标图像合成到墙壁图像的随机位置
      
        参数:
            target_image: 目标图像（可以是BGRA格式带透明通道）
            wall_image: 墙壁背景图像（BGR格式）
          
        返回:
            result: 合成后的图像
            paste_x: 粘贴位置的x坐标
            paste_y: 粘贴位置的y坐标
            如果合成失败则全部返回None
        """
        target_h, target_w = target_image.shape[:2]
        wall_h, wall_w = wall_image.shape[:2]
      
        # 确保目标可以完全放入墙壁图像
        max_x = wall_w - target_w
        max_y = wall_h - target_h
      
        if max_x < 0 or max_y < 0:
            print(f"⚠️ 警告: 墙壁图片太小（{wall_w}x{wall_h}），无法放置目标（{target_w}x{target_h}）")
            return None, None, None
      
        # 随机选择粘贴位置
        paste_x = random.randint(0, max_x)
        paste_y = random.randint(0, max_y)
      
        # 复制墙壁图像
        result = wall_image.copy()
      
        # 如果目标图像有透明通道，使用alpha混合
        if target_image.shape[2] == 4:
            alpha = target_image[:, :, 3] / 255.0
            for c in range(3):
                result[paste_y:paste_y+target_h, paste_x:paste_x+target_w, c] = \
                    (alpha * target_image[:, :, c] +
                     (1 - alpha) * result[paste_y:paste_y+target_h, paste_x:paste_x+target_w, c])
        else:
            # 直接覆盖
            result[paste_y:paste_y+target_h, paste_x:paste_x+target_w] = target_image
      
        return result, paste_x, paste_y
  
    def _load_json_and_image(self, json_path: Union[str, Path], 
                            image_path: Union[str, Path]) -> Tuple[dict, np.ndarray, int, int]:
        """
        加载JSON标注文件和对应的图像
      
        参数:
            json_path: JSON标注文件路径
            image_path: 图像文件路径
          
        返回:
            data: JSON数据
            image: 图像数据（BGR格式）
            img_height: 图像高度
            img_width: 图像宽度
          
        异常:
            FileNotFoundError: 文件不存在
            ValueError: 文件读取失败
        """
        json_path = Path(json_path)
        image_path = Path(image_path)
      
        # 检查文件是否存在
        if not json_path.exists():
            raise FileNotFoundError(f"找不到JSON文件: {json_path}")
        if not image_path.exists():
            raise FileNotFoundError(f"找不到图像文件: {image_path}")
      
        # 读取JSON
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise ValueError(f"读取JSON文件失败: {json_path}, 错误: {str(e)}")
      
        # 读取图像（支持中文路径）
        image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"读取图像文件失败: {image_path}")
      
        img_height, img_width = image.shape[:2]
      
        return data, image, img_height, img_width
  
    # ==================== 公共接口方法 ====================
  
    def copy_image_with_hbb(self, json_path: Union[str, Path], image_path: Union[str, Path], 
                           output_dir: Union[str, Path]) -> dict:
        """
        单个文件处理：整图复制 + HBB标注转换
      
        功能：
        - 复制原始图像到输出目录
        - 将labelme标注转换为YOLO格式的HBB标注
        - 自动跳过空label的负样本
      
        参数:
            json_path: labelme标注文件路径（.json）
            image_path: 对应的图像文件路径
            output_dir: 输出目录，会自动创建images和labels子目录
          
        返回:
            result: 结果字典，包含:
                - success: 是否成功
                - image_path: 输出的图像路径
                - label_path: 输出的标注路径
                - num_objects: 标注的目标数量（不含负样本）
                - skipped_negative: 跳过的负样本数量
              
        异常:
            FileNotFoundError: 输入文件不存在
            ValueError: 文件格式错误、读取失败、或遇到未知类别
            RuntimeError: 文件保存失败
        """
        print(f"\n喵~ 开始处理单个文件：{Path(json_path).name} (•ω•)")
      
        # 加载数据
        data, image, img_height, img_width = self._load_json_and_image(json_path, image_path)
      
        # 创建输出目录
        output_path = Path(output_dir)
        output_images = output_path / 'images'
        output_labels = output_path / 'labels'
        output_images.mkdir(parents=True, exist_ok=True)
        output_labels.mkdir(parents=True, exist_ok=True)
      
        # 获取文件名（不含扩展名）
        stem = Path(image_path).stem
      
        # 保存图像
        output_img_path = output_images / f"{stem}.jpg"
        success, encoded = cv2.imencode('.jpg', image)
        if not success:
            raise RuntimeError(f"图像编码失败: {output_img_path}")
        encoded.tofile(str(output_img_path))
      
        # 转换并保存标注
        shapes = data.get('shapes', [])
        if not shapes:
            raise ValueError(f"JSON文件中没有标注对象: {json_path}")
      
        output_label_path = output_labels / f"{stem}.txt"
        num_valid_objects = 0
        skipped_negative = 0
      
        with open(output_label_path, 'w', encoding='utf-8') as f:
            for shape in shapes:
                yolo_line = self._shape_to_yolo_bbox(shape, img_width, img_height)
                if yolo_line:
                    f.write(yolo_line + '\n')
                    num_valid_objects += 1
                else:
                    # None表示负样本或不支持的形状
                    label = shape.get('label', '')
                    if not label or label.strip() == "":
                        skipped_negative += 1
      
        result = {
            'success': True,
            'image_path': str(output_img_path),
            'label_path': str(output_label_path),
            'num_objects': num_valid_objects,
            'skipped_negative': skipped_negative
        }
      
        print(f"✓ 完成！图像: {output_img_path.name}, 标注: {num_valid_objects}个目标", end="")
        if skipped_negative > 0:
            print(f", 跳过: {skipped_negative}个负样本", end="")
        print(" ฅ^•ﻌ•^ฅ")
      
        return result
  
    def batch_copy_images_with_hbb(self, source_dir: Union[str, Path], 
                                   output_dir: Union[str, Path]) -> dict:
        """
        批量处理：整图复制 + HBB标注转换
      
        功能：
        - 遍历source_dir中的所有JSON文件
        - 自动从JSON中读取imagePath字段匹配图像文件
        - 批量转换为YOLO格式
      
        参数:
            source_dir: 源目录，包含JSON标注文件和对应的图像文件
            output_dir: 输出目录，会自动创建images和labels子目录
          
        返回:
            result: 结果字典，包含:
                - total: 总文件数
                - success: 成功处理的文件数
                - failed: 失败的文件数
                - total_objects: 总目标数量
                - total_skipped_negative: 总跳过的负样本数量
                - failed_files: 失败的文件列表（包含文件名和错误信息）
              
        异常:
            FileNotFoundError: 源目录不存在
            ValueError: 源目录中没有JSON文件
        """
        source_path = Path(source_dir)
      
        if not source_path.exists():
            raise FileNotFoundError(f"源目录不存在: {source_dir}")
      
        # 获取所有JSON文件
        json_files = list(source_path.glob('*.json'))
        if not json_files:
            raise ValueError(f"源目录中没有找到JSON文件: {source_dir}")
      
        print(f"\n喵~ 开始批量处理！找到 {len(json_files)} 个JSON文件 (๑•̀ㅂ•́)و✧")
      
        # 创建输出目录
        output_path = Path(output_dir)
        output_images = output_path / 'images'
        output_labels = output_path / 'labels'
        output_images.mkdir(parents=True, exist_ok=True)
        output_labels.mkdir(parents=True, exist_ok=True)
      
        # 统计信息
        total = len(json_files)
        success_count = 0
        failed_count = 0
        total_objects = 0
        total_skipped_negative = 0
        failed_files = []
      
        # 遍历处理
        for json_file in json_files:
            try:
                # 读取JSON获取图像路径
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
              
                image_path = source_path / data['imagePath']
              
                # 处理单个文件
                result = self.copy_image_with_hbb(json_file, image_path, output_dir)
              
                success_count += 1
                total_objects += result['num_objects']
                total_skipped_negative += result['skipped_negative']
              
            except Exception as e:
                failed_count += 1
                failed_files.append({
                    'file': str(json_file.name),
                    'error': str(e)
                })
                print(f"✗ 处理失败: {json_file.name}, 错误: {str(e)} (╥﹏╥)")
      
        # 返回统计结果
        result = {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'total_objects': total_objects,
            'total_skipped_negative': total_skipped_negative,
            'failed_files': failed_files
        }
      
        print(f"\n喵呜~ 批量处理完成！✧(≖ ◡ ≖✿)")
        print(f"  总计: {total} | 成功: {success_count} | 失败: {failed_count}")
        print(f"  总目标数: {total_objects} | 跳过负样本: {total_skipped_negative}")
        print(f"  输出目录: {output_dir}")
      
        return result
  
    def extract_and_composite(self, json_path: Union[str, Path], image_path: Union[str, Path],
                             wall_image_path: Union[str, Path], output_dir: Union[str, Path]) -> dict:
        """
        单个文件处理：提取目标 + 合成到墙壁
      
        功能：
        - 从原图中提取所有标注的目标（圆形/矩形）
        - 将每个目标合成到指定的墙壁图像上的随机位置
        - 生成对应的YOLO格式标注
        - 自动跳过空label的负样本
      
        参数:
            json_path: labelme标注文件路径
            image_path: 对应的图像文件路径
            wall_image_path: 墙壁背景图像路径
            output_dir: 输出目录，会自动创建images和labels子目录
          
        返回:
            result: 结果字典，包含:
                - success: 是否成功
                - num_extracted: 成功提取并合成的目标数量
                - num_skipped: 跳过的目标数量（负样本或合成失败）
                - output_files: 输出文件列表，每个元素包含image、label、scale信息
              
        异常:
            FileNotFoundError: 输入文件不存在
            ValueError: 文件格式错误、处理失败、或遇到未知类别
            RuntimeError: 文件保存失败
        """
        print(f"\n喵~ 开始提取和合成：{Path(json_path).name} (๑•̀ㅂ•́)و✧")
      
        # 加载数据
        data, image, img_height, img_width = self._load_json_and_image(json_path, image_path)
      
        # 加载墙壁图像
        wall_image_path = Path(wall_image_path)
        if not wall_image_path.exists():
            raise FileNotFoundError(f"找不到墙壁图像: {wall_image_path}")
      
        wall_image = cv2.imdecode(np.fromfile(str(wall_image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if wall_image is None:
            raise ValueError(f"读取墙壁图像失败: {wall_image_path}")
      
        # 创建输出目录
        output_path = Path(output_dir)
        output_images = output_path / 'images'
        output_labels = output_path / 'labels'
        output_images.mkdir(parents=True, exist_ok=True)
        output_labels.mkdir(parents=True, exist_ok=True)
      
        # 获取文件名
        stem = Path(image_path).stem
        shapes = data.get('shapes', [])
      
        if not shapes:
            raise ValueError(f"JSON文件中没有标注对象: {json_path}")
      
        output_files = []
        wall_h, wall_w = wall_image.shape[:2]
        num_skipped = 0
      
        # 遍历每个标注对象
        for idx, shape in enumerate(shapes):
            try:
                shape_type = shape.get('shape_type', '')
                points = shape.get('points', [])
                label = shape.get('label', '')
              
                # 获取类别ID（空label会返回None）
                class_id = self._get_class_id(label)
                if class_id is None:
                    print(f"  ⊙ 跳过负样本: 目标 {idx}")
                    num_skipped += 1
                    continue
              
                # 提取目标（根据shape_type决定提取方式）
                if shape_type == 'circle' and len(points) == 2:
                    center = (int(points[0][0]), int(points[0][1]))
                    radius_point = (int(points[1][0]), int(points[1][1]))
                    radius = int(np.sqrt((center[0] - radius_point[0])**2 +
                                       (center[1] - radius_point[1])**2))
                    extracted, bbox = self._extract_circle(image, center, radius)
                    
                elif shape_type == 'rectangle' and len(points) >= 2:
                    extracted, bbox = self._extract_rectangle(image, points)
                    
                else:
                    print(f"  ⚠️ 跳过不支持的形状类型: {shape_type}")
                    num_skipped += 1
                    continue
                
                # 缩放（如果需要）
                resized, scale = self._resize_if_needed(extracted)
                target_h, target_w = resized.shape[:2]
                
                # 合成到墙壁
                result_img, paste_x, paste_y = self._composite_on_wall(resized, wall_image)
                
                if result_img is None:
                    print(f"  ✗ 合成失败：目标 {idx} (墙壁太小) (╥﹏╥)")
                    num_skipped += 1
                    continue
                
                # 保存合成图像
                syn_img_name = f"{stem}_syn_{idx}.jpg"
                syn_img_path = output_images / syn_img_name
                success, encoded = cv2.imencode('.jpg', result_img)
                if not success:
                    raise RuntimeError(f"合成图像编码失败: {syn_img_path}")
                encoded.tofile(str(syn_img_path))
                
                # 生成YOLO标注
                x_center = (paste_x + target_w / 2) / wall_w
                y_center = (paste_y + target_h / 2) / wall_h
                width = target_w / wall_w
                height = target_h / wall_h
                
                # 确保在有效范围内
                x_center = max(0.0, min(1.0, x_center))
                y_center = max(0.0, min(1.0, y_center))
                width = max(0.0, min(1.0, width))
                height = max(0.0, min(1.0, height))
                
                syn_label_path = output_labels / f"{stem}_syn_{idx}.txt"
                with open(syn_label_path, 'w', encoding='utf-8') as f:
                    f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
                
                output_files.append({
                    'image': str(syn_img_path),
                    'label': str(syn_label_path),
                    'scale': scale,
                    'class_id': class_id,
                    'class_name': label
                })
                
                print(f"  ✓ 目标 {idx} ({label}): {syn_img_name}, 缩放={scale:.2f}")
                
            except ValueError as e:
                # 未知类别等错误，直接向上抛出
                raise
            except Exception as e:
                print(f"  ✗ 处理失败: 目标 {idx}, 错误: {str(e)} (╥﹏╥)")
                num_skipped += 1
                continue
        
        result = {
            'success': True,
            'num_extracted': len(output_files),
            'num_skipped': num_skipped,
            'output_files': output_files
        }
        
        print(f"✓ 完成！成功: {len(output_files)}个, 跳过: {num_skipped}个 ฅ^•ﻌ•^ฅ")
        
        return result
    
    def batch_extract_and_composite(self, source_dir: Union[str, Path], 
                                   wall_dir: Union[str, Path], 
                                   output_dir: Union[str, Path]) -> dict:
        """
        批量处理：提取目标 + 合成到墙壁
        
        功能：
        - 遍历source_dir中的所有JSON文件
        - 自动从JSON中读取imagePath字段匹配图像文件
        - 从wall_dir中随机选择墙壁图像进行合成
        - 批量生成合成数据集
        
        参数:
            source_dir: 源目录，包含JSON标注文件和对应的图像文件
            wall_dir: 墙壁图像目录，包含用作背景的墙壁图片（.jpg或.png）
            output_dir: 输出目录，会自动创建images和labels子目录
            
        返回:
            result: 结果字典，包含:
                - total_files: 总JSON文件数
                - success_files: 成功处理的文件数
                - failed_files_list: 失败的文件列表
                - total_extracted: 总共提取并合成的目标数
                - total_skipped: 总共跳过的目标数
                - wall_images_count: 可用的墙壁图像数量
                
        异常:
            FileNotFoundError: 源目录或墙壁目录不存在
            ValueError: 源目录中没有JSON文件或墙壁目录中没有图像
        """
        source_path = Path(source_dir)
        wall_path = Path(wall_dir)
        
        # 检查目录
        if not source_path.exists():
            raise FileNotFoundError(f"源目录不存在: {source_dir}")
        if not wall_path.exists():
            raise FileNotFoundError(f"墙壁目录不存在: {wall_dir}")
        
        # 获取所有JSON文件
        json_files = list(source_path.glob('*.json'))
        if not json_files:
            raise ValueError(f"源目录中没有找到JSON文件: {source_dir}")
        
        # 获取所有墙壁图片
        wall_images = list(wall_path.glob('*.jpg')) + list(wall_path.glob('*.png'))
        if not wall_images:
            raise ValueError(f"墙壁目录中没有找到图片文件: {wall_dir}")
        
        print(f"\n喵~ 开始批量提取和合成！(๑•̀ㅂ•́)و✧")
        print(f"  JSON文件: {len(json_files)}个")
        print(f"  墙壁图像: {len(wall_images)}个")
        
        # 创建输出目录
        output_path = Path(output_dir)
        output_images = output_path / 'images'
        output_labels = output_path / 'labels'
        output_images.mkdir(parents=True, exist_ok=True)
        output_labels.mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        total_files = len(json_files)
        success_files = 0
        failed_files = 0
        total_extracted = 0
        total_skipped = 0
        failed_files_list = []
        
        # 遍历处理
        for json_file in json_files:
            try:
                # 读取JSON获取图像路径
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                image_path = source_path / data['imagePath']
                
                # 随机选择墙壁图片
                wall_image_path = random.choice(wall_images)
                
                # 处理单个文件
                result = self.extract_and_composite(json_file, image_path, 
                                                   wall_image_path, output_dir)
                
                success_files += 1
                total_extracted += result['num_extracted']
                total_skipped += result['num_skipped']
                
            except Exception as e:
                failed_files += 1
                failed_files_list.append({
                    'file': str(json_file.name),
                    'error': str(e)
                })
                print(f"✗ 处理失败: {json_file.name}, 错误: {str(e)} (╥﹏╥)")
        
        # 返回统计结果
        result = {
            'total_files': total_files,
            'success_files': success_files,
            'failed_files': failed_files,
            'failed_files_list': failed_files_list,
            'total_extracted': total_extracted,
            'total_skipped': total_skipped,
            'wall_images_count': len(wall_images)
        }
        
        print(f"\n喵呜~ 批量提取和合成完成！✧(≖ ◡ ≖✿)")
        print(f"  处理文件: {total_files} | 成功: {success_files} | 失败: {failed_files}")
        print(f"  生成图像: {total_extracted}张 | 跳过: {total_skipped}个")
        print(f"  输出目录: {output_dir}")
        
        return result

# ==================== 使用示例 ====================

if __name__ == '__main__':
    """
    使用示例代码
    """
    
    # 1. 准备类别映射字典（通常从dataset.yaml读取）
    class_mapping = {
        "圆形": 0,
        "矩形": 1,

    }
    
    # 2. 创建工具实例
    toolkit = DataAugmentationToolkit(
        class_mapping=class_mapping,
        random_seed=42,
        max_target_size=100
    )
    
    # # 3. 示例1：单个文件 - 整图复制+HBB标注
    # try:
    #     result = toolkit.copy_image_with_hbb(
    #         json_path=r'E:\meter\目标\测试组14\sample.json',
    #         image_path=r'E:\meter\目标\测试组14\sample.jpg',
    #         output_dir=r'E:\meter\输出\dataset_test'
    #     )
    #     print(f"单个处理结果: {result}")
    # except Exception as e:
    #     print(f"单个处理出错: {e}")
    
    # 4. 示例2：批量处理 - 整图复制+HBB标注
    try:
        result = toolkit.batch_copy_images_with_hbb(
            source_dir=r'E:\DataForge\目标\表计（手动标注）整合目标',
            output_dir=r'E:\DataForge\输出\dataset7'
        )
        print(f"批量处理结果: {result}")
    except Exception as e:
        print(f"批量处理出错: {e}")
    
    # # 5. 示例3：单个文件 - 提取目标+合成到墙壁
    # try:
    #     result = toolkit.extract_and_composite(
    #         json_path=r'E:\meter\目标\测试组14\sample.json',
    #         image_path=r'E:\meter\目标\测试组14\sample.jpg',
    #         wall_image_path=r'E:\meter\数据集\墙壁负样本\wall_001.jpg',
    #         output_dir=r'E:\meter\输出\dataset_composite'
    #     )
    #     print(f"单个合成结果: {result}")
    # except Exception as e:
    #     print(f"单个合成出错: {e}")
    
    # # 6. 示例4：批量处理 - 提取目标+合成到墙壁
    # try:
    #     result = toolkit.batch_extract_and_composite(
    #         source_dir=r'E:\meter\目标\测试组14',
    #         wall_dir=r'E:\meter\数据集\墙壁负样本',
    #         output_dir=r'E:\meter\输出\dataset_composite_batch'
    #     )
    #     print(f"批量合成结果: {result}")
    # except Exception as e:
    #     print(f"批量合成出错: {e}")
