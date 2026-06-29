import sys
import json
import os
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


# --- カスタムボタンスタイル (ホバーエフェクト付き) ---
class StyledButton(QPushButton):
    def __init__(self, text, base_color, parent=None, width=None):
        super().__init__(text, parent)
        self.base_color = base_color
        self.setCursor(QCursor(Qt.PointingHandCursor))
        if width:
            self.setFixedWidth(width)
        
        hover_color = self.lighten(base_color)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {base_color};
                color: white;
                font-family: 'Segoe UI';
                font-size: 18px;
                font-weight: bold;
                border-radius: 8px;
                padding: 18px 20px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """)

    def lighten(self, color):
        ov = {
            "#0047AB": "#1E90FF", 
            "#00A86B": "#3CB371", 
            "#2E8B57": "#3CB371", 
            "#DC143C": "#FF4500", 
            "#757575": "#9E9E9E", 
            "#E0E0E0": "#F5F5F5",
            "#555555": "#777777"  
        }
        return ov.get(color, color)


# --- カスタム入力ダイアログ ---
class StyledInputDialog(QDialog):
    def __init__(self, title, prompt, initial_value="", is_password=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 220)
        self.setStyleSheet("background-color: #FFFFFF;")
        self.setWindowModality(Qt.WindowModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        card = QWidget()
        card.setStyleSheet("background-color: #F5F5F5; border-radius: 6px;")
        card_layout = QVBoxLayout(card)
        
        lbl = QLabel(prompt)
        lbl.setStyleSheet("color: #212121; font-family: 'Segoe UI'; font-size: 14px;")
        lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(lbl)

        self.entry = QLineEdit()
        self.entry.setText(initial_value)
        self.entry.setStyleSheet("""
            QLineEdit {
                background-color: white;
                color: #212121;
                font-family: 'Segoe UI';
                font-size: 14px;
                border: 1px solid #757575;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        if is_password:
            self.entry.setEchoMode(QLineEdit.Password)
        card_layout.addWidget(self.entry)

        btn = StyledButton("決定", "#0047AB")
        btn.clicked.connect(self.accept)
        card_layout.addWidget(btn)

        layout.addWidget(card)

    def get_value(self):
        return self.entry.text()


# --- メインアプリケーションクラス ---
class MultiApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multifunctional Memo")
        self.resize(700, 850)
        
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.DATA_FILE = os.path.join(BASE_DIR, "memo_pro_data.json")
        self.VAULT_FILE = os.path.join(BASE_DIR, "vault_pro_data.json")

        self.init_style()
        self.load_all_data()

        # 画面管理用のスタックウィジェット
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.timer_worker = None

        # 全ての画面レイアウトをはじめに構築して固定配置（バグの根本原因の修正）
        self.screens = {}
        self.create_all_screens()

    def init_style(self):
        self.colors = {
            "bg_base": "#FFFFFF",      
            "card_bg": "#F5F5F5",      
            "primary": "#0047AB",      
            "accent": "#7F068A",      
            "success": "#2E8B57",      
            "danger": "#DC143C",       
            "neutral": "#757575",      
            "text_main": "#212121",    
            "text_sub": "#616161",     
            "tab_active": "#0047AB",   
            "tab_inactive": "#E0E0E0",
            "btn_back": "#555555"     
        }
        self.setStyleSheet(f"background-color: {self.colors['bg_base']};")

    def load_all_data(self):
        if os.path.exists(self.DATA_FILE):
            try:
                with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    self.todo_items = d.get("todo", [])
                    self.memo_data = d.get("memo", {"メイン": ""})
                    self.calendar_notes = d.get("calendar", {})
            except (json.JSONDecodeError, ValueError):
                self.todo_items, self.memo_data, self.calendar_notes = [], {"メイン": ""}, {}
        else:
            self.todo_items, self.memo_data, self.calendar_notes = [], {"メイン": ""}, {}

        if os.path.exists(self.VAULT_FILE):
            try:
                with open(self.VAULT_FILE, "r", encoding="utf-8") as f:
                    v = json.load(f)
                    self.master_hash = v.get("hash")
                    self.birth_hash = v.get("birth_hash")
                    self.vault_items = v.get("items", [])
            except (json.JSONDecodeError, ValueError):
                self.master_hash = None
                self.birth_hash = None
                self.vault_items = []
        else:
            self.master_hash, self.birth_hash, self.vault_items = None, None, []

        self.current_memo_folder = list(self.memo_data.keys())[0]
        self.is_authenticated = False
        self.cur_year, self.cur_month = datetime.now().year, datetime.now().month
        self.sounds = {"📢 警告音": "SystemHand", "🎵 標準音": "SystemAsterisk"}

    def save_all_data(self):
        data = {"todo": self.todo_items, "memo": self.memo_data, "calendar": self.calendar_notes}
        with open(self.DATA_FILE, "w", encoding="utf-8") as f: 
            json.dump(data, f, ensure_ascii=False, indent=4)
        vault = {"hash": self.master_hash, "birth_hash": self.birth_hash, "items": self.vault_items}
        with open(self.VAULT_FILE, "w", encoding="utf-8") as f: 
            json.dump(vault, f, ensure_ascii=False, indent=4)

    def change_screen(self, screen_key):
        self.save_all_data()
        
        # 画面切り替え時、特定の画面なら動的に要素をリフレッシュする
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

        layout = QVBoxLayout(screen)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(25)

        title = QLabel("多機能メモツール")
        title.setAlignment(Qt.AlignCenter)

        title.setStyleSheet(f"""
            color: {self.colors['primary']};
            font-family: 'Bashnschift';
            font-size: 60px;
            font-weight: bold;
            letter-spacing: 2px;
            margin-bottom: 50px;
        """)
        layout.addWidget(title)

        opts = [
            ("⏲ タイマー", lambda: self.change_screen("timer"), self.colors["primary"]),
            ("📝 TO DO リスト", lambda: self.change_screen("todo"), self.colors["accent"]),
            ("📄 メモ", lambda: self.change_screen("memo"), self.colors["success"]),
            ("📅 カレンダー", lambda: self.change_screen("calendar"), self.colors["neutral"]),
            ("🔒 セキュリティ強化メモ", self.handle_vault_navigation, self.colors["danger"])
        ]

        for text, slot, color in opts:
            btn = StyledButton(text, color, width=450)
            btn.setFixedHeight(70)
            btn.clicked.connect(slot)
            layout.addWidget(btn, alignment=Qt.AlignCenter)

        self.stacked_widget.addWidget(screen)
        self.screens["selector"] = screen

    # --- 1. タイマー機能 ---
    def create_timer_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(20, 20, 20, 20)

        back_btn = StyledButton("戻る", self.colors["btn_back"], width=80)
        back_btn.clicked.connect(self.back_to_selector)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        self.timer_display = QLabel("00:00")
        self.timer_display.setStyleSheet("font-family: 'Consolas'; font-size: 96px; font-weight: bold; color: #212121; margin: 40px 0px;")
        self.timer_display.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timer_display)

        in_f = QWidget()
        in_layout = QHBoxLayout(in_f)

