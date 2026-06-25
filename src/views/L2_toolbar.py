"""顶部工具栏组件 - L2_toolbar"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QToolBar, QVBoxLayout

# 导入所有L1 dialog
from .L1_bing_download_dialog import BingDownloadDialog
from .L1_bing_download_batch_dialog import BingDownloadBatchDialog
from .L1_pexels_download_dialog import PexelsDownloadDialog
from .L1_pexels_download_batch_dialog import PexelsDownloadBatchDialog
from .L1_copy_image_with_hbb_dialog import CopyImageWithHbbDialog
from .L1_batch_copy_images_with_hbb_dialog import BatchCopyImagesWithHbbDialog
from .L1_extract_and_composite_dialog import ExtractAndCompositeDialog
from .L1_batch_extract_and_composite_dialog import BatchExtractAndCompositeDialog
from .L1_yolo_class_extract_dialog import YOLOClassExtractDialog


class TopToolbar(QWidget):
    """顶部工具栏组件

    功能：
    - 提供9个快捷按钮，分为3组
    - 点击按钮拉起对应的功能弹窗
    - 参考HTML样式的米色系配色方案
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """构建UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建工具栏
        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        toolbar.setObjectName("mainToolbar")

        # 第一组：网络收集器 (dataset_network_collector)
        action_bing = toolbar.addAction("Bing下载")
        action_bing.triggered.connect(self._show_bing_download)

        action_bing_batch = toolbar.addAction("Bing批量")
        action_bing_batch.triggered.connect(self._show_bing_download_batch)

        action_pexels = toolbar.addAction("Pexels下载")
        action_pexels.triggered.connect(self._show_pexels_download)

        action_pexels_batch = toolbar.addAction("Pexels批量")
        action_pexels_batch.triggered.connect(self._show_pexels_download_batch)

        # 分隔符
        toolbar.addSeparator()

        # 第二组：数据增强工具 (DataAugmentationToolkit)
        action_hbb = toolbar.addAction("HBB转换")
        action_hbb.triggered.connect(self._show_copy_image_with_hbb)

        action_hbb_batch = toolbar.addAction("HBB批量")
        action_hbb_batch.triggered.connect(self._show_batch_copy_images_with_hbb)

        action_extract = toolbar.addAction("提取合成")
        action_extract.triggered.connect(self._show_extract_and_composite)

        action_extract_batch = toolbar.addAction("提取批量")
        action_extract_batch.triggered.connect(self._show_batch_extract_and_composite)

        # 分隔符
        toolbar.addSeparator()

        # 第三组：YOLO提取器 (YOLOClassExtractor)
        action_yolo = toolbar.addAction("YOLO提取")
        action_yolo.triggered.connect(self._show_yolo_class_extract)

        layout.addWidget(toolbar)

    def _apply_styles(self):
        """应用样式表"""
        self.setStyleSheet("""
            QWidget {
                background-color: #EDD5B8;
                font-family: "Microsoft YaHei", "SimHei", Arial, sans-serif;
                color: #4A4A4A;
            }

            QToolBar#mainToolbar {
                background-color: #EDD5B8;
                border-bottom: 2px solid #C9B79C;
                padding: 12px 20px;
                spacing: 10px;
            }

            QToolBar QToolButton {
                background-color: #D4B896;
                color: #4A4A4A;
                border: 1px solid #C9B79C;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 500;
                margin: 0px 4px;
            }

            QToolBar QToolButton:hover {
                background-color: #C9B79C;
            }

            QToolBar QToolButton:pressed {
                background-color: #B8A688;
            }

            QToolBar::separator {
                background-color: #C9B79C;
                width: 2px;
                margin: 0px 15px;
            }
        """)

    # ==================== 槽函数：拉起对话框 ====================

    def _show_bing_download(self):
        """显示Bing下载对话框"""
        dialog = BingDownloadDialog(self)
        dialog.exec_()

    def _show_bing_download_batch(self):
        """显示Bing批量下载对话框"""
        dialog = BingDownloadBatchDialog(self)
        dialog.exec_()

    def _show_pexels_download(self):
        """显示Pexels下载对话框"""
        dialog = PexelsDownloadDialog(self)
        dialog.exec_()

    def _show_pexels_download_batch(self):
        """显示Pexels批量下载对话框"""
        dialog = PexelsDownloadBatchDialog(self)
        dialog.exec_()

    def _show_copy_image_with_hbb(self):
        """显示HBB转换对话框"""
        dialog = CopyImageWithHbbDialog(self)
        dialog.exec_()

    def _show_batch_copy_images_with_hbb(self):
        """显示HBB批量转换对话框"""
        dialog = BatchCopyImagesWithHbbDialog(self)
        dialog.exec_()

    def _show_extract_and_composite(self):
        """显示提取合成对话框"""
        dialog = ExtractAndCompositeDialog(self)
        dialog.exec_()

    def _show_batch_extract_and_composite(self):
        """显示提取批量合成对话框"""
        dialog = BatchExtractAndCompositeDialog(self)
        dialog.exec_()

    def _show_yolo_class_extract(self):
        """显示YOLO类别提取对话框"""
        dialog = YOLOClassExtractDialog(self)
        dialog.exec_()
