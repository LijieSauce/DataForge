import json
import cv2
import numpy as np
from pathlib import Path

def extract_circle(image, center, radius):
    """提取圆形区域"""
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

    return result

def extract_rectangle(image, points):
    """提取矩形区域"""
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

    return result

def process_annotation(json_path, image_dir, output_dir):
    """处理单个标注文件"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    image_path = Path(image_dir) / data['imagePath']
    if not image_path.exists():
        print(f"错误: 找不到图片 {image_path}")
        return

    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        print(f"错误: 无法读取图片 {image_path}")
        return

    shapes = data.get('shapes', [])
    if not shapes:
        print("警告: 没有找到标注对象")
        return

    for idx, shape in enumerate(shapes):
        shape_type = shape.get('shape_type', '')
        points = shape.get('points', [])

        if shape_type == 'circle' and len(points) == 2:
            center = (int(points[0][0]), int(points[0][1]))
            radius_point = (int(points[1][0]), int(points[1][1]))
            radius = int(np.sqrt((center[0] - radius_point[0])**2 +
                                (center[1] - radius_point[1])**2))

            result = extract_circle(image, center, radius)

        elif shape_type == 'rectangle' and len(points) >= 2:
            result = extract_rectangle(image, points)

        else:
            print(f"警告: 不支持的形状类型 {shape_type}")
            continue

        output_filename = f"{image_path.stem}_extracted.png"
        if len(shapes) > 1:
            output_filename = f"{image_path.stem}_extracted_{idx}.png"

        output_path = Path(output_dir) / output_filename
        cv2.imencode('.png', result)[1].tofile(str(output_path))
        print(f"成功提取: {output_path}")

if __name__ == '__main__':
    json_path = r'E:\meter\目标\images\105.json'
    image_dir = r'E:\meter\目标\images'
    output_dir = r'E:\meter\输出'

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    process_annotation(json_path, image_dir, output_dir)
