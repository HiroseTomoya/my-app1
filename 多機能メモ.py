import sys
import json
import os
import shutil
import time #時間関連の機能をモジュール
import hashlib
from datetime import datetime
import calendar #カレンダー機能をモジュール

# PySide6 モジュールのインポート
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QStackedWidget, QTextEdit,
    QScrollArea, QDialog, QComboBox, QMessageBox, QGridLayout
)
from PySide6.QtGui import QFont, QCursor

# Windows環境用の音声再生 (Mac/Linux環境を考慮してtry-except)
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


# --- タイマー並行処理用のQThread ---
class TimerWorker(QThread):
    timeout_signal = Signal()
    tick_signal = Signal(int)

    def __init__(self, seconds):
        super().__init__()
        self.seconds = seconds
        self.is_running = True

    def run(self):
        while self.seconds > 0 and self.is_running:
            time.sleep(1)
            if not self.is_running:
                break
            self.seconds -= 1
            self.tick_signal.emit(self.seconds)

        if self.seconds == 0 and self.is_running:
            self.timeout_signal.emit()

    def stop(self):
        self.is_running = False


# --- カスタム入力ダイアログ ---
class StyledInputDialog(QDialog):
    def __init__(self, title, prompt, initial_value="", is_password=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E2E;
                border: 1px solid #313244;
            }
        """)
        self.setWindowModality(Qt.WindowModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        lbl = QLabel(prompt)
        lbl.setStyleSheet("""
            color: #CDD6F4;
            font-family: 'Meiryo UI', 'Segoe UI', sans-serif;
            font-size: 16px;
            font-weight: 600;
        """)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.entry = QLineEdit()
        self.entry.setText(initial_value)
        self.entry.setStyleSheet("""
            QLineEdit {
                background-color: #313244;
                color: #CDD6F4;
                font-family: 'Meiryo UI', 'Segoe UI', sans-serif;
                font-size: 16px;
                border: 2px solid #45475A;
                border-radius: 12px;
                padding: 14px 18px;
                min-height: 22px;
            }
            QLineEdit:focus {
                border: 2px solid #89B4FA;
            }
        """)
        if is_password:
            self.entry.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.entry)

        btn = QPushButton("決定")
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setFixedHeight(50)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #89B4FA;
                color: #1E1E2E;
                font-size: 16px;
                font-weight: 700;
                border-radius: 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #A6C8FF;
            }
        """)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_value(self):
        return self.entry.text()


