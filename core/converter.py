"""
坐标转换与棋谱模块

功能:
1. UCI ↔ 中文棋谱互转
2. 棋盘坐标 ↔ 屏幕像素坐标映射
3. FEN 局面串生成与解析
4. 中国象棋规则常量
"""

# ─── 中国象棋常量 ──────────────────────────────────────────

# 棋子 Unicode 符号 (红方大写, 黑方小写)
PIECE_SYMBOLS = {
    # 红方
    'R': '车', 'N': '马', 'B': '相', 'A': '仕',
    'K': '帅', 'P': '兵', 'C': '炮',
    # 黑方
    'r': '车', 'n': '马', 'b': '象', 'a': '士',
    'k': '将', 'p': '卒', 'c': '炮',
}

# 棋子 Unicode 符号 (用于显示)
PIECE_UNICODE = {
    'R': '♖', 'N': '♘', 'B': '♗', 'A': '♕',
    'K': '♔', 'P': '♙', 'C': '♖',
    'r': '♜', 'n': '♞', 'b': '♝', 'a': '♛',
    'k': '♚', 'p': '♟', 'c': '♜',
}

# 棋子颜色
def is_red(piece: str) -> bool:
    """判断是否为红方棋子"""
    return piece.isupper()

def is_black(piece: str) -> bool:
    """判断是否为黑方棋子"""
    return piece.islower() and piece.isalpha()

# ─── 中文棋谱 ─────────────────────────────────────────────

CHINESE_NUMBERS = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']
CHINESE_NUMBERS_BLACK = ['０', '１', '２', '３', '４', '５', '６', '７', '８', '９']


def to_chinese_number(n: int, is_red: bool = True) -> str:
    """数字转中文数字"""
    nums = CHINESE_NUMBERS if is_red else CHINESE_NUMBERS_BLACK
    if 0 <= n <= 9:
        return nums[n]
    return str(n)


def uci_to_chinese(move_uci: str, fen_before: str = None) -> str:
    """
    将 UCI 走法转为中文棋谱 (完整版, 需要局面信息)

    UCI 格式: 列(0-8)+行(0-9) → 列+行
    中文棋盘: 红方从右到左 1-9, 黑方从左到右 1-9

    Args:
        move_uci: UCI走法, 如 "e2e4"
        fen_before: 走法之前的 FEN 局面, 用于确定棋子类型

    Returns:
        中文棋谱, 如 "炮二平五"
    """
    if not move_uci or len(move_uci) < 4:
        return move_uci

    from_col = ord(move_uci[0]) - ord('a')   # 0-8
    from_row = int(move_uci[1])               # 0-9
    to_col = ord(move_uci[2]) - ord('a')      # 0-8
    to_row = int(move_uci[3])                 # 0-9

    # 从 FEN 获取棋子类型
    piece = None
    if fen_before:
        piece = fen_to_piece(fen_before, from_col, from_row)

    if not piece:
        # 无 FEN 时的备用格式: 使用中文数字列号
        fr_cn = 9 - from_col  # 红方视角列号
        to_cn = 9 - to_col
        col_diff = to_col - from_col
        row_diff = to_row - from_row
        action = "进" if row_diff > 0 else "退" if row_diff < 0 else "平"
        target = to_cn if action != "平" else to_cn
        return f"{CHINESE_NUMBERS[fr_cn]}{action}{CHINESE_NUMBERS[target]}" if abs(fr_cn) <= 9 else f"{move_uci[:2]}-{move_uci[2:]}"

    # 确定颜色和棋子名
    red = piece.isupper()
    piece_name = PIECE_SYMBOLS.get(piece, piece)

    # 红方列号从右到左 1-9 (a=9, b=8, ..., i=1)
    # 黑方列号从左到右 1-9 (a=1, b=2, ..., i=9)
    if red:
        col_from_num = 9 - from_col
        col_to_num = 9 - to_col
        col_names = CHINESE_NUMBERS
    else:
        col_from_num = from_col + 1
        col_to_num = to_col + 1
        col_names = CHINESE_NUMBERS_BLACK

    col_from_str = col_names[col_from_num]
    col_to_str = col_names[col_to_num]

    # 确定动作类型
    row_diff = to_row - from_row
    col_diff = to_col - from_col

    if row_diff == 0:
        # 平移: 炮二平五
        action = "平"
        target = col_to_str
    elif col_diff == 0:
        # 直走: 车一进三 / 车一退三
        action = "进" if (row_diff > 0) == red else "退"
        target = col_names[abs(row_diff)]
    elif abs(col_diff) == abs(row_diff):
        # 斜走 (马/相/士): 马八进七
        action = "进" if (row_diff > 0) == red else "退"
        target = col_to_str
    else:
        # 马走日
        action = "进" if (row_diff > 0) == red else "退"
        target = col_to_str

    return f"{piece_name}{col_from_str}{action}{target}"


