import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cv2
import numpy as np
from pathlib import Path

from src.serve.formatConversion.YoloToYOLO import YoloToYOLO



# 示例用法
converter = YoloToYOLO(
    input_path=Path(r"E:\meter\数据集\表计_2"),
    output_path=Path(r"E:\meter\输出\表计_2"),
    keep_labels=["meter"], 
)

converter.convert()