from __future__ import annotations
import os, math
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPixmap, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer

# ===== Canvas / grid =====
PX_GRID = 10.0
GRID_STEP = PX_GRID
SCENE_W = 1100.0
SCENE_H = 750.0
EPS = 0.5

# ===== Colors =====
ROOM_COLOR = QColor(100, 160, 255, 90)
ROOM_BORDER = QColor(30, 90, 200)
DEV_COLOR = QColor(255, 220, 0, 150)
DEV_BORDER = QColor(120, 95, 0)

# ===== Grid visuals =====
GRID_STEP = 10.0
MAJOR_EVERY = 5
BG_COLOR = QColor("#F2F4F7")
GRID_MINOR = QColor("#D0D6E0")
GRID_MAJOR = QColor("#A8B3C2")
SCENE_BORDER = QColor("#111827")
SCENE_BORDER_W = 2

# ===== Preview sizing =====
PREVIEW_MAX_W = 320
PREVIEW_MAX_H = 180
DEVICE_PREVIEW_SIZE = 40

CATEGORY_ICON_ROOMS = "assets/icons/rooms.svg"
CATEGORY_ICON_DEVICES = "assets/icons/devices.svg"
CATEGORY_ICON_FURNITURE = "assets/icons/furniture.svg"

def snap(v: float, step: float) -> float:
    return round(v / step) * step

def _scene_rect_of_item(item) -> QRectF:
    r = item.rect()
    return QRectF(item.pos().x(), item.pos().y(), r.width(), r.height())

def _rects_overlap_strict(a: QRectF, b: QRectF, eps: float = EPS) -> bool:
    return (
        (a.left()   < b.right()  - eps) and
        (a.right()  > b.left()   + eps) and
        (a.top()    < b.bottom() - eps) and
        (a.bottom() > b.top()    + eps)
    )

def load_svg_icon(path: str, size: int):
    try:
        if not os.path.exists(path):
            return None
        renderer = QSvgRenderer(path)
        if not renderer.isValid():
            return None
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        renderer.render(p, QRectF(0, 0, size, size))
        p.end()
        from PySide6.QtGui import QIcon
        return QIcon(pm)
    except Exception:
        return None
