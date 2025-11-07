from __future__ import annotations
import json
from typing import Dict, Tuple
from PySide6.QtCore import Qt, QRectF, QPointF, QPoint, QSize, QMimeData, QRect, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QFont, QDrag, QColor, QCursor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QApplication,QGridLayout, QScrollArea, QToolButton, QListWidget, QListWidgetItem
from .utils import (ROOM_COLOR, DEV_COLOR, PREVIEW_MAX_W, PREVIEW_MAX_H, DEVICE_PREVIEW_SIZE,
                    load_svg_icon, CATEGORY_ICON_ROOMS, CATEGORY_ICON_DEVICES, CATEGORY_ICON_FURNITURE)
from typing import Dict, Tuple, Optional

def make_icon(w: int, h: int, color: QColor, label: str = "") -> QIcon:
    pm = QPixmap(w, h); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(color); p.setPen(QPen(QColor(70,70,70), 1))
    r = QRectF(2, 2, w-4, h-4)
    p.drawRoundedRect(r, 4, 4)
    if label:
        p.setPen(Qt.black); p.setFont(QFont("", 8, QFont.Bold))
        p.drawText(r, Qt.AlignCenter, label)
    p.end()
    return QIcon(pm)

def make_category_icon(kind: str, size: int = 44) -> QIcon:
    svg_path = CATEGORY_ICON_ROOMS if kind == "rooms" else (CATEGORY_ICON_DEVICES if kind == "devices" else CATEGORY_ICON_FURNITURE)
    svg_icon = load_svg_icon(svg_path, size)
    if svg_icon is not None:
        return svg_icon
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, True)
    r = QRectF(4, 6, size - 8, size - 12)
    p.setBrush(QColor(160,160,160,200)); p.setPen(QPen(QColor(70,70,70), 1))
    p.drawRoundedRect(r, 6, 6); p.end()
    from PySide6.QtGui import QIcon
    return QIcon(pm)

