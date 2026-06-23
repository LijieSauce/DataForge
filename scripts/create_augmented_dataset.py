import json
import cv2
import numpy as np
from pathlib import Path
import random
import shutil

def extract_circle(image, center, radius):
    """提取圆形区域，带透明背景"""
    h, w = image.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, center, radius, 255, -1)

    x, y = center
    x1 = max(0, x - radius)
    y1 = max(0, y - radius)
    x2 = min(w, x + radius)
    y2 = min(h, y + radius)

    cropped_image = image[y1:y2, x1:x2]
    cropped_mask = mask[y1:y2, x1:x2]

    result = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2BGRA)
    result[:, :, 3] = cropped_mask

    return result, (x1, y1, x2, y2)

def extract_rectangle(image, points):
    """提取矩形区域，带透明背景"""
    points = np.array(points, dtype=np.int32)
    x_coords = points[:, 0]
    y_coords = points[:, 1]

    x1, y1 = int(x_coords.min()), int(y_coords.min())
    x2, y2 = int(x_coords.max()), int(y_coords.max())

    h, w = image.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    cropped = image[y1:y2, x1:x2]
    result = cv2.cvtColor(cropped, cv2.COLOR_BGR2BGRA)

    return result, (x1, y1, x2, y2)

def resize_if_needed(image, max_size=50):
    """如果图片尺寸超过max_size，等比例缩放到最长边<=max_size"""
    h, w = image.shape[:2]

    if h <= max_size and w <= max_size:
        return image, 1.0

    scale = max_size / max(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, scale

def shape_to_yolo_bbox(shape, img_width, img_height):
    """将shape转换为YOLO格式的归一化bbox"""
    shape_type = shape.get('shape_type', '')
    points = shape.get('points', [])
    label = shape.get('label', '')

    # 确定class_id
    if '圆形' in label or shape_type == 'circle':
        class_id = 0
    elif '矩形' in label or shape_type == 'rectangle':
        # class_id = 1
        class_id = 0  # 目前统一为0，后续可以根据需要区分
    else:
        class_id = 0

    if shape_type == 'circle' and len(points) == 2:
        center = points[0]
        radius_point = points[1]
        radius = np.sqrt((center[0] - radius_point[0])**2 +
                        (center[1] - radius_point[1])**2)

        x1 = center[0] - radius
        y1 = center[1] - radius
        x2 = center[0] + radius
        y2 = center[1] + radius

    elif shape_type == 'rectangle' and len(points) >= 2:
        points_arr = np.array(points)
        x1 = points_arr[:, 0].min()
        y1 = points_arr[:, 1].min()
        x2 = points_arr[:, 0].max()
        y2 = points_arr[:, 1].max()
    else:
        return None

    # 边界限制：确保bbox在图片范围内
    x1 = max(0, min(x1, img_width))
    y1 = max(0, min(y1, img_height))
    x2 = max(0, min(x2, img_width))
    y2 = max(0, min(y2, img_height))

    # 转换为YOLO格式（归一化）
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

def composite_on_wall(target_image, wall_image):
    """将目标图像合成到墙壁图像上的随机位置"""
    target_h, target_w = target_image.shape[:2]
    wall_h, wall_w = wall_image.shape[:2]

    # 确保目标完全在图片内
    max_x = wall_w - target_w
    max_y = wall_h - target_h

    if max_x < 0 or max_y < 0:
        print(f"警告: 墙壁图片太小，无法放置目标")
        return None, None, None

    # 随机位置
    paste_x = random.randint(0, max_x)
    paste_y = random.randint(0, max_y)

    # 合成
    result = wall_image.copy()

    # 处理透明通道
    if target_image.shape[2] == 4:
        alpha = target_image[:, :, 3] / 255.0
        for c in range(3):
            result[paste_y:paste_y+target_h, paste_x:paste_x+target_w, c] = \
                (alpha * target_image[:, :, c] +
                 (1 - alpha) * result[paste_y:paste_y+target_h, paste_x:paste_x+target_w, c])
    else:
        result[paste_y:paste_y+target_h, paste_x:paste_x+target_w] = target_image

    return result, paste_x, paste_y

def create_augmented_dataset(source_dir, wall_dir, output_dir):
    """创建增强数据集"""
    source_path = Path(source_dir)
    wall_path = Path(wall_dir)
    output_images = Path(output_dir) / 'images'
    output_labels = Path(output_dir) / 'labels'

    output_images.mkdir(parents=True, exist_ok=True)
    output_labels.mkdir(parents=True, exist_ok=True)

    # # 获取所有墙壁图片
    # wall_images = list(wall_path.glob('*.jpg')) + list(wall_path.glob('*.png'))
    # if not wall_images:
    #     print(f"错误: 在 {wall_dir} 中没有找到墙壁图片")
    #     return

    # print(f"找到 {len(wall_images)} 张墙壁图片")

    # 遍历所有JSON文件
    json_files = list(source_path.glob('*.json'))
    print(f"找到 {len(json_files)} 个JSON标注文件")

    for json_file in json_files:
        print(f"\n处理: {json_file.name}")

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            image_path = source_path / data['imagePath']
            if not image_path.exists():
                print(f"  错误: 找不到图片 {image_path}")
                continue

            image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                print(f"  错误: 无法读取图片 {image_path}")
                continue

            img_height, img_width = image.shape[:2]
            shapes = data.get('shapes', [])

            if not shapes:
                print(f"  警告: 没有标注对象")
                continue

            # ===== 任务1: 整图复制 + HBB标注 =====
            stem = image_path.stem

            # 复制图片
            output_img_path = output_images / f"{stem}.jpg"
            cv2.imencode('.jpg', image)[1].tofile(str(output_img_path))

            # 生成YOLO标注
            output_label_path = output_labels / f"{stem}.txt"
            with open(output_label_path, 'w', encoding='utf-8') as f:
                for shape in shapes:
                    yolo_line = shape_to_yolo_bbox(shape, img_width, img_height)
                    if yolo_line:
                        f.write(yolo_line + '\n')

            print(f"  任务1完成: {output_img_path.name}")

            # # ===== 任务2: 提取目标 + 合成到墙壁 =====
            # for idx, shape in enumerate(shapes):
            #     shape_type = shape.get('shape_type', '')
            #     points = shape.get('points', [])
            #     label = shape.get('label', '')

            #     # 确定class_id
            #     if '圆形' in label or shape_type == 'circle':
            #         class_id = 0
            #     elif '矩形' in label or shape_type == 'rectangle':
            #         class_id = 1
            #     else:
            #         class_id = 0

            #     # 提取目标
            #     if shape_type == 'circle' and len(points) == 2:
            #         center = (int(points[0][0]), int(points[0][1]))
            #         radius_point = (int(points[1][0]), int(points[1][1]))
            #         radius = int(np.sqrt((center[0] - radius_point[0])**2 +
            #                             (center[1] - radius_point[1])**2))

            #         extracted, bbox = extract_circle(image, center, radius)

            #     elif shape_type == 'rectangle' and len(points) >= 2:
            #         extracted, bbox = extract_rectangle(image, points)

            #     else:
            #         print(f"  警告: 不支持的形状类型 {shape_type}")
            #         continue

            #     # 缩放（如果需要）
            #     resized, scale = resize_if_needed(extracted, max_size=100)
            #     target_h, target_w = resized.shape[:2]

            #     # 随机选择墙壁图片
            #     wall_img_path = random.choice(wall_images)
            #     wall_img = cv2.imdecode(np.fromfile(str(wall_img_path), dtype=np.uint8), cv2.IMREAD_COLOR)

            #     if wall_img is None:
            #         print(f"  错误: 无法读取墙壁图片 {wall_img_path}")
            #         continue

            #     # 合成
            #     result, paste_x, paste_y = composite_on_wall(resized, wall_img)

            #     if result is None:
            #         continue

            #     # 保存合成图片
            #     syn_img_name = f"{stem}_syn_{idx}.jpg"
            #     syn_img_path = output_images / syn_img_name
            #     cv2.imencode('.jpg', result)[1].tofile(str(syn_img_path))

            #     # 生成新标注
            #     wall_h, wall_w = wall_img.shape[:2]
            #     x_center = (paste_x + target_w / 2) / wall_w
            #     y_center = (paste_y + target_h / 2) / wall_h
            #     width = target_w / wall_w
            #     height = target_h / wall_h

            #     syn_label_path = output_labels / f"{stem}_syn_{idx}.txt"
            #     with open(syn_label_path, 'w', encoding='utf-8') as f:
            #         f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")

            #     print(f"  任务2完成: {syn_img_name} (缩放比例: {scale:.2f})")

        except Exception as e:
            print(f"  错误: {str(e)}")
            continue

    print(f"\n全部完成！输出目录: {output_dir}")

if __name__ == '__main__':
    source_dir = r'E:\meter\目标\测试组14'
    wall_dir = r'E:\meter\数据集\墙壁负样本'
    output_dir = r'E:\meter\输出\dataset7'

    create_augmented_dataset(source_dir, wall_dir, output_dir)
