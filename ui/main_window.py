"""
主设置窗口 - 应用配置与校准界面
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QSpinBox, QSlider, QComboBox,
    QGroupBox, QTabWidget, QCheckBox, QLineEdit, QMessageBox,
    QFileDialog, QApplication,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon


class MainWindow(QMainWindow):
    """主配置窗口"""

    def __init__(self, config=None, state_machine=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.state_machine = state_machine
        self._setup_ui()
        self._load_config()

        # 从配置读取存储的窗口位置
        geom = self.screen().geometry()
        self.resize(520, 480)
        self.move(
            (geom.width() - self.width()) // 2,
            (geom.height() - self.height()) // 2,
        )

    def _setup_ui(self):
        """初始化 UI"""
        self.setWindowTitle("象棋辅助工具 - 设置")
        self.setMinimumSize(480, 420)

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 选项卡
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ─── 基本设置页 ─────────────────────────────────
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)
        tabs.addTab(basic_tab, "基本设置")

        # 引擎路径
        engine_layout = QHBoxLayout()
        self.engine_path_edit = QLineEdit()
        self.engine_path_edit.setPlaceholderText("自动搜索")
        engine_layout.addWidget(self.engine_path_edit)
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._browse_engine)
        engine_layout.addWidget(btn_browse)
        basic_layout.addRow("引擎路径:", engine_layout)

        # 思考时间
        self.think_time_spin = QSpinBox()
        self.think_time_spin.setRange(100, 30000)
        self.think_time_spin.setSuffix(" ms")
        self.think_time_spin.setSingleStep(100)
        basic_layout.addRow("思考时间:", self.think_time_spin)

        # AI 难度
        diff_layout = QHBoxLayout()
        self.diff_slider = QSlider(Qt.Orientation.Horizontal)
        self.diff_slider.setRange(0, 20)
        self.diff_label = QLabel("20 (最强)")
        diff_layout.addWidget(self.diff_slider)
        diff_layout.addWidget(self.diff_label)
        self.diff_slider.valueChanged.connect(
            lambda v: self.diff_label.setText(f"{v} {'(最强)' if v==20 else '(最弱)' if v==0 else ''}")
        )
        basic_layout.addRow("AI难度:", diff_layout)

        # 哈希表大小
        self.hash_spin = QSpinBox()
        self.hash_spin.setRange(16, 2048)
        self.hash_spin.setSuffix(" MB")
        self.hash_spin.setSingleStep(16)
        basic_layout.addRow("哈希表:", self.hash_spin)

        # CPU 线程数
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 16)
        basic_layout.addRow("CPU线程:", self.threads_spin)

        # ─── 视觉设置页 ─────────────────────────────────
        vision_tab = QWidget()
        vision_layout = QFormLayout(vision_tab)
        tabs.addTab(vision_tab, "视觉识别")

        self.auto_detect_cb = QCheckBox("自动检测棋盘位置")
        vision_layout.addRow(self.auto_detect_cb)

        btn_calibrate = QPushButton("手动校准棋盘")
        btn_calibrate.clicked.connect(self._calibrate_board)
        vision_layout.addRow(btn_calibrate)

        self.board_x_spin = QSpinBox()
        self.board_x_spin.setRange(0, 9999)
        vision_layout.addRow("棋盘 X:", self.board_x_spin)

        self.board_y_spin = QSpinBox()
        self.board_y_spin.setRange(0, 9999)
        vision_layout.addRow("棋盘 Y:", self.board_y_spin)

        self.board_size_spin = QSpinBox()
        self.board_size_spin.setRange(100, 2000)
        vision_layout.addRow("棋盘大小:", self.board_size_spin)

        # ─── 热键设置页 ─────────────────────────────────
        hotkey_tab = QWidget()
        hotkey_layout = QFormLayout(hotkey_tab)
        tabs.addTab(hotkey_tab, "热键设置")

        self.hk_toggle = QLineEdit("F1")
        hotkey_layout.addRow("开启/关闭:", self.hk_toggle)
        self.hk_calibrate = QLineEdit("F2")
        hotkey_layout.addRow("校准棋盘:", self.hk_calibrate)
        self.hk_screenshot = QLineEdit("F3")
        hotkey_layout.addRow("手动识别:", self.hk_screenshot)

        # ─── 显示设置页 ─────────────────────────────────
        display_tab = QWidget()
        display_layout = QFormLayout(display_tab)
        tabs.addTab(display_tab, "显示设置")

        self.show_best_cb = QCheckBox("显示最优走法")
        self.show_best_cb.setChecked(True)
        display_layout.addRow(self.show_best_cb)

        self.show_score_cb = QCheckBox("显示局面评分")
        self.show_score_cb.setChecked(True)
        display_layout.addRow(self.show_score_cb)

        self.show_pv_cb = QCheckBox("显示推演变例")
        self.show_pv_cb.setChecked(True)
        display_layout.addRow(self.show_pv_cb)

        self.show_depth_cb = QCheckBox("显示搜索深度")
        self.show_depth_cb.setChecked(True)
        display_layout.addRow(self.show_depth_cb)

        self.minimize_tray_cb = QCheckBox("最小化到系统托盘")
        self.minimize_tray_cb.setChecked(True)
        display_layout.addRow(self.minimize_tray_cb)

        # ─── 底部按钮 ───────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_save = QPushButton("保存设置")
        btn_save.clicked.connect(self._save_config)
        btn_save.setMinimumWidth(100)
        btn_layout.addWidget(btn_save)

        btn_default = QPushButton("恢复默认")
        btn_default.clicked.connect(self._reset_config)
        btn_layout.addWidget(btn_default)

        btn_test = QPushButton("启动引擎")
        btn_test.clicked.connect(self._test_engine)
        btn_layout.addWidget(btn_test)

        layout.addLayout(btn_layout)

    def _load_config(self):
        """加载配置到界面"""
        if not self.config:
            return
        self.engine_path_edit.setText(self.config.get("engine.path", ""))
        self.think_time_spin.setValue(self.config.get("engine.think_time", 1000))
        self.diff_slider.setValue(self.config.get("engine.skill_level", 20))
        self.hash_spin.setValue(self.config.get("engine.hash_size", 64))
        self.threads_spin.setValue(self.config.get("engine.threads", 2))
        self.auto_detect_cb.setChecked(self.config.get("vision.auto_detect", True))
        self.board_x_spin.setValue(self.config.get("vision.board_x", 0))
        self.board_y_spin.setValue(self.config.get("vision.board_y", 0))
        self.board_size_spin.setValue(self.config.get("vision.board_size", 0))
        self.hk_toggle.setText(self.config.get("hotkeys.toggle", "F1"))
        self.hk_calibrate.setText(self.config.get("hotkeys.calibrate", "F2"))
        self.hk_screenshot.setText(self.config.get("hotkeys.screenshot", "F3"))
        self.show_best_cb.setChecked(self.config.get("features.show_best_move", True))
        self.show_score_cb.setChecked(self.config.get("features.show_score", True))
        self.show_pv_cb.setChecked(self.config.get("features.show_pv", True))
        self.show_depth_cb.setChecked(self.config.get("features.show_depth", True))
        self.minimize_tray_cb.setChecked(self.config.get("ui.minimize_to_tray", True))

    def _save_config(self):
        """保存界面设置到配置"""
        if not self.config:
            return

        self.config.set("engine.path", self.engine_path_edit.text())
        self.config.set("engine.think_time", self.think_time_spin.value())
        self.config.set("engine.skill_level", self.diff_slider.value())
        self.config.set("engine.hash_size", self.hash_spin.value())
        self.config.set("engine.threads", self.threads_spin.value())
        self.config.set("vision.auto_detect", self.auto_detect_cb.isChecked())
        self.config.set("vision.board_x", self.board_x_spin.value())
        self.config.set("vision.board_y", self.board_y_spin.value())
        self.config.set("vision.board_size", self.board_size_spin.value())
        self.config.set("hotkeys.toggle", self.hk_toggle.text())
        self.config.set("hotkeys.calibrate", self.hk_calibrate.text())
        self.config.set("hotkeys.screenshot", self.hk_screenshot.text())
        self.config.set("features.show_best_move", self.show_best_cb.isChecked())
        self.config.set("features.show_score", self.show_score_cb.isChecked())
        self.config.set("features.show_pv", self.show_pv_cb.isChecked())
        self.config.set("features.show_depth", self.show_depth_cb.isChecked())
        self.config.set("ui.minimize_to_tray", self.minimize_tray_cb.isChecked())

        QMessageBox.information(self, "提示", "设置已保存")

    def _reset_config(self):
        """恢复默认设置"""
        reply = QMessageBox.question(
            self, "确认", "确定恢复所有设置为默认值?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.reset()
            self._load_config()
            QMessageBox.information(self, "提示", "已恢复默认设置")

    def _browse_engine(self):
        """浏览选择引擎文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Pikafish 引擎", "", "可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if path:
            self.engine_path_edit.setText(path)

    def _test_engine(self):
        """测试引擎连接"""
        from engine.pikafish_engine import PikafishEngine
        path = self.engine_path_edit.text() or None
        eng = PikafishEngine(engine_path=path)
        if eng.start():
            # 测试分析
            eng.set_position()  # 起始局面
            move = eng.go(movetime=1000)
            eng.stop()
            if move:
                QMessageBox.information(
                    self, "引擎测试成功",
                    f"引擎运行正常!\n推荐走法: {move}"
                )
            else:
                QMessageBox.warning(self, "引擎测试", "引擎已启动但未返回走法")
        else:
            QMessageBox.critical(self, "引擎测试失败",
                                 f"无法启动引擎: {path or '自动搜索'}\n"
                                 "请检查引擎路径设置")

    def _calibrate_board(self):
        """棋盘校准 (全屏选取棋子区域)"""
        from vision.board_recognition import BoardRecognizer
        rec = BoardRecognizer()

        QMessageBox.information(
            self, "棋盘校准",
            "请确保象棋软件在前台显示完整棋盘,\n"
            "点击确定后将尝试自动定位棋盘。"
        )

        rect = rec.locate_board()
        if rect:
            x, y, w, h = rect
            self.board_x_spin.setValue(x)
            self.board_y_spin.setValue(y)
            self.board_size_spin.setValue(w)
            QMessageBox.information(
                self, "校准成功",
                f"棋盘位置:\nX={x}, Y={y}, 大小={w}x{h}\n"
                f"设置已自动保存"
            )
            self.config.set("vision.board_x", x)
            self.config.set("vision.board_y", y)
            self.config.set("vision.board_size", w)
        else:
            QMessageBox.warning(
                self, "校准失败",
                "未自动检测到棋盘, 请手动输入坐标。\n"
                "提示: 可以使用截图工具获取棋盘区域坐标。"
            )

    def closeEvent(self, event):
        """关闭窗口时最小化到托盘而不是退出"""
        if self.minimize_tray_cb.isChecked():
            event.ignore()
            self.hide()
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.showMessage(
                    "象棋辅助", "程序已最小化到系统托盘",
                    QIcon(), 2000
                )
        else:
            event.accept()
