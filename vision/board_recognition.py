"""
棋盘截图工具 (已弃用所有 OpenCV 检测逻辑)

所有视觉识别功能已迁移到 YOLO 检测器 (yolo_detector.py)。
此文件仅保留截图功能供主程序引用。
"""

from .yolo_detector import capture_screen

__all__ = ["capture_screen"]
