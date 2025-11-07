from __future__ import annotations
from typing import Optional, Dict
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QMessageBox, QGraphicsItem
from .models import ItemProps
from .items import RoomItem, DeviceItem, FurnitureItem, OpeningItem
from .utils import SCENE_W, SCENE_H, PX_GRID, snap, _scene_rect_of_item, _rects_overlap_strict

class ItemFactory:
    def __init__(self, scene):
        self.scene = scene

    def _create_room(self, meta: Dict, pos: QPointF, w: float, h: float) -> Optional[RoomItem]:
        if pos.x() + w > SCENE_W or pos.y() + h > SCENE_H:
            QMessageBox.warning(None, "Вне холста", "Комната не может выходить за границы холста.")
            return None
        item = RoomItem(ItemProps(meta.get("name", "Комната"), w, h, meta.get("desc", ""), "room"),
                        QRectF(0, 0, w, h))
        item.setPos(pos)
        self.scene.addItem(item)
        myr = _scene_rect_of_item(item)
        need_touch = any(isinstance(it, RoomItem) and it is not item and
                         _rects_overlap_strict(myr, _scene_rect_of_item(it)) for it in self.scene.items())
        if need_touch:
            self.scene.nudge_room_to_touch(item)
            myr = _scene_rect_of_item(item)
            still = any(isinstance(it, RoomItem) and it is not item and
                        _rects_overlap_strict(myr, _scene_rect_of_item(it)) for it in self.scene.items())
            if still:
                self.scene.removeItem(item)
                QMessageBox.warning(None, "Пересечение", "Не удалось разместить без перекрытий.")
                return None
        return item
    
    def create_from_meta(self, meta: Dict, scene_pos: QPointF):
        kind = meta.get("kind", "device")
        w = float(meta.get("w", 100)); h = float(meta.get("h", 50))
        pos = QPointF(scene_pos)
        if self.scene.snap_to_grid:
            pos = QPointF(snap(pos.x(), PX_GRID), snap(pos.y(), PX_GRID))
        if kind == "room":
            return self._create_room(meta, pos, w, h)
        elif kind == "opening":
            return self._create_opening(meta, pos, w, h)
        elif kind == "furniture":
            return self._create_placeable(meta, pos, w, h, FurnitureItem)
        else:
            return self._create_placeable(meta, pos, w, h, DeviceItem)

    def _create_placeable(self, meta: Dict, pos: QPointF, w: float, h: float, cls):
        room = self.scene.room_at(pos)
        if not room:
            QMessageBox.information(None, "Только в комнате",
                                    "Сначала добавьте комнату и перетащите объект внутрь неё.")
            return None
        item = cls(ItemProps(meta.get("name","Объект"), w, h, meta.get("desc",""),
                            "furniture" if cls is FurnitureItem else "device"),
                QRectF(0,0,w,h))
        local = room.mapFromScene(pos)
        lx = min(max(local.x(), 0), room.rect().width()  - w)
        ly = min(max(local.y(), 0), room.rect().height() - h)
        item.setParentItem(room)
        item.setPos(QPointF(lx, ly))
        self.scene.addItem(item)
        return item


    def _create_placeable(self, meta: Dict, pos: QPointF, w: float, h: float, cls) -> Optional[QGraphicsItem]:
        room = self.scene.room_at(pos)
        if not room:
            QMessageBox.information(None, "Только в комнате",
                                    "Сначала добавьте комнату и перетащите объект внутрь неё.")
            return None
        item = cls(ItemProps(meta.get("name", "Объект"), w, h, meta.get("desc", ""),
                            "furniture" if cls is FurnitureItem else "device"),
                QRectF(0, 0, w, h))
        local = room.mapFromScene(pos)
        lx = min(max(local.x(), 0), room.rect().width()  - w)
        ly = min(max(local.y(), 0), room.rect().height() - h)
        item.setParentItem(room)
        item.setPos(QPointF(lx, ly))
        self.scene.addItem(item)
        return item
    
    def _create_opening(self, meta: Dict, pos: QPointF, w: float, h: float):
        subtype = meta.get("subtype", "window")  # "window" | "door"
        length = float(meta.get("length", w))
        thickness = float(meta.get("thickness", max(8.0, min(20.0, h))))

        snap = self.scene._magnet_for_opening(pos, subtype, length, thickness)
        if not snap:
            return None  # на сцене нет комнат — просто не создаём

        room, edge, offset, length, thickness, side = snap

        if edge in ("T", "B"):
            rect = QRectF(0, 0, length, thickness)
        else:
            rect = QRectF(0, 0, thickness, length)

        item = OpeningItem(ItemProps(meta.get("name", "Проём"),
                                    rect.width(), rect.height(),
                                    meta.get("desc", ""), "opening"),
                        rect, subtype=subtype)
        self.scene.addItem(item)
        item.set_anchor(room, edge, offset, length, thickness, side)
        return item

