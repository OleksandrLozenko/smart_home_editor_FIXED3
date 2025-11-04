#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import sys, json
from PySide6.QtCore import Qt, QSizeF
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QDockWidget, QStyle, QLabel, QWidget, QWidgetAction   # ← добавлено
)

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
        # Палитра
        self.palette_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.palette_dock.setMinimumWidth(220)
        self.palette_dock.setMaximumWidth(520)  # чтобы не раздувалась бесконечно

        # Свойства
        self.props_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.props_dock.setMinimumWidth(280)
        self.props_dock.setMaximumWidth(560)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.palette_dock)

        # 4) Тулбар/статус
        self.undo_manager = UndoManager(on_change=self._update_status)
        self._build_toolbar()
        self.setStatusBar(QStatusBar(self))

        self.view.scaleChanged.connect(lambda s: self.statusBar().showMessage(
            f"Режим: {'Просмотр' if self.scene.mode==Mode.VIEW else 'Редактирование'} | "
            f"Слой: {self.scene.active_layer} | Масштаб: {int(s*100)}%"
        ))

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
    
    def _sep_label(self, tb: QToolBar, text: str):
        lbl = QLabel(f"  {text}  ")
        lbl.setStyleSheet("color:#667085; font-weight:600;")
        wa = QWidgetAction(self)
        wa.setDefaultWidget(lbl)
        tb.addAction(wa)


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
        tb = QToolBar("Панель", self)
        tb.setMovable(False)
        tb.setIconSize(QSizeF(18, 18).toSize())
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.TopToolBarArea, tb)

        style = self.style()
        # аккуратный загрузчик svg с фолбэком на системную иконку
        from files.utils import load_svg_icon
        def ico(path: str | None, fallback: QStyle.StandardPixmap):
            if path:
                icon = load_svg_icon(path, 18)
                if icon: 
                    return icon
            return style.standardIcon(fallback)

        # --- ДЕЙСТВИЯ ---
        self.act_viewmode = QAction(ico("assets/icons/view.svg", QStyle.SP_DesktopIcon),
                                    "Просмотр", self, checkable=True)
        self.act_viewmode.toggled.connect(self._toggle_viewmode)

        self.act_snap = QAction(ico("assets/icons/grid.svg", QStyle.SP_DialogResetButton),
                                "Сетка", self, checkable=True)
        self.act_snap.setChecked(True)
        self.act_snap.toggled.connect(lambda on: setattr(self.scene, "snap_to_grid", on))

        self.act_import = QAction(ico("assets/icons/open.svg", QStyle.SP_DirOpenIcon),
                                "Импорт", self)
        self.act_import.setShortcut(QKeySequence("Ctrl+O"))
        self.act_import.triggered.connect(self._import_json_dialog)

        self.act_export = QAction(ico("assets/icons/export.svg", QStyle.SP_ArrowRight),
                                "Экспорт", self)
        self.act_export.setShortcut(QKeySequence("Ctrl+E"))
        self.act_export.triggered.connect(self._export_json_dialog)

        self.act_save = QAction(ico("assets/icons/save.svg", QStyle.SP_DialogSaveButton),
                                "Сохранить", self)
        self.act_save.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save.triggered.connect(self._export_json_dialog)

        self.act_undo = QAction(ico("assets/icons/undo.svg", QStyle.SP_ArrowBack),
                                "Откат", self)
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.act_undo.triggered.connect(self._undo)

        self.act_redo = QAction(ico("assets/icons/redo.svg", QStyle.SP_ArrowForward),
                                "Обратно", self)
        self.act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        self.act_redo.triggered.connect(self._redo)

        self.act_settings = QAction(ico("assets/icons/settings.svg", QStyle.SP_FileDialogDetailedView),
                                    "Настройки", self)
        self.act_settings.triggered.connect(lambda: None)  # заглушка

        # — Тогглеры доков. Иконки: если нет своих svg, берём системные.
        self.act_toggle_props = QAction(
            ico("assets/icons/props.svg", QStyle.SP_FileDialogInfoView),  # ← нет файла? возьмём стандартную
            "Свойства", self, checkable=True
        )
        self.act_toggle_palette = QAction(
            ico("assets/icons/palette.svg", QStyle.SP_DirIcon),           # ← нет файла? возьмём стандартную
            "Палитра", self, checkable=True
        )
        def _sync_dock_actions():
            self.act_toggle_props.setChecked(not self.props_dock.isHidden())
            self.act_toggle_palette.setChecked(not self.palette_dock.isHidden())
        _sync_dock_actions()
        self.act_toggle_props.toggled.connect(lambda on: (self.props_dock.show() if on else self.props_dock.hide()))
        self.act_toggle_palette.toggled.connect(lambda on: (self.palette_dock.show() if on else self.palette_dock.hide()))
        self.props_dock.visibilityChanged.connect(lambda _: _sync_dock_actions())
        self.palette_dock.visibilityChanged.connect(lambda _: _sync_dock_actions())

        # --- Разметка на тулбаре ---
        from PySide6.QtWidgets import QLabel, QWidgetAction
        def _lbl(text: str):
            lab = QLabel(f"  {text}  "); lab.setStyleSheet("color:#667085; font-weight:600;")
            wa = QWidgetAction(self); wa.setDefaultWidget(lab); tb.addAction(wa)

        _lbl("Проект")
        tb.addAction(self.act_save)
        tb.addAction(self.act_import)   # ← Импорт на месте
        tb.addAction(self.act_export)

        _lbl("Редактирование")
        tb.addAction(self.act_snap)
        tb.addAction(self.act_viewmode)
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)

        _lbl("Окна")
        tb.addAction(self.act_toggle_props)
        tb.addAction(self.act_toggle_palette)

        tb.addSeparator()
        tb.addAction(self.act_settings)


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
    with open("smart_theme.qss", "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())
    win = MainWindow()
    win.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
