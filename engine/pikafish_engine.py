"""
Pikafish 引擎通信模块
UCI (Universal Chess Interface) 协议实现

Pikafish 基于 Stockfish 架构，使用标准 UCI 协议通信。
引擎进程通过 stdin/stdout 进行交互。
"""

import subprocess
import threading
import time
import re
import os
from pathlib import Path
from typing import Optional, List, Tuple


class PikafishEngine:
    """Pikafish 引擎管理器 - 负责引擎进程生命周期与 UCI 协议通信"""

    def __init__(self, engine_path: str = None):
        """
        初始化引擎管理器

        Args:
            engine_path: Pikafish 可执行文件路径. 默认自动查找.
        """
        self.engine_path = engine_path or self._find_engine()
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._best_move: Optional[str] = None
        self._info: dict = {}
        self._hash_size = 64  # MB
        self._threads = 2
        self._move_time = 1000  # 毫秒, 思考时间

    def _find_engine(self) -> str:
        """自动查找引擎文件"""
        search_patterns = [
            "pikafish.exe",
            "Pikafish.exe",
            "engine/pikafish.exe",
            "engine/Pikafish.exe",
            "../pikafish.exe",
        ]
        # 在项目目录及子目录查找
        base = Path(__file__).parent.parent
        for pattern in search_patterns:
            candidates = list(base.rglob(pattern))
            if candidates:
                return str(candidates[0])

        # 尝试直接找 .exe
        for f in base.rglob("*.exe"):
            name = f.name.lower()
            if "pikafish" in name or "pika" in name:
                return str(f)
        return "pikafish.exe"  # 默认 PATH 查找

    # ─── 引擎生命周期 ───────────────────────────────────────────

    def start(self) -> bool:
        """启动引擎进程"""
        if self.process and self.process.poll() is None:
            return True  # 已在运行

        try:
            self.process = subprocess.Popen(
                [self.engine_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,  # 行缓冲
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
        except FileNotFoundError:
            print(f"[ERROR] 找不到引擎: {self.engine_path}")
            return False
        except Exception as e:
            print(f"[ERROR] 启动引擎失败: {e}")
            return False

        # 启动输出读取线程
        t = threading.Thread(target=self._reader_loop, daemon=True)
        t.start()

        # UCI 初始化握手
        self._send("uci")
        self._wait_for("uciok", timeout=3)

        # 配置引擎参数 (Pikafish 支持的选项)
        self._send(f"setoption name Hash value {self._hash_size}")
        self._send(f"setoption name Threads value {self._threads}")
        # Pikafish 无 Skill Level 选项, 通过限制搜索深度或时间控制难度

        # 准备就绪
        self._send("isready")
        self._wait_for("readyok", timeout=3)
        self._ready.set()
        print(f"[OK] 引擎已启动: {self.engine_path}")
        return True

    def stop(self):
        """停止引擎进程"""
        if self.process and self.process.poll() is None:
            self._send("quit")
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        self._ready.clear()

    def restart(self) -> bool:
        """重启引擎"""
        self.stop()
        time.sleep(0.2)
        return self.start()

    # ─── UCI 指令 ──────────────────────────────────────────────

    def set_position(self, fen: str = None, moves: List[str] = None):
        """
        设置棋盘局面
        Args:
            fen: FEN 局面串, None 表示起始局面
            moves: 已走的棋步列表 (UCI 格式, 如 ["e2e4", "e7e5"])
        """
        cmd = "position"
        if fen:
            cmd += f" fen {fen}"
        else:
            cmd += " startpos"
        if moves:
            cmd += " moves " + " ".join(moves)
        self._send(cmd)

    def go(self, movetime: int = None, depth: int = None) -> Optional[str]:
        """
        开始计算最优走法 (阻塞等待结果)

        Args:
            movetime: 思考时间(毫秒). 默认使用 self._move_time
            depth: 搜索深度. 默认不限制, 由 movetime 控制

        Returns:
            UCI 格式走法 (如 "e2e4"), 失败返回 None
        """
        cmd = "go"
        if depth:
            cmd += f" depth {depth}"
        else:
            cmd += f" movetime {movetime or self._move_time}"

        self._best_move = None
        self._info = {}
        self._send(cmd)
        self._wait_for("bestmove", timeout=(movetime or self._move_time) // 1000 + 5)
        return self._best_move

    def go_async(self, movetime: int = None, depth: int = None,
                  callback=None):
        """
        开始计算最优走法 (异步)

        Args:
            movetime: 思考时间(毫秒)
            depth: 搜索深度
            callback: 回调函数, 接收 (best_move, info_dict)
        """
        cmd = "go"
        if depth:
            cmd += f" depth {depth}"
        else:
            cmd += f" movetime {movetime or self._move_time}"

        self._best_move = None
        self._info = {}

        def _async_go():
            self._send(cmd)
            self._wait_for("bestmove",
                           timeout=(movetime or self._move_time)//1000 + 5)
            if callback:
                callback(self._best_move, self._info)

        t = threading.Thread(target=_async_go, daemon=True)
        t.start()
        return t

    def stop_calculation(self):
        """立即停止引擎计算"""
        self._send("stop")

    def evaluate(self, fen: str) -> dict:
        """
        快速评估局面

        Returns:
            {"score": 分数(centipawn, 正=红优), "bestmove": 最优走法}
        """
        self.set_position(fen)
        self._best_move = None
        self._info = {}
        self._send("go movetime 500")  # 快速评估, 0.5秒
        self._wait_for("bestmove", timeout=3)
        score = self._info.get("score", 0)
        return {
            "score": score,
            "bestmove": self._best_move,
        }

    # ─── 设置 ──────────────────────────────────────────────────

    def set_option(self, name: str, value):
        """设置引擎选项"""
        self._send(f"setoption name {name} value {value}")

    def set_difficulty(self, level: int):
        """
        设置AI难度 (简化: 通过调整思考时间控制)
        level: 0=最弱(快速) ~ 20=最强(深度思考)
        """
        # Pikafish 没有 Skill Level, 通过时间控制难度
        think_ms = max(200, min(10000, level * 150 + 200))
        self._move_time = think_ms

    def set_think_time(self, ms: int):
        """设置思考时间(毫秒)"""
        self._move_time = max(100, min(30000, ms))

    def set_hash(self, mb: int):
        """设置哈希表大小(MB)"""
        self._hash_size = mb
        self._send(f"setoption name Hash value {mb}")

    # ─── 内部方法 ──────────────────────────────────────────────

    def _send(self, cmd: str):
        """发送指令到引擎"""
        if not self.process or self.process.poll() is not None:
            return
        try:
            with self._lock:
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            print(f"[WARN] 引擎管道已关闭")

    def _reader_loop(self):
        """后台读取引擎输出的线程"""
        pattern_bestmove = re.compile(r"bestmove\s+(\S+)")
        pattern_score = re.compile(r"score\s+(cp|mate)\s*(-?\d+)")
        pattern_pv = re.compile(r"pv\s+(.+)")

        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                line = line.strip()

                # 调试输出
                if line and not line.startswith("info"):
                    print(f"[ENGINE] {line}")

                # 解析 bestmove
                m = pattern_bestmove.search(line)
                if m:
                    self._best_move = m.group(1)

                # 解析 info 行 (局面评估)
                if line.startswith("info"):
                    m = pattern_score.search(line)
                    if m:
                        score_type, score_val = m.groups()
                        score_val = int(score_val)
                        if score_type == "mate":
                            # 将杀棋分数转为大分
                            self._info["score"] = 10000 if score_val > 0 else -10000
                        else:
                            self._info["score"] = score_val

                    # 解析 PV (主要变例)
                    m = pattern_pv.search(line)
                    if m:
                        self._info["pv"] = m.group(1).strip()

                    # 解析深度/节点数
                    d = re.search(r"depth\s+(\d+)", line)
                    if d:
                        self._info["depth"] = int(d.group(1))
                    n = re.search(r"nodes\s+(\d+)", line)
                    if n:
                        self._info["nodes"] = int(n.group(1))
                    t = re.search(r"time\s+(\d+)", line)
                    if t:
                        self._info["time_ms"] = int(t.group(1))

                # 特殊响应
                if "uciok" in line:
                    self._ready.set()
                if line == "readyok":
                    self._ready.set()

            except (OSError, ValueError):
                break

    def _wait_for(self, keyword: str, timeout: float = 5):
        """等待引擎输出包含关键字的行"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._best_move and "bestmove" in keyword:
                return True
            if keyword in ["uciok", "readyok"] and self._ready.is_set():
                return True
            time.sleep(0.01)
        return False

    def __del__(self):
        self.stop()


# ─── 便捷函数 ─────────────────────────────────────────────────

def uci_to_chinese(move_uci: str) -> str:
    """
    将 UCI 走法转为中文棋谱记法

    示例: "e2e4" → "炮二平五"
    UCI 格式: 列(0-8)+行(0-9) → 列+行
    中文棋盘列: 从右到左 1-9 (红方视角)
    中文棋盘行: 从近到远 1-10 (红方视角)
    """
    if not move_uci or len(move_uci) < 4:
        return move_uci

    from_col = ord(move_uci[0]) - ord('a')  # 0-8
    from_row = int(move_uci[1])             # 0-9
    to_col = ord(move_uci[2]) - ord('a')    # 0-8
    to_row = int(move_uci[3])               # 0-9

    # 棋子名称
    piece_names = {
        'R': '车', 'N': '马', 'B': '象', 'A': '士',
        'K': '帅', 'P': '兵', 'C': '炮',
        'r': '车', 'n': '马', 'b': '象', 'a': '士',
        'k': '将', 'p': '卒', 'c': '炮',
    }

    # 红方列号: 从右到左 1-9 (a=9, b=8, ..., i=1)
    def col_to_chinese(col_idx, is_red=True):
        if is_red:
            return str(9 - col_idx)
        else:
            return str(col_idx + 1)  # 黑方视角从左到右 1-9

    col_from = col_to_chinese(from_col)
    col_to = col_to_chinese(to_col)
    row_from = from_row
    row_to = to_row

    # 简略返回: "e2e4" → "e2-e4"
    return f"{move_uci[:2]}-{move_uci[2:]}"


def parse_uci_bestmove(output: str) -> Optional[str]:
    """从引擎输出中解析 bestmove"""
    m = re.search(r"bestmove\s+(\S+)", output)
    return m.group(1) if m else None


if __name__ == "__main__":
    # 快速测试
    eng = PikafishEngine()
    if eng.start():
        # 从起始局面开始
        eng.set_position()
        move = eng.go(movetime=2000)
        print(f"推荐走法: {move} ({uci_to_chinese(move) if move else 'N/A'})")
        print(f"评估: {eng._info}")
        eng.stop()
    else:
        print("引擎启动失败!")
