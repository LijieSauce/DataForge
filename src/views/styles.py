"""DataForge 弹窗视图的统一样式文件。

这里只集中管理外观，不放任何业务逻辑，这样每个弹窗文件都可以
保持独立，同时又能共享同一套米黄色 UI 风格。
"""

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QDialog, QGraphicsDropShadowEffect, QWidget


# 这里集中放所有弹窗共用的配色和控件样式，避免每个文件各写一套。
DIALOG_QSS = """
QDialog {
    background-color: #F5E6D3;
    color: #4A4A4A;
    font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif;
    font-size: 14px;
}

QFrame#panel {
    background-color: #EDD5B8;
    border: 1px solid #C9B79C;
    border-radius: 6px;
}

QLabel#titleLabel {
    color: #4A4A4A;
    font-size: 20px;
    font-weight: 600;
}

QLabel#descriptionLabel {
    color: #6F6254;
    line-height: 1.4;
}

QLabel#sectionLabel {
    color: #4A4A4A;
    font-size: 15px;
    font-weight: 600;
}

QLineEdit,
QSpinBox,
QDoubleSpinBox,
QTableWidget,
QPlainTextEdit {
    background-color: #F5E6D3;
    color: #4A4A4A;
    border: 1px solid #C9B79C;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: #C9B79C;
}

QLineEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QPlainTextEdit:focus {
    border-color: #B8A688;
}

QHeaderView::section {
    background-color: #D4B896;
    color: #4A4A4A;
    border: 1px solid #C9B79C;
    padding: 6px;
    font-weight: 600;
}

QTableWidget {
    gridline-color: #C9B79C;
}

QPushButton {
    background-color: #D4B896;
    color: #4A4A4A;
    border: 1px solid #C9B79C;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #C9B79C;
}

QPushButton:pressed {
    background-color: #B8A688;
}

QPushButton#primaryButton {
    background-color: #C9B79C;
    font-weight: 600;
}

QPushButton#primaryButton:hover {
    background-color: #B8A688;
}

QProgressBar {
    background-color: #F5E6D3;
    color: #4A4A4A;
    border: 1px solid #C9B79C;
    border-radius: 6px;
    height: 16px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #B8A688;
    border-radius: 5px;
}
"""


def apply_dialog_style(dialog: QDialog) -> None:
    """给单个弹窗应用统一的米黄色主题样式。"""
    dialog.setStyleSheet(DIALOG_QSS)


def apply_panel_shadow(widget: QWidget) -> None:
    """给主面板加上接近 HTML 样本的柔和阴影效果。"""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(18)
    shadow.setOffset(0, 3)
    shadow.setColor(QColor(74, 74, 74, 35))
    widget.setGraphicsEffect(shadow)
