from __future__ import annotations
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QHBoxLayout, QToolButton
from .models import Layer
from .palette import make_category_icon

class LayersHUD(QWidget):
    def __init__(self, view):
        QWidget.__init__(self, view.viewport())
        self.view = view
        self.setObjectName("hud")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("""
            QWidget#hud { background: rgba(255,255,255,190); border:1px solid #e5e7eb; border-radius:6px; }
            QToolButton { border:none; background:transparent; width:36px; height:36px; }
            QToolButton:checked { background:#e3f2ff; border-radius:6px; }
            QToolButton:hover { background:#f3f4f6; border-radius:6px; }
        """)
        lay = QHBoxLayout(self); lay.setContentsMargins(6,6,6,6); lay.setSpacing(4)
        self.btn_rooms   = QToolButton(self)
        self.btn_devices = QToolButton(self)
        self.btn_furn    = QToolButton(self)
        self.btn_rooms.setIcon(make_category_icon("rooms", 28))
        self.btn_devices.setIcon(make_category_icon("devices", 28))
        self.btn_furn.setIcon(make_category_icon("furniture", 28))
        self.btn_furn.setIcon(QIcon())

        for b in (self.btn_rooms, self.btn_devices, self.btn_furn):
            b.setCheckable(True); b.setAutoExclusive(True)
            b.setIconSize(QSize(28, 28)); b.setFixedSize(36, 36); lay.addWidget(b)

        self.btn_rooms.setChecked(True)
        self.btn_rooms.clicked.connect(lambda: self._set_layer(Layer.ROOMS))
        self.btn_devices.clicked.connect(lambda: self._set_layer(Layer.DEVICES))
        self.btn_furn.clicked.connect(lambda: self._set_layer(Layer.FURNITURE))

        self.resize(self.sizeHint())
        self.setMinimumSize(self.sizeHint())
        self.show()
        self.raise_()

    def set_checked(self, layer: str):
        if layer == Layer.ROOMS:
            self.btn_rooms.setChecked(True)
        elif layer == Layer.DEVICES:
            self.btn_devices.setChecked(True)
        elif layer == Layer.FURNITURE:
            self.btn_furn.setChecked(True)

    def _set_layer(self, layer: str):
        from .scene import PlanScene  # избежать циклов
        scene = self.view.scene()
        if isinstance(scene, PlanScene):
            scene.set_active_layer(layer)

    def reposition(self):
        margin = 12
        vw = self.view.viewport().width()
        vh = self.view.viewport().height()
        self.move(vw - self.width() - margin, vh - self.height() - margin)
