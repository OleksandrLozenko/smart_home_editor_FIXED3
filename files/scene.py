from __future__ import annotations
import json, math
from typing import Optional, Dict, Callable

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsProxyWidget, QGraphicsItem,
    QWidget, QHBoxLayout, QDoubleSpinBox, QLabel, QApplication
)

from .models import Mode, Layer, ItemProps
from .utils import (BG_COLOR, GRID_STEP, MAJOR_EVERY, GRID_MAJOR, GRID_MINOR,
                    SCENE_BORDER, SCENE_BORDER_W, snap, PX_GRID, _scene_rect_of_item, _rects_overlap_strict,
                    SCENE_W, SCENE_H, EPS, DEV_BORDER)
from .state import SceneState
from .factory import ItemFactory
from .items import RoomItem, DeviceItem, PlanRectItem, FurnitureItem, OpeningItem
from .hud import LayersHUD

# ---- SizeOverlay (как в монолитной версии) ----
class SizeOverlay(QWidget):
    sizeChanged = Signal(float, float)
    def __init__(self, w: float, h: float, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        self.w = QDoubleSpinBox(); self.h = QDoubleSpinBox()
        for s in (self.w, self.h):
            s.setRange(1, 99999); s.setDecimals(0); s.setSingleStep(5); s.setSuffix(" px"); s.setFixedWidth(110)
        self.w.setValue(w); self.h.setValue(h)
        lay.addWidget(QLabel("W:")); lay.addWidget(self.w)
        lay.addWidget(QLabel("H:")); lay.addWidget(self.h)
        self.w.valueChanged.connect(self._emit); self.h.valueChanged.connect(self._emit)
    def _emit(self, *_): self.sizeChanged.emit(self.w.value(), self.h.value())

class PlanScene(QGraphicsScene):
    def __init__(self, status_cb: Optional[Callable[[str], None]] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = Mode.EDIT
        self.snap_to_grid = True
        self.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.setSceneRect(0, 0, SCENE_W, SCENE_H)
        self._size_proxy = None
        self._overlay_owner = None
        self._pre_snapshot: Optional[str] = None
        self._status_cb = status_cb
        self.state = SceneState(self.sceneRect())
        self.factory = ItemFactory(self)
        self.active_layer = Layer.ROOMS
        self._drag_preview: Optional[PlanRectItem] = None
        self._drag_meta: Optional[Dict] = None
        self.selectionChanged.connect(self._on_selection_changed)


    def import_from_data(self, data: Dict):
        """Добавляет содержимое JSON в текущую сцену (merge, без очистки)."""
        # 1) создаём комнаты и запоминаем индекс->объект
        idx_to_room = {}
        rooms = data.get("rooms", [])
        for idx, r in enumerate(rooms):
            w = float(r.get("w", 200)); h = float(r.get("h", 150))
            item = RoomItem(ItemProps(r.get("name","Комната"), w, h, r.get("desc",""), "room"), QRectF(0,0,w,h))
            self.addItem(item)
            item.setPos(QPointF(float(r.get("x", 0)), float(r.get("y", 0))))
            rot = float(r.get("rot", 0)); 
            try: item.setRotation(rot)
            except: pass
            idx_to_room[idx] = item

        # 2) устройства
        for d in data.get("devices", []):
            w = float(d.get("w", 40)); h = float(d.get("h", 40))
            dev = DeviceItem(ItemProps(d.get("name","Устройство"), w, h, d.get("desc",""), "device"), QRectF(0,0,w,h))
            room = idx_to_room.get(d.get("room_id"))
            if room:
                dev.setParentItem(room)
                dev.setPos(QPointF(float(d.get("x", 0)), float(d.get("y", 0))))
            else:
                # на всякий случай — в сцену по абсолютным координатам
                dev.setPos(QPointF(float(d.get("x", 0)), float(d.get("y", 0))))
            try: dev.setRotation(float(d.get("rot", 0)))
            except: pass
            self.addItem(dev)

        # 3) мебель
        for f in data.get("furniture", []):
            w = float(f.get("w", 60)); h = float(f.get("h", 40))
            fur = FurnitureItem(ItemProps(f.get("name","Мебель"), w, h, f.get("desc",""), "furniture"), QRectF(0,0,w,h))
            room = idx_to_room.get(f.get("room_id"))
            if room:
                fur.setParentItem(room)
                fur.setPos(QPointF(float(f.get("x", 0)), float(f.get("y", 0))))
            else:
                fur.setPos(QPointF(float(f.get("x", 0)), float(f.get("y", 0))))
            try: fur.setRotation(float(f.get("rot", 0)))
            except: pass
            self.addItem(fur)

        self.apply_layer_state()

    def _on_selection_changed(self):
    # no-op: MainWindow сам слушает scene.selectionChanged и обновляет панель свойств
        pass
    
    def _magnet_for_opening(self, scene_pos: QPointF, subtype: str,
                            length: float, thickness: float):
        """
        Возвращает (room, edge, offset, length, thickness, side) для ближайшей комнаты/стены.
        Если на сцене нет ни одной комнаты — вернёт None.
        """
        side = "outside" if subtype == "window" else "inside"

        # 1) ищем ближайшую комнату (по евклидову расстоянию до bbox)
        best_room = None
        best_dist = 1e18
        for it in self.items():
            if not isinstance(it, RoomItem):
                continue
            r = _scene_rect_of_item(it)
            dx = max(r.left() - scene_pos.x(), 0, scene_pos.x() - r.right())
            dy = max(r.top()  - scene_pos.y(), 0, scene_pos.y() - r.bottom())
            dist = (dx*dx + dy*dy) ** 0.5
            if dist < best_dist:
                best_room, best_dist = it, dist

        if not best_room:
            return None

        # 2) ближайшая сторона этой комнаты
        local = best_room.mapFromScene(scene_pos)
        rr = best_room.rect()
        dL = abs(local.x() - 0.0)
        dR = abs(local.x() - rr.width())
        dT = abs(local.y() - 0.0)
        dB = abs(local.y() - rr.height())
        edge, _ = min((("L", dL), ("R", dR), ("T", dT), ("B", dB)), key=lambda x: x[1])

        # 3) offset вдоль стены (центрируем по курсору) + clamp + snap
        if edge in ("T", "B"):
            offset = local.x() - length / 2.0
            offset = max(0.0, min(offset, rr.width() - length))
        else:
            offset = local.y() - length / 2.0
            offset = max(0.0, min(offset, rr.height() - length))
        offset = snap(offset, PX_GRID)

        return (best_room, edge, float(offset), float(length), float(thickness), side)


    def apply_layer_state(self):
        """Разрешаем двигать/выделять ТОЛЬКО объекты активного слоя. Остальные — залочены и не выделяются."""
        self.clearSelection()

        # helper: разрешены ли item в активном слое
        def _is_allowed(it) -> bool:
            if self.active_layer == Layer.ROOMS:
                return isinstance(it, RoomItem)
            if self.active_layer == Layer.DEVICES:
                return isinstance(it, DeviceItem)
            if self.active_layer == Layer.FURNITURE:
                return isinstance(it, FurnitureItem)
            if hasattr(Layer, "OPENINGS") and self.active_layer == Layer.OPENINGS:
                from .items import OpeningItem
                return isinstance(it, OpeningItem)
            return False

        for it in self.items():
            if not isinstance(it, PlanRectItem):
                continue

            allowed = _is_allowed(it)

            # Жёсткие флаги
            it.setFlag(QGraphicsItem.ItemIsMovable,   bool(allowed))
            it.setFlag(QGraphicsItem.ItemIsSelectable, bool(allowed))

            # Визуальные режимы (чтобы было видно, что неактивные тусклые, но полностью залочены)
            if hasattr(it, "set_view_mode"):
                it.set_view_mode("active_bright" if allowed else "dim")

        # если был размерный оверлей не на своём слое — скрыть
        if self._overlay_owner and not _is_allowed(self._overlay_owner):
            self.hide_size_overlay(self._overlay_owner)

    def set_active_layer(self, layer: str):
        if layer == self.active_layer:
            return
        self.active_layer = layer
        self.clearSelection()
        self.apply_layer_state()

        # синхронизация HUD
        for v in self.views():
            hud = getattr(v, "hud", None)
            if hud: hud.set_checked(layer)

        mw = QApplication.activeWindow()
        if hasattr(mw, "_update_status"):
            mw._update_status()


    def _make_preview(self, meta: Dict):
        self._clear_preview()
        kind = meta.get("kind", "device")

        if kind == "room":
            w = float(meta.get("w", 100)); h = float(meta.get("h", 50))
            item = RoomItem(ItemProps(meta.get("name","Комната"), w, h, meta.get("desc",""), "room"), QRectF(0,0,w,h))
        elif kind == "furniture":
            w = float(meta.get("w", 100)); h = float(meta.get("h", 50))
            item = FurnitureItem(ItemProps(meta.get("name","Мебель"), w, h, meta.get("desc",""), "furniture"), QRectF(0,0,w,h))
        elif kind == "opening":
            L = float(meta.get("length", 70)); T = float(meta.get("thickness", 12))
            item = OpeningItem(meta.get("subtype","window"), length=L, thickness=T)
        else:
            w = float(meta.get("w", 100)); h = float(meta.get("h", 50))
            item = DeviceItem(ItemProps(meta.get("name","Устройство"), w, h, meta.get("desc",""), "device"), QRectF(0,0,w,h))

        self.addItem(item)
        item._is_preview = True
        if hasattr(item, "set_view_mode"):
            item.set_view_mode("ghost")
        else:
            item.setOpacity(0.5)

        item.setZValue(10_000)
        item.setFlag(QGraphicsItem.ItemIsMovable, False)
        item.setFlag(QGraphicsItem.ItemIsSelectable, False)

        self._drag_preview = item
        self._drag_meta = meta




    def _clear_preview(self):
        if self._drag_preview:
            self.removeItem(self._drag_preview)
            self._drag_preview = None
            self._drag_meta = None

    def _update_preview_pos(self, scene_pos: QPointF):
        if not (self._drag_preview and self._drag_meta): 
            return

        kind = self._drag_meta.get("kind","device")
        pos = QPointF(scene_pos)
        if self.snap_to_grid:
            pos = QPointF(snap(pos.x(), PX_GRID), snap(pos.y(), PX_GRID))

        if kind == "room":
            w = float(self._drag_meta.get("w",100)); h = float(self._drag_meta.get("h",50))
            x = min(max(pos.x(), self.sceneRect().left()),  self.sceneRect().right() - w)
            y = min(max(pos.y(), self.sceneRect().top()),   self.sceneRect().bottom() - h)
            self._drag_preview.setParentItem(None)
            self._drag_preview.setPos(QPointF(x, y))
            # (опционально) ваш nudge + подсветка пересечений — как было
            return

        # device/furniture/opening — внутрь ближайшей комнаты (как потом при drop)
        room = self.room_at(scene_pos)
        if not room:
            self._drag_preview.setVisible(False)
            return

        self._drag_preview.setVisible(True)
        self._drag_preview.setParentItem(room)

        # размер для позиционирования
        if kind == "opening":
            w = float(self._drag_meta.get("length", 70))
            h = float(self._drag_meta.get("thickness", 12))
        else:
            w = float(self._drag_meta.get("w", 40))
            h = float(self._drag_meta.get("h", 40))

        local = room.mapFromScene(pos)
        lx = min(max(local.x(), 0), room.rect().width()  - w)
        ly = min(max(local.y(), 0), room.rect().height() - h)
        if self.snap_to_grid:
            lx = snap(lx, PX_GRID); ly = snap(ly, PX_GRID)

        self._drag_preview.setPos(QPointF(lx, ly))

    def _owner_in_active_layer(self, owner: "PlanRectItem") -> bool:
        return (
            (self.active_layer == Layer.ROOMS     and isinstance(owner, RoomItem)) or
            (self.active_layer == Layer.DEVICES   and isinstance(owner, DeviceItem)) or
            (self.active_layer == Layer.FURNITURE and isinstance(owner, FurnitureItem)) or
            (self.active_layer == Layer.OPENINGS  and isinstance(owner, OpeningItem))
        )


    def nudge_room_to_touch(self, room: "RoomItem"):
        for _ in range(12):
            moved = False
            a = _scene_rect_of_item(room).intersected(self.sceneRect())
            for it in self.items():
                if not isinstance(it, RoomItem) or it is room: continue
                b = _scene_rect_of_item(it)
                overlap_x = min(a.right(), b.right()) - max(a.left(), b.left())
                overlap_y = min(a.bottom(), b.bottom()) - max(a.top(), b.top())
                if overlap_x <= EPS or overlap_y <= EPS: continue
                if overlap_x <= overlap_y:
                    dx = (b.left() - a.right()) if a.center().x() < b.center().x() else (b.right() - a.left()); dy = 0.0
                else:
                    dx = 0.0; dy = (b.top() - a.bottom()) if a.center().y() < b.center().y() else (b.bottom() - a.top())
                new_x = min(max(room.pos().x() + dx, self.sceneRect().left()), self.sceneRect().right() - room.rect().width())
                new_y = min(max(room.pos().y() + dy, self.sceneRect().top()),  self.sceneRect().bottom() - room.rect().height())
                if self.snap_to_grid:
                    new_x = snap(new_x, PX_GRID); new_y = snap(new_y, PX_GRID)
                if abs(new_x - room.pos().x()) > EPS or abs(new_y - room.pos().y()) > EPS:
                    room.setPos(QPointF(new_x, new_y)); moved = True; a = _scene_rect_of_item(room)
            if not moved: break

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, BG_COLOR)
        step = GRID_STEP
        left = math.floor(rect.left() / step) * step
        top  = math.floor(rect.top()  / step) * step
        x = left; i = int(x // step)
        while x < rect.right():
            is_major = (i % MAJOR_EVERY == 0)
            painter.setPen(QPen(GRID_MAJOR if is_major else GRID_MINOR, 1.5 if is_major else 1, Qt.SolidLine, Qt.SquareCap))
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += step; i += 1
        y = top; j = int(y // step)
        while y < rect.bottom():
            is_major = (j % MAJOR_EVERY == 0)
            painter.setPen(QPen(GRID_MAJOR if is_major else GRID_MINOR, 1.5 if is_major else 1, Qt.SolidLine, Qt.SquareCap))
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += step; j += 1
        painter.setPen(QPen(SCENE_BORDER, SCENE_BORDER_W)); painter.setBrush(Qt.NoBrush); painter.drawRect(self.sceneRect())

    # ---- DnD ----
    def dragEnterEvent(self, event):
        if self.mode == Mode.EDIT and event.mimeData().hasFormat("application/x-smart"):
            try:
                meta = json.loads(bytes(event.mimeData().data("application/x-smart").data()).decode("utf-8"))
            except Exception:
                meta = {"name":"Объект","w":100,"h":50,"kind":"device"}
            self._make_preview(meta); self._update_preview_pos(event.scenePos())
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self.mode == Mode.EDIT and event.mimeData().hasFormat("application/x-smart"):
            self._update_preview_pos(event.scenePos()); event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._clear_preview(); event.accept()

    def dropEvent(self, event):
        if self.mode != Mode.EDIT or not event.mimeData().hasFormat("application/x-smart"):
            event.ignore(); return
        data = event.mimeData().data("application/x-smart").data()
        try:
            meta = json.loads(bytes(data).decode("utf-8"))
        except Exception:
            meta = {"name": "Объект", "w": 100, "h": 50, "kind": "device"}

        created = self.factory.create_from_meta(meta, event.scenePos())
        self._clear_preview()                   # ← убрать «призрак» в любом случае
        if created is None:
            event.ignore(); return

        if hasattr(created, "set_view_mode"):
            created.set_view_mode("active")
        created.setOpacity(1.0)

        self._push_snapshot("drop")
        self.clearSelection()
        self.apply_layer_state()
        event.acceptProposedAction()


    def room_at(self, scene_pos: QPointF) -> Optional[RoomItem]:
        for it in self.items(scene_pos):
            if isinstance(it, RoomItem): return it
        return None

    def show_size_overlay(self, owner):
        return

    def hide_size_overlay(self, owner=None):
        return

    def _apply_size(self, item: PlanRectItem, w: float, h: float):
        self._stash_snapshot()
        if item.set_size_px(w, h):
            self._commit_snapshot("size")
        else:
            self._pre_snapshot = None
        # Хелпер: список приборов в комнате
    def devices_in_room(self, room) -> list:
        out = []
        if not isinstance(room, RoomItem):
            return out
        for ch in room.childItems():
            if isinstance(ch, DeviceItem):
                out.append(ch)
        return out

    # Хелпер: сфокусировать/прокрутить к элементу
    def ensure_visible_item(self, item):
        views = self.views()
        if not views: return
        view = views[0]
        r = item.mapRectToScene(item.rect())
        view.ensureVisible(r, 40, 40)

    # ---- snapshots ----
    def serialize(self) -> Dict:
        return self.state.serialize(self)

    def clear_all_items(self):
        for it in list(self.items()):
            if isinstance(it, (RoomItem, DeviceItem, QGraphicsProxyWidget)):
                self.removeItem(it)

    def deserialize(self, data: Dict):
        self.state.deserialize(self, data)

    def _stash_snapshot(self):
        self._pre_snapshot = json.dumps(self.serialize())

    def _commit_snapshot(self, _label="change"):
        if self._pre_snapshot is not None:
            self._push_snapshot(_label); self._pre_snapshot = None

    def _push_snapshot(self, _label="change"):
        if self._status_cb:
            self._status_cb(f"Сохранено действие: { _label }")
        from PySide6.QtWidgets import QApplication
        mw = QApplication.activeWindow()
        if hasattr(mw, "undo_manager"):
            mw.undo_manager.push(json.dumps(self.serialize()))

    # files/scene.py
    def set_editable(self, editable: bool):
        """VIEW = всё залочить; EDIT = управление полностью через apply_layer_state()."""
        if not editable:
            for it in self.items():
                if isinstance(it, PlanRectItem):
                    it.setFlag(QGraphicsItem.ItemIsMovable,   False)
                    it.setFlag(QGraphicsItem.ItemIsSelectable, False)
        else:
            self.apply_layer_state()



class PlanView(QGraphicsView):
    # правильное объявление сигнала — на уровне класса
    scaleChanged = Signal(float)  # текущее m11()

    def __init__(self, scene: PlanScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._space_down = False
        self.setBackgroundBrush(Qt.NoBrush)

        # HUD слоёв
        self.hud = LayersHUD(self)
        self.hud.reposition()
        self.hud.adjustSize()
        self.hud.show()
        self.hud.raise_()
        self.hud.reposition()

        # один раз сообщим текущий масштаб (1.0)
        self.scaleChanged.emit(self.transform().m11())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "hud") and self.hud:
            self.hud.reposition()

    def wheelEvent(self, event: QWheelEvent):
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            angle = event.angleDelta().y()
            factor = 1.15 if angle > 0 else 1.0 / 1.15
            self.scale(factor, factor)
            self.scaleChanged.emit(self.transform().m11())
            event.accept()
            return
        super().wheelEvent(event)


    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not self._space_down:
            self._space_down = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and self._space_down:
            self._space_down = False
            self.setDragMode(QGraphicsView.RubberBandDrag)
            event.accept()
            return
        super().keyReleaseEvent(event)
