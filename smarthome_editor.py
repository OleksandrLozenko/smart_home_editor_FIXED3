#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import sys, json
from PySide6.QtCore import Qt, QSizeF
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow, QToolBar, QStatusBar, QFileDialog, QMessageBox, QDockWidget, QStyle
from files import PlanScene, PlanView, UndoManager, Mode, PalettePanel, SCENE_W, SCENE_H, PropertyPanel, Layer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartHome WYSIWYG — Demo (px)")
        self.resize(1280, 860)

        # 1) Сцена/вью
        self.scene = PlanScene(status_cb=self._status)
        self.view = PlanView(self.scene)
        self.setCentralWidget(self.view)

        # 2) Панель свойств — СОЗДАЁМ СРАЗУ, до любых addDockWidget()
        self.props_panel = PropertyPanel(self.scene, self)
        self.props_dock = QDockWidget("Свойства", self)
        self.props_dock.setWidget(self.props_panel)
        self.props_dock.setMinimumWidth(300)
        self.addDockWidget(Qt.RightDockWidgetArea, self.props_dock)

        # 3) Палитра
        self.palette = PalettePanel()
        self.palette_dock = QDockWidget("Палитра", self)
        self.palette_dock.setWidget(self.palette)
        self.palette_dock.setMinimumWidth(260)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.palette_dock)

        # 4) Тулбар/статус
        self.undo_manager = UndoManager(on_change=self._update_status)
        self._build_toolbar()
        self.setStatusBar(QStatusBar(self))

        # 5) Подписки: открывать «Свойства», когда что-то выделили
        def _show_props_if_hidden():
            if self.props_dock.isHidden():
                self.props_dock.show()
                self.props_dock.raise_()

        self.scene.selectionChanged.connect(_show_props_if_hidden)
        self.scene.selectionChanged.connect(self._on_scene_selection)

        # 6) Фокус из панели (дабл-клик по прибору/мебели/комнате)
        self.props_panel.requestFocusItem.connect(self._focus_item)

        # 7) Стартовое состояние
        self.undo_manager.push(json.dumps(self.scene.serialize()))
        self.scene.apply_layer_state()
        self._update_status()

    def _build_properties_panel(self):
        self.props_panel = PropertyPanel(self.scene, self)
        self.props_dock = QDockWidget("Свойства", self)
        self.props_dock.setWidget(self.props_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.props_dock)
        self.props_dock.setMinimumWidth(300)

    def _on_scene_selection(self):
        sel = [it for it in self.scene.selectedItems() if hasattr(it, "props")]
        item = sel[0] if sel else None
        self.props_panel.load_item(item)

    def _focus_item(self, item):
        # показать/прокрутить
        self.scene.ensure_visible_item(item)
        # подсветим статусом
        kind = "Комната" if item.props.kind == "room" else "Прибор"
        self._status(f"Перешли к: {kind} — {item.props.name or '(без названия)'}")

    def _build_palette(self):
        self.palette = PalettePanel()
        self.palette_dock = QDockWidget("Палитра", self)
        self.palette_dock.setWidget(self.palette)
        self.addDockWidget(Qt.RightDockWidgetArea, self.palette_dock)
        self.palette_dock.setMinimumWidth(260)

    def _build_toolbar(self):
        tb = QToolBar("Управление", self)
        tb.setMovable(False)
        tb.setIconSize(QSizeF(18, 18).toSize())
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.setStyleSheet("QToolBar { background: #ffffff; border-bottom: 1px solid #e5e7eb; padding: 4px; }")
        self.addToolBar(Qt.TopToolBarArea, tb)

        style = self.style()
        ico_view   = style.standardIcon(QStyle.SP_DesktopIcon)
        ico_grid   = style.standardIcon(QStyle.SP_DialogResetButton)
        ico_save   = style.standardIcon(QStyle.SP_DialogSaveButton)
        ico_open   = style.standardIcon(QStyle.SP_DirOpenIcon)
        ico_export = style.standardIcon(QStyle.SP_ArrowRight)
        ico_undo   = style.standardIcon(QStyle.SP_ArrowBack)
        ico_redo   = style.standardIcon(QStyle.SP_ArrowForward)

        self.act_viewmode = QAction(ico_view, "Просмотр", self, checkable=True)
        self.act_viewmode.toggled.connect(self._toggle_viewmode)

        self.act_snap = QAction(ico_grid, "Сетка", self, checkable=True)
        self.act_snap.setChecked(True)
        self.act_snap.toggled.connect(lambda on: setattr(self.scene, "snap_to_grid", on))

        self.act_save = QAction(ico_save, "Сохранить", self)
        self.act_save.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save.triggered.connect(self._export_json_dialog)

        self.act_import = QAction(ico_open, "Импорт", self)
        self.act_import.setShortcut(QKeySequence("Ctrl+O"))
        self.act_import.triggered.connect(self._import_json_dialog)

        self.act_export = QAction(ico_export, "Экспорт", self)
        self.act_export.setShortcut(QKeySequence("Ctrl+E"))
        self.act_export.triggered.connect(self._export_json_dialog)

        self.act_undo = QAction(ico_undo, "Отменить", self)
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.act_undo.triggered.connect(self._undo)

        self.act_redo = QAction(ico_redo, "Повторить", self)
        self.act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        self.act_redo.triggered.connect(self._redo)

        tb.addAction(self.act_viewmode)
        tb.addAction(self.act_snap)
        tb.addSeparator()
        tb.addAction(self.act_save)
        tb.addAction(self.act_import)
        tb.addAction(self.act_export)
        tb.addSeparator()
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)

    def _import_json_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт JSON", "", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.scene.deserialize(data)
            self.undo_manager.push(json.dumps(self.scene.serialize()))
            self._status("Импортировано.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка импорта", str(e))

    def _export_json_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт JSON", "smarthome_scene.json", "JSON (*.json)")
        if not path: return
        try:
            data = self.scene.serialize()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._status("Сохранено.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сохранения", str(e))

    def _undo(self):
        snap = self.undo_manager.undo()
        if snap is None: return
        self.scene.deserialize(json.loads(snap))
        self._update_status()

    def _redo(self):
        snap = self.undo_manager.redo()
        if snap is None: return
        self.scene.deserialize(json.loads(snap))
        self._update_status()

    def _toggle_viewmode(self, on: bool):
        self.scene.mode = Mode.VIEW if on else Mode.EDIT
        self.scene.set_editable(not on)
        if on:
            self.scene.clearSelection()
            self.scene.hide_size_overlay()
        self._update_status()

    def _status(self, text: str):
        self.statusBar().showMessage(text, 3000)


    def _update_status(self):
        self.statusBar().showMessage(
            f"Режим: {'Просмотр' if self.scene.mode==Mode.VIEW else 'Редактирование'} | "
            f"Сетка: {'ON' if self.scene.snap_to_grid else 'OFF'} | "
            f"Холст: {int(SCENE_W)}×{int(SCENE_H)} px"
        )


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
