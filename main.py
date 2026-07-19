"""
象棋辅助工具 - 主入口

基于 PySide6 + OpenCV + Pikafish 引擎的智能象棋辅助系统

核心流程:
  截图 → 识别棋盘 → 生成FEN → 引擎分析 → 显示建议

架构:
  main.py          - 主入口, 生命周期管理
  config.py        - 配置管理
  core/            - 状态机、热键、坐标转换
  vision/          - OpenCV 视觉识别
  engine/          - Pikafish UCI引擎通信
  ui/              - PySide6 界面(悬浮窗、设置、托盘)
"""

import sys
import os
import threading

# 确保项目目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer

from config import Config
from core.state_machine import StateMachine, AppState
from core.hotkey_manager import HotkeyManager
from core.converter import uci_to_chinese
from engine.pikafish_engine import PikafishEngine
from vision.yolo_detector import YOLODetector, capture_screen
from ui.overlay import OverlayWindow
from ui.main_window import MainWindow
from ui.tray import TrayManager


class ChessAssistant:
    """象棋辅助主控制器 - 串联所有模块"""

    def __init__(self, app: QApplication):
        self.app = app
        self.config = Config()
        self.state_machine = StateMachine()
        self.hotkey_manager = HotkeyManager()

        # 核心模块
        self.engine = None
        self.yolo = None
        self.overlay = None
        self.main_window = None
        self.tray = None

        # 状态跟踪
        self.last_fen = None
        self._engine_busy = False
        self._analysis_count = 0

        # 定时器: 每 2 秒检测棋盘是否变化 (仅 YOLO 推理, 不阻塞)
        self._check_timer = QTimer()
        self._check_timer.timeout.connect(self._check_board_change)
        self._check_interval = 2000  # ms

        # 初始化
        self._init_modules()

    def _init_modules(self):
        """初始化所有模块"""
        # 1. 状态机
        self.state_machine.on_change(self._on_state_changed)

        # 2. 初始化引擎
        self.engine = PikafishEngine(
            engine_path=self.config.get("engine.path") or None
        )

        # YOLO 检测器
        self.yolo = YOLODetector()
        if self.yolo.is_loaded:
            print("[OK] YOLO 棋子检测器就绪")
        else:
            print("[INFO] YOLO 不可用, 使用 OpenCV 模板匹配")

        # 3. 设置引擎参数
        self.engine.set_think_time(self.config.get("engine.think_time", 1000))
        self.engine.set_difficulty(self.config.get("engine.skill_level", 20))
        self.engine.set_hash(self.config.get("engine.hash_size", 64))

        # 4. UI
        self.overlay = OverlayWindow()
        self.overlay.toggle_requested.connect(self._toggle_assist)

        self.main_window = MainWindow(self.config, self.state_machine)
        self.main_window.setWindowFlags(
            self.main_window.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        self.tray = TrayManager()
        self.tray.show_main_requested.connect(self.main_window.show)
        self.tray.toggle_requested.connect(self._toggle_assist)
        self.tray.quit_requested.connect(self._quit)

        # 6. 热键 — 双重绑定: keyboard 库 + Qt QShortcut
        self._setup_hotkeys()

        # 将 Qt 快捷键绑定到主窗口和悬浮窗, 确保按键可被捕获
        self.hotkey_manager.bind_to_qt(self.main_window)
        self.hotkey_manager.bind_to_qt(self.overlay)

        print("[OK] 所有模块初始化完成")

    def _setup_hotkeys(self):
        """设置全局热键"""
        toggle_key = self.config.get("hotkeys.toggle", "z")
        refresh_key = self.config.get("hotkeys.calibrate", "x")
        quit_key = self.config.get("hotkeys.quit", "esc")

        self.hotkey_manager.register(toggle_key, lambda k: self._toggle_assist())
        self.hotkey_manager.register(refresh_key, lambda k: self._refresh_analysis())
        self.hotkey_manager.register(quit_key, lambda k: self._quit())

        self.hotkey_manager.start()

    # ─── 状态管理 ──────────────────────────────────────────

    def _on_state_changed(self, old_state: AppState, new_state: AppState):
        """状态变化回调"""
        print(f"[STATE] {old_state.name} → {new_state.name}")

        if new_state == AppState.IDLE:
            self.overlay.set_active(False)
            self.tray.set_active(False)
            self._check_timer.stop()
        elif new_state == AppState.ASSISTING:
            self.overlay.set_active(True)
            self.tray.set_active(True)
            self._start_engine()
            self.last_fen = None
            if self.yolo:
                self.yolo.reset_grid()  # 重新锁定棋盘网格
            self._check_timer.start(self._check_interval)
            self._do_analysis()

    def _toggle_assist(self):
        """切换辅助状态"""
        if not self.state_machine.is_idle():
            self.state_machine.set_state(AppState.IDLE)
            if self.engine:
                self.engine.stop_calculation()
            self.overlay.show_message("辅助已关闭", 1500)
        else:
            self.state_machine.set_state(AppState.ASSISTING)
            self.overlay.show_message("辅助已开启", 1500)

        # 确保悬浮窗可见
        if self.state_machine.is_active():
            self.overlay.show()
        else:
            self.overlay.show()  # 即使待机也显示, 但灰色

    # ─── 引擎管理 ──────────────────────────────────────────

    def _start_engine(self):
        """启动引擎"""
        if not self.engine:
            return
        if self.engine.process and self.engine.process.poll() is None:
            return True
        return self.engine.start()

    # ─── 分析循环 ──────────────────────────────────────────

    def _do_analysis(self):
        """执行一轮分析: 截图 → 识别 → 引擎分析 → 显示"""
        if not self.state_machine.is_assisting():
            return
        if self._engine_busy:
            return

        self._analysis_count += 1

        # 0. 截图 (YOLO 和 OpenCV 都需要)
        screenshot = capture_screen()
        if screenshot is None:
            return

        # 1. 识别棋盘 → FEN
        fen = None

        # 优先 YOLO (端到端检测, 无需校准)
        if self.yolo and self.yolo.is_loaded:
            import numpy as np, cv2
            img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            detections = self.yolo.detect(img, conf_thresh=0.5)
            if detections:
                fen = self.yolo.board_to_fen(detections)

        if fen is None:
            return

        # 2. 检测是否同一局面
        if fen == self.last_fen:
            return
        self.last_fen = fen

        # 3. 检查是否空棋盘
        board_part = fen.split()[0] if " " in fen else fen
        piece_letters = sum(1 for c in board_part if c.isalpha())
        if piece_letters < 8:
            return

        # 4. 更新悬浮窗
        print(f"[YOLO] {piece_letters}棋子 FEN={fen[:35]}...")
        self.overlay.set_fen(fen)

        # 5. 引擎分析 (异步)
        self._engine_busy = True
        self.engine.set_position(fen)
        self.engine.go_async(
            movetime=self.config.get("engine.think_time", 1000),
            callback=self._on_analysis_result,
        )

    def _on_analysis_result(self, best_move: str, info: dict):
        """引擎分析完成回调"""
        self._engine_busy = False
        self._analysis_count += 1

        # 防御: 引擎返回无效走法 → 清空悬浮窗显示
        if not best_move or best_move == "(none)" or len(best_move) < 4:
            self.overlay.update_analysis(
                best_move="等待走棋...",
                score=0, depth=0, pv="", fen=self.last_fen,
            )
            return

        score = info.get("score", 0)
        depth = info.get("depth", 0)
        pv = info.get("pv", "")

        # 转为中文棋谱
        chinese_move = uci_to_chinese(best_move, self.last_fen)
        display_text = chinese_move if chinese_move and '-' not in chinese_move else best_move

        # 更新悬浮窗
        self.overlay.update_analysis(
            best_move=display_text,
            score=score,
            depth=depth,
            pv=pv,
            fen=self.last_fen,
        )

    # ─── 辅助功能 ──────────────────────────────────────────

    def _check_board_change(self):
        """定时检测棋盘是否变化"""
        if not self.state_machine.is_assisting() or self._engine_busy:
            return
        self.last_fen = None
        self._do_analysis()

    def _refresh_analysis(self):
        """手动刷新分析 (按 X 触发)"""
        if not self.state_machine.is_assisting():
            self.state_machine.set_state(AppState.ASSISTING)
        self.engine.stop_calculation()
        self._engine_busy = False
        self.last_fen = None
        if self.yolo:
            self.yolo.reset_grid()
        self.overlay.show_message("正在分析...", 1000)
        self._do_analysis()

    # ─── 启动/退出 ──────────────────────────────────────────

    def start(self):
        """启动应用"""
        # 启动引擎
        if self.config.get("features.auto_analyze", True):
            self._start_engine()

        # 显示悬浮窗
        self.overlay.show()

        # 显示托盘
        self.tray.show()
        self.tray.show_message(
            "象棋辅助工具已启动",
            f"按 {self.config.get('hotkeys.toggle', 'F1')} 切换辅助模式"
        )

        print("[OK] 象棋辅助工具已启动")
        print(f"[INFO] 按 z 切换辅助模式")

    def _quit(self):
        """退出应用"""
        print("[INFO] 正在退出...")
        self._check_timer.stop()
        self.hotkey_manager.stop()
        if self.engine:
            self.engine.stop()
        self.tray.hide()
        self.app.quit()

    def run(self):
        """运行应用主循环"""
        self.start()
        sys.exit(self.app.exec())


def main():
    """程序入口"""
    # 高空DPI支持
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("象棋辅助工具")
    app.setOrganizationName("XiangqiTool")

    assistant = ChessAssistant(app)
    assistant.run()


if __name__ == "__main__":
    main()
