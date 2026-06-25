"""Pexels 批量下载弹窗的纯 UI 文件。

这个窗口只负责收集关键词、数量、输出目录和通用参数，不执行下载。
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


class PexelsDownloadBatchDialog(QDialog):
    """Pexels 批量下载的独立 UI 弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 批量下载需要比单图多留一点空间，方便查看结果占位区。
        self.setWindowTitle("Pexels 批量下载")
        self.resize(680, 520)
        apply_dialog_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        """搭建 Pexels 批量下载窗口的完整界面。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # 主面板统一承载标题、参数、进度和结果区域。
        panel = QFrame(self)
        panel.setObjectName("panel")
        apply_panel_shadow(panel)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 18, 22, 18)
        panel_layout.setSpacing(14)
        main_layout.addWidget(panel)

        # 顶部说明帮助用户区分当前是批量下载窗口。
        title = QLabel("Pexels 批量下载", panel)
        title.setObjectName("titleLabel")
        description = QLabel("填写 Pexels 搜索关键词和目标数量，用于批量图片采集。", panel)
        description.setObjectName("descriptionLabel")
        description.setWordWrap(True)
        panel_layout.addWidget(title)
        panel_layout.addWidget(description)

        # 参数区只摆放控件，后续业务层可以按这些控件取值。
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        self.query_edit = QLineEdit(panel)
        self.query_edit.setPlaceholderText("例如：industrial wall")
        form_layout.addRow("搜索关键词 *", self.query_edit)

        self.count_spin = QSpinBox(panel)
        self.count_spin.setRange(1, 100000)
        self.count_spin.setValue(10)
        form_layout.addRow("下载数量 *", self.count_spin)

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

        # 进度条用于批量下载时的连续状态展示。
        self.progress_bar = QProgressBar(panel)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("等待执行")
        panel_layout.addWidget(self.progress_bar)

        # 结果框只作为界面容器，供后续业务写入执行摘要。
        self.result_text = QPlainTextEdit(panel)
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("执行结果显示区域")
        self.result_text.setMinimumHeight(90)
        panel_layout.addWidget(self.result_text)

        # 底部按钮仅保留界面行为，不在 UI 层执行任何下载。
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
        """把目录输入框和浏览按钮封成统一的一行。"""
        row = QFrame(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("浏览目录", row)
        button.clicked.connect(self._browse_output_dir)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return row

    def _browse_output_dir(self) -> None:
        """把目录选择器里的结果回填到输出目录输入框。"""
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir_edit.setText(path)

    def update_progress(self, current: int, total: int) -> None:
        """统一的批量进度刷新接口。"""
        if total <= 0:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("等待执行")
            return
        percent = max(0, min(100, int(current * 100 / total)))
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{current}/{total} ({percent}%)")
