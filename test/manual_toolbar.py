"""手动测试 L2_toolbar 工具栏组件"""

import sys
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from PyQt5.QtWidgets import QApplication, QMainWindow
from views.L2_toolbar import TopToolbar


class TestWindow(QMainWindow):
    """测试窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("L2_toolbar 工具栏测试")
        self.resize(1200, 600)

        # 创建工具栏并添加到窗口
        toolbar = TopToolbar(self)
        self.setCentralWidget(toolbar)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
