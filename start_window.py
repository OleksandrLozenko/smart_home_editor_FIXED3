# start_window.py
from __future__ import annotations
import os, json
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QToolButton, QLabel
)
from smarthome_editor import MainWindow

# ========= THEME (dark tech) =========
ACCENT           = "#22D3EE"   # неон-циан (акцент)
ACCENT_HOVER     = "#1CC3DB"
ACCENT_ACTIVE    = "#18B2C8"

PANEL_BG         = "rgba(11, 18, 32, 0.80)"   # «матовое стекло»
PANEL_STROKE     = "rgba(120, 162, 255, 0.35)"
PANEL_RADIUS     = 14
BTN_RADIUS       = 10

FONT_FAMILY      = "Segoe UI, Inter, Roboto, sans-serif"
TEXT_MAIN        = "#E6E7EA"
TEXT_DIM         = "#9AA4B2"

# фон: если есть assets/images/start.png — берём картинку; иначе — градиент
START_BG_PATH    = "assets/images/start.png"
AUTOSAVE_PATH    = "smarthome_autosave.json"
# =====================================

class StartWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("StartRoot")
        self.setWindowTitle("SmartHome — старт")
        self.resize(1200, 780)

        # --- UI ---
        root = QVBoxLayout(self); root.setContentsMargins(28, 28, 28, 28); root.setSpacing(0)

        # Верхняя панель с настройками справа
        top = QHBoxLayout(); top.setContentsMargins(0, 0, 0, 0); top.setSpacing(0)
        title = QLabel("SmartHome Editor")
        title.setObjectName("Brand")
        top.addWidget(title); top.addStretch(1)

        self.btn_settings = QToolButton(self); self.btn_settings.setObjectName("SettingsBtn")
        self.btn_settings.setIcon(self._icon_or_fallback("assets/icons/settings.svg"))
        self.btn_settings.setIconSize(QSize(22, 22))
        self.btn_settings.setToolTip("Настройки")
        self.btn_settings.clicked.connect(lambda: QMessageBox.information(self, "Настройки", "Пока без настроек 🙂"))
        top.addWidget(self.btn_settings)
        root.addLayout(top); root.addSpacing(16)

        # Центральная зона
        mid = QHBoxLayout(); mid.setSpacing(24)

        # Левая колонка — карточки
        left = QVBoxLayout(); left.setSpacing(22)

        # Карточка действий (красная)
        actions = QFrame(self); actions.setObjectName("ActionsCard")
        vact = QVBoxLayout(actions); vact.setContentsMargins(28, 24, 28, 24); vact.setSpacing(12)
        cap = QLabel("Быстрый старт"); cap.setObjectName("CardTitle"); vact.addWidget(cap)

        self.btn_new  = QPushButton("Создать проект");           self._style_action_btn(self.btn_new)
        self.btn_open = QPushButton("Открыть проект…");           self._style_action_btn(self.btn_open)
        self.btn_cont = QPushButton("Открыть автосохранённый");   self._style_action_btn(self.btn_cont)

        vact.addWidget(self.btn_new); vact.addWidget(self.btn_open); vact.addWidget(self.btn_cont)
        left.addWidget(actions)

        # Карточка «Недавние» (синяя)
        recent = QFrame(self); recent.setObjectName("RecentCard")
        vrec = QVBoxLayout(recent); vrec.setContentsMargins(24, 20, 24, 20); vrec.setSpacing(10)
        rcap = QLabel("Недавние проекты"); rcap.setObjectName("RecentTitle"); vrec.addWidget(rcap)

        self.list_recent = QListWidget(); self.list_recent.setObjectName("RecentList"); vrec.addWidget(self.list_recent, 1)
        left.addWidget(recent, 1)

        mid.addLayout(left, 0)
        mid.addStretch(1)   # пустая правая зона (как в твоей схеме)
        root.addLayout(mid, 1)

        # Сигналы
        self.btn_new.clicked.connect(self._new)
        self.btn_open.clicked.connect(self._open)
        self.btn_cont.clicked.connect(self._continue)
        self.list_recent.itemDoubleClicked.connect(self._open_recent)

        # Данные
        self._load_recent()
        self.btn_cont.setEnabled(Path(AUTOSAVE_PATH).exists())

        # Стиль
        self._apply_qss()

    # ---------- STYLE ----------
    def _apply_qss(self):
        from pathlib import Path
        bg_exists = Path(START_BG_PATH).exists()
        if bg_exists:
            bg_css = f"background: url('{START_BG_PATH.replace('\\', '/')}') center/cover no-repeat fixed;"
        else:
            bg_css = ("background: radial-gradient(1200px 800px at 20% 0%, #0B1220 0%, "
                    "#0B1220 30%, #0A1020 65%, #0A0F1D 100%);")

        self.setStyleSheet(f"""
        QWidget#StartRoot {{
            {bg_css}
            color: {TEXT_MAIN};
            font-family: {FONT_FAMILY};
        }}

        /* Заголовок */
        #Brand {{
            font-size: 18px; font-weight: 700; color: #E2E8F0; letter-spacing: .3px;
            text-shadow: 0 1px 0 rgba(0,0,0,.5);
        }}

        /* Обе карточки — тёмное стекло */
        #ActionsCard, #RecentCard {{
            background: {PANEL_BG};
            border: 1px solid {PANEL_STROKE};
            border-radius: {PANEL_RADIUS}px;
            backdrop-filter: blur(6px);
        }}

        #CardTitle, #RecentTitle {{ color: {TEXT_MAIN}; font-weight: 700; }}

        /* Кнопки действий — неон-циан */
        QPushButton.Action {{
            background: {ACCENT};
            color: #06202A;
            border: none; border-radius: {BTN_RADIUS}px;
            padding: 10px 14px; font-weight: 700;
            box-shadow: 0 6px 18px rgba(34,211,238,0.25);
        }}
        QPushButton.Action:hover  {{ background: {ACCENT_HOVER}; }}
        QPushButton.Action:pressed{{ background: {ACCENT_ACTIVE}; box-shadow:none; }}
        QPushButton.Action:disabled{{ background: #2A3B4A; color: #6B7280; }}

        /* Кнопка настроек — иконка в стеклянной таблетке */
        #SettingsBtn {{
            background: rgba(255,255,255,0.08);
            border: 1px solid {PANEL_STROKE};
            border-radius: 10px; padding: 6px 8px;
        }}
        #SettingsBtn:hover {{ background: rgba(255,255,255,0.14); }}

        /* Недавние проекты — светлая карточка внутри */
        #RecentList {{
            background: rgba(255,255,255,0.06);
            color: {TEXT_MAIN};
            border: 1px solid {PANEL_STROKE};
            border-radius: 10px; padding: 6px;
        }}
        #RecentList::item {{ padding: 7px 10px; color: {TEXT_MAIN}; }}
        #RecentList::item:selected {{
            background: rgba(34, 211, 238, 0.20);
            color: #EFFFFF;
            border-radius: 6px;
        }}
        """)


    def _style_action_btn(self, b: QPushButton):
        b.setProperty("class", "action")
        b.setObjectName("")  # нам не нужен id, чтобы не перебить QSS по классу
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(36)
        # класс в QSS
        b.setStyleSheet("QPushButton { }")
        b.setProperty("cssClass", "Action")
        b.setProperty("class", "Action")
        b.setProperty("role", "Action")
        b.setObjectName("ActionButton")
        b.setProperty("qtClass", "Action")
        b.setProperty("state", "Action")
        # принудительно применим стиль-класс
        b.setStyleSheet("QPushButton.Action { }")
        b.setProperty("class", "Action")
        b.setStyleSheet("")

    def _icon_or_fallback(self, path: str) -> QIcon:
        try:
            from files.utils import load_svg_icon
            ico = load_svg_icon(path, 22)
            if ico: return ico
        except Exception:
            pass
        from PySide6.QtWidgets import QStyle
        return self.style().standardIcon(QStyle.SP_FileDialogDetailedView)

    # ---------- DATA ----------
    def _load_recent(self):
        self.list_recent.clear()
        st = QSettings("SmartHome", "Editor")
        files = st.value("recent", [], list)
        for p in files:
            if os.path.exists(p):
                self.list_recent.addItem(QListWidgetItem(p))

    def _push_recent(self, path: str):
        st = QSettings("SmartHome", "Editor")
        files = st.value("recent", [], list)
        if path in files: files.remove(path)
        files.insert(0, path)
        st.setValue("recent", files[:12])

    def _launch_editor(self, data: dict | None):
        # Переход в редактор — СРАЗУ полноэкранно
        self.hide()
        self.editor = MainWindow()
        if data:
            try: self.editor.scene.deserialize(data)
            except Exception: pass
        self.editor.showFullScreen()     # ← как просил
        self.close()

    # ---------- ACTIONS ----------
    def _new(self):
        self._launch_editor(None)

    def _open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть проект", "", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f: data = json.load(f)
            self._push_recent(path)
            self._launch_editor(data)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _continue(self):
        if not os.path.exists(AUTOSAVE_PATH):
            QMessageBox.information(self, "Нет автосохранения", "Файл автосохранения не найден.")
            return
        try:
            with open(AUTOSAVE_PATH, "r", encoding="utf-8") as f: data = json.load(f)
            self._launch_editor(data)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _open_recent(self, it: QListWidgetItem):
        path = it.text()
        try:
            with open(path, "r", encoding="utf-8") as f: data = json.load(f)
            self._push_recent(path)
            self._launch_editor(data)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
