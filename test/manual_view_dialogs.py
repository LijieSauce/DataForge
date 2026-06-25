"""用于手动拉起 9 个 PyQt5 弹窗的测试启动器。

这个文件只负责展示窗口，不执行任何业务流程，便于人工检查
每个弹窗的布局、按钮、输入框和样式是否正常。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Type

# 先把项目根目录插入搜索路径，这样从 test 目录直接运行时也能导入 src.views。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QGridLayout, QLabel, QPushButton, QVBoxLayout

from src.views.L1_batch_copy_images_with_hbb_dialog import BatchCopyImagesWithHbbDialog
from src.views.L1_batch_extract_and_composite_dialog import BatchExtractAndCompositeDialog
from src.views.L1_bing_download_batch_dialog import BingDownloadBatchDialog
from src.views.L1_bing_download_dialog import BingDownloadDialog
from src.views.L1_copy_image_with_hbb_dialog import CopyImageWithHbbDialog
from src.views.L1_extract_and_composite_dialog import ExtractAndCompositeDialog
from src.views.L1_pexels_download_batch_dialog import PexelsDownloadBatchDialog
from src.views.L1_pexels_download_dialog import PexelsDownloadDialog
from src.views.styles import apply_dialog_style
from src.views.L1_yolo_class_extract_dialog import YOLOClassExtractDialog


DialogClass = Type[QDialog]


class DialogLauncher(QDialog):
    """手动测试用的启动器窗口。

    这个窗口只提供按钮，用来逐个打开 9 个独立弹窗，方便人工确认
    每个 UI 窗口的样式和控件布局。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 启动器本身也沿用同一套主题，保证视觉一致。
        self.setWindowTitle("DataForge 弹窗手动测试")
        self.resize(560, 360)
        self._opened_dialogs: list[QDialog] = []
        apply_dialog_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        """搭建 9 个弹窗按钮和关闭按钮，只负责界面排列。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        # 顶部标题和说明只用于提示这个窗口的用途。
        title = QLabel("DataForge 弹窗手动测试", self)
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        hint = QLabel("点击按钮拉起对应弹窗。这里只检查 UI，不执行任何业务逻辑。", self)
        hint.setObjectName("descriptionLabel")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        # 中间是 9 个按钮，每个按钮只打开一个对应的独立弹窗。
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        layout.addLayout(grid)

        dialogs: list[tuple[str, DialogClass]] = [
            ("YOLO 类别提取", YOLOClassExtractDialog),
            ("Bing 单图下载", BingDownloadDialog),
            ("Bing 批量下载", BingDownloadBatchDialog),
            ("Pexels 单图下载", PexelsDownloadDialog),
            ("Pexels 批量下载", PexelsDownloadBatchDialog),
            ("整图复制 HBB", CopyImageWithHbbDialog),
            ("批量复制 HBB", BatchCopyImagesWithHbbDialog),
            ("提取并合成", ExtractAndCompositeDialog),
            ("批量提取并合成", BatchExtractAndCompositeDialog),
        ]

        for index, (label, dialog_class) in enumerate(dialogs):
            button = QPushButton(label, self)
            button.clicked.connect(lambda checked=False, cls=dialog_class: self._open_dialog(cls))
            grid.addWidget(button, index // 3, index % 3)

        # 关闭按钮只退出当前测试启动器，不影响已经打开的子窗口。
        close_button = QPushButton("关闭测试窗口", self)
        close_button.clicked.connect(self.reject)
        layout.addWidget(close_button)

    def _open_dialog(self, dialog_class: DialogClass) -> None:
        """实例化并显示一个独立弹窗，同时保留引用避免被回收。"""
        dialog = dialog_class(self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        self._opened_dialogs.append(dialog)
        dialog.destroyed.connect(lambda: self._forget_dialog(dialog))
        dialog.show()

    def _forget_dialog(self, dialog: QDialog) -> None:
        """子窗口关闭后，从引用列表中移除它。"""
        if dialog in self._opened_dialogs:
            self._opened_dialogs.remove(dialog)


def main() -> int:
    """程序入口，启动 Qt 事件循环。"""
    app = QApplication(sys.argv)
    launcher = DialogLauncher()
    launcher.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
