"""
热键管理器 - 全局热键监听

双重机制:
1. keyboard 库 — 全局系统钩子 (需要管理员权限时可捕获任意按键)
2. PySide6 QShortcut — Qt 层面快捷键 (无管理员权限时的可靠方案)

支持: 单字母键、F1-F12、Ctrl/Alt/Shift 组合
"""

import threading
from typing import Callable, Dict


class HotkeyManager:
    """全局热键管理器"""

    def __init__(self):
        self._hotkeys: Dict[str, Callable] = {}
        self._running = False
        self._keyboard_available = False
        self._qshortcuts = []  # 保存 QShortcut 引用防止 GC

    def register(self, hotkey: str, callback: Callable):
        """
        注册热键

        Args:
            hotkey: 热键组合
                   字母键: "z", "x", "c"
                   功能键: "F1", "F2"
                   组合键: "ctrl+z", "alt+x"
            callback: 回调函数 (接收 hotkey 字符串)
        """
        self._hotkeys[hotkey] = callback

    def unregister(self, hotkey: str):
        """取消注册热键"""
        self._hotkeys.pop(hotkey, None)

    def start(self):
        """启动所有热键监听"""
        if self._running:
            return
        self._start_keyboard_hook()
        self._running = True

    def _start_keyboard_hook(self):
        """启动 keyboard 库全局钩子"""
        try:
            import keyboard
            for hotkey, callback in self._hotkeys.items():
                keyboard.add_hotkey(hotkey, lambda h=hotkey, cb=callback: cb(h))
            self._keyboard_available = True
            print(f"[OK] 全局热键已启动: {list(self._hotkeys.keys())}")
        except (ImportError, OSError, RuntimeError) as e:
            print(f"[INFO] keyboard 库不可用 ({e}), 使用 Qt 快捷键替代")

    def bind_to_qt(self, parent_widget):
        """
        将热键绑定到 Qt 窗口 (作为第二重保障)

        当 keyboard 库的全局钩子因权限不足失效时,
        通过 Qt 的 QShortcut 仍然可以捕获按键。
        需在 showEvent 或初始化时调用, 传入主窗口/悬浮窗。

        Args:
            parent_widget: QWidget 子类实例 (通常是 MainWindow 或 OverlayWindow)
        """
        try:
            from PySide6.QtGui import QShortcut, QKeySequence
            from PySide6.QtCore import Qt

            qt_key_map = {
                # 字母键
                "z": "Z", "x": "X", "c": "C",
                "a": "A", "b": "B", "d": "D", "e": "E", "f": "F", "g": "G",
                "h": "H", "i": "I", "j": "J", "k": "K", "l": "L", "m": "M",
                "n": "N", "o": "O", "p": "P", "q": "Q", "r": "R", "s": "S",
                "t": "T", "u": "U", "v": "V", "w": "W", "y": "Y",
                # 功能键
                "F1": "F1", "F2": "F2", "F3": "F3", "F4": "F4",
                "F5": "F5", "F6": "F6", "F7": "F7", "F8": "F8",
                "F9": "F9", "F10": "F10", "F11": "F11", "F12": "F12",
                # 特殊键
                "esc": "Escape", "escape": "Escape",
                "enter": "Return", "return": "Return",
                "space": "Space", "tab": "Tab",
                "backspace": "Backspace", "delete": "Delete",
            }

            for hotkey, callback in self._hotkeys.items():
                # 解析热键
                parts = hotkey.split("+")
                modifiers = []
                key = parts[-1].strip().lower()

                for mod in parts[:-1]:
                    mod = mod.strip().lower()
                    if mod in ("ctrl", "control"):
                        modifiers.append("Ctrl")
                    elif mod in ("alt",):
                        modifiers.append("Alt")
                    elif mod in ("shift",):
                        modifiers.append("Shift")
                    elif mod in ("win", "meta", "command"):
                        modifiers.append("Meta")

                qt_key = qt_key_map.get(key, key.upper())
                seq_text = "+".join(modifiers + [qt_key])

                try:
                    seq = QKeySequence(seq_text)
                    sc = QShortcut(seq, parent_widget)
                    sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
                    sc.activated.connect(lambda cb=callback, k=hotkey: cb(k))
                    self._qshortcuts.append(sc)
                except Exception:
                    pass

            print(f"[OK] Qt 快捷键已绑定: {list(self._hotkeys.keys())}")

        except ImportError:
            pass

    def stop(self):
        """停止所有热键监听"""
        self._running = False
        # 停止 keyboard 钩子
        if self._keyboard_available:
            try:
                import keyboard
                keyboard.unhook_all()
            except ImportError:
                pass
        # 释放 QShortcut 引用
        self._qshortcuts.clear()
        print("[OK] 热键已停止")

    def __del__(self):
        self.stop()
