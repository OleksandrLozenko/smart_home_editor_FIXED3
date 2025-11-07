from __future__ import annotations
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QHBoxLayout, QToolButton
from .models import Layer
from .palette import make_category_icon
from .utils import load_svg_icon, CATEGORY_ICON_ROOMS, CATEGORY_ICON_DEVICES, CATEGORY_ICON_FURNITURE

class LayersHUD(QWidget):
    def __init__(self, view):
        super().__init__(view.viewport())
        self.view = view
        self.setObjectName("LayersHUD")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("""
            QWidget#LayersHUD { background: rgba(255,255,255,0.95); border:1px solid #e7e8ee; border-radius:12px; }
            QToolButton.layer { border:none; padding:6px; border-radius:10px; }
            QToolButton.layer:hover { background:#f2f4f7; }
            QToolButton.layer:checked { background:#dbe7ff; }
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8,8,8,8)
        lay.setSpacing(6)

        # Кнопки слоёв
        self.btn_rooms    = QToolButton(self)
        self.btn_devices  = QToolButton(self)
        self.btn_furn     = QToolButton(self)
        self.btn_openings = QToolButton(self)

        buttons = [
            (self.btn_rooms,    Layer.ROOMS,    "Дом",      CATEGORY_ICON_ROOMS),
            (self.btn_devices,  Layer.DEVICES,  "Приборы",  CATEGORY_ICON_DEVICES),
            (self.btn_furn,     Layer.FURNITURE,"Мебель",   CATEGORY_ICON_FURNITURE),
            # для «Проёмов» используем ту же иконку, что и «Дом» (позже можно заменить на дверь)
            (self.btn_openings, Layer.OPENINGS, "Проёмы",   CATEGORY_ICON_ROOMS),
        ]

        for btn, layer, tooltip, svg_path in buttons:
            btn.setProperty("class", "layer")
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setIcon(make_category_icon("rooms" if svg_path==CATEGORY_ICON_ROOMS else
                                           "devices" if svg_path==CATEGORY_ICON_DEVICES else
                                           "furniture", 24))
            # перекрываем на случай наличия SVG-иконок
            svg = load_svg_icon(svg_path, 20)
            if svg: btn.setIcon(svg)
            btn.setIconSize(QSize(20,20))
            btn.setFixedSize(36,36)
            btn.clicked.connect(lambda _=False, L=layer: self._set_layer(L))
            lay.addWidget(btn)

        # Стартовое состояние
        self.btn_rooms.setChecked(True)
        self.resize(self.sizeHint())
        self.setMinimumSize(self.sizeHint())
        self.show()
        self.raise_()

    def set_checked(self, layer: Layer):
        self.btn_rooms.setChecked(layer == Layer.ROOMS)
        self.btn_devices.setChecked(layer == Layer.DEVICES)
        self.btn_furn.setChecked(layer == Layer.FURNITURE)
        self.btn_openings.setChecked(layer == Layer.OPENINGS)

    def _set_layer(self, layer: Layer):
        # синхронизация кнопок
        self.set_checked(layer)
        # передаём в сцену
        from .scene import PlanScene
        scene = self.view.scene()
        if isinstance(scene, PlanScene):
            scene.set_active_layer(layer)

    def reposition(self):
        margin = 12
        vw = self.view.viewport().width()
        vh = self.view.viewport().height()
        self.move(vw - self.width() - margin, vh - self.height() - margin)
