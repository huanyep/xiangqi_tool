"""YOLO 检测诊断 — 运行: python debug_yolo.py"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np, cv2
from PIL import ImageGrab
from vision.yolo_detector import YOLODetector

detector = YOLODetector()
if not detector.is_loaded:
    print("模型加载失败！")
    exit(1)

# 截屏
screenshot = np.array(ImageGrab.grab())
img = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)

# 用不同阈值测试
for thresh in [0.1, 0.25, 0.5, 0.7]:
    results = detector.detect(img, conf_thresh=thresh)
    pieces = [r for r in results if r['piece']]
    boards = [r for r in results if r['label'] == 'board']
    print(f'阈值 {thresh:.1f}: 棋子={len(pieces)} 棋盘={len(boards)}')

# 用最低阈值看具体检测了什么
results = detector.detect(img, conf_thresh=0.1)
print(f'\n阈值0.1全部检测 ({len(results)}个):')
for r in sorted(results, key=lambda x: -x['score'])[:20]:
    print(f"  {r['label']:12s} score={r['score']:.3f}  pos=({r['x']:.0f},{r['y']:.0f})")

# 图片信息
print(f'\n截图尺寸: {img.shape[1]}x{img.shape[0]}')
print(f'图片大小: {img.nbytes/1024/1024:.0f} MB')
