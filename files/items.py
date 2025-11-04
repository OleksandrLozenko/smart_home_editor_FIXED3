from __future__ import annotations
from typing import Optional, List
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from .models import ItemProps
from .utils import (ROOM_COLOR, ROOM_BORDER, DEV_COLOR, DEV_BORDER, EPS, PX_GRID,
                    snap, _scene_rect_of_item, _rects_overlap_strict)
# Важно: PlanScene используется только через методы scene(), импорт внутри методов не нужен

class ResizeHandle(QGraphicsRectItem):
    SIZE = 10.0
    def __init__(self, owner: "PlanRectItem", cx: float, cy: float, corner: str):
        super().__init__(0, 0, self.SIZE, self.SIZE, owner)
        self.owner = owner
        self.corner = corner
        self.setZValue(1000)
        self.setBrush(QColor(255, 255, 255))
        self.setPen(QPen(QColor(80, 80, 80), 1))
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setCursor({
            "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
        }[corner])
        self.update_pos(cx, cy)

    def update_pos(self, cx: float, cy: float):
        self.setPos(cx - self.SIZE/2, cy - self.SIZE/2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            new_pos: QPointF = value
            parent = self.owner
            scene = parent.scene()
            if not scene:
                return super().itemChange(change, value)
            lx = new_pos.x() + self.SIZE/2
            ly = new_pos.y() + self.SIZE/2
            if scene.snap_to_grid:
                lx = snap(lx, PX_GRID)
                ly = snap(ly, PX_GRID)
            rect = QRectF(parent.rect())
            L, T, R, B = 0.0, 0.0, rect.width(), rect.height()
            if self.corner == "tl":
                new_w = R - lx; new_h = B - ly
                dx = lx; dy = ly
                if parent.set_size_px(max(1, new_w), max(1, new_h)):
                    parent.setPos(parent.pos() + QPointF(dx, dy))
            elif self.corner == "tr":
                new_w = lx - L; new_h = B - T - (ly - T)
                dy = ly
                if parent.set_size_px(max(1, new_w), max(1, new_h)):
                    parent.setPos(parent.pos() + QPointF(0, dy))
            elif self.corner == "bl":
                new_w = R - L - (lx - L); new_h = ly - T
                dx = lx
                if parent.set_size_px(max(1, new_w), max(1, new_h)):
                    parent.setPos(parent.pos() + QPointF(dx, 0))
            elif self.corner == "br":
                new_w = lx - L; new_h = ly - T
                parent.set_size_px(max(1, new_w), max(1, new_h))
            return self.pos()
        return super().itemChange(change, value)

class PlanRectItem(QGraphicsRectItem):
    def __init__(self, props: ItemProps, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.props: ItemProps = props
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self._handles: List[ResizeHandle] = []
        self._rounded = 6.0
        self._view_mode = "active"

        if self.props.kind == "room":
            self.brush_normal = QBrush(ROOM_COLOR)
            self.pen_normal = QPen(ROOM_BORDER, 2, Qt.SolidLine)
        else:
            self.brush_normal = QBrush(DEV_COLOR)
            self.pen_normal = QPen(DEV_BORDER, 1, Qt.SolidLine)

        self.brush_selected = QBrush(QColor(255, 240, 180, 160))
        self.pen_selected = QPen(QColor(255, 140, 0), 2, Qt.DashLine)

        self.setBrush(self.brush_normal)
        self.setPen(self.pen_normal)
        self.update_tooltip()

    def set_view_mode(self, mode: str):
        self._view_mode = mode
        # визуально «ярче/тусклее», без кликов:
        if mode in ("active", "active_bright"):
            self.setOpacity(1.0)
        elif mode == "dim_strong_border":
            self.setOpacity(0.85)
        else:  # "dim" и любые прочие
            self.setOpacity(0.45)
        self.update()


    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setOpacity(0.6)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setOpacity(1.0)
        super().mouseReleaseEvent(e)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect()
        brush = self.brush_normal if not self.isSelected() else self.brush_selected
        pen   = self.pen_normal   if not self.isSelected() else self.pen_selected

        if isinstance(self, RoomItem):
            sz = f"{self.rect().width():.0f}×{self.rect().height():.0f}"
            painter.setFont(QFont("", 8, QFont.DemiBold))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(sz) + 8
            th = fm.height() + 4
            pill = QRectF(self.rect().left() + 4, self.rect().top() + 4, tw, th)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 110))
            painter.drawRoundedRect(pill, 4, 4)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(pill, Qt.AlignCenter, sz)
            if self._view_mode == "dim_strong_border":
                c = ROOM_COLOR
                brush = QBrush(QColor(c.red(), c.green(), c.blue(), 50))
                pen = QPen(ROOM_BORDER, 3, Qt.SolidLine)
            elif self._view_mode == "dim":
                c = ROOM_COLOR
                brush = QBrush(QColor(c.red(), c.green(), c.blue(), 40))
                pen = QPen(ROOM_BORDER, 1.5, Qt.SolidLine)

        elif isinstance(self, (DeviceItem, FurnitureItem)):
            if self._view_mode == "active_bright":
                c = DEV_COLOR
                painter.setPen(QPen(DEV_BORDER, 1.5, Qt.SolidLine))
                painter.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), 220)))
            elif self._view_mode == "dim":
                c = DEV_COLOR
                painter.setPen(QPen(DEV_BORDER, 1, Qt.SolidLine))
                painter.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), 60)))

        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawRoundedRect(r, self._rounded, self._rounded)

    def update_tooltip(self):
        rect = self.rect()
        self.setToolTip(
            f"{('Комната' if self.props.kind=='room' else 'Устройство')}: {self.props.name or '(без названия)'}\n"
            f"Размер: {rect.width():.0f} × {rect.height():.0f} px\n"
            f"{self.props.description}"
        )

    def _any_room_overlap(self) -> bool:
        if not isinstance(self, RoomItem):
            return False
        scene = self.scene()
        if scene is None:
            return False
        myr = _scene_rect_of_item(self)
        for it in scene.items():
            if isinstance(it, RoomItem) and it is not self:
                if _rects_overlap_strict(myr, _scene_rect_of_item(it)):
                    return True
        return False

    def _create_handles(self):
        if self._handles:
            return
        if isinstance(self, RoomItem):
            r = self.rect()
            self._handles = [
                ResizeHandle(self, r.left(),  r.top(),    "tl"),
                ResizeHandle(self, r.right(), r.top(),    "tr"),
                ResizeHandle(self, r.left(),  r.bottom(), "bl"),
                ResizeHandle(self, r.right(), r.bottom(), "br"),
            ]

    def _remove_handles(self):
        for h in self._handles:
            h.setParentItem(None)
            scene = self.scene()
            if scene:
                scene.removeItem(h)
        self._handles.clear()

    def _layout_handles(self):
        if not self._handles:
            return
        r = self.rect()
        for h in self._handles:
            if   h.corner == "tl": h.update_pos(r.left(),  r.top())
            elif h.corner == "tr": h.update_pos(r.right(), r.top())
            elif h.corner == "bl": h.update_pos(r.left(),  r.bottom())
            elif h.corner == "br": h.update_pos(r.right(), r.bottom())

    def setRect(self, *args, **kwargs):
        super().setRect(*args, **kwargs)
        self._layout_handles()

    def set_size_px(self, width_px: float, height_px: float) -> bool:
        width_px = max(1.0, float(width_px))
        height_px = max(1.0, float(height_px))
        scene = self.scene()
        if scene is None:
            return False

        parent = self.parentItem()
        if parent and isinstance(parent, RoomItem):
            allowed = parent.rect()
            max_w = allowed.width()  - self.pos().x()
            max_h = allowed.height() - self.pos().y()
            width_px = min(width_px, max_w)
            height_px = min(height_px, max_h)
            super().setRect(QRectF(0, 0, width_px, height_px))
            self.update_tooltip()
            return True

        new_rect_scene = QRectF(self.pos(), QSizeF(width_px, height_px))
        allowed_scene = scene.sceneRect()

        if new_rect_scene.right() > allowed_scene.right() or new_rect_scene.bottom() > allowed_scene.bottom():
            width_px = min(width_px, allowed_scene.right() - self.pos().x())
            height_px = min(height_px, allowed_scene.bottom() - self.pos().y())

        if isinstance(self, RoomItem):
            old = self.rect()
            super().setRect(QRectF(0, 0, width_px, height_px))
            if (self.pos().x() < allowed_scene.left() or
                self.pos().y() < allowed_scene.top() or
                self._any_room_overlap()):
                super().setRect(old)
                return False

        super().setRect(QRectF(0, 0, width_px, height_px))
        self.update_tooltip()
        return True

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        from .scene import PlanScene  # локальный импорт, чтобы избежать циклов
        if change == QGraphicsItem.ItemSelectedChange:
            if bool(value):
                self.setBrush(self.brush_selected)
                self.setPen(self.pen_selected)
                if isinstance(self, RoomItem):
                    self._create_handles()
                scene = self.scene()
                if scene: scene.show_size_overlay(self)
            else:
                self.setBrush(self.brush_normal)
                self.setPen(self.pen_normal)
                self._remove_handles()
                scene = self.scene()
                if scene: scene.hide_size_overlay(self)

        elif change == QGraphicsItem.ItemPositionChange:
            new_pos: QPointF = value
            scene = self.scene()
            if scene is not None:
                rect = self.rect()
                parent = self.parentItem()
                if parent and isinstance(parent, RoomItem):
                    allowed = parent.rect()
                    x = min(max(new_pos.x(), allowed.left()),  allowed.right()  - rect.width())
                    y = min(max(new_pos.y(), allowed.top()),   allowed.bottom() - rect.height())
                    if scene.snap_to_grid:
                        x = snap(x, PX_GRID)
                        y = snap(y, PX_GRID)
                    return QPointF(x, y)
                else:
                    allowed = scene.sceneRect()
                    x = min(max(new_pos.x(), allowed.left()),  allowed.right()  - rect.width())
                    y = min(max(new_pos.y(), allowed.top()),   allowed.bottom() - rect.height())
                    if scene.snap_to_grid:
                        x = snap(x, PX_GRID)
                        y = snap(y, PX_GRID)
                    return QPointF(x, y)

        elif change == QGraphicsItem.ItemPositionHasChanged:
            if isinstance(self, RoomItem):
                scene = self.scene()
                if scene and self._any_room_overlap():
                    scene.nudge_room_to_touch(self)

        return super().itemChange(change, value)

class RoomItem(PlanRectItem):
    def __init__(self, props: ItemProps, *args, **kwargs):
        super().__init__(props, *args, **kwargs)
        self.props.kind = "room"

class DeviceItem(PlanRectItem):
    def __init__(self, props: ItemProps, *args, **kwargs):
        super().__init__(props, *args, **kwargs)
        self.props.kind = "device"
class FurnitureItem(PlanRectItem):
    def __init__(self, props: ItemProps, *args, **kwargs):
        super().__init__(props, *args, **kwargs)
        self.props.kind = "furniture"