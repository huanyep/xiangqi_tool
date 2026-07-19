
"""
透明悬浮窗 - 在棋盘旁显示最优走法建议

特性:
- 半透明无边框窗口, 不遮挡棋盘
- 可拖动位置
- 实时更新走法建议和局面评分
- 显示引擎搜索深度和主要变例
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QFrame, QApplication)
from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtGui import QFont, QPainter, QColor, QBrush, QPen, QFontDatabase


class OverlayWindow(QWidget):
    """透明悬浮窗"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # 数据
        self.best_move = ""
        self.score = 0
        self.depth = 0
        self.pv_line = ""
        self.is_active = False

        # UI
        self._setup_ui()
        self._apply_style()

        # 默认位置 (右上角)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 50, 100)

    def _setup_ui(self):
        """初始化 UI 组件"""
        self.setFixedSize(280, 160)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 10, 12, 10)
        self.layout.setSpacing(6)

        # 标题栏
        title_layout = QHBoxLayout()
        self.status_icon = QLabel("●")
        self.status_icon.setStyleSheet("color: #888; font-size: 16px;")
        title_layout.addWidget(self.status_icon)

        self.title_label = QLabel("象棋辅助")
        self.title_label.setStyleSheet("color: #ccc; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        self.fen_label = QLabel("等待开局...")
        self.fen_label.setStyleSheet("color: #999; font-size: 11px;")
        title_layout.addWidget(self.fen_label)

        self.layout.addLayout(title_layout)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #444;")
        self.layout.addWidget(line)

        # 最优走法
        move_layout = QHBoxLayout()
        move_layout.addWidget(QLabel("推荐走法:"))
        self.move_label = QLabel("--")
        self.move_label.setStyleSheet("color: #4fc3f7; font-size: 18px; font-weight: bold;")
        move_layout.addWidget(self.move_label)
        move_layout.addStretch()
        self.layout.addLayout(move_layout)

        # 局面评分
        score_layout = QHBoxLayout()
        score_layout.addWidget(QLabel("局面评分:"))
        self.score_label = QLabel("0.0")
        self.score_label.setStyleSheet("color: #fff; font-size: 14px;")
        score_layout.addWidget(self.score_label)
        score_layout.addStretch()
        self.layout.addLayout(score_layout)

        # 搜索深度
        depth_layout = QHBoxLayout()
        depth_layout.addWidget(QLabel("搜索深度:"))
        self.depth_label = QLabel("0")
        self.depth_label.setStyleSheet("color: #aaa; font-size: 12px;")
        depth_layout.addWidget(self.depth_label)
        depth_layout.addStretch()
        self.layout.addLayout(depth_layout)

        # 推演变例 (滚动文本)
        pv_layout = QHBoxLayout()
        pv_layout.addWidget(QLabel("推演:"))
        self.pv_label = QLabel("")
        self.pv_label.setWordWrap(True)
        self.pv_label.setStyleSheet("color: #aaa; font-size: 11px;")
        pv_layout.addWidget(self.pv_label, 1)
        self.layout.addLayout(pv_layout)

        # 提示标签
        self.hint_label = QLabel("Z:辅助  X:刷新分析  Esc:退出")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #888; font-size: 10px;")
        self.layout.addWidget(self.hint_label)

    def _apply_style(self):
        """应用全局样式"""
        self.setStyleSheet("""
            QLabel { color: #ddd; background: transparent; }
            QWidget { background: transparent; }
        """)

    def paintEvent(self, event):
        """绘制半透明背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        bg_color = QColor(30, 30, 35, 200) if not self.is_active else QColor(20, 60, 30, 210)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(QColor(80, 80, 90, 150), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

        # 激活状态边框
        if self.is_active:
            painter.setPen(QPen(QColor(76, 175, 80, 120), 2))
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

    # ─── 数据更新 ──────────────────────────────────────────

    def update_analysis(self, best_move: str, score: int,
                        depth: int = 0, pv: str = "",
                        fen: str = ""):
        """更新分析结果"""
        self.best_move = best_move
        self.score = score
        self.depth = depth
        self.pv_line = pv

        # 更新显示
        self.move_label.setText(best_move if best_move else "--")

        # 评分显示
        if abs(score) >= 10000:
            score_text = f"{'#' if score > 0 else '-#'}{abs(score)//10000}"
        else:
            score_text = f"{score/100:.1f}"
        score_color = "#4caf50" if score > 0 else "#f44336" if score < 0 else "#fff"
        self.score_label.setText(score_text)
        self.score_label.setStyleSheet(f"color: {score_color}; font-size: 14px;")

        self.depth_label.setText(str(depth))

        # PV 截断显示
        if pv:
            moves = pv.split()[:6]  # 只显示前6步
            self.pv_label.setText(" ".join(moves))
        else:
            self.pv_label.setText("")

    def set_active(self, active: bool):
        """设置激活状态"""
        self.is_active = active
        self.status_icon.setText("●")
        self.status_icon.setStyleSheet(
            f"color: {'#4caf50' if active else '#888'}; font-size: 16px;"
        )
        self.title_label.setText("辅助中" if active else "待机中")
        self.hint_label.setText(
            "Z:切换  X:刷新  Esc:退出" if active else "按 Z 开启辅助  X:刷新"
        )
        self.update()  # 重绘背景

    def set_fen(self, fen: str):
        """显示当前局面信息"""
        if fen:
            short = fen.split()[0] if " " in fen else fen
            self.fen_label.setText(short[:20] + (".." if len(short) > 20 else ""))
            self.fen_label.setToolTip(fen)

    def show_message(self, text: str, duration_ms: int = 2000):
        """在提示标签上临时显示消息"""
        old_text = self.hint_label.text()
        self.hint_label.setText(f"⚡ {text}")
        self.hint_label.setStyleSheet("color: #ffd54f; font-size: 10px;")

        # 一段时间后恢复
        if duration_ms > 0:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(duration_ms, lambda: (
                self.hint_label.setText(
                    "按 Z 切换" if self.is_active else "按 Z 开启辅助"
                ),
                self.hint_label.setStyleSheet("color: #666; font-size: 10px;")
            ))

    # ─── 鼠标交互 ──────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            diff = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + diff)
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        """双击切换辅助状态"""
        self.toggle_requested.emit()
        super().mouseDoubleClickEvent(event)

    toggle_requested = Signal()

    def enterEvent(self, event):
        """鼠标进入时提示可拖动"""
        QApplication.setOverrideCursor(Qt.CursorShape.OpenHandCursor)

    def leaveEvent(self, event):
        QApplication.restoreOverrideCursor()
