"""YOLO 类别提取弹窗的纯 UI 文件。

这个文件只负责收集路径、类别映射和结果展示区域，不直接调用
YOLOClassExtractor，也不承载任何数据处理逻辑。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .styles import apply_dialog_style, apply_panel_shadow


class YOLOClassExtractDialog(QDialog):
    """YOLO 类别提取的独立 UI 弹窗。

    这个类只负责搭建界面控件，不导入、不调用 YOLOClassExtractor。
    后续业务层可以从公开控件读取路径和映射表，再自行绑定执行逻辑。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 窗口标题和默认尺寸只影响 UI 呈现，不承载任何业务状态。
        self.setWindowTitle("YOLO 类别提取")
        self.resize(720, 620)
        apply_dialog_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        """搭建 YOLO 类别提取弹窗的完整界面。"""
        # 最外层留白参考 HTML 样本的工具面板距离，让弹窗不贴边。
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # 主面板承载所有输入项，统一加浅色背景、边框和阴影。
        panel = QFrame(self)
        panel.setObjectName("panel")
        apply_panel_shadow(panel)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 18, 22, 18)
        panel_layout.setSpacing(14)
        main_layout.addWidget(panel)

        # 顶部标题区只展示功能名称和简短说明，方便用户确认当前窗口。
        title = QLabel("YOLO 类别提取", panel)
        title.setObjectName("titleLabel")
        description = QLabel("从 YOLO 数据集中提取指定类别，并生成新的数据集目录。", panel)
        description.setObjectName("descriptionLabel")
        description.setWordWrap(True)
        panel_layout.addWidget(title)
        panel_layout.addWidget(description)

        section = QLabel("参数输入", panel)
        section.setObjectName("sectionLabel")
        panel_layout.addWidget(section)

        # 参数表单区放路径类输入；路径行统一由 _path_row 组合输入框和浏览按钮。
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        self.source_dir_edit = QLineEdit(panel)
        source_row = self._path_row(self.source_dir_edit, "浏览目录", self._browse_source_dir)
        form_layout.addRow("源数据集目录 *", source_row)

        self.output_dir_edit = QLineEdit(panel)
        output_row = self._path_row(self.output_dir_edit, "浏览目录", self._browse_output_dir)
        form_layout.addRow("输出目录 *", output_row)

        panel_layout.addLayout(form_layout)

        # 类别映射用表格表达，后续业务可按“原类别 ID -> 新类别 ID”读取每一行。
        mapping_title = QLabel("类别映射表", panel)
        mapping_title.setObjectName("sectionLabel")
        panel_layout.addWidget(mapping_title)

        self.mapping_table = QTableWidget(0, 2, panel)
        self.mapping_table.setHorizontalHeaderLabels(["原类别 ID", "新类别 ID"])
        self.mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mapping_table.verticalHeader().setVisible(False)
        self.mapping_table.setMinimumHeight(130)
        panel_layout.addWidget(self.mapping_table)

        mapping_buttons = QHBoxLayout()
        self.add_row_button = QPushButton("添加行", panel)
        self.remove_row_button = QPushButton("删除选中行", panel)
        self.add_row_button.clicked.connect(self._add_mapping_row)
        self.remove_row_button.clicked.connect(self._remove_mapping_rows)
        mapping_buttons.addWidget(self.add_row_button)
        mapping_buttons.addWidget(self.remove_row_button)
        mapping_buttons.addStretch()
        panel_layout.addLayout(mapping_buttons)
        self._add_mapping_row()

        # 进度条默认静止，业务层若需要展示进度，可以调用 update_progress。
        self.progress_bar = QProgressBar(panel)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("等待执行")
        panel_layout.addWidget(self.progress_bar)

        # # 结果框只作为 UI 占位，具体写入内容由未来业务绑定决定。
        # self.result_text = QPlainTextEdit(panel)
        # self.result_text.setReadOnly(True)
        # self.result_text.setPlaceholderText("执行结果显示区域")
        # self.result_text.setMinimumHeight(90)
        # panel_layout.addWidget(self.result_text)

        # 开始按钮故意不绑定业务逻辑；关闭按钮只负责退出当前弹窗。
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.start_button = QPushButton("开始执行", panel)
        self.start_button.setObjectName("primaryButton")
        self.close_button = QPushButton("取消/关闭", panel)
        self.close_button.clicked.connect(self.reject)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.close_button)
        panel_layout.addLayout(button_row)

    def _path_row(self, line_edit: QLineEdit, button_text: str, callback) -> QFrame:
        """创建可复用的路径输入行，包含输入框和浏览按钮。"""
        row = QFrame(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        button = QPushButton(button_text, row)
        button.clicked.connect(callback)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return row

    def _browse_source_dir(self) -> None:
        """选择源数据集目录，并回填到源目录输入框。"""
        path = QFileDialog.getExistingDirectory(self, "选择源数据集目录")
        if path:
            self.source_dir_edit.setText(path)

    def _browse_output_dir(self) -> None:
        """选择输出目录，并回填到输出目录输入框。"""
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir_edit.setText(path)

    def _add_mapping_row(self) -> None:
        """Append an empty mapping row for old class ID and new class ID."""
        row = self.mapping_table.rowCount()
        self.mapping_table.insertRow(row)
        self.mapping_table.setItem(row, 0, QTableWidgetItem(""))
        self.mapping_table.setItem(row, 1, QTableWidgetItem(""))

    def _remove_mapping_rows(self) -> None:
        """Remove selected mapping rows, keeping one editable row available."""
        rows = sorted({index.row() for index in self.mapping_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.mapping_table.removeRow(row)
        if self.mapping_table.rowCount() == 0:
            self._add_mapping_row()

    def update_progress(self, current: int, total: int) -> None:
        """刷新进度条显示，不执行任何数据处理任务。"""
        if total <= 0:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("等待执行")
            return
        percent = max(0, min(100, int(current * 100 / total)))
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{current}/{total} ({percent}%)")