# 左右に余白を入れて完全中央寄せ
        in_layout.addStretch()

        self.e_min = QLineEdit("0")
        self.e_sec = QLineEdit("00")

        for entry in (self.e_min, self.e_sec):
            entry.setFixedWidth(70)
            entry.setAlignment(Qt.AlignCenter)
            entry.setStyleSheet(f"""
                font-family: 'Consolas';
                font-size: 28px;
                border: 1px solid {self.colors['primary']};
                background: white;
                color: #212121;
            """)

        min_lbl = QLabel("分")
        sec_lbl = QLabel("秒")
        min_lbl.setStyleSheet("font-size:16px;")
        sec_lbl.setStyleSheet("font-size:16px;")

        in_layout.addWidget(self.e_min)
        in_layout.addSpacing(5)
        in_layout.addWidget(min_lbl)
        in_layout.addSpacing(15)
        in_layout.addWidget(self.e_sec)
        in_layout.addSpacing(5)
        in_layout.addWidget(sec_lbl)

        in_layout.addStretch()

        layout.addWidget(in_f)

        sound_f = QWidget()
        sound_layout = QHBoxLayout(sound_f)
        sound_layout.setAlignment(Qt.AlignCenter)

        self.sound_combo = QComboBox()
        self.sound_combo.addItems(list(self.sounds.keys()))
        self.sound_combo.setStyleSheet(f"font-family: 'Segoe UI'; font-size: 14px; background-color: {self.colors['primary']}; color: white; padding: 5px; border-radius: 4px;")
        self.sound_combo.setFixedWidth(150)
        
        preview_btn = StyledButton("♪ 試聴", self.colors["neutral"])
        preview_btn.clicked.connect(self.preview_sound)

        sound_layout.addWidget(self.sound_combo)
        sound_layout.addWidget(preview_btn)
        layout.addWidget(sound_f)

        btn_f = QWidget()
        btn_layout = QHBoxLayout(btn_f)
        btn_layout.setAlignment(Qt.AlignCenter)

        start_btn = StyledButton("スタート", self.colors["primary"])
        start_btn.clicked.connect(self.start_timer)
        stop_btn = StyledButton("ストップ", self.colors["danger"])
        stop_btn.clicked.connect(self.stop_timer)
        reset_btn = StyledButton("リセット", self.colors["neutral"])
        reset_btn.clicked.connect(self.reset_timer)

        btn_layout.addWidget(start_btn)
        btn_layout.addWidget(stop_btn)
        btn_layout.addWidget(reset_btn)
        layout.addWidget(btn_f)
        
        layout.addStretch()
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
        layout.setContentsMargins(20, 20, 20, 20)

        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)

        back_btn = StyledButton("戻る", self.colors["btn_back"], width=80)
        back_btn.clicked.connect(self.back_to_selector)
        top_layout.addWidget(back_btn)

        info_lbl = QLabel("※右クリック: フォルダ削除")
        info_lbl.setStyleSheet(f"color: {self.colors['text_sub']}; font-family: 'Segoe UI'; font-size: 12px;")
        top_layout.addWidget(info_lbl)
        top_layout.addStretch()

        rename_btn = StyledButton("フォルダ名変更", self.colors["primary"])
        rename_btn.clicked.connect(self.rename_current_folder)
        add_btn = StyledButton("新規フォルダ", self.colors["accent"])
        add_btn.clicked.connect(self.add_folder)
        top_layout.addWidget(rename_btn)
        top_layout.addWidget(add_btn)
        layout.addWidget(top_bar)

        tab_scroll = QScrollArea()
        tab_scroll.setFixedHeight(50)
        tab_scroll.setWidgetResizable(True)
        tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tab_scroll.setStyleSheet("border: none; background: transparent;")
        
        self.tab_widget = QWidget()
        self.tab_layout = QHBoxLayout(self.tab_widget)
        self.tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_layout.setSpacing(5)
        self.tab_layout.setAlignment(Qt.AlignLeft)
        tab_scroll.setWidget(self.tab_widget)
        layout.addWidget(tab_scroll)

        self.memo_text_widget = QTextEdit()
        self.memo_text_widget.setFont(QFont("Segoe UI", 12))
        self.memo_text_widget.setStyleSheet(f"background-color: white; color: #212121; border: 1px solid {self.colors['primary']}; border-radius: 4px; padding: 10px;")
        self.memo_text_widget.textChanged.connect(self.save_memo_content)
        layout.addWidget(self.memo_text_widget)

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
            fg = "white" if is_active else self.colors["text_sub"]

            btn = QPushButton(name.upper())
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {fg};
                    font-family: 'Segoe UI';
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 6px 15px;
                    border: none;
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
            QMessageBox.warning(self, "警告", "既存 of メインフォルダは削除できません")
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
        
        # 【修正】認証画面から確実にトップへ戻る
        back_btn = StyledButton("戻る", self.colors["btn_back"], width=80)
        back_btn.clicked.connect(self.back_to_selector)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        auth_card = QWidget()
        auth_card.setStyleSheet(f"background-color: {self.colors['card_bg']}; border-radius: 8px;")
        auth_card.setFixedSize(400, 300)
        auth_layout = QVBoxLayout(auth_card)
        auth_layout.setAlignment(Qt.AlignCenter)

        lbl = QLabel("パスワードを入力してください")
        lbl.setStyleSheet("font-family: 'Segoe UI'; font-size: 16px; font-weight: bold; color: #212121;")
        auth_layout.addWidget(lbl, alignment=Qt.AlignCenter)

        self.pw_entry = QLineEdit()
        self.pw_entry.setEchoMode(QLineEdit.Password)
        self.pw_entry.setStyleSheet("background: white; color: black; border: 1px solid #0047AB; padding: 6px; border-radius: 4px;")
        self.pw_entry.setFixedWidth(250)
        auth_layout.addWidget(self.pw_entry, alignment=Qt.AlignCenter)

        login_btn = StyledButton("ログイン", self.colors["primary"], width=150)
        login_btn.clicked.connect(self.check_vault_password)
        auth_layout.addWidget(login_btn, alignment=Qt.AlignCenter)

        reset_btn = QPushButton("パスワードを忘れた場合はこちら (生年月日でリセット)")
        reset_btn.setStyleSheet("color: #616161; font-family: 'Segoe UI'; font-size: 11px; border: none; background: transparent;")
        reset_btn.setCursor(QCursor(Qt.PointingHandCursor))
        reset_btn.clicked.connect(self.reset_vault_password)
        auth_layout.addWidget(reset_btn, alignment=Qt.AlignCenter)

        layout.addWidget(auth_card, alignment=Qt.AlignCenter)
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
        layout.setContentsMargins(20, 20, 20, 20)

        def logout():
            self.is_authenticated = False
            self.back_to_selector()

        # 【修正】中身の画面からも確実にログアウトしてトップへ戻る
        back_btn = StyledButton("ログアウト & 戻る", self.colors["btn_back"], width=150)
        back_btn.clicked.connect(logout)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        card = QWidget()
        card.setStyleSheet(f"background-color: {self.colors['card_bg']}; border-radius: 6px;")
        card_layout = QVBoxLayout(card)

        add_btn = StyledButton("+ メモを追加", self.colors["accent"])
        add_btn.clicked.connect(self.add_vault_item)
        card_layout.addWidget(add_btn, alignment=Qt.AlignCenter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        
        self.vault_list_widget = QWidget()
        self.vault_list_layout = QVBoxLayout(self.vault_list_widget)
        self.vault_list_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.vault_list_widget)
        card_layout.addWidget(scroll)

        layout.addWidget(card)
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
            row.setStyleSheet("background-color: white; border-radius: 4px; margin: 2px 0px;")
            row_layout = QHBoxLayout(row)

            lbl_title = QLabel(f"  {item['title']}")
            lbl_title.setFixedWidth(150)
            lbl_title.setStyleSheet("color: #212121; font-family: 'Segoe UI'; font-size: 13px;")
            
            p_disp = item["pass"] if item.get("show") else "********"
            lbl_pass = QLabel(p_disp)
            lbl_pass.setStyleSheet("font-family: 'Consolas'; color: #616161; font-size: 14px;")

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
                self.vault_items.pop(idx)
                self.refresh_vault()

            v_btn = QPushButton("表示")
            v_btn.setStyleSheet(f"color: {self.colors['primary']}; font-weight: bold; background: transparent; border: none;")
            v_btn.clicked.connect(toggle_show)

            e_btn = QPushButton("編集")
            e_btn.setStyleSheet(f"color: {self.colors['success']}; font-weight: bold; background: transparent; border: none;")
            e_btn.clicked.connect(rename_item)

            d_btn = QPushButton("削除")
            d_btn.setStyleSheet(f"color: {self.colors['danger']}; font-weight: bold; background: transparent; border: none;")
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
        layout.setContentsMargins(20, 20, 20, 20)

        back_btn = StyledButton("戻る", self.colors["btn_back"], width=80)
        back_btn.clicked.connect(self.back_to_selector)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        card = QWidget()
        card.setStyleSheet(f"background-color: {self.colors['card_bg']}; border-radius: 8px;")
        card_layout = QVBoxLayout(card)

        add_btn = StyledButton("+ タスクを追加", self.colors["accent"])
        add_btn.clicked.connect(self.add_todo_item)
        card_layout.addWidget(add_btn, alignment=Qt.AlignCenter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        
        self.todo_list_widget = QWidget()
        self.todo_list_layout = QVBoxLayout(self.todo_list_widget)
        self.todo_list_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.todo_list_widget)
        card_layout.addWidget(scroll)

        layout.addWidget(card)
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
            row.setStyleSheet("background-color: white; border-radius: 4px; margin: 3px 0px; padding: 5px;")
            row_layout = QHBoxLayout(row)

            lbl = QLabel(f"  {task}")
            lbl.setStyleSheet("font-family: 'Segoe UI'; font-size: 14px; color: #212121;")
            row_layout.addWidget(lbl)
            row_layout.addStretch()

            done_btn = QPushButton("完了")
            done_btn.setStyleSheet(f"color: {self.colors['accent']}; font-weight: bold; background: transparent; border: none;")
            done_btn.setCursor(QCursor(Qt.PointingHandCursor))
            done_btn.clicked.connect(lambda checked=False, idx=i: [self.todo_items.pop(idx), self.refresh_todo()])
            row_layout.addWidget(done_btn)

            self.todo_list_layout.addWidget(row)
        self.save_all_data()


    # --- 5. カレンダー機能 ---
    def create_calendar_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(20, 20, 20, 20)

        # 【修正】カレンダーから確実にトップへ戻る
        back_btn = StyledButton("戻る", self.colors["btn_back"], width=80)
        back_btn.clicked.connect(self.back_to_selector)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        center_wrapper = QWidget()
        center_layout = QVBoxLayout(center_wrapper)
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setContentsMargins(0, 0, 0, 0)

        ctrl_f = QWidget()
        ctrl_layout = QHBoxLayout(ctrl_f)
        ctrl_layout.setAlignment(Qt.AlignCenter)

        prev_btn = StyledButton("＜", self.colors["primary"])
        prev_btn.clicked.connect(self.prev_month)
        
        self.cal_label = QLabel()
        self.cal_label.setStyleSheet("font-family: 'Segoe UI'; font-size: 22px; font-weight: bold; color: #212121; min-width: 150px;")
        self.cal_label.setAlignment(Qt.AlignCenter)
        
        next_btn = StyledButton("＞", self.colors["primary"])
        next_btn.clicked.connect(self.next_month)

        ctrl_layout.addWidget(prev_btn)
        ctrl_layout.addWidget(self.cal_label)
        ctrl_layout.addWidget(next_btn)
        center_layout.addWidget(ctrl_f)

        card = QWidget()
        card.setStyleSheet(f"background-color: {self.colors['card_bg']}; border-radius: 8px; padding: 15px;")
        self.calendar_grid_layout = QGridLayout(card)
        self.calendar_grid_layout.setSpacing(5)
        self.calendar_grid_layout.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(card)

        layout.addStretch()
        layout.addWidget(center_wrapper)
        layout.addStretch()

        self.stacked_widget.addWidget(screen)
        self.screens["calendar"] = screen

    def draw_calendar(self):
        self.cal_label.setText(f"{self.cur_year} / {self.cur_month}")
        
        while self.calendar_grid_layout.count():
            child = self.calendar_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        days = ["月","火","水","木","金","土","日"]
        for i, d in enumerate(days):
            lbl = QLabel(d)
            lbl.setStyleSheet("font-family: 'Segoe UI'; font-size: 12px; font-weight: bold; color: #616161;")
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
                    bg, fg = self.colors["primary"], "white"
                elif key in self.calendar_notes:
                    bg, fg = self.colors["accent"], "white"
                else:
                    bg, fg = "white", self.colors["text_main"]

                btn = QPushButton(str(day))
                btn.setFixedSize(65, 45)
                btn.setCursor(QCursor(Qt.PointingHandCursor))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        color: {fg};
                        font-family: 'Segoe UI';
                        font-size: 12px;
                        font-weight: bold;
                        border: 1px solid {self.colors['primary']};
                        border-radius: 4px;
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
