# files/properties.py
from __future__ import annotations
import json, os
from typing import Optional, List
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox, QComboBox,
    QListWidget, QListWidgetItem, QLabel, QHBoxLayout, QPushButton,QGroupBox
)

from .items import RoomItem, DeviceItem, PlanRectItem, FurnitureItem
from .scene import PlanScene
from .scene import Layer  # если у вас Layer объявлен в scene.py — импорт скорректируйте: from .scene import Layer

class PropertyPanel(QWidget):
    # полезный сигнал, если нужно куда-то отдать инфу наружу
    requestFocusItem = Signal(object)  # item

    def __init__(self, scene: PlanScene, parent=None):
        super().__init__(parent)
        self.scene = scene
        self._current: Optional[PlanRectItem] = None

        self.setMinimumWidth(280)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        # Заголовок текущего типа
        self.lbl_title = QLabel("Ничего не выбрано")
        self.lbl_title.setStyleSheet("font-weight: 600;")
        root.addWidget(self.lbl_title)

        # ------- Комната -------
        self.frm_room = QWidget()
        fr = QFormLayout(self.frm_room)
        fr.setLabelAlignment(Qt.AlignRight)

        self.ed_room_name = QLineEdit()
        self.sp_room_w = QDoubleSpinBox(); self.sp_room_h = QDoubleSpinBox()
        for s in (self.sp_room_w, self.sp_room_h):
            s.setRange(1, 99999); s.setDecimals(0); s.setSingleStep(5); s.setSuffix(" px")

        self.list_devices = QListWidget()
        self.list_furniture = QListWidget()
        self.list_devices.setMinimumHeight(120)
        self.list_furniture.setMinimumHeight(120)
        self.list_devices.setStyleSheet("QListWidget{ background:#fafafa; }")
        self.list_furniture.setStyleSheet("QListWidget{ background:#fafafa; }")

        fr.addRow("Название:", self.ed_room_name)
        fr.addRow("Ширина:", self.sp_room_w)
        fr.addRow("Высота:", self.sp_room_h)
        fr.addRow(QLabel("Приборы в комнате:"), self.list_devices)
        fr.addRow(QLabel("Мебель в комнате:"), self.list_furniture)

        self.list_devices.itemDoubleClicked.connect(self._go_to_device)
        self.list_furniture.itemDoubleClicked.connect(self._go_to_furniture)
        # хендлеры изменений комнаты
        self.ed_room_name.textEdited.connect(self._apply_room_name)
        self.sp_room_w.valueChanged.connect(self._apply_room_size)
        self.sp_room_h.valueChanged.connect(self._apply_room_size)

        root.addWidget(self.frm_room)

        # ------- Прибор -------
        self.frm_dev = QWidget()
        fd = QFormLayout(self.frm_dev)
        fd.setLabelAlignment(Qt.AlignRight)

        self.ed_dev_name = QLineEdit()
        self.ed_dev_model = QLineEdit()

        fd.addRow("Название:", self.ed_dev_name)
        fd.addRow("Модель/описание:", self.ed_dev_model)

        # хендлеры изменений прибора
        self.ed_dev_name.textEdited.connect(self._apply_dev_name)
        self.ed_dev_model.textEdited.connect(self._apply_dev_model)

        root.addWidget(self.frm_dev)
        root.addStretch(1)
        self.grp_opening = QGroupBox("Проём")
        fo = QFormLayout(self.grp_opening)

        self.opening_kind = QLabel("-")            # окно/дверь (read-only)
        self.sp_open_w = QDoubleSpinBox()          # ширина окна
        self.sp_open_h = QDoubleSpinBox()          # высота окна
        for s in (self.sp_open_w, self.sp_open_h):
            s.setRange(1, 9999); s.setDecimals(0); s.setSingleStep(5); s.setSuffix(" px")

        self.cmb_door_swing = QComboBox()
        self.cmb_door_swing.addItems(["Вправо", "Влево"])

        fo.addRow("Тип:", self.opening_kind)
        fo.addRow("Ширина (окно):", self.sp_open_w)
        fo.addRow("Высота (окно):", self.sp_open_h)
        fo.addRow("Открытие (дверь):", self.cmb_door_swing)

        root.addWidget(self.grp_opening)  # где root — основной layout панели
        self.grp_opening.setVisible(False)

        # сигналы
        self.sp_open_w.valueChanged.connect(self._apply_opening_size)
        self.sp_open_h.valueChanged.connect(self._apply_opening_size)
        self.cmb_door_swing.currentIndexChanged.connect(self._apply_door_swing)

        self.clear()

    # ---------- API ----------
    def clear(self):
        self._current = None
        self.lbl_title.setText("Ничего не выбрано")
        self.frm_room.setVisible(False)
        self.frm_dev.setVisible(False)

    def load_item(self, item: Optional[PlanRectItem]):
        self._current = item
        if item is None:
            self.clear()
            return

        if isinstance(item, RoomItem):
            self.lbl_title.setText("Свойства: Комната")
            self._populate_room_devices(item)
            self._populate_room_furniture(item)
            self.frm_room.setVisible(True)
            self.frm_dev.setVisible(False)

            # прокинуть текущее состояние
            self.ed_room_name.blockSignals(True)
            self.sp_room_w.blockSignals(True)
            self.sp_room_h.blockSignals(True)

            self.ed_room_name.setText(item.props.name or "")
            self.sp_room_w.setValue(item.rect().width())
            self.sp_room_h.setValue(item.rect().height())

            # тип хранить в props.description как метка типа (чтобы не ломать модель)
            # формат: "type:<НазваниеТипа>|<другой текст>"

            self.ed_room_name.blockSignals(False)
            self.sp_room_w.blockSignals(False)
            self.sp_room_h.blockSignals(False)

        elif isinstance(item, DeviceItem):
            self.lbl_title.setText("Свойства: Прибор")
            self.frm_room.setVisible(False)
            self.frm_dev.setVisible(True)

            self.ed_dev_name.blockSignals(True)
            self.ed_dev_model.blockSignals(True)

            self.ed_dev_name.setText(item.props.name or "")
            self.ed_dev_model.setText(item.props.description or "")

            self.ed_dev_name.blockSignals(False)
            self.ed_dev_model.blockSignals(False)
        else:
            self.clear()

    # ---------- helpers ----------
    def _populate_room_devices(self, room: RoomItem):
        self.list_devices.clear()
        for child in room.childItems():
            if isinstance(child, DeviceItem):
                li = QListWidgetItem(child.props.name or "Прибор")
                li.setData(Qt.UserRole, child)
                self.list_devices.addItem(li)

    # ---------- apply handlers ----------
    def _apply_room_name(self, text: str):
        if not isinstance(self._current, RoomItem): return
        self._current.props.name = text.strip()
        self._current.update_tooltip()
        self.scene._push_snapshot("room.name")

    def _apply_room_size(self, *_):
        if not isinstance(self._current, RoomItem): return
        w = float(self.sp_room_w.value()); h = float(self.sp_room_h.value())
        self.scene._stash_snapshot()
        if self._current.set_size_px(w, h):
            self.scene._commit_snapshot("room.size")
        # если не удалось (перекрытие/границы), спин вернём к актуальному размеру
        self.sp_room_w.blockSignals(True); self.sp_room_h.blockSignals(True)
        self.sp_room_w.setValue(self._current.rect().width())
        self.sp_room_h.setValue(self._current.rect().height())
        self.sp_room_w.blockSignals(False); self.sp_room_h.blockSignals(False)

    def _go_to_device(self, item: QListWidgetItem):
        dev = item.data(Qt.UserRole)
        if not isinstance(dev, DeviceItem): return
        self.scene.set_active_layer(Layer.DEVICES)   # переключаем слой (HUD сам подсветится)
        for it in self.scene.selectedItems():
            it.setSelected(False)
        dev.setSelected(True)
        self.requestFocusItem.emit(dev)

    def _go_to_furniture(self, item: QListWidgetItem):
        furn = item.data(Qt.UserRole)
        if not isinstance(furn, FurnitureItem): return
        self.scene.set_active_layer(Layer.FURNITURE) # переключаем слой (HUD сам подсветится)
        for it in self.scene.selectedItems():
            it.setSelected(False)
        furn.setSelected(True)
        self.requestFocusItem.emit(furn)


    def _apply_dev_name(self, text: str):
        if not isinstance(self._current, DeviceItem): return
        self._current.props.name = text.strip()
        self._current.update_tooltip()
        self.scene._push_snapshot("device.name")

    def _apply_dev_model(self, text: str):
        if not isinstance(self._current, DeviceItem): return
        # используем description как «модель/описание»
        self._current.props.description = text.strip()
        self._current.update_tooltip()
        self.scene._push_snapshot("device.model")

    def _populate_room_devices(self, room: RoomItem):
        self.list_devices.clear()
        for ch in room.childItems():
            if isinstance(ch, DeviceItem):
                li = QListWidgetItem(ch.props.name or "Прибор")
                li.setData(Qt.UserRole, ch)
                self.list_devices.addItem(li)

    def _populate_room_furniture(self, room: RoomItem):
        self.list_furniture.clear()
        for ch in room.childItems():
            if isinstance(ch, FurnitureItem):
                li = QListWidgetItem(ch.props.name or "Мебель")
                li.setData(Qt.UserRole, ch)
                self.list_furniture.addItem(li)

