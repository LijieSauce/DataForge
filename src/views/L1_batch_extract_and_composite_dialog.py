"""批量目标提取并合成到背景的纯 UI 文件。

这个窗口只收集源目录、背景图目录、输出目录和类别映射，
不扫描目录、不读取图片，也不执行合成逻辑。
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


class BatchExtractAndCompositeDialog(QDialog):
    """批量提取并合成的独立 UI 弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 批量合成需要多个目录输入和映射表，因此默认窗口保持较大尺寸。
        self.setWindowTitle("批量提取目标 + 合成到背景")
        self.resize(760, 700)
        apply_dialog_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        """搭建批量提取并合成弹窗的完整界面。"""
        # 外层布局提供统一的窗口留白。
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # 主面板统一容纳全部控件，并应用共享主题阴影。
        panel = QFrame(self)
        panel.setObjectName("panel")
        apply_panel_shadow(panel)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 18, 22, 18)
        panel_layout.setSpacing(14)
        main_layout.addWidget(panel)

        # 标题区说明当前窗口是批量合成场景。
        title = QLabel("批量提取目标 + 合成到背景", panel)
        title.setObjectName("titleLabel")
        description = QLabel("选择源目录、背景图片目录和输出目录，界面只准备批量参数。", panel)
        description.setObjectName("descriptionLabel")
        description.setWordWrap(True)
        panel_layout.addWidget(title)
        panel_layout.addWidget(description)

        # 参数表单只负责采集目录和通用配置，不做目录遍历。
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        self.source_dir_edit = QLineEdit(panel)
        form_layout.addRow("源目录 *", self._dir_row(self.source_dir_edit, self._browse_source_dir))

        self.wall_dir_edit = QLineEdit(panel)
        form_layout.addRow("背景图片目录 *", self._dir_row(self.wall_dir_edit, self._browse_wall_dir))

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

        # 类别映射表用于后续业务层读取类别名称和类别 ID 的对应关系。
        mapping_title = QLabel("类别映射表", panel)
        mapping_title.setObjectName("sectionLabel")
        panel_layout.addWidget(mapping_title)

        self.mapping_table = QTableWidget(0, 2, panel)
        self.mapping_table.setHorizontalHeaderLabels(["类别名称", "类别 ID"])
        self.mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mapping_table.verticalHeader().setVisible(False)
        self.mapping_table.setMinimumHeight(120)
        panel_layout.addWidget(self.mapping_table)

        # 表格按钮只管理行的增删，不把数据提交给业务层。
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

        # 进度条用于未来批量合成任务的状态反馈。
        self.progress_bar = QProgressBar(panel)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("等待执行")
        panel_layout.addWidget(self.progress_bar)

        # 结果框用于显示批量合成摘要、失败文件或提示文本。
        self.result_text = QPlainTextEdit(panel)
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("执行结果显示区域")
        self.result_text.setMinimumHeight(80)
        panel_layout.addWidget(self.result_text)

        # 开始按钮只作为预留入口；关闭按钮只退出当前弹窗。
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
        """创建目录输入行，统一放置输入框和浏览按钮。"""
        row = QFrame(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("浏览目录", row)
        button.clicked.connect(callback)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return row

    def _browse_source_dir(self) -> None:
        """选择包含 JSON 和原图的源目录，并回填到源目录输入框。"""
        path = QFileDialog.getExistingDirectory(self, "选择源目录")
        if path:
            self.source_dir_edit.setText(path)

    def _browse_wall_dir(self) -> None:
        """选择背景图片目录，并回填到背景图片目录输入框。"""
        path = QFileDialog.getExistingDirectory(self, "选择背景图片目录")
        if path:
            self.wall_dir_edit.setText(path)

    def _browse_output_dir(self) -> None:
        """选择批量合成输出目录，并回填到输出目录输入框。"""
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
        """删除选中的映射行，并保证表格至少保留一行。"""
        rows = sorted({index.row() for index in self.mapping_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.mapping_table.removeRow(row)
        if self.mapping_table.rowCount() == 0:
            self._add_mapping_row()

    def update_progress(self, current: int, total: int) -> None:
        """刷新批量合成进度，只负责界面显示。"""
        if total <= 0:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("等待执行")
            return
        percent = max(0, min(100, int(current * 100 / total)))
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{current}/{total} ({percent}%)")
