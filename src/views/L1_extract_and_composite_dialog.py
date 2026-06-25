"""单文件目标提取并合成到背景的纯 UI 文件。

这个弹窗只收集 JSON、原始图片、背景图片、输出目录和类别映射，
不读取图像、不执行合成，也不调用 DataAugmentationToolkit。
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


class ExtractAndCompositeDialog(QDialog):
    """单文件提取并合成的独立 UI 弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 该窗口需要展示四个路径输入和类别映射表，所以默认尺寸较大。
        self.setWindowTitle("提取目标 + 合成到背景")
        self.resize(760, 740)
        apply_dialog_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        """搭建单文件提取并合成弹窗的完整界面。"""
        # 外层布局设置统一边距，保证窗口内容不贴边。
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # 主面板集中容纳所有控件，并复用统一背景、边框和阴影。
        panel = QFrame(self)
        panel.setObjectName("panel")
        apply_panel_shadow(panel)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 18, 22, 18)
        panel_layout.setSpacing(14)
        main_layout.addWidget(panel)

        # 标题区提示这是单文件提取与合成场景。
        title = QLabel("提取目标 + 合成到背景", panel)
        title.setObjectName("titleLabel")
        description = QLabel("选择单个 JSON、对应图片、背景图片和输出目录，界面不调用合成业务。", panel)
        description.setObjectName("descriptionLabel")
        description.setWordWrap(True)
        panel_layout.addWidget(title)
        panel_layout.addWidget(description)

        # 参数表单只摆放输入控件，不解析 JSON，也不校验图片尺寸。
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        self.json_path_edit = QLineEdit(panel)
        form_layout.addRow("JSON 标注文件 *", self._file_row(self.json_path_edit, "选择 JSON", self._browse_json_path))

        self.image_path_edit = QLineEdit(panel)
        form_layout.addRow("原始图片 *", self._file_row(self.image_path_edit, "选择图片", self._browse_image_path))

        self.wall_image_path_edit = QLineEdit(panel)
        form_layout.addRow("背景图片 *", self._file_row(self.wall_image_path_edit, "选择背景", self._browse_wall_image_path))

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

        # 类别映射表让用户维护“类别名称 -> 类别 ID”的后续业务输入。
        mapping_title = QLabel("类别映射表", panel)
        mapping_title.setObjectName("sectionLabel")
        panel_layout.addWidget(mapping_title)

        self.mapping_table = QTableWidget(0, 2, panel)
        self.mapping_table.setHorizontalHeaderLabels(["类别名称", "类别 ID"])
        self.mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mapping_table.verticalHeader().setVisible(False)
        self.mapping_table.setMinimumHeight(120)
        panel_layout.addWidget(self.mapping_table)

        # 增删行按钮只负责 UI 表格行管理，不转换、不提交业务参数。
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

        # 进度条供后续合成过程刷新，当前 UI 层只负责显示。
        self.progress_bar = QProgressBar(panel)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("等待执行")
        panel_layout.addWidget(self.progress_bar)

        # 结果框预留给业务层显示合成结果、跳过数量或错误信息。
        self.result_text = QPlainTextEdit(panel)
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("执行结果显示区域")
        self.result_text.setMinimumHeight(80)
        panel_layout.addWidget(self.result_text)

        # 开始按钮只预留控件；关闭按钮只关闭窗口。
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.start_button = QPushButton("开始执行", panel)
        self.start_button.setObjectName("primaryButton")
        self.close_button = QPushButton("取消/关闭", panel)
        self.close_button.clicked.connect(self.reject)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.close_button)
        panel_layout.addLayout(button_row)

    def _file_row(self, line_edit: QLineEdit, button_text: str, callback) -> QFrame:
        """创建文件路径输入行，用于 JSON、原图和背景图选择。"""
        row = QFrame(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton(button_text, row)
        button.clicked.connect(callback)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return row

    def _dir_row(self, line_edit: QLineEdit, callback) -> QFrame:
        """创建目录路径输入行，用于输出目录选择。"""
        row = QFrame(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("浏览目录", row)
        button.clicked.connect(callback)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return row

    def _browse_json_path(self) -> None:
        """选择 Labelme JSON 标注文件，并回填到 JSON 输入框。"""
        path, _ = QFileDialog.getOpenFileName(self, "选择 JSON 标注文件", "", "JSON Files (*.json);;All Files (*)")
        if path:
            self.json_path_edit.setText(path)

    def _browse_image_path(self) -> None:
        """选择原始图片文件，并回填到原始图片输入框。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择原始图片",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp);;All Files (*)",
        )
        if path:
            self.image_path_edit.setText(path)

    def _browse_wall_image_path(self) -> None:
        """选择背景图片文件，并回填到背景图片输入框。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择背景图片",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp);;All Files (*)",
        )
        if path:
            self.wall_image_path_edit.setText(path)

    def _browse_output_dir(self) -> None:
        """选择合成结果输出目录，并回填到输出目录输入框。"""
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
        """删除选中的映射行，并至少保留一行可编辑记录。"""
        rows = sorted({index.row() for index in self.mapping_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.mapping_table.removeRow(row)
        if self.mapping_table.rowCount() == 0:
            self._add_mapping_row()

    def update_progress(self, current: int, total: int) -> None:
        """刷新合成处理进度，只更新界面，不执行任何业务。"""
        if total <= 0:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("等待执行")
            return
        percent = max(0, min(100, int(current * 100 / total)))
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{current}/{total} ({percent}%)")
