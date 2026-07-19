"""
系统托盘模块

提供系统托盘图标, 支持:
- 显示/隐藏主窗口
- 切换辅助状态
- 退出应用
"""

from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Signal, QObject


def create_tray_icon():
    """生成一个简单的象棋盘图标 (无需外部图片)"""
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 背景圆
    painter.setBrush(QColor(60, 60, 70))
    painter.setPen(QColor(100, 100, 110))
    painter.drawEllipse(1, 1, 30, 30)

    # 写 "象" 字
    painter.setPen(QColor(200, 200, 210))
    font = QFont("SimSun", 16, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), 0x0084, "象")  # AlignCenter

    painter.end()
    return QIcon(pixmap)


class TrayManager(QObject):
    """系统托盘管理器"""

    show_main_requested = Signal()
    toggle_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray = None
        self._setup()

    def _setup(self):
        """初始化系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("[WARN] 系统托盘不可用")
            return

        # 创建托盘图标
        icon = create_tray_icon()

        # 创建菜单
        menu = QMenu()

        self.action_show = QAction("显示主窗口", menu)
        self.action_show.triggered.connect(self.show_main_requested.emit)
        menu.addAction(self.action_show)

        self.action_toggle = QAction("开启辅助", menu)
        self.action_toggle.triggered.connect(self.toggle_requested.emit)
        menu.addAction(self.action_toggle)

        menu.addSeparator()

        self.action_quit = QAction("退出", menu)
        self.action_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(self.action_quit)

        # 创建托盘
        self.tray = QSystemTrayIcon(icon, parent=None)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("象棋辅助工具 - 待机中")

        # 点击托盘显示消息
        self.tray.activated.connect(self._on_activated)

    def show(self):
        """显示托盘图标"""
        if self.tray:
            self.tray.show()

    def hide(self):
        """隐藏托盘图标"""
        if self.tray:
            self.tray.hide()

    def set_active(self, active: bool):
        """更新辅助状态显示"""
        if not self.tray:
            return
        if active:
            self.tray.setToolTip("象棋辅助工具 - 辅助中 ✓")
            self.action_toggle.setText("关闭辅助")
        else:
            self.tray.setToolTip("象棋辅助工具 - 待机中")
            self.action_toggle.setText("开启辅助")

    def show_message(self, title: str, msg: str, duration: int = 3000):
        """显示气泡通知"""
        if self.tray:
            self.tray.showMessage(title, msg, QIcon(), duration)

    def _on_activated(self, reason):
        """托盘点击事件"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main_requested.emit()
