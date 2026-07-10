import sys
import json
import os
import shutil
import time #時間関連の機能をモジュール
import hashlib
from datetime import datetime
import calendar #カレンダー機能をモジュール

# PySide6 モジュールのインポート
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QStackedWidget, QTextEdit,
    QScrollArea, QDialog, QComboBox, QMessageBox, QGridLayout, QCheckBox,
    QSplitter, QSizePolicy
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


# --- カスタムボタンスタイル ---
class StyledButton(QPushButton):
    def __init__(self, text, base_color, parent=None, width=None, compact=False):
        super().__init__(text, parent)
        self.base_color = base_color
        self.setCursor(QCursor(Qt.PointingHandCursor))
        if width:
            self.setFixedWidth(width)

        hover_color = self.lighten(base_color)
        pad = "11px 22px" if compact else "14px 30px"
        font_size = "14px" if compact else "16px"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {base_color};
                color: white;
                font-family: 'Meiryo UI', 'Segoe UI', sans-serif;
                font-size: {font_size};
                font-weight: 600;
                border-radius: 12px;
                padding: {pad};
                border: none;
                min-height: 38px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """)

    def lighten(self, color):
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        r = min(255, r + 35)
        g = min(255, g + 35)
        b = min(255, b + 35)
        return f"#{r:02x}{g:02x}{b:02x}"


# --- カスタム入力ダイアログ ---
class StyledInputDialog(QDialog):
    def __init__(self, title, prompt, initial_value="", is_password=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setStyleSheet("""
            QDialog {
                background-color: #F4F6FB;
                border: 1px solid #D4D8E3;
            }
        """)
        self.setWindowModality(Qt.WindowModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        lbl = QLabel(prompt)
        lbl.setStyleSheet("""
            color: #3B3F51;
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
                background-color: #F4F6FB;
                color: #3B3F51;
                font-family: 'Meiryo UI', 'Segoe UI', sans-serif;
                font-size: 16px;
                border: 2px solid #D4D8E3;
                border-radius: 12px;
                padding: 14px 18px;
                min-height: 22px;
            }
            QLineEdit:focus {
                border: 2px solid #1E66F5;
            }
        """)
        if is_password:
            self.entry.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.entry)

        btn = StyledButton("決定", "#1E66F5")
        btn.setFixedHeight(50)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_value(self):
        return self.entry.text()


# --- 参照するメモの複数選択ダイアログ ---
class ReferenceSelectDialog(QDialog):
    def __init__(self, folder_names, checked_names, current_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("参照するメモを選択")
        self.setMinimumWidth(360)
        self.setStyleSheet("""
            QDialog {
                background-color: #F4F6FB;
                border: 1px solid #D4D8E3;
            }
        """)
        self.setWindowModality(Qt.WindowModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)

        lbl = QLabel("参照しながら書きたいメモにチェックしてください")
        lbl.setStyleSheet("color: #3B3F51; font-size: 15px; font-weight: 600;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.checkboxes = {}
        for name in folder_names:
            label = f"{name}（編集中）" if name == current_name else name
            cb = QCheckBox(label)
            cb.setChecked(name in checked_names)
            cb.setStyleSheet("color: #3B3F51; font-size: 14px; padding: 4px 0;")
            layout.addWidget(cb)
            self.checkboxes[name] = cb

        btn = StyledButton("決定", "#1E66F5")
        btn.setFixedHeight(48)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def selected_names(self):
        return [name for name, cb in self.checkboxes.items() if cb.isChecked()]


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

        # 画面管理用のスタックウィジェット
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.timer_worker = None

        # メモ入力後、少し間が空いたら自動でディスクに保存するためのタイマー
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self.save_all_data)

        # 全ての画面レイアウトをはじめに構築して固定配置（バグの根本原因の修正）
        self.screens = {}
        self.create_all_screens()

    def init_style(self):
        self.colors = {
            "bg_base": "#F4F6FB",
            "bg_surface": "#E9ECF3",
            "card_bg": "#FFFFFF",
            "primary": "#1E66F5",
            "accent": "#8839EF",
            "success": "#3FA34D",
            "danger": "#D20F39",
            "neutral": "#8C90A4",
            "text_main": "#3B3F51",
            "text_sub": "#6C7086",
            "tab_active": "#1E66F5",
            "tab_inactive": "#D4D8E3",
            "btn_back": "#6C7086"
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
                border: 2px solid #D4D8E3;
                border-radius: 14px;
                padding: 18px;
                selection-background-color: #D4D8E3;
            }}
            QTextEdit:focus {{
                border: 2px solid {self.colors['primary']};
            }}
            QLineEdit {{
                background-color: {self.colors['card_bg']};
                color: {self.colors['text_main']};
                font-size: 15px;
                border: 2px solid #D4D8E3;
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
                border: 2px solid #D4D8E3;
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
                selection-background-color: #D4D8E3;
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
        self.reference_folders = []
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
        
        # 画面切り替え時、特定の画面なら動的に要素をリフレッシュする
        if screen_key == "memo":
            self.draw_tabs()
            self.load_current_memo_text()
            self.refresh_reference_panel()
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
        # 起動時にすべての画面パーツを生成して登録しておくことで遷移バグを完全解消
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
        container.setMaximumWidth(800)
        container.setMinimumWidth(500)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        title = QLabel("Multi Memo")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            color: {self.colors['primary']};
            font-size: 36px;
            font-weight: 700;
            padding-bottom: 4px;
        """)
        layout.addWidget(title)

        subtitle = QLabel("多機能メモツール")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 15px; padding-bottom: 32px;")
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(16)

        opts = [
            ("⏲", "タイマー", "時間を管理", lambda: self.change_screen("timer"), self.colors["primary"]),
            ("📝", "TO DO", "タスク管理", lambda: self.change_screen("todo"), self.colors["accent"]),
            ("📄", "メモ", "テキスト入力", lambda: self.change_screen("memo"), self.colors["success"]),
            ("📅", "カレンダー", "予定を記録", lambda: self.change_screen("calendar"), self.colors["neutral"]),
        ]

        for idx, (icon, label, desc, slot, color) in enumerate(opts):
            btn = QPushButton(f"{icon}\n{label}")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setMinimumHeight(160)
            btn.setMinimumWidth(180)
            btn.setToolTip(desc)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.colors['card_bg']};
                    color: {color};
                    font-size: 24px;
                    font-weight: 700;
                    border: 2px solid #D4D8E3;
                    border-radius: 22px;
                    padding: 24px;
                }}
                QPushButton:hover {{
                    background-color: #D4D8E3;
                    border-color: {color};
                }}
            """)
            btn.clicked.connect(slot)
            grid.addWidget(btn, idx // 2, idx % 2)

        layout.addLayout(grid)
        layout.addSpacing(18)

        vault_btn = QPushButton("🔒  セキュリティメモ")
        vault_btn.setCursor(QCursor(Qt.PointingHandCursor))
        vault_btn.setFixedHeight(72)
        vault_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['card_bg']};
                color: {self.colors['danger']};
                font-size: 20px;
                font-weight: 700;
                border: 2px solid {self.colors['danger']};
                border-radius: 16px;
                padding: 18px 28px;
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
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)

        back_btn = StyledButton("← 戻る", self.colors["btn_back"], compact=True)
        back_btn.clicked.connect(self.back_to_selector)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        layout.addStretch(2)

        self.timer_display = QLabel("00:00")
        self.timer_display.setStyleSheet(f"""
            font-family: 'Consolas', 'SF Mono', monospace;
            font-size: 96px;
            font-weight: 700;
            color: {self.colors['primary']};
        """)
        self.timer_display.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timer_display)

        layout.addSpacing(24)

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
                border: 2px solid #D4D8E3;
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
        layout.addWidget(in_f)

        layout.addSpacing(16)

        sound_f = QWidget()
        sound_layout = QHBoxLayout(sound_f)
        sound_layout.setAlignment(Qt.AlignCenter)
        sound_layout.setSpacing(10)
        self.sound_combo = QComboBox()
        self.sound_combo.addItems(list(self.sounds.keys()))
        self.sound_combo.setFixedWidth(160)
        self.sound_combo.setFixedHeight(40)
        preview_btn = StyledButton("♪ 試聴", self.colors["neutral"], compact=True)
        preview_btn.clicked.connect(self.preview_sound)
        sound_layout.addWidget(self.sound_combo)
        sound_layout.addWidget(preview_btn)
        layout.addWidget(sound_f)

        layout.addStretch(3)

        # 操作ボタンを下部に固定配置
        btn_bar = QWidget()
        btn_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {self.colors['card_bg']};
                border-radius: 16px;
                border: 1px solid #D4D8E3;
            }}
        """)
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(12, 12, 12, 12)
        btn_layout.setSpacing(10)

        start_btn = StyledButton("▶ スタート", self.colors["primary"])
        start_btn.clicked.connect(self.start_timer)
        stop_btn = StyledButton("■ ストップ", self.colors["danger"])
        stop_btn.clicked.connect(self.stop_timer)
        reset_btn = StyledButton("↺ リセット", self.colors["neutral"])
        reset_btn.clicked.connect(self.reset_timer)

        for b in (start_btn, stop_btn, reset_btn):
            b.setFixedHeight(52)
            btn_layout.addWidget(b)

        layout.addWidget(btn_bar)
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

        # ヘッダー: 戻るボタンのみ（シンプル）
        back_btn = StyledButton("← 戻る", self.colors["btn_back"], compact=True)
        back_btn.clicked.connect(self.back_to_selector)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        # タブ行: フォルダタブ + 新規ボタンを同じ行に
        tab_row = QWidget()
        tab_row_layout = QHBoxLayout(tab_row)
        tab_row_layout.setContentsMargins(0, 0, 0, 0)
        tab_row_layout.setSpacing(6)

        tab_scroll = QScrollArea()
        tab_scroll.setFixedHeight(42)
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
        add_btn.setFixedSize(40, 40)
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['accent']};
                color: #1E1E2E;
                font-size: 20px;
                font-weight: 700;
                border: none;
                border-radius: 20px;
            }}
            QPushButton:hover {{
                background-color: {StyledButton.lighten(None, self.colors['accent'])};
            }}
        """)
        add_btn.clicked.connect(self.add_folder)
        tab_row_layout.addWidget(add_btn)

        ref_select_btn = StyledButton("📚 参照するメモを選択", self.colors["accent"], compact=True)
        ref_select_btn.clicked.connect(self.open_reference_selector)
        tab_row_layout.addWidget(ref_select_btn)
        layout.addWidget(tab_row)

        # メイン領域: 左にエディタ、右に参照メモパネル（境界をドラッグして幅を調整できる）
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(10)
        content_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: #D4D8E3;
                border-radius: 4px;
            }}
        """)

        editor_widget = QWidget()
        editor_col = QVBoxLayout(editor_widget)
        editor_col.setContentsMargins(0, 0, 0, 0)
        editor_col.setSpacing(10)

        # テキストエリア（メイン領域、最大限広く）
        self.memo_text_widget = QTextEdit()
        self.memo_text_widget.setFont(QFont("Meiryo UI", 15))
        self.memo_text_widget.setPlaceholderText("ここにメモを入力...")
        self.memo_text_widget.textChanged.connect(self.save_memo_content)
        editor_col.addWidget(self.memo_text_widget, stretch=1)

        # 下部ツールバー: フォルダ操作
        bottom_bar = QWidget()
        bottom_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {self.colors['card_bg']};
                border-radius: 12px;
                border: 1px solid #D4D8E3;
            }}
        """)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(12, 8, 12, 8)
        bottom_layout.setSpacing(8)

        rename_btn = StyledButton("✏ 名前変更", self.colors["primary"], compact=True)
        rename_btn.clicked.connect(self.rename_current_folder)
        bottom_layout.addWidget(rename_btn)
        bottom_layout.addStretch()

        hint_lbl = QLabel("タブ右クリックで削除")
        hint_lbl.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 12px; border: none;")
        bottom_layout.addWidget(hint_lbl)

        editor_col.addWidget(bottom_bar)
        content_splitter.addWidget(editor_widget)

        # 参照パネル: 選択した他のメモを読み取り専用で並べて表示
        ref_panel = QWidget()
        ref_panel.setMinimumWidth(320)
        ref_panel_layout = QVBoxLayout(ref_panel)
        ref_panel_layout.setContentsMargins(0, 0, 0, 0)
        ref_panel_layout.setSpacing(8)

        ref_title = QLabel("📚 参照中のメモ")
        ref_title.setStyleSheet(f"color: {self.colors['text_main']}; font-size: 15px; font-weight: 700; border: none;")
        ref_panel_layout.addWidget(ref_title)

        ref_hint = QLabel("↔ 境界線をドラッグすると幅を調整できます")
        ref_hint.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 12px; border: none;")
        ref_panel_layout.addWidget(ref_hint)

        ref_scroll = QScrollArea()
        ref_scroll.setWidgetResizable(True)
        ref_scroll.setStyleSheet("border: none; background: transparent;")
        ref_container = QWidget()
        self.reference_layout = QVBoxLayout(ref_container)
        self.reference_layout.setAlignment(Qt.AlignTop)
        self.reference_layout.setSpacing(10)
        ref_scroll.setWidget(ref_container)
        ref_panel_layout.addWidget(ref_scroll, stretch=1)

        content_splitter.addWidget(ref_panel)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 1)
        content_splitter.setSizes([560, 560])
        layout.addWidget(content_splitter, stretch=1)

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
            btn.setFixedHeight(40)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {fg};
                    font-family: 'Meiryo UI', 'Segoe UI', sans-serif;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 20px;
                    padding: 8px 20px;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {'#D4D8E3' if not is_active else bg};
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
        self.refresh_reference_panel()

    def save_memo_content(self):
        if hasattr(self, 'memo_text_widget'):
            self.memo_data[self.current_memo_folder] = self.memo_text_widget.toPlainText()
            self.autosave_timer.start(800)

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
                self.reference_folders = [res if n == old_name else n for n in self.reference_folders]
                self.draw_tabs()
                self.refresh_reference_panel()

    def delete_folder(self, name):
        if len(self.memo_data) <= 1:
            QMessageBox.warning(self, "警告", "既存 of メインフォルダは削除できません")
            return

        ret = QMessageBox.question(self, "確認", f"フォルダ「{name}」を削除しますか？", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            del self.memo_data[name]
            if self.current_memo_folder == name:
                self.current_memo_folder = list(self.memo_data.keys())[0]
            self.reference_folders = [n for n in self.reference_folders if n != name]
            self.draw_tabs()
            self.refresh_reference_panel()

    def open_reference_selector(self):
        dialog = ReferenceSelectDialog(
            list(self.memo_data.keys()), self.reference_folders, self.current_memo_folder, parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.reference_folders = dialog.selected_names()
            self.refresh_reference_panel()

    def refresh_reference_panel(self):
        if not hasattr(self, 'reference_layout'):
            return
        while self.reference_layout.count():
            child = self.reference_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        names = [n for n in self.reference_folders if n in self.memo_data]
        if not names:
            empty = QLabel("「📚 参照するメモを選択」から\n見ながら書きたいメモを選べます")
            empty.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 13px; border: none;")
            empty.setWordWrap(True)
            self.reference_layout.addWidget(empty)
            return

        for name in names:
            card = QWidget()
            card.setStyleSheet(f"""
                QWidget {{
                    background-color: {self.colors['card_bg']};
                    border-radius: 12px;
                    border: 1px solid #D4D8E3;
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(6)

            title = QLabel(name)
            title.setStyleSheet(f"color: {self.colors['accent']}; font-size: 14px; font-weight: 700; border: none;")
            card_layout.addWidget(title)

            content = QTextEdit()
            content.setPlainText(self.memo_data.get(name, ""))
            content.setReadOnly(True)
            content.setMinimumHeight(320)
            content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            content.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {self.colors['bg_surface']};
                    color: {self.colors['text_main']};
                    border: 1px solid #D4D8E3;
                    border-radius: 8px;
                    padding: 10px;
                    font-size: 15px;
                    line-height: 1.6;
                }}
            """)
            card_layout.addWidget(content)

            self.reference_layout.addWidget(card)


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
        layout.setContentsMargins(24, 20, 24, 20)

        back_btn = StyledButton("← 戻る", self.colors["btn_back"], compact=True)
        back_btn.clicked.connect(self.back_to_selector)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        layout.addStretch()

        auth_card = QWidget()
        auth_card.setStyleSheet(f"""
            background-color: {self.colors['card_bg']};
            border-radius: 16px;
            border: 1px solid #D4D8E3;
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
        self.pw_entry.setFixedHeight(44)
        auth_layout.addWidget(self.pw_entry)

        login_btn = StyledButton("ログイン", self.colors["primary"])
        login_btn.setFixedHeight(48)
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

        # ヘッダー
        back_btn = StyledButton("🔓 ログアウト", self.colors["btn_back"], compact=True)
        back_btn.clicked.connect(logout)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        # リスト領域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.vault_list_widget = QWidget()
        self.vault_list_layout = QVBoxLayout(self.vault_list_widget)
        self.vault_list_layout.setAlignment(Qt.AlignTop)
        self.vault_list_layout.setSpacing(8)
        self.vault_list_layout.setContentsMargins(4, 8, 4, 8)
        scroll.setWidget(self.vault_list_widget)
        layout.addWidget(scroll, stretch=1)

        # 追加ボタンを下部固定
        add_btn = StyledButton("＋ セキュリティメモを追加", self.colors["accent"])
        add_btn.setFixedHeight(52)
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
                    border: 1px solid #D4D8E3;
                }}
            """)
            row.setMinimumHeight(56)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 10, 12, 10)
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
                    padding: 6px 12px;
                    min-height: 32px;
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

        # ヘッダー
        back_btn = StyledButton("← 戻る", self.colors["btn_back"], compact=True)
        back_btn.clicked.connect(self.back_to_selector)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        # リスト領域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.todo_list_widget = QWidget()
        self.todo_list_layout = QVBoxLayout(self.todo_list_widget)
        self.todo_list_layout.setAlignment(Qt.AlignTop)
        self.todo_list_layout.setSpacing(8)
        self.todo_list_layout.setContentsMargins(4, 8, 4, 8)
        scroll.setWidget(self.todo_list_widget)
        layout.addWidget(scroll, stretch=1)

        # 追加ボタンを下部に固定（FABスタイル）
        add_btn = StyledButton("＋ タスクを追加", self.colors["accent"])
        add_btn.setFixedHeight(52)
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
                    border: 1px solid #D4D8E3;
                }}
            """)
            row.setFixedHeight(58)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(18, 10, 14, 10)

            lbl = QLabel(task)
            lbl.setStyleSheet(f"font-size: 15px; color: {self.colors['text_main']}; border: none;")
            row_layout.addWidget(lbl)
            row_layout.addStretch()

            done_btn = QPushButton("✓ 完了")
            done_btn.setFixedHeight(36)
            done_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {self.colors['success']};
                    font-weight: 600;
                    font-size: 14px;
                    background: transparent;
                    border: 1px solid {self.colors['success']};
                    border-radius: 8px;
                    padding: 6px 16px;
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

        back_btn = StyledButton("← 戻る", self.colors["btn_back"], compact=True)
        back_btn.clicked.connect(self.back_to_selector)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        # 月ナビゲーション
        ctrl_f = QWidget()
        ctrl_f.setStyleSheet(f"""
            QWidget {{
                background-color: {self.colors['card_bg']};
                border-radius: 12px;
                border: 1px solid #D4D8E3;
            }}
        """)
        ctrl_layout = QHBoxLayout(ctrl_f)
        ctrl_layout.setContentsMargins(8, 8, 8, 8)

        prev_btn = QPushButton("◀  前月")
        prev_btn.setFixedHeight(44)
        prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        prev_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.colors['primary']};
                font-size: 15px;
                font-weight: 600;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
            }}
            QPushButton:hover {{ background: #D4D8E3; }}
        """)
        prev_btn.clicked.connect(self.prev_month)

        self.cal_label = QLabel()
        self.cal_label.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {self.colors['text_main']};
            border: none;
        """)
        self.cal_label.setAlignment(Qt.AlignCenter)

        next_btn = QPushButton("次月  ▶")
        next_btn.setFixedHeight(44)
        next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        next_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.colors['primary']};
                font-size: 15px;
                font-weight: 600;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
            }}
            QPushButton:hover {{ background: #D4D8E3; }}
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
            border: 1px solid #D4D8E3;
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
        day_colors = [self.colors["text_sub"]] * 5 + ["#1E66F5", "#D20F39"]
        for i, d in enumerate(days):
            lbl = QLabel(d)
            lbl.setFixedSize(64, 36)
            lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {day_colors[i]};")
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
                    bg, fg, border = "#D4D8E3", self.colors["accent"], f"2px solid {self.colors['accent']}"
                else:
                    bg, fg, border = self.colors["bg_base"], self.colors["text_main"], "1px solid #D4D8E3"

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
                        background-color: #D4D8E3;
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