class PreviewTile(QWidget):
    def __init__(self, meta: Dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.meta = meta
        self.setMouseTracking(True)
        self._press_pos: Optional[QPoint] = None
        self._drag_from_icon: bool = False      # перетаскивание только если клик по иконке
        self._icon_rect: QRect = QRect()
        self.setObjectName("PreviewTile")
        self.setProperty("class", "PreviewTile")  # для QSS селектора .PreviewTile

    def sizeHint(self) -> QSize:
        iw, ih = self._scaled_size()
        top_pad = 8
        text_pad = 22 if self.meta.get("name") else 10
        bottom_pad = 8
        # ширина = текущая ширина тайла (получаем из layout) либо базовая
        w = max(int(iw) + 16, 160)
        h = top_pad + int(ih) + text_pad + bottom_pad
        return QSize(w, h)

    def _scaled_size(self) -> Tuple[float, float]:
        # доступная ширина с учётом внутренних отступов
        avail = max(80, self.width() - 24)
        w, h = float(self.meta.get("w", 100)), float(self.meta.get("h", 100))
        kind = self.meta.get("kind")
        if kind == "room":
            # масштабируем по ширине дока, но ограничиваем разумно
            max_w = min(avail, 360.0)
            k = min(max_w / max(1.0, w), PREVIEW_MAX_H / max(1.0, h))
            return w * k, h * k
        # device/furniture — небольшой квадрат, растущий, но с потолком
        base = min( max(64.0, avail * 0.45), 120.0)
        return base, base


    def _layout_icon_rect(self) -> QRect:
        iw, ih = self._scaled_size()
        w = int(iw); h = int(ih)
        x = (self.width() - w) // 2
        y = 8
        r = QRect(x, y, w, h)
        self._icon_rect = r
        return r

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = self._layout_icon_rect()
        kind = self.meta.get("kind", "")

        if kind == "room":
            # прежний вид комнаты в палитре
            p.setBrush(ROOM_COLOR)
            p.setPen(QPen(QColor(70, 70, 70), 1))
            p.drawRoundedRect(r, 6, 6)
        else:
            # приборы/мебель — жёлтый квадрат
            p.setBrush(QColor("#FFE169"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, 6, 6)

        name = self.meta.get("name", "")
        if name:
            p.setPen(QPen(QColor("#222"), 1))
            fm = p.fontMetrics()
            text_w = fm.horizontalAdvance(name)
            p.drawText(max(8, (self.width()-text_w)//2), r.bottom()+18, name)


    def enterEvent(self, ev):
        # курсор «ладонь» только над иконкой
        pos = self.mapFromGlobal(QCursor.pos())
        self.setCursor(Qt.OpenHandCursor if self._icon_rect.contains(pos) else Qt.ArrowCursor)

    def mouseMoveEvent(self, ev):
        self.setCursor(Qt.OpenHandCursor if self._icon_rect.contains(ev.pos()) else Qt.ArrowCursor)

        if not self._drag_from_icon or self._press_pos is None:
            return
        if (ev.pos() - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return

        # старт drag — НИКАКОГО drag pixmap
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-smart", QByteArray(json.dumps(self.meta, ensure_ascii=False).encode("utf-8")))
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)

        self._drag_from_icon = False
        self._press_pos = None

    def mousePressEvent(self, ev):
        # берём только если клик внутри квадрата
        if ev.button() == Qt.LeftButton and self._icon_rect.contains(ev.pos()):
            self._press_pos = ev.pos()
            self._drag_from_icon = True
        else:
            self._press_pos = None
            self._drag_from_icon = False
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._press_pos = None
        self._drag_from_icon = False
        super().mouseReleaseEvent(ev)

    def resizeEvent(self, ev):
        self._layout_icon_rect()
        self.updateGeometry() 
        super().resizeEvent(ev)

class PalettePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = "rooms"
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Левая колонка с категориями
        icon_bar = QWidget(self)
        icon_bar.setFixedWidth(72)
        icon_bar.setStyleSheet("background:#f0f2f5; border-right:1px solid #e5e7eb;")
        vb = QVBoxLayout(icon_bar)
        vb.setContentsMargins(6, 6, 6, 6)
        vb.setSpacing(8)

        self.btn_rooms = QToolButton(icon_bar)
        self.btn_devices = QToolButton(icon_bar)
        self.btn_furniture = QToolButton(icon_bar)
        for b in (self.btn_rooms, self.btn_devices, self.btn_furniture):
            b.setProperty("class", "category")
            b.setAutoExclusive(True)
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonIconOnly)
            b.setIconSize(QSize(28, 28))
            b.setFixedSize(44, 44)
            vb.addWidget(b)
        vb.addStretch(1)
        root.addWidget(icon_bar)

        from .utils import CATEGORY_ICON_ROOMS, CATEGORY_ICON_DEVICES, CATEGORY_ICON_FURNITURE, load_svg_icon
        def _cat(kind: str, size: int = 28):
            path = CATEGORY_ICON_ROOMS if kind == "rooms" else (CATEGORY_ICON_DEVICES if kind == "devices" else CATEGORY_ICON_FURNITURE)
            return load_svg_icon(path, size)

        self.btn_rooms.setIcon(_cat("rooms", 28) or self.btn_rooms.icon())
        self.btn_rooms.setToolTip("Дом")
        self.btn_devices.setIcon(_cat("devices", 28) or self.btn_devices.icon())
        self.btn_devices.setToolTip("Приборы")
        self.btn_furniture.setIcon(_cat("furniture", 28) or self.btn_furniture.icon())
        self.btn_furniture.setToolTip("Мебель")

        # Правая часть — скролл и контент
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea{background:#ffffff;}")
        root.addWidget(self.scroll, 1)

        self.content = QWidget()                        # ← создаём content
        self.content.setObjectName("PaletteContent")    # ← теперь можно задавать objectName
        self.scroll.setWidget(self.content)

        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(8)

        # Сигналы переключения
        self.btn_rooms.clicked.connect(lambda: self._switch("rooms"))
        self.btn_devices.clicked.connect(lambda: self._switch("devices"))
        self.btn_furniture.clicked.connect(lambda: self._switch("furniture"))

        # Стартовая вкладка
        self.btn_rooms.setChecked(True)
        self._current = "rooms"
        self._populate_rooms()


    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

    def _switch(self, cat: str):
        if cat == self._current: return
        self._current = cat
        self._clear_content()
        if cat == "rooms":
            self._populate_rooms()
        elif cat == "devices":
            self._populate_devices()
        else:
            self._populate_furniture()

    def _populate_rooms(self):
        blocks = [
            # Комната
            {"name": "Комната 300x200", "w": 300, "h": 200, "kind": "room", "desc": "Прямоугольная"},
            # Проёмы
            {"name": "Окно", "w": 100, "h": 12, "kind": "opening", "subtype": "window", "desc": "Проём (окно)"},
            {"name": "Дверь", "w": 90,  "h": 16, "kind": "opening", "subtype": "door",   "desc": "Проём (дверь)"},
        ]
        for meta in blocks:
            self.content_layout.addWidget(PreviewTile(meta))
        self.content_layout.addStretch(1)


    def _populate_devices(self):
        devices = [
            {"name":"Лампа","w":40,"h":40,"kind":"device","desc":""},
            {"name":"Розетка","w":30,"h":30,"kind":"device","desc":""},
            {"name":"Датчик","w":30,"h":30,"kind":"device","desc":"Датчик движения/дыма"},
            {"name":"Камера","w":46,"h":32,"kind":"device","desc":""},
            {"name":"Кондиционер","w":90,"h":30,"kind":"device","desc":""},
        ]
        grid_host = QWidget(); grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8)
        for i, meta in enumerate(devices):
            grid.addWidget(PreviewTile(meta), i // 2, i % 2)
        self.content_layout.addWidget(grid_host)
        self.content_layout.addStretch(1)

    def _populate_furniture(self):
            furniture = [
                {"name":"Стол","w":80,"h":60,"kind":"furniture","desc":""},
                {"name":"Стул","w":30,"h":30,"kind":"furniture","desc":""},
                {"name":"Диван","w":120,"h":60,"kind":"furniture","desc":""},
                {"name":"Шкаф","w":90,"h":40,"kind":"furniture","desc":""},
            ]
            grid_host = QWidget(); grid = QGridLayout(grid_host)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8)
            for i, meta in enumerate(furniture):
                grid.addWidget(PreviewTile(meta), i // 2, i % 2)
            self.content_layout.addWidget(grid_host)
            self.content_layout.addStretch(1)
    def resizeEvent(self, e):
        super().resizeEvent(e)
        # перерисовать плитки, чтобы sizeHint учитывал новую ширину
        for i in range(self.content_layout.count()):
            w = self.content_layout.itemAt(i).widget()
            if w and hasattr(w, "updateGeometry"):
                w.updateGeometry()
        self.content.updateGeometry()

