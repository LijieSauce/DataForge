"""Bing 单图下载弹窗的纯 UI 文件。

这个弹窗只收集搜索页地址、输出目录和基础参数，不直接执行下载。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .styles import apply_dialog_style, apply_panel_shadow


class BingDownloadDialog(QDialog):
    """Bing 单图下载的独立 UI 弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 单图窗口尺寸稍小，主要用于快速填写参数和查看结果占位区。
        self.setWindowTitle("Bing 单图下载")
        self.resize(680, 480)
        apply_dialog_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        """搭建 Bing 单图下载窗口的完整界面。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # 主面板统一放输入区、进度条和结果框，保持和 HTML 样本一致的层次。
        panel = QFrame(self)
        panel.setObjectName("panel")
        apply_panel_shadow(panel)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 18, 22, 18)
        panel_layout.setSpacing(14)
        main_layout.addWidget(panel)

        # 顶部标题和说明只负责告诉用户当前窗口用途。
        title = QLabel("Bing 单图下载", panel)
        title.setObjectName("titleLabel")
        description = QLabel("填写 Bing 图片搜索页地址，并准备下载 1 张图片。", panel)
        description.setObjectName("descriptionLabel")
        description.setWordWrap(True)
        panel_layout.addWidget(title)
        panel_layout.addWidget(description)

        # 参数区只负责摆放控件，不做任何下载逻辑。
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        self.search_url_edit = QLineEdit(panel)
        self.search_url_edit.setPlaceholderText("https://www.bing.com/images/search?q=...")
        form_layout.addRow("Bing 搜索页 URL *", self.search_url_edit)

        self.output_dir_edit = QLineEdit(panel)
        form_layout.addRow("输出目录 *", self._dir_row(self.output_dir_edit))

        self.thread_count_spin = QSpinBox(panel)
        self.thread_count_spin.setRange(1, 64)
        self.thread_count_spin.setValue(5)
        form_layout.addRow("线程数", self.thread_count_spin)

        self.timeout_spin = QDoubleSpinBox(panel)
        self.timeout_spin.setRange(0.1, 600.0)
        self.timeout_spin.setDecimals(1)
        self.timeout_spin.setValue(15.0)
        self.timeout_spin.setSuffix(" 秒")
        form_layout.addRow("超时时间", self.timeout_spin)
        panel_layout.addLayout(form_layout)

        # 进度条保留给后续业务层调用 update_progress 时刷新显示。
        self.progress_bar = QProgressBar(panel)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("等待执行")
        panel_layout.addWidget(self.progress_bar)

        # 结果框只是 UI 占位，后续可由业务层写入执行日志或路径信息。
        self.result_text = QPlainTextEdit(panel)
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("执行结果显示区域")
        self.result_text.setMinimumHeight(90)
        panel_layout.addWidget(self.result_text)

        # 开始按钮不绑定业务，关闭按钮只负责关闭当前弹窗。
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.start_button = QPushButton("开始执行", panel)
        self.start_button.setObjectName("primaryButton")
        self.close_button = QPushButton("取消/关闭", panel)
        self.close_button.clicked.connect(self.reject)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.close_button)
        panel_layout.addLayout(button_row)

    def _dir_row(self, line_edit: QLineEdit) -> QFrame:
        """封装“输入框 + 浏览目录按钮”的一行布局。"""
        row = QFrame(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("浏览目录", row)
        button.clicked.connect(self._browse_output_dir)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return row

    def _browse_output_dir(self) -> None:
        """把目录选择器里选中的路径填回输出目录输入框。"""
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir_edit.setText(path)

    def update_progress(self, current: int, total: int) -> None:
        """只更新进度条显示，不负责执行任务本身。"""
        if total <= 0:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("等待执行")
            return
        percent = max(0, min(100, int(current * 100 / total)))
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{current}/{total} ({percent}%)")
