from __future__ import annotations
from typing import Optional, List, Tuple
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from .models import ItemProps
from .utils import (ROOM_COLOR, ROOM_BORDER, DEV_COLOR, DEV_BORDER, EPS, PX_GRID,
                    snap, _scene_rect_of_item, _rects_overlap_strict)
# Важно: PlanScene используется только через методы scene(), импорт внутри методов не нужен

GHOST_PEN   = QPen(QColor("#94A3B8"), 1, Qt.DashLine)
GHOST_BRUSH = QBrush(QColor(148, 163, 184, 80))
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
        self._is_preview = False     # признак «призрака»
        self._view_mode  = "active"  # active | dim | dim_strong_border | ghost

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

        # «призрак» действует только на превью (drag-preview)
        if mode == "ghost" and getattr(self, "_is_preview", False):
            try:
                self.setOpacity(0.5)
                self.setPen(GHOST_PEN)
                self.setBrush(GHOST_BRUSH)
            except Exception:
                pass
            self.update()
            return

        # обычные режимы — реальный элемент всегда видим
        try:
            self.setOpacity(1.0)
            pen = self.pen()
            pen.setStyle(Qt.SolidLine)
            self.setPen(pen)
        except Exception:
            pass

        # лёгкое «тускление» по слоям (не через полную прозрачность!)
        if mode == "dim":
            try:
                self.setOpacity(0.55)
            except Exception:
                pass
        elif mode == "dim_strong_border":
            try:
                self.setOpacity(0.65)
                pen = self.pen()
                pen.setColor(QColor("#64748B"))
                self.setPen(pen)
            except Exception:
                pass



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
        self.setPen(QPen(QColor("#2563EB"), 2))
        self.setBrush(QBrush(QColor(37, 99, 235, 70)))
        self.setOpacity(1.0)

    
    # Внутрь RoomItem:
    def _notify_openings(self):
        sc = self.scene()
        if not sc:
            return
        # Импорт не сверху, чтобы не ловить циклических импортов
        from .items import OpeningItem
        for it in sc.items():
            if isinstance(it, OpeningItem) and it.anchor_room is self:
                it._reposition_on_wall()

    def itemChange(self, change, value):
        # вызываем базовую логику
        newv = super().itemChange(change, value)
        from PySide6.QtWidgets import QGraphicsItem
        # после факта изменения позиции — обновляем проёмы
        if change in (QGraphicsItem.ItemPositionHasChanged, QGraphicsItem.ItemTransformHasChanged):
            self._notify_openings()
        return newv

    # И если у тебя есть метод, меняющий размер (в RoomItem/PlanRectItem)
    def set_size_px(self, w: float, h: float) -> bool:
        ok = super().set_size_px(w, h)
        if ok:
            self._notify_openings()
        return ok


class DeviceItem(PlanRectItem):
    def __init__(self, props: ItemProps, *args, **kwargs):
        super().__init__(props, *args, **kwargs)
        self.props.kind = "device"
        self.setPen(QPen(QColor("#334155"), 1))
        self.setBrush(QBrush(QColor(226, 232, 240)))
        self.setOpacity(1.0)

class FurnitureItem(PlanRectItem):
    def __init__(self, props: ItemProps, *args, **kwargs):
        super().__init__(props, *args, **kwargs)
        self.props.kind = "furniture"
        self.setPen(QPen(QColor("#334155"), 1))
        self.setBrush(QBrush(QColor(226, 232, 240)))
        self.setOpacity(1.0)

