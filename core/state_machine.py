"""
核心状态机 - 管理应用生命周期与状态切换

状态:
  IDLE       - 待机中, 仅监听热键
  MONITORING - 监控中, 识别棋盘但不主动输出
  ASSISTING  - 辅助中, 实时分析并给出建议
"""

from enum import Enum, auto
from typing import Callable


class AppState(Enum):
    IDLE = auto()       # 待机 - 仅热键监听, 不占资源
    CALIBRATING = auto()  # 校准中 - 棋盘区域校准
    MONITORING = auto() # 监控 - 识别棋盘但不主动建议
    ASSISTING = auto()  # 辅助 - 实时分析并显示建议


class StateMachine:
    """应用状态机"""

    def __init__(self):
        self._state = AppState.IDLE
        self._listeners = {}  # state -> [callbacks]

    @property
    def state(self) -> AppState:
        return self._state

    def set_state(self, new_state: AppState):
        """切换状态"""
        if new_state == self._state:
            return
        old_state = self._state
        self._state = new_state
        self._notify(old_state, new_state)

    def toggle(self):
        """IDLE ↔ ASSISTING 切换 (快捷键常用)"""
        if self._state == AppState.ASSISTING:
            self.set_state(AppState.IDLE)
        elif self._state == AppState.IDLE:
            self.set_state(AppState.ASSISTING)
        else:
            self.set_state(AppState.ASSISTING)

    def on_change(self, callback: Callable[[AppState, AppState], None]):
        """注册状态变化监听器"""
        if callback not in self._listeners:
            self._listeners[callback] = True

    def _notify(self, old_state: AppState, new_state: AppState):
        """通知所有监听器"""
        for cb in list(self._listeners.keys()):
            try:
                cb(old_state, new_state)
            except Exception as e:
                print(f"[WARN] 状态监听器异常: {e}")

    def is_idle(self) -> bool:
        return self._state == AppState.IDLE

    def is_monitoring(self) -> bool:
        return self._state == AppState.MONITORING

    def is_assisting(self) -> bool:
        return self._state == AppState.ASSISTING

    def is_active(self) -> bool:
        """是否处于活跃状态(非待机)"""
        return self._state != AppState.IDLE

    def __str__(self) -> str:
        names = {
            AppState.IDLE: "待机",
            AppState.CALIBRATING: "校准中",
            AppState.MONITORING: "监控中",
            AppState.ASSISTING: "辅助中",
        }
        return f"[{names.get(self._state, '未知')}]"
