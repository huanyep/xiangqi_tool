"""
YOLOv5 ONNX 推理模块 — 中国象棋棋子检测

模型来源: VinXiangQi (Vincentzyx/VinXiangQi)
输出格式: (1, 25200, 20) → [cx, cy, w, h, bg_prob, cls1..cls15]
15类: b_ma, b_xiang, b_shi, b_jiang, b_che, b_pao, b_bing,
      r_che, r_ma, r_shi, r_jiang, r_xiang, r_pao, r_bing, board
"""

import numpy as np
from pathlib import Path
from typing import List, Optional

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# 15 类标签 (0-indexed, ONNX 输出顺序)
CLASS_LABELS = [
    'b_ma', 'b_xiang', 'b_shi', 'b_jiang', 'b_che', 'b_pao', 'b_bing',
    'r_che', 'r_ma', 'r_shi', 'r_jiang', 'r_xiang', 'r_pao', 'r_bing', 'board'
]

# 标签 → 棋子字符
LABEL_TO_PIECE = {
    'b_ma': 'n', 'b_xiang': 'b', 'b_shi': 'a', 'b_jiang': 'k',
    'b_che': 'r', 'b_pao': 'c', 'b_bing': 'p',
    'r_che': 'R', 'r_ma': 'N', 'r_shi': 'A', 'r_jiang': 'K',
    'r_xiang': 'B', 'r_pao': 'C', 'r_bing': 'P',
}

# 棋子字符 → 标签名
PIECE_TO_LABEL = {v: k for k, v in LABEL_TO_PIECE.items()}

PIECE_NAMES = {
    'n': '黑马', 'b': '黑象', 'a': '黑士', 'k': '黑将',
    'r': '黑车', 'c': '黑炮', 'p': '黑卒',
    'R': '红车', 'N': '红马', 'A': '红仕', 'K': '红帅',
    'B': '红相', 'C': '红炮', 'P': '红兵',
}


def _nms(boxes, scores, iou_thresh=0.45):
    """非极大值抑制"""
    if len(boxes) == 0:
        return []
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        denom = areas[i] + areas[order[1:]] - w * h
        iou = np.divide(w * h, denom, out=np.zeros_like(w), where=denom > 0)
        inds = np.where(iou <= iou_thresh)[0]
        order = order[inds + 1]
    return keep


def capture_screen(region=None):
    """截取屏幕"""
    if not PIL_AVAILABLE:
        return None
    try:
        return ImageGrab.grab(bbox=region) if region else ImageGrab.grab()
    except Exception as e:
        print(f"[ERROR] 截图失败: {e}")
        return None