def fen_to_piece(fen: str, col: int, row: int) -> str:
    """
    从 FEN 局面中获取指定位置的棋子

    FEN 格式: 从红方视角, 从上到下(黑方底线在顶部), 行用 / 分隔
    行内: 大写=红方, 小写=黑方, 数字=空格数

    注意: FEN 行0是顶部(黑方底线, row=9), 行9是底部(红方底线, row=0)
    """
    if not fen:
        return None

    board_part = fen.split(" ")[0]
    rows = board_part.split("/")

    # FEN 行索引: 0=顶部(黑方底线) => row=9
    # 我们需要: row=0 => 底部 => rows[9]
    fen_row = 9 - row

    if fen_row < 0 or fen_row >= len(rows):
        return None

    r = rows[fen_row]
    c = 0
    for ch in r:
        if ch.isdigit():
            c += int(ch)
        else:
            if c == col:
                return ch
            c += 1
    return None


def fen_to_board_array(fen: str) -> list:
    """将 FEN 转为 10x9 二维数组, [row][col], None=空位"""
    board = [[None for _ in range(9)] for _ in range(10)]
    if not fen:
        return board

    board_part = fen.split(" ")[0]
    rows = board_part.split("/")

    for fen_row, row_str in enumerate(rows):
        board_row = 9 - fen_row  # FEN 顶部是 row 9
        col = 0
        for ch in row_str:
            if ch.isdigit():
                col += int(ch)
            else:
                if 0 <= board_row < 10 and 0 <= col < 9:
                    board[board_row][col] = ch
                col += 1
    return board


def board_to_fen(board: list) -> str:
    """将 10x9 棋盘数组转为 FEN 串"""
    rows = []
    for board_row in range(9, -1, -1):  # FEN: 顶部是 row9
        row_str = ""
        empty = 0
        for col in range(9):
            piece = board[board_row][col]
            if piece is None:
                empty += 1
            else:
                if empty > 0:
                    row_str += str(empty)
                    empty = 0
                row_str += piece
        if empty > 0:
            row_str += str(empty)
        rows.append(row_str)
    return "/".join(rows) + " w - - 0 1"


# ─── 屏幕坐标映射 ──────────────────────────────────────────

class BoardRegion:
    """棋盘坐标↔屏幕像素坐标映射"""

    def __init__(self, x: int = 0, y: int = 0, size: int = 400):
        """
        Args:
            x, y: 棋盘左上角屏幕坐标
            size: 棋盘宽度(像素), 棋盘是正方形
        """
        self.x = x
        self.y = y
        self.size = size
        self.cell_size = size / 9  # 9格间距
        self.margin = self.cell_size * 0.5  # 边距(半格)

    def calibrate(self, x: int, y: int, size: int):
        """重新校准棋盘区域"""
        self.x = x
        self.y = y
        self.size = size
        self.cell_size = size / 9
        self.margin = self.cell_size * 0.5

    def board_to_screen(self, col: int, row: int) -> tuple:
        """
        棋盘坐标(0-8, 0-9) → 屏幕像素坐标(中心点)

        col: 0-8 (左→右, a→i)
        row: 0-9 (下→上, 0=红方底线, 9=黑方底线)
        """
        px = self.x + self.margin + col * self.cell_size
        py = self.y + self.margin + (9 - row) * self.cell_size
        return int(px), int(py)

    def screen_to_board(self, px: int, py: int) -> tuple:
        """
        屏幕像素坐标 → 棋盘坐标 (col, row)

        Returns:
            (col, row) 或 (None, None) 如果在棋盘外
        """
        col = (px - self.x - self.margin) / self.cell_size
        row = 9 - (py - self.y - self.margin) / self.cell_size

        if 0 <= col < 9 and 0 <= row < 10:
            return int(round(col)), int(round(row))
        return None, None


# ─── 走法解析 ──────────────────────────────────────────────

def parse_go_output(output: str) -> dict:
    """解析引擎 go 命令的完整输出"""
    result = {
        "bestmove": None,
        "score": None,
        "depth": None,
        "nodes": None,
        "time_ms": None,
        "pv": None,
        "ponder": None,
    }

    import re
    # bestmove
    m = re.search(r"bestmove\s+(\S+)", output)
    if m:
        result["bestmove"] = m.group(1)

    # ponder
    m = re.search(r"ponder\s+(\S+)", output)
    if m:
        result["ponder"] = m.group(1)

    # info 行解析
    for line in output.split("\n"):
        if not line.startswith("info"):
            continue

        m = re.search(r"score\s+(cp|mate)\s*(-?\d+)", line)
        if m:
            score_type, score_val = m.groups()
            score_val = int(score_val)
            result["score"] = 10000 if score_type == "mate" and score_val > 0 else -10000 if score_type == "mate" else score_val

        m = re.search(r"depth\s+(\d+)", line)
        if m:
            result["depth"] = int(m.group(1))

        m = re.search(r"nodes\s+(\d+)", line)
        if m:
            result["nodes"] = int(m.group(1))

        m = re.search(r"time\s+(\d+)", line)
        if m:
            result["time_ms"] = int(m.group(1))

        m = re.search(r"pv\s+(.+)", line)
        if m:
            result["pv"] = m.group(1).strip()

    return result


if __name__ == "__main__":
    # 测试
    test_fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    board = fen_to_board_array(test_fen)
    print(f"棋盘大小: {len(board)}x{len(board[0])}")
    print(f"e2 位置棋子: {fen_to_piece(test_fen, 4, 2)}")  # 应该是兵

    # 测试坐标
    region = BoardRegion(100, 100, 360)
    print(f"e4 屏幕坐标: {region.board_to_screen(4, 4)}")
    print(f"中心附近棋盘坐标: {region.screen_to_board(300, 300)}")