class OpeningItem(PlanRectItem):
    """
    Проём (окно/дверь), якорится на стену комнаты и может двигаться
    только вдоль своей стены. Не является дочерним элементом комнаты.
    """
    MAG_DIST = 24.0
    EDGE_SWITCH_EPS = 8.0
    def __init__(self, props: ItemProps, *args, subtype: str = "window", **kwargs):
        super().__init__(props, *args, **kwargs)
        self.props.kind = "opening"
        # subtype: "window" | "door"
        self.subtype = subtype
        # якорь
        self.anchor_room: Optional[RoomItem] = None
        self.edge: Optional[str] = None         # 'T'|'R'|'B'|'L'
        self.offset: float = 0.0                # вдоль стены
        self.length: float = self.rect().width()
        self.thickness: float = self.rect().height()
        self.side: str = "outside" if subtype == "window" else "inside"
        # в __init__ OpeningItem:
        self.setPen(QPen(QColor("#0EA5E9" if self.subtype=="window" else "#2563EB"), 2))
        self.setBrush(QBrush(QColor(14,165,233,40) if self.subtype=="window" else QColor(37,99,235,40)))
        self.setOpacity(1.0)


        # визуал
        if self.subtype == "window":
            self.brush_normal = QBrush(QColor(80, 180, 255, 150))
            self.pen_normal = QPen(QColor(30, 120, 200), 1)
        else:
            self.brush_normal = QBrush(QColor(230, 170, 60, 160))
            self.pen_normal = QPen(QColor(180, 120, 30), 1)
        self.setBrush(self.brush_normal)
        self.setPen(self.pen_normal)
        self._rounded = 2.0

        # проём не масштабируем ручками через угловые хэндлы (пока)
        self._remove_handles()

        # движется сам, но всегда «зажат» стеной
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    # --- API якоря ---
    def set_anchor(self, room: RoomItem, edge: str, offset: float,
                   length: float, thickness: float, side: str):
        self.anchor_room = room
        self.edge = edge
        self.offset = float(offset)
        self.length = float(length)
        self.thickness = float(thickness)
        self.side = side
        # геометрию прямоугольника поворачиваем по ориентации стены:
        if edge in ("T", "B"):
            super().setRect(QRectF(0, 0, self.length, self.thickness))
        else:
            super().setRect(QRectF(0, 0, self.thickness, self.length))
        self._reposition_on_wall()

    def _reposition_on_wall(self):
        if not (self.anchor_room and self.edge):
            return
        r = self.anchor_room.rect()
        # локальные координаты «нижнего левого» угла прямоугольника
        if self.edge == "T":
            x = max(0.0, min(self.offset, r.width() - self.length))
            y = -self.thickness if self.side == "outside" else 0.0
            local = QPointF(x, y)
        elif self.edge == "B":
            x = max(0.0, min(self.offset, r.width() - self.length))
            y = r.height() if self.side == "outside" else (r.height() - self.thickness)
            local = QPointF(x, y)
        elif self.edge == "L":
            y = max(0.0, min(self.offset, r.height() - self.length))
            x = -self.thickness if self.side == "outside" else 0.0
            local = QPointF(x, y)
        else:  # "R"
            y = max(0.0, min(self.offset, r.height() - self.length))
            x = r.width() if self.side == "outside" else (r.width() - self.thickness)
            local = QPointF(x, y)
        scene_pt = self.anchor_room.mapToScene(local)
        self.setPos(scene_pt)

    # запрещаем менять размер обычными путями
    def set_size_px(self, width_px: float, height_px: float) -> bool:
        # размеры задаём через set_anchor (length/thickness)
        return False

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.anchor_room and self.edge:
            new_scene_pos: QPointF = value if isinstance(value, QPointF) else QPointF(value)
            room = self.anchor_room
            rr = room.rect()
            local = room.mapFromScene(new_scene_pos)

            # текущие параметры
            L = self.length
            T = self.thickness
            eps = self.EDGE_SWITCH_EPS

            # Ветвь для горизонтальной стены (edge T/B):
            if self.edge in ("T", "B"):
                x = local.x()

                # ЛЕВЫЙ перекат — как было:
                if x < -eps:
                    self._set_edge_and_rect("L")
                    y_local = max(0.0, min(local.y(), rr.height() - L))
                    x_local = -T if self.side == "outside" else 0.0
                    self.offset = y_local
                    return room.mapToScene(QPointF(x_local, snap(y_local, PX_GRID)))

                # ПРАВЫЙ перекат — ИСПРАВЛЕНО:
                right_trigger = rr.width() - L + eps   # ← учитываем длину проёма!
                if x > right_trigger:
                    self._set_edge_and_rect("R")
                    y_local = max(0.0, min(local.y(), rr.height() - L))
                    x_local = rr.width() if self.side == "outside" else (rr.width() - T)
                    self.offset = y_local
                    return room.mapToScene(QPointF(x_local, snap(y_local, PX_GRID)))

                # Без переката — ходим вдоль X в пределах [0, W-L]
                x = max(0.0, min(x, rr.width() - L))
                x = snap(x, PX_GRID)
                self.offset = x
                y = (-T if self.side == "outside" else 0.0) if self.edge == "T" \
                    else (rr.height() if self.side == "outside" else rr.height() - T)
                return room.mapToScene(QPointF(x, y))

            # Ветвь для вертикальной стены (edge L/R):
            else:
                y = local.y()

                # ВЕРХНИЙ перекат — как было:
                if y < -eps:
                    self._set_edge_and_rect("T")
                    x_local = max(0.0, min(local.x(), rr.width() - L))
                    y_local = -T if self.side == "outside" else 0.0
                    self.offset = x_local
                    return room.mapToScene(QPointF(snap(x_local, PX_GRID), y_local))

                # НИЖНИЙ перекат — ИСПРАВЛЕНО:
                bottom_trigger = rr.height() - L + eps  # ← учитываем длину проёма!
                if y > bottom_trigger:
                    self._set_edge_and_rect("B")
                    x_local = max(0.0, min(local.x(), rr.width() - L))
                    y_local = rr.height() if self.side == "outside" else (rr.height() - T)
                    self.offset = x_local
                    return room.mapToScene(QPointF(snap(x_local, PX_GRID), y_local))

                # Без переката — ходим вдоль Y в пределах [0, H-L]
                y = max(0.0, min(y, rr.height() - L))
                y = snap(y, PX_GRID)
                self.offset = y
                x = (-T if self.side == "outside" else 0.0) if self.edge == "L" \
                    else (rr.width() if self.side == "outside" else rr.width() - T)
                return room.mapToScene(QPointF(x, y))

        return super().itemChange(change, value)

    def _wall_len(self) -> float:
        rr = self.anchor_room.rect()
        return rr.width() if self.edge in ("T","B") else rr.height()

    def _max_offset(self) -> float:
        return max(0.0, self._wall_len() - self.length)

    def _set_edge_and_rect(self, new_edge: str):
        """Поменять сторону стены и форму прямоугольника (гориз/верт)."""
        self.edge = new_edge
        if new_edge in ("T","B"):
            super().setRect(QRectF(0, 0, self.length, self.thickness))
        else:
            super().setRect(QRectF(0, 0, self.thickness, self.length))

    def paint(self, painter, option, widget=None):
        r = self.rect()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # общий бордер/фон
        if self.subtype == "door":
            # дверь — «квадратная»: заметнее, толще обводка
            pen = QPen(QColor("#2563EB"), 2)
            brush = QBrush(QColor(37, 99, 235, 30))  # лёгкая синяя заливка
        else:
            # окно — тонкий «брусок», полупрозрачный
            pen = QPen(QColor("#0EA5E9"), 1.5)
            brush = QBrush(QColor(14, 165, 233, 30))

        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawRoundedRect(r, 2, 2)