class YOLODetector:
    def __init__(self, model_path: str = None):
        self.model_path = model_path or str(
            Path(__file__).parent.parent / "yolo_xiangqi.onnx"
        )
        self.session = None
        # 缓存——首次成功检测后固定棋盘网格, 后续不再更新
        self._grid_locked = False   # 是否已锁定
        self._bx = 0                # 棋盘左上角 x
        self._by = 0                # 棋盘左上角 y
        self._grid_w = 0            # 每格宽度
        self._grid_h = 0            # 每格高度
        self._load_model()

    def _load_model(self):
        try:
            import onnxruntime as ort
            if not Path(self.model_path).exists():
                print(f"[ERROR] 模型文件不存在: {self.model_path}")
                return
            self.session = ort.InferenceSession(
                self.model_path, providers=['CPUExecutionProvider']
            )
            print(f"[OK] YOLO 模型: {Path(self.model_path).name}")
        except Exception as e:
            print(f"[ERROR] YOLO 加载失败: {e}")

    @property
    def is_loaded(self):
        return self.session is not None

    def detect(self, img: np.ndarray, conf_thresh=0.5) -> List[dict]:
        """
        YOLO 推理

        Args:
            img: BGR 图像
            conf_thresh: 置信度阈值

        Returns:
            [{label, piece, score, x, y, w, h, x1, y1, x2, y2}, ...]
        """
        if not self.is_loaded:
            return []

        h_orig, w_orig = img.shape[:2]
        target = 640
        scale = target / max(h_orig, w_orig)
        nh, nw = int(h_orig * scale), int(w_orig * scale)

        resized = cv2.resize(img, (nw, nh))
        padded = np.full((target, target, 3), 114, dtype=np.uint8)
        pad_t = (target - nh) // 2
        pad_l = (target - nw) // 2
        padded[pad_t:pad_t+nh, pad_l:pad_l+nw] = resized

        # 预处理
        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = np.transpose(rgb, (2, 0, 1))[None, :, :, :]

        # 推理
        outputs = self.session.run(None, {'images': blob})
        pred = np.squeeze(outputs[0])  # (25200, 20)

        # 解析: [cx, cy, w, h, obj_conf, cls1..cls15]
        # obj_conf 和 class scores 都是 logits, 需要 sigmoid
        boxes = pred[:, :4]            # cx, cy, w, h (640 坐标系)
        obj_conf = pred[:, 4]          # object confidence logit
        class_scores = pred[:, 5:]     # 15 class score logits

        # Sigmoid
        obj_prob = 1.0 / (1.0 + np.exp(-obj_conf))
        cls_prob = 1.0 / (1.0 + np.exp(-class_scores))

        # 联合分数 = obj_conf * max(cls)
        max_cls = cls_prob.max(axis=1)
        final_scores = obj_prob * max_cls

        # 置信度过滤
        keep = final_scores > conf_thresh
        if not keep.any():
            return []

        boxes = boxes[keep]
        final_scores = final_scores[keep]
        class_ids = cls_prob[keep].argmax(axis=1)

        # cx,cy,w,h → x1,y1,x2,y2
        x1 = (boxes[:, 0] - boxes[:, 2] / 2 - pad_l) / scale
        y1 = (boxes[:, 1] - boxes[:, 3] / 2 - pad_t) / scale
        x2 = (boxes[:, 0] + boxes[:, 2] / 2 - pad_l) / scale
        y2 = (boxes[:, 1] + boxes[:, 3] / 2 - pad_t) / scale

        # 限制在原图范围内
        x1 = np.clip(x1, 0, w_orig)
        y1 = np.clip(y1, 0, h_orig)
        x2 = np.clip(x2, 0, w_orig)
        y2 = np.clip(y2, 0, h_orig)

        # NMS
        nms_idx = _nms(np.stack([x1, y1, x2, y2], axis=1), final_scores)
        if len(nms_idx) == 0:
            return []

        results = []
        for i in nms_idx:
            cid = int(class_ids[i])
            label = CLASS_LABELS[cid]
            piece = LABEL_TO_PIECE.get(label)
            results.append({
                'label': label,
                'piece': piece,
                'score': float(final_scores[i]),
                'x': float((x1[i] + x2[i]) / 2),
                'y': float((y1[i] + y2[i]) / 2),
                'w': float(x2[i] - x1[i]),
                'h': float(y2[i] - y1[i]),
                'x1': float(x1[i]),
                'y1': float(y1[i]),
                'x2': float(x2[i]),
                'y2': float(y2[i]),
            })

        return results

    def reset_grid(self):
        """重置棋盘网格缓存 (窗口移动或切换对局时调用)"""
        self._grid_locked = False
        print("[YOLO] 棋盘网格已重置")

    def board_to_fen(self, detections: List[dict]) -> Optional[str]:
        """检测结果 → FEN (带棋盘网格缓存)"""
        pieces = [d for d in detections if d['piece'] is not None]
        if len(pieces) < 2:
            return None

        if not self._grid_locked:
            # 首次检测: 从 board 检测或棋子推算棋盘网格
            board_rect = next((d for d in detections if d['label'] == 'board'), None)

            if board_rect:
                cx, cy, bw, bh = board_rect['x'], board_rect['y'], board_rect['w'], board_rect['h']
                bx = cx - bw / 2
                by = cy - bh / 2
                # 用棋子分布校验
                xs = [p['x'] for p in pieces]
                ys = [p['y'] for p in pieces]
                pw = max(xs) - min(xs)
                ph = max(ys) - min(ys)
                if pw > bw * 0.3 or ph > bh * 0.3:
                    margin_x = pw / 16
                    margin_y = ph / 18
                    bx = min(xs) - margin_x
                    by = min(ys) - margin_y
                    bw = pw + 2 * margin_x
                    bh = ph + 2 * margin_y
            else:
                xs = [p['x'] for p in pieces]
                ys = [p['y'] for p in pieces]
                bx, by = min(xs), min(ys)
                bw = max(xs) - bx if max(xs) > bx else 1
                bh = max(ys) - by if max(ys) > by else 1

            bw = max(bw, 1)
            bh = max(bh, 1)
            self._bx = bx
            self._by = by
            self._grid_w = bw / 8
            self._grid_h = bh / 9
            self._grid_locked = True
            print(f"[YOLO] 棋盘网格已锁定: ({bx:.0f},{by:.0f}) 格子={self._grid_w:.1f}x{self._grid_h:.1f}")

        board = [[None for _ in range(9)] for _ in range(10)]
        pieces.sort(key=lambda p: -p['score'])

        for p in pieces:
            col = int(round((p['x'] - self._bx) / self._grid_w))
            row = 9 - int(round((p['y'] - self._by) / self._grid_h))
            if 0 <= col <= 8 and 0 <= row <= 9:
                if board[row][col] is None:
                    board[row][col] = p['piece']

        total = sum(1 for r in board for c in r if c and c.isalpha())
        if total > 32 or total < 2:
            return None

        has_red = any(board[r][c] == 'K' for r in range(10) for c in range(9))
        has_blk = any(board[r][c] == 'k' for r in range(10) for c in range(9))
        if not (has_red and has_blk):
            return None

        rows = []
        for ri in range(9, -1, -1):
            fr = ""
            emp = 0
            for c in board[ri]:
                if c is None:
                    emp += 1
                else:
                    if emp:
                        fr += str(emp)
                        emp = 0
                    fr += str(c)
            if emp:
                fr += str(emp)
            rows.append(fr)
        return "/".join(rows) + " w - - 0 1"