# --- メインアプリケーションクラス ---
class MultiApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi Memo")
        self.resize(900, 750)
        self.setMinimumSize(600, 500)

        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.DATA_FILE = os.path.join(BASE_DIR, "memo_pro_data.json")
        self.VAULT_FILE = os.path.join(BASE_DIR, "vault_pro_data.json")

        self.init_style()
        self.load_all_data()

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.timer_worker = None

        self.screens = {}
        self.create_all_screens()

    def init_style(self):
        self.colors = {
            "bg_base": "#1E1E2E",
            "bg_surface": "#181825",
            "card_bg": "#313244",
            "primary": "#89B4FA",
            "accent": "#CBA6F7",
            "success": "#A6E3A1",
            "danger": "#F38BA8",
            "neutral": "#9399B2",
            "text_main": "#CDD6F4",
            "text_sub": "#A6ADC8",
            "tab_active": "#89B4FA",
            "tab_inactive": "#45475A",
            "btn_back": "#585B70"
        }
        self.setStyleSheet(f"""
            * {{
                font-family: 'Meiryo UI', 'Segoe UI', 'Yu Gothic UI', 'Hiragino Sans', sans-serif;
                font-size: 15px;
            }}
            QMainWindow {{
                background-color: {self.colors['bg_base']};
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QTextEdit {{
                background-color: {self.colors['card_bg']};
                color: {self.colors['text_main']};
                font-size: 16px;
                line-height: 1.7;
                border: 2px solid #45475A;
                border-radius: 14px;
                padding: 18px;
                selection-background-color: #45475A;
            }}
            QTextEdit:focus {{
                border: 2px solid {self.colors['primary']};
            }}
            QLineEdit {{
                background-color: {self.colors['card_bg']};
                color: {self.colors['text_main']};
                font-size: 15px;
                border: 2px solid #45475A;
                border-radius: 12px;
                padding: 12px 16px;
                min-height: 24px;
            }}
            QLineEdit:focus {{
                border: 2px solid {self.colors['primary']};
            }}
            QLabel {{
                color: {self.colors['text_main']};
                font-size: 15px;
            }}
            QComboBox {{
                font-size: 15px;
                padding: 10px 14px;
                border: 2px solid #45475A;
                border-radius: 12px;
                background: {self.colors['card_bg']};
                color: {self.colors['text_main']};
                min-height: 24px;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {self.colors['card_bg']};
                color: {self.colors['text_main']};
                selection-background-color: #45475A;
            }}
            QMessageBox {{
                background-color: {self.colors['bg_base']};
                font-size: 15px;
            }}
            QMessageBox QLabel {{
                color: {self.colors['text_main']};
                font-size: 15px;
                min-width: 300px;
            }}
            QMessageBox QPushButton {{
                background-color: {self.colors['primary']};
                color: #1E1E2E;
                min-width: 100px;
                min-height: 40px;
                padding: 10px 24px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 14px;
                border: none;
            }}
        """)

    def _make_header_bar(self, title, back_action, extra_widgets=None):
        bar = QWidget()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"""
            QWidget {{
                background-color: {self.colors['card_bg']};
                border-radius: 14px;
                border: 1px solid #45475A;
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)

        back_btn = QPushButton("←")
        back_btn.setFixedSize(44, 44)
        back_btn.setCursor(QCursor(Qt.PointingHandCursor))
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['btn_back']};
                color: {self.colors['text_main']};
                font-size: 20px;
                font-weight: 700;
                border: none;
                border-radius: 22px;
            }}
            QPushButton:hover {{
                background-color: #6C7086;
            }}
        """)
        back_btn.clicked.connect(back_action)
        layout.addWidget(back_btn)

        lbl = QLabel(title)
        lbl.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {self.colors['text_main']};
            border: none;
        """)
        layout.addWidget(lbl)
        layout.addStretch()

        if extra_widgets:
            for w in extra_widgets:
                layout.addWidget(w)

        return bar

    def _make_action_btn(self, text, color, height=56):
        btn = QPushButton(text)
        btn.setFixedHeight(height)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: #1E1E2E;
                font-size: 17px;
                font-weight: 700;
                border: none;
                border-radius: 14px;
                padding: 12px 24px;
            }}
            QPushButton:hover {{
                background-color: {self._lighten(color)};
            }}
        """)
        return btn

    def _lighten(self, color):
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        r = min(255, r + 35)
        g = min(255, g + 35)
        b = min(255, b + 35)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _load_json_with_backup(self, filepath):
        for path in [filepath, filepath + ".bak"]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if path.endswith(".bak"):
                        shutil.copy2(path, filepath)
                    return data
                except (json.JSONDecodeError, ValueError):
                    continue
        return None

    def load_all_data(self):
        d = self._load_json_with_backup(self.DATA_FILE)
        if d:
            self.todo_items = d.get("todo", [])
            self.memo_data = d.get("memo", {"メイン": ""})
            self.calendar_notes = d.get("calendar", {})
        else:
            self.todo_items, self.memo_data, self.calendar_notes = [], {"メイン": ""}, {}

        v = self._load_json_with_backup(self.VAULT_FILE)
        if v:
            self.master_hash = v.get("hash")
            self.birth_hash = v.get("birth_hash")
            self.vault_items = v.get("items", [])
        else:
            self.master_hash = None
            self.birth_hash = None
            self.vault_items = []

        self.current_memo_folder = list(self.memo_data.keys())[0]
        self.is_authenticated = False
        self.cur_year, self.cur_month = datetime.now().year, datetime.now().month
        self.sounds = {"📢 警告音": "SystemHand", "🎵 標準音": "SystemAsterisk"}

    def _save_json_safe(self, filepath, data):
        tmp_path = filepath + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        if os.path.exists(filepath):
            shutil.copy2(filepath, filepath + ".bak")
        os.replace(tmp_path, filepath)

    def save_all_data(self):
        data = {"todo": self.todo_items, "memo": self.memo_data, "calendar": self.calendar_notes}
        self._save_json_safe(self.DATA_FILE, data)
        vault = {"hash": self.master_hash, "birth_hash": self.birth_hash, "items": self.vault_items}
        self._save_json_safe(self.VAULT_FILE, vault)

    def change_screen(self, screen_key):
        self.save_all_data()

        if screen_key == "memo":
            self.draw_tabs()
            self.load_current_memo_text()
        elif screen_key == "todo":
            self.refresh_todo()
        elif screen_key == "calendar":
            self.draw_calendar()
        elif screen_key == "vault_inside":
            self.refresh_vault()

        widget = self.screens[screen_key]
        self.stacked_widget.setCurrentWidget(widget)

    def back_to_selector(self):
        self.save_all_data()
        if hasattr(self, 'memo_text_widget'):
            self.save_memo_content()
        self.stacked_widget.setCurrentWidget(self.screens["selector"])

    def create_all_screens(self):
        self.create_selector_screen()
        self.create_timer_screen()
        self.create_todo_screen()
        self.create_memo_screen()
        self.create_calendar_screen()
        self.create_vault_auth_screen()
        self.create_vault_inside_screen()

    # --- メニューセレクター画面 ---
    def create_selector_screen(self):
        screen = QWidget()
        screen.setStyleSheet(f"background-color: {self.colors['bg_base']};")

        outer_layout = QVBoxLayout(screen)
        outer_layout.setAlignment(Qt.AlignCenter)

        container = QWidget()
        container.setMaximumWidth(520)
        container.setMinimumWidth(380)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(14)

        title = QLabel("Multi Memo")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            color: {self.colors['primary']};
            font-size: 32px;
            font-weight: 700;
            padding-bottom: 2px;
        """)
        layout.addWidget(title)

        subtitle = QLabel("多機能メモツール")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 14px; padding-bottom: 20px;")
        layout.addWidget(subtitle)

        opts = [
            ("⏲  タイマー", "時間を管理する", lambda: self.change_screen("timer"), self.colors["primary"]),
            ("📝  TO DO", "タスクを管理する", lambda: self.change_screen("todo"), self.colors["accent"]),
            ("📄  メモ", "テキストを記録する", lambda: self.change_screen("memo"), self.colors["success"]),
            ("📅  カレンダー", "予定を記録する", lambda: self.change_screen("calendar"), self.colors["neutral"]),
        ]

        for label, desc, slot, color in opts:
            btn = QPushButton()
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setFixedHeight(80)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.colors['card_bg']};
                    color: {self.colors['text_main']};
                    font-size: 20px;
                    font-weight: 700;
                    border: 2px solid #45475A;
                    border-radius: 16px;
                    padding: 0px 24px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: #45475A;
                    border-color: {color};
                }}
            """)
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(20, 8, 20, 8)
            btn_label = QLabel(label)
            btn_label.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {color}; border: none; background: transparent;")
            btn_desc = QLabel(desc)
            btn_desc.setStyleSheet(f"font-size: 13px; color: {self.colors['text_sub']}; border: none; background: transparent;")
            left_col = QVBoxLayout()
            left_col.setSpacing(2)
            left_col.addWidget(btn_label)
            left_col.addWidget(btn_desc)
            btn_layout.addLayout(left_col)
            btn_layout.addStretch()

            arrow = QLabel("›")
            arrow.setStyleSheet(f"font-size: 28px; color: {self.colors['text_sub']}; border: none; background: transparent;")
            btn_layout.addWidget(arrow)

            btn.clicked.connect(slot)
            layout.addWidget(btn)

        layout.addSpacing(8)

        vault_btn = QPushButton("🔒  セキュリティメモ")
        vault_btn.setCursor(QCursor(Qt.PointingHandCursor))
        vault_btn.setFixedHeight(64)
        vault_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['card_bg']};
                color: {self.colors['danger']};
                font-size: 18px;
                font-weight: 700;
                border: 2px solid {self.colors['danger']};
                border-radius: 16px;
                padding: 14px 24px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['danger']};
                color: #1E1E2E;
            }}
        """)
        vault_btn.clicked.connect(self.handle_vault_navigation)
        layout.addWidget(vault_btn)

        layout.addStretch()
        outer_layout.addWidget(container)
        self.stacked_widget.addWidget(screen)
        self.screens["selector"] = screen

    # --- 1. タイマー機能 ---
    def create_timer_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = self._make_header_bar("タイマー", self.back_to_selector)
        layout.addWidget(header)

        layout.addStretch(2)

        self.timer_display = QLabel("00:00")
        self.timer_display.setStyleSheet(f"""
            font-family: 'Consolas', 'SF Mono', monospace;
            font-size: 80px;
            font-weight: 700;
            color: {self.colors['primary']};
        """)
        self.timer_display.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timer_display)

        layout.addSpacing(20)

        in_f = QWidget()
        in_layout = QHBoxLayout(in_f)
        in_layout.setAlignment(Qt.AlignCenter)
        in_layout.setSpacing(8)

        self.e_min = QLineEdit("0")
        self.e_sec = QLineEdit("00")
        for entry in (self.e_min, self.e_sec):
            entry.setFixedSize(80, 52)
            entry.setAlignment(Qt.AlignCenter)
            entry.setStyleSheet(f"""
                font-family: 'Consolas', monospace;
                font-size: 24px;
                font-weight: 600;
                border: 2px solid #45475A;
                border-radius: 12px;
                background: {self.colors['card_bg']};
                color: {self.colors['text_main']};
            """)

        min_lbl = QLabel("分")
        sec_lbl = QLabel("秒")
        for l in (min_lbl, sec_lbl):
            l.setStyleSheet("font-size: 15px; font-weight: 600;")

        in_layout.addWidget(self.e_min)
        in_layout.addWidget(min_lbl)
        in_layout.addSpacing(16)
        in_layout.addWidget(self.e_sec)
        in_layout.addWidget(sec_lbl)
        layout.addWidget(in_f, alignment=Qt.AlignCenter)

        layout.addSpacing(12)

        sound_f = QWidget()
        sound_layout = QHBoxLayout(sound_f)
        sound_layout.setAlignment(Qt.AlignCenter)
        sound_layout.setSpacing(10)
        self.sound_combo = QComboBox()
        self.sound_combo.addItems(list(self.sounds.keys()))
        self.sound_combo.setFixedWidth(160)
        self.sound_combo.setFixedHeight(40)
        preview_btn = self._make_action_btn("♪ 試聴", self.colors["neutral"], 40)
        preview_btn.setFixedWidth(80)
        preview_btn.clicked.connect(self.preview_sound)
        sound_layout.addWidget(self.sound_combo)
        sound_layout.addWidget(preview_btn)
        layout.addWidget(sound_f, alignment=Qt.AlignCenter)

        layout.addStretch(3)

        # 操作ボタン - 縦に大きく配置
        btn_container = QWidget()
        btn_container.setMaximumWidth(400)
        btn_vlayout = QVBoxLayout(btn_container)
        btn_vlayout.setContentsMargins(0, 0, 0, 0)
        btn_vlayout.setSpacing(10)

        start_btn = self._make_action_btn("▶  スタート", self.colors["primary"], 56)
        start_btn.clicked.connect(self.start_timer)
        btn_vlayout.addWidget(start_btn)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        stop_btn = self._make_action_btn("■  ストップ", self.colors["danger"], 50)
        stop_btn.clicked.connect(self.stop_timer)
        reset_btn = self._make_action_btn("↺  リセット", self.colors["neutral"], 50)
        reset_btn.clicked.connect(self.reset_timer)
        btn_row.addWidget(stop_btn)
        btn_row.addWidget(reset_btn)
        btn_vlayout.addLayout(btn_row)

        # center the btn_container
        h_wrap = QHBoxLayout()
        h_wrap.addStretch()
        h_wrap.addWidget(btn_container)
        h_wrap.addStretch()
        layout.addLayout(h_wrap)

        self.stacked_widget.addWidget(screen)
        self.screens["timer"] = screen

    def preview_sound(self):
        if HAS_WINSOUND:
            target = self.sounds[self.sound_combo.currentText()]
            winsound.PlaySound(target, winsound.SND_ALIAS | winsound.SND_ASYNC)

    def start_timer(self):
        if self.timer_worker and self.timer_worker.isRunning():
            return
        try:
            seconds = int(self.e_min.text()) * 60 + int(self.e_sec.text())
            if seconds <= 0:
                return

            self.timer_worker = TimerWorker(seconds)
            self.timer_worker.tick_signal.connect(self.update_timer_display)
            self.timer_worker.timeout_signal.connect(self.timer_timeout)
            self.timer_worker.start()
        except ValueError:
            pass

    def update_timer_display(self, secs):
        self.timer_display.setText(f"{secs//60:02d}:{secs%60:02d}")

    def timer_timeout(self):
        self.timer_display.setText("00:00")
        if HAS_WINSOUND:
            target = self.sounds[self.sound_combo.currentText()]
            winsound.PlaySound(target, winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_LOOP)
        QMessageBox.information(self, "Time Up", "時間になりました！")
        if HAS_WINSOUND:
            winsound.PlaySound(None, winsound.SND_PURGE)

    def stop_timer(self):
        if self.timer_worker:
            self.timer_worker.stop()
        if HAS_WINSOUND:
            winsound.PlaySound(None, winsound.SND_PURGE)

    def reset_timer(self):
        self.stop_timer()
        self.timer_display.setText("00:00")
        self.e_min.setText("0")
        self.e_sec.setText("00")


    # --- 2. メモ帳機能 ---
    def create_memo_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = self._make_header_bar("メモ", self.back_to_selector)
        layout.addWidget(header)

        # タブ行: フォルダタブ + 新規ボタンを同じ行に
        tab_row = QWidget()
        tab_row_layout = QHBoxLayout(tab_row)
        tab_row_layout.setContentsMargins(0, 0, 0, 0)
        tab_row_layout.setSpacing(6)

        tab_scroll = QScrollArea()
        tab_scroll.setFixedHeight(46)
        tab_scroll.setWidgetResizable(True)
        tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tab_scroll.setStyleSheet("border: none; background: transparent;")

        self.tab_widget = QWidget()
        self.tab_layout = QHBoxLayout(self.tab_widget)
        self.tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_layout.setSpacing(6)
        self.tab_layout.setAlignment(Qt.AlignLeft)
        tab_scroll.setWidget(self.tab_widget)
        tab_row_layout.addWidget(tab_scroll)

        add_btn = QPushButton("+")
        add_btn.setFixedSize(44, 44)
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['accent']};
                color: #1E1E2E;
                font-size: 22px;
                font-weight: 700;
                border: none;
                border-radius: 22px;
            }}
            QPushButton:hover {{
                background-color: {self._lighten(self.colors['accent'])};
            }}
        """)
        add_btn.clicked.connect(self.add_folder)
        tab_row_layout.addWidget(add_btn)
        layout.addWidget(tab_row)

        # テキストエリア
        self.memo_text_widget = QTextEdit()
        self.memo_text_widget.setFont(QFont("Meiryo UI", 15))
        self.memo_text_widget.setPlaceholderText("ここにメモを入力...")
        self.memo_text_widget.textChanged.connect(self.save_memo_content)
        layout.addWidget(self.memo_text_widget, stretch=1)

        # 下部ツールバー
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        rename_btn = self._make_action_btn("✏  名前変更", self.colors["primary"], 48)
        rename_btn.clicked.connect(self.rename_current_folder)
        bottom_bar.addWidget(rename_btn)

        bottom_bar.addStretch()

        hint_lbl = QLabel("タブ右クリックで削除")
        hint_lbl.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 12px;")
        bottom_bar.addWidget(hint_lbl)

        layout.addLayout(bottom_bar)

        self.stacked_widget.addWidget(screen)
        self.screens["memo"] = screen

    def draw_tabs(self):
        while self.tab_layout.count():
            child = self.tab_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for name in self.memo_data.keys():
            is_active = (name == self.current_memo_folder)
            bg = self.colors["tab_active"] if is_active else self.colors["tab_inactive"]
            fg = "#1E1E2E" if is_active else self.colors["text_sub"]

            btn = QPushButton(name)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setFixedHeight(42)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {fg};
                    font-family: 'Meiryo UI', 'Segoe UI', sans-serif;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 21px;
                    padding: 8px 22px;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {'#45475A' if not is_active else bg};
                }}
            """)
            btn.clicked.connect(lambda checked=False, n=name: self.change_folder(n))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, n=name: self.delete_folder(n))

            self.tab_layout.addWidget(btn)

    def load_current_memo_text(self):
        try:
            self.memo_text_widget.textChanged.disconnect(self.save_memo_content)
        except RuntimeError:
            pass
        self.memo_text_widget.setPlainText(self.memo_data.get(self.current_memo_folder, ""))
        self.memo_text_widget.textChanged.connect(self.save_memo_content)

    def change_folder(self, name):
        self.current_memo_folder = name
        self.draw_tabs()
        self.load_current_memo_text()

    def save_memo_content(self):
        if hasattr(self, 'memo_text_widget'):
            self.memo_data[self.current_memo_folder] = self.memo_text_widget.toPlainText()

    def add_folder(self):
        dialog = StyledInputDialog("新しいフォルダ", "フォルダ名を入力してください", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            res = dialog.get_value().strip()
            if res and res not in self.memo_data:
                self.memo_data[res] = ""
                self.current_memo_folder = res
                self.draw_tabs()
                self.load_current_memo_text()

    def rename_current_folder(self):
        old_name = self.current_memo_folder
        dialog = StyledInputDialog("フォルダ名変更", f"「{old_name}」の新しい名前を入力", old_name, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            res = dialog.get_value().strip()
            if res and res != old_name:
                if res in self.memo_data:
                    QMessageBox.warning(self, "警告", "既に同じ名前のフォルダが存在します")
                    return
                new_memo_data = {}
                for k, v in self.memo_data.items():
                    if k == old_name:
                        new_memo_data[res] = v
                    else:
                        new_memo_data[k] = v
                self.memo_data = new_memo_data
                self.current_memo_folder = res
                self.draw_tabs()

    def delete_folder(self, name):
        if len(self.memo_data) <= 1:
            QMessageBox.warning(self, "警告", "最後のフォルダは削除できません")
            return

        ret = QMessageBox.question(self, "確認", f"フォルダ「{name}」を削除しますか？", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            del self.memo_data[name]
            if self.current_memo_folder == name:
                self.current_memo_folder = list(self.memo_data.keys())[0]
            self.draw_tabs()
            self.load_current_memo_text()


    # --- 3. セキュリティ強化メモ (Vault) ---
    def handle_vault_navigation(self):
        if self.is_authenticated:
            self.change_screen("vault_inside")
            return

        if not self.master_hash:
            self.setup_vault_first_time()
            return

        if self.birth_hash is None:
            dialog = StyledInputDialog("初期設定", "リセット用の生年月日を登録してください\n(8桁: 19950510等)", parent=self)
            if dialog.exec_() == QDialog.Accepted:
                b1 = dialog.get_value().strip()
                if b1 and len(b1) == 8 and b1.isdigit():
                    self.birth_hash = hashlib.sha256(b1.encode()).hexdigest()
                    self.save_all_data()
                    QMessageBox.information(self, "成功", "生年月日を登録しました。")
                    self.change_screen("vault_auth")
                else:
                    QMessageBox.warning(self, "警告", "正しい形式(8桁の数字)で入力してください。")
                    self.back_to_selector()
            return

        self.change_screen("vault_auth")

    def setup_vault_first_time(self):
        d1 = StyledInputDialog("設定", "新しいパスワード", is_password=True, parent=self)
        if d1.exec_() != QDialog.Accepted or not d1.get_value():
            self.back_to_selector()
            return

        d2 = StyledInputDialog("設定", "生年月日 (8桁: 19950510等)", parent=self)
        if d2.exec_() == QDialog.Accepted:
            b1 = d2.get_value().strip()
            if b1 and len(b1) == 8 and b1.isdigit():
                self.master_hash = hashlib.sha256(d1.get_value().encode()).hexdigest()
                self.birth_hash = hashlib.sha256(b1.encode()).hexdigest()
                self.save_all_data()
                QMessageBox.information(self, "成功", "初期設定が完了しました。")
                self.handle_vault_navigation()
            else:
                QMessageBox.critical(self, "エラー", "生年月日は8桁の数字で入力してください。")
                self.back_to_selector()

    def create_vault_auth_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = self._make_header_bar("セキュリティメモ", self.back_to_selector)
        layout.addWidget(header)

        layout.addStretch()

        auth_card = QWidget()
        auth_card.setStyleSheet(f"""
            background-color: {self.colors['card_bg']};
            border-radius: 16px;
            border: 1px solid #45475A;
        """)
        auth_card.setMaximumWidth(420)
        auth_card.setMinimumWidth(300)
        auth_layout = QVBoxLayout(auth_card)
        auth_layout.setContentsMargins(32, 36, 32, 32)
        auth_layout.setSpacing(18)
        auth_layout.setAlignment(Qt.AlignCenter)

        icon_lbl = QLabel("🔒")
        icon_lbl.setStyleSheet("font-size: 40px; border: none;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        auth_layout.addWidget(icon_lbl)

        lbl = QLabel("パスワードを入力")
        lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {self.colors['text_main']}; border: none;")
        lbl.setAlignment(Qt.AlignCenter)
        auth_layout.addWidget(lbl)

        self.pw_entry = QLineEdit()
        self.pw_entry.setEchoMode(QLineEdit.Password)
        self.pw_entry.setPlaceholderText("パスワード")
        self.pw_entry.setFixedHeight(48)
        auth_layout.addWidget(self.pw_entry)

        login_btn = self._make_action_btn("ログイン", self.colors["primary"], 52)
        login_btn.clicked.connect(self.check_vault_password)
        auth_layout.addWidget(login_btn)

        reset_btn = QPushButton("パスワードを忘れた方はこちら")
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                color: {self.colors['text_sub']};
                font-size: 13px;
                border: none;
                background: transparent;
                padding: 8px;
            }}
            QPushButton:hover {{
                color: {self.colors['primary']};
            }}
        """)
        reset_btn.setCursor(QCursor(Qt.PointingHandCursor))
        reset_btn.clicked.connect(self.reset_vault_password)
        auth_layout.addWidget(reset_btn, alignment=Qt.AlignCenter)

        layout.addWidget(auth_card, alignment=Qt.AlignCenter)
        layout.addStretch()
        self.stacked_widget.addWidget(screen)
        self.screens["vault_auth"] = screen

    def check_vault_password(self):
        h = hashlib.sha256(self.pw_entry.text().encode()).hexdigest()
        if h == self.master_hash:
            self.is_authenticated = True
            self.pw_entry.clear()
            self.change_screen("vault_inside")
        else:
            QMessageBox.critical(self, "エラー", "パスワードが違います")

    def reset_vault_password(self):
        dialog = StyledInputDialog("リセット", "登録した生年月日(8桁)を入力", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            if hashlib.sha256(dialog.get_value().encode()).hexdigest() == self.birth_hash:
                new_p = StyledInputDialog("リセット", "新しいパスワードを再設定", is_password=True, parent=self)
                if new_p.exec_() == QDialog.Accepted and new_p.get_value():
                    self.master_hash = hashlib.sha256(new_p.get_value().encode()).hexdigest()
                    self.save_all_data()
                    QMessageBox.information(self, "成功", "パスワードを更新しました。")
                    self.is_authenticated = False
                    self.change_screen("vault_auth")
            else:
                QMessageBox.critical(self, "エラー", "生年月日が一致しません")

    def create_vault_inside_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        def logout():
            self.is_authenticated = False
            self.back_to_selector()

        logout_btn = self._make_action_btn("🔓 ログアウト", self.colors["btn_back"], 40)
        logout_btn.setFixedWidth(160)
        header = self._make_header_bar("セキュリティメモ", logout, extra_widgets=[])
        layout.addWidget(header)

        # リスト領域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.vault_list_widget = QWidget()
        self.vault_list_layout = QVBoxLayout(self.vault_list_widget)
        self.vault_list_layout.setAlignment(Qt.AlignTop)
        self.vault_list_layout.setSpacing(10)
        self.vault_list_layout.setContentsMargins(4, 8, 4, 8)
        scroll.setWidget(self.vault_list_widget)
        layout.addWidget(scroll, stretch=1)

        # 追加ボタン
        add_btn = self._make_action_btn("＋  セキュリティメモを追加", self.colors["accent"], 56)
        add_btn.clicked.connect(self.add_vault_item)
        layout.addWidget(add_btn)

        self.stacked_widget.addWidget(screen)
        self.screens["vault_inside"] = screen

    def add_vault_item(self):
        t_diag = StyledInputDialog("新規項目", "項目名を入力", parent=self)
        if t_diag.exec_() == QDialog.Accepted and t_diag.get_value():
            p_diag = StyledInputDialog("新規メモ", "暗号化メモを入力", parent=self)
            if p_diag.exec_() == QDialog.Accepted:
                self.vault_items.append({"title": t_diag.get_value(), "pass": p_diag.get_value(), "show": False})
                self.refresh_vault()

    def refresh_vault(self):
        while self.vault_list_layout.count():
            child = self.vault_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for i, item in enumerate(self.vault_items):
            row = QWidget()
            row.setStyleSheet(f"""
                QWidget {{
                    background-color: {self.colors['card_bg']};
                    border-radius: 12px;
                    border: 1px solid #45475A;
                }}
            """)
            row.setMinimumHeight(64)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 12, 12, 12)
            row_layout.setSpacing(10)

            lbl_title = QLabel(item['title'])
            lbl_title.setMinimumWidth(120)
            lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {self.colors['text_main']}; border: none;")

            p_disp = item["pass"] if item.get("show") else "••••••••"
            lbl_pass = QLabel(p_disp)
            lbl_pass.setStyleSheet(f"font-family: 'Consolas', monospace; color: {self.colors['text_sub']}; font-size: 14px; border: none;")

            row_layout.addWidget(lbl_title)
            row_layout.addWidget(lbl_pass)
            row_layout.addStretch()

            def toggle_show(idx=i):
                self.vault_items[idx]["show"] = not self.vault_items[idx]["show"]
                self.refresh_vault()

            def rename_item(idx=i):
                d = StyledInputDialog("項目名変更", "新しい項目名を入力", self.vault_items[idx]["title"], parent=self)
                if d.exec_() == QDialog.Accepted and d.get_value().strip():
                    self.vault_items[idx]["title"] = d.get_value()
                    self.refresh_vault()

            def delete_item(idx=i):
                ret = QMessageBox.question(self, "確認", f"「{self.vault_items[idx]['title']}」を削除しますか？", QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.Yes:
                    self.vault_items.pop(idx)
                    self.refresh_vault()

            action_style = """
                QPushButton {{
                    color: {color};
                    font-weight: 600;
                    font-size: 13px;
                    background: transparent;
                    border: 1px solid {color};
                    border-radius: 8px;
                    padding: 8px 14px;
                    min-height: 36px;
                }}
                QPushButton:hover {{
                    background: {color};
                    color: #1E1E2E;
                }}
            """

            v_btn = QPushButton("👁 表示" if not item.get("show") else "🙈 隠す")
            v_btn.setStyleSheet(action_style.format(color=self.colors['primary']))
            v_btn.setCursor(QCursor(Qt.PointingHandCursor))
            v_btn.clicked.connect(toggle_show)

            e_btn = QPushButton("✏ 編集")
            e_btn.setStyleSheet(action_style.format(color=self.colors['success']))
            e_btn.setCursor(QCursor(Qt.PointingHandCursor))
            e_btn.clicked.connect(rename_item)

            d_btn = QPushButton("🗑 削除")
            d_btn.setStyleSheet(action_style.format(color=self.colors['danger']))
            d_btn.setCursor(QCursor(Qt.PointingHandCursor))
            d_btn.clicked.connect(delete_item)

            row_layout.addWidget(v_btn)
            row_layout.addWidget(e_btn)
            row_layout.addWidget(d_btn)

            self.vault_list_layout.addWidget(row)
        self.save_all_data()


    # --- 4. TO DO リスト機能 ---
    def create_todo_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = self._make_header_bar("TO DO", self.back_to_selector)
        layout.addWidget(header)

        # リスト領域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.todo_list_widget = QWidget()
        self.todo_list_layout = QVBoxLayout(self.todo_list_widget)
        self.todo_list_layout.setAlignment(Qt.AlignTop)
        self.todo_list_layout.setSpacing(10)
        self.todo_list_layout.setContentsMargins(4, 8, 4, 8)
        scroll.setWidget(self.todo_list_widget)
        layout.addWidget(scroll, stretch=1)

        # 追加ボタン
        add_btn = self._make_action_btn("＋  タスクを追加", self.colors["accent"], 56)
        add_btn.clicked.connect(self.add_todo_item)
        layout.addWidget(add_btn)

        self.stacked_widget.addWidget(screen)
        self.screens["todo"] = screen

    def add_todo_item(self):
        dialog = StyledInputDialog("タスク追加", "タスク内容を入力してください", parent=self)
        if dialog.exec_() == QDialog.Accepted and dialog.get_value().strip():
            self.todo_items.append(dialog.get_value().strip())
            self.refresh_todo()

    def refresh_todo(self):
        while self.todo_list_layout.count():
            child = self.todo_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for i, task in enumerate(self.todo_items):
            row = QWidget()
            row.setStyleSheet(f"""
                QWidget {{
                    background-color: {self.colors['card_bg']};
                    border-radius: 12px;
                    border: 1px solid #45475A;
                }}
            """)
            row.setFixedHeight(64)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(18, 10, 14, 10)

            lbl = QLabel(task)
            lbl.setStyleSheet(f"font-size: 15px; color: {self.colors['text_main']}; border: none;")
            row_layout.addWidget(lbl)
            row_layout.addStretch()

            done_btn = QPushButton("✓ 完了")
            done_btn.setFixedHeight(40)
            done_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {self.colors['success']};
                    font-weight: 600;
                    font-size: 14px;
                    background: transparent;
                    border: 2px solid {self.colors['success']};
                    border-radius: 10px;
                    padding: 8px 18px;
                }}
                QPushButton:hover {{
                    background: {self.colors['success']};
                    color: #1E1E2E;
                }}
            """)
            done_btn.setCursor(QCursor(Qt.PointingHandCursor))
            done_btn.clicked.connect(lambda checked=False, idx=i: [self.todo_items.pop(idx), self.refresh_todo()])
            row_layout.addWidget(done_btn)

            self.todo_list_layout.addWidget(row)
        self.save_all_data()


    # --- 5. カレンダー機能 ---
    def create_calendar_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = self._make_header_bar("カレンダー", self.back_to_selector)
        layout.addWidget(header)

        # 月ナビゲーション
        ctrl_f = QWidget()
        ctrl_f.setFixedHeight(56)
        ctrl_f.setStyleSheet(f"""
            QWidget {{
                background-color: {self.colors['card_bg']};
                border-radius: 14px;
                border: 1px solid #45475A;
            }}
        """)
        ctrl_layout = QHBoxLayout(ctrl_f)
        ctrl_layout.setContentsMargins(8, 8, 8, 8)

        prev_btn = QPushButton("◀  前月")
        prev_btn.setFixedHeight(44)
        prev_btn.setFixedWidth(100)
        prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        prev_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.colors['primary']};
                font-size: 16px;
                font-weight: 700;
                border: none;
                padding: 8px 16px;
                border-radius: 10px;
            }}
            QPushButton:hover {{ background: #45475A; }}
        """)
        prev_btn.clicked.connect(self.prev_month)

        self.cal_label = QLabel()
        self.cal_label.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 700;
            color: {self.colors['text_main']};
            border: none;
        """)
        self.cal_label.setAlignment(Qt.AlignCenter)

        next_btn = QPushButton("次月  ▶")
        next_btn.setFixedHeight(44)
        next_btn.setFixedWidth(100)
        next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        next_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.colors['primary']};
                font-size: 16px;
                font-weight: 700;
                border: none;
                padding: 8px 16px;
                border-radius: 10px;
            }}
            QPushButton:hover {{ background: #45475A; }}
        """)
        next_btn.clicked.connect(self.next_month)

        ctrl_layout.addWidget(prev_btn)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.cal_label)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(next_btn)
        layout.addWidget(ctrl_f)

        # カレンダーグリッド
        card = QWidget()
        card.setStyleSheet(f"""
            background-color: {self.colors['card_bg']};
            border-radius: 14px;
            border: 1px solid #45475A;
            padding: 14px;
        """)
        self.calendar_grid_layout = QGridLayout(card)
        self.calendar_grid_layout.setSpacing(5)
        self.calendar_grid_layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(card, stretch=1)

        self.stacked_widget.addWidget(screen)
        self.screens["calendar"] = screen

    def draw_calendar(self):
        self.cal_label.setText(f"{self.cur_year}年 {self.cur_month}月")

        while self.calendar_grid_layout.count():
            child = self.calendar_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        days = ["月", "火", "水", "木", "金", "土", "日"]
        day_colors = [self.colors["text_sub"]] * 5 + ["#2563EB", "#DC2626"]
        for i, d in enumerate(days):
            lbl = QLabel(d)
            lbl.setFixedSize(64, 36)
            lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {day_colors[i]}; background: transparent; border: none;")
            lbl.setAlignment(Qt.AlignCenter)
            self.calendar_grid_layout.addWidget(lbl, 0, i)

        cal = calendar.monthcalendar(self.cur_year, self.cur_month)
        today = datetime.now()

        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0:
                    continue
                key = f"{self.cur_year}-{self.cur_month}-{day}"
                is_today = (day == today.day and self.cur_month == today.month and self.cur_year == today.year)

                if is_today:
                    bg, fg, border = self.colors["primary"], "#1E1E2E", "none"
                elif key in self.calendar_notes:
                    bg, fg, border = "#45475A", self.colors["accent"], f"2px solid {self.colors['accent']}"
                else:
                    bg, fg, border = self.colors["bg_base"], self.colors["text_main"], "1px solid #45475A"

                btn = QPushButton(str(day))
                btn.setFixedSize(64, 48)
                btn.setCursor(QCursor(Qt.PointingHandCursor))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        color: {fg};
                        font-size: 14px;
                        font-weight: 600;
                        border: {border};
                        border-radius: 10px;
                    }}
                    QPushButton:hover {{
                        background-color: #45475A;
                        color: {self.colors['primary']};
                    }}
                """)
                btn.clicked.connect(lambda checked=False, d=day: self.edit_day_memo(d))
                self.calendar_grid_layout.addWidget(btn, r + 1, c)

    def prev_month(self):
        if self.cur_month == 1:
            self.cur_month = 12
            self.cur_year -= 1
        else:
            self.cur_month -= 1
        self.draw_calendar()

    def next_month(self):
        if self.cur_month == 12:
            self.cur_month = 1
            self.cur_year += 1
        else:
            self.cur_month += 1
        self.draw_calendar()

    def edit_day_memo(self, day):
        key = f"{self.cur_year}-{self.cur_month}-{day}"
        old_val = self.calendar_notes.get(key, "")

        dialog = StyledInputDialog(f"DATE: {day}", "メモを入力", old_val, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            res = dialog.get_value().strip()
            if res == "":
                self.calendar_notes.pop(key, None)
            else:
                self.calendar_notes[key] = res
            self.draw_calendar()


class MainWindowContainer(MultiApp):
    def closeEvent(self, event):
        self.stop_timer()
        self.save_all_data()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindowContainer()
    window.show()
    sys.exit(app.exec_())
