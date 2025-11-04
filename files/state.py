from __future__ import annotations
from typing import Dict, List
from PySide6.QtCore import QRectF, QPointF
from .models import ItemProps
from .items import RoomItem, DeviceItem, FurnitureItem


class SceneState:
    def __init__(self, scene_rect: QRectF):
        self.scene_rect = scene_rect

    def serialize(self, scene) -> Dict:
        rooms: List[Dict] = []
        devices: List[Dict] = []
        furniture: List[Dict] = []
        room_ids: Dict[RoomItem, int] = {}
        rid = 0
        for it in scene.items():
            if isinstance(it, RoomItem):
                room_ids[it] = rid
                rooms.append({
                    "id": rid,
                    "name": it.props.name,
                    "x": it.pos().x(), "y": it.pos().y(),
                    "w": it.rect().width(), "h": it.rect().height(),
                    "desc": it.props.description
                })
                rid += 1
        for it in scene.items():
            if isinstance(it, DeviceItem):
                parent_room = it.parentItem() if isinstance(it.parentItem(), RoomItem) else None
                devices.append({
                    "name": it.props.name,
                    "room_id": room_ids.get(parent_room, None),
                    "x": it.pos().x(), "y": it.pos().y(),
                    "w": it.rect().width(), "h": it.rect().height(),
                    "rot": it.rotation(),
                    "desc": it.props.description
                })
        for it in scene.items():
            if isinstance(it, FurnitureItem):
                parent_room = it.parentItem() if isinstance(it.parentItem(), RoomItem) else None
                furniture.append({
                    "name": it.props.name,
                    "room_id": room_ids.get(parent_room, None),
                    "x": it.pos().x(), "y": it.pos().y(),
                    "w": it.rect().width(), "h": it.rect().height(),
                    "rot": it.rotation(),
                    "desc": it.props.description
                })
        return {"canvas": {"w": self.scene_rect.width(), "h": self.scene_rect.height(), "grid": 10.0},
                "rooms": rooms, "devices": devices, "furniture": furniture}

    def deserialize(self, scene, data: Dict):
        scene.clear_all_items()
        by_id: Dict[int, RoomItem] = {}
        for r in data.get("rooms", []):
            item = RoomItem(ItemProps(r.get("name","Комната"), r["w"], r["h"], r.get("desc",""), "room"),
                            QRectF(0,0,r["w"], r["h"]))
            item.setPos(QPointF(r["x"], r["y"]))
            scene.addItem(item)
            by_id[int(r["id"])] = item
        for d in data.get("devices", []):
            item = DeviceItem(ItemProps(d.get("name","Устройство"), d["w"], d["h"], d.get("desc",""), "device"),
                              QRectF(0,0,d["w"], d["h"]))
            room = by_id.get(d.get("room_id"))
            if room: item.setParentItem(room)
            item.setPos(QPointF(d["x"], d["y"]))
            item.setRotation(float(d.get("rot", 0)))
            scene.addItem(item)
        for f in data.get("furniture", []):
            item = FurnitureItem(ItemProps(f.get("name","Мебель"), f["w"], f["h"], f.get("desc",""), "furniture"),
                                QRectF(0,0,f["w"], f["h"]))
            room = by_id.get(f.get("room_id"))
            if room: item.setParentItem(room)
            item.setPos(QPointF(f["x"], f["y"]))
            item.setRotation(float(f.get("rot", 0)))
            scene.addItem(item)

