"""批量整图复制与 HBB 标注转换弹窗的纯 UI 文件。

这个文件只负责批量转换场景的参数界面，不遍历目录、不读取 JSON，
也不调用任何数据增强业务代码。
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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .styles import apply_dialog_style, apply_panel_shadow


class BatchCopyImagesWithHbbDialog(QDialog):
    """批量 HBB 转换的独立 UI 弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 批量场景需要源目录、输出目录和映射表，所以默认窗口高度较高。
        self.setWindowTitle("批量整图复制 + HBB 标注转换")
        self.resize(740, 680)
        apply_dialog_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        """搭建批量 HBB 转换弹窗的完整界面。"""
        # 外层布局提供统一留白，让窗口内容和边缘保持舒服距离。
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # 主面板集中承载标题、参数、映射表、进度条和按钮。
        panel = QFrame(self)
        panel.setObjectName("panel")
        apply_panel_shadow(panel)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 18, 22, 18)
        panel_layout.setSpacing(14)
        main_layout.addWidget(panel)

        # 标题区说明当前窗口用于批量处理，而不是单文件处理。
        title = QLabel("批量整图复制 + HBB 标注转换", panel)
        title.setObjectName("titleLabel")
        description = QLabel("选择包含 JSON 和图片的源目录，以及转换后的输出目录。", panel)
        description.setObjectName("descriptionLabel")
        description.setWordWrap(True)
        panel_layout.addWidget(title)
        panel_layout.addWidget(description)

        # 参数表单区只收集目录和通用参数，不做目录扫描。
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        self.source_dir_edit = QLineEdit(panel)
        form_layout.addRow("源目录 *", self._dir_row(self.source_dir_edit, self._browse_source_dir))

        self.output_dir_edit = QLineEdit(panel)
        form_layout.addRow("输出目录 *", self._dir_row(self.output_dir_edit, self._browse_output_dir))

        self.random_seed_spin = QSpinBox(panel)
        self.random_seed_spin.setRange(0, 999999)
        self.random_seed_spin.setValue(42)
        form_layout.addRow("随机种子", self.random_seed_spin)

        self.max_target_size_spin = QSpinBox(panel)
        self.max_target_size_spin.setRange(1, 10000)
        self.max_target_size_spin.setValue(100)
        self.max_target_size_spin.setSuffix(" px")
        form_layout.addRow("最大目标尺寸", self.max_target_size_spin)
        panel_layout.addLayout(form_layout)

        # 类别映射表用于维护“类别名称 -> 类别 ID”的人工输入。
        mapping_title = QLabel("类别映射表", panel)
        mapping_title.setObjectName("sectionLabel")
        panel_layout.addWidget(mapping_title)

        self.mapping_table = QTableWidget(0, 2, panel)
        self.mapping_table.setHorizontalHeaderLabels(["类别名称", "类别 ID"])
        self.mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mapping_table.verticalHeader().setVisible(False)
        self.mapping_table.setMinimumHeight(120)
        panel_layout.addWidget(self.mapping_table)

        # 表格按钮只操作 UI 行数，不把表格内容转换成业务参数。
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

        # 进度条用于未来批量处理过程的状态展示。
        self.progress_bar = QProgressBar(panel)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("等待执行")
        panel_layout.addWidget(self.progress_bar)

        # 结果框用于显示批量处理摘要或错误列表。
        self.result_text = QPlainTextEdit(panel)
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("执行结果显示区域")
        self.result_text.setMinimumHeight(80)
        panel_layout.addWidget(self.result_text)

        # 开始按钮只预留控件；取消/关闭按钮只关闭弹窗。
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.start_button = QPushButton("开始执行", panel)
        self.start_button.setObjectName("primaryButton")
        self.close_button = QPushButton("取消/关闭", panel)
        self.close_button.clicked.connect(self.reject)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.close_button)
        panel_layout.addLayout(button_row)

    def _dir_row(self, line_edit: QLineEdit, callback) -> QFrame:
        """创建目录输入行，统一使用输入框和浏览目录按钮。"""
        row = QFrame(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("浏览目录", row)
        button.clicked.connect(callback)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return row

    def _browse_source_dir(self) -> None:
        """选择包含 JSON 和图片的源目录，并回填到源目录输入框。"""
        path = QFileDialog.getExistingDirectory(self, "选择源目录")
        if path:
            self.source_dir_edit.setText(path)

    def _browse_output_dir(self) -> None:
        """选择批量转换输出目录，并回填到输出目录输入框。"""
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir_edit.setText(path)

    def _add_mapping_row(self) -> None:
        """给类别映射表追加一行空白记录。"""
        row = self.mapping_table.rowCount()
        self.mapping_table.insertRow(row)
        self.mapping_table.setItem(row, 0, QTableWidgetItem(""))
        self.mapping_table.setItem(row, 1, QTableWidgetItem(""))

    def _remove_mapping_rows(self) -> None:
        """删除选中的映射行，并保证表格不会完全空掉。"""
        rows = sorted({index.row() for index in self.mapping_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.mapping_table.removeRow(row)
        if self.mapping_table.rowCount() == 0:
            self._add_mapping_row()

    def update_progress(self, current: int, total: int) -> None:
        """刷新批量处理进度，只负责显示当前进度文本和百分比。"""
        if total <= 0:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("等待执行")
            return
        percent = max(0, min(100, int(current * 100 / total)))
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{current}/{total} ({percent}%)")
