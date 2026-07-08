import sys
import os
import json
import shutil
import calendar
from datetime import datetime, date, timedelta

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QDateEdit, QCheckBox, QDialog,
    QScrollArea, QMessageBox, QColorDialog, QFrame, QSizePolicy
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "recruitment_calendar_data.json")

# 企業の背景色として使うカラーパレット（登録順に自動で割り当てる）
COMPANY_COLOR_PALETTE = [
    "#F38BA8", "#FAB387", "#F9E2AF", "#A6E3A1", "#94E2D5", "#89DCEB",
    "#74C7EC", "#89B4FA", "#B4BEFE", "#CBA6F7", "#F5C2E7", "#EBA0AC",
    "#E6C58A", "#9CCFD8", "#C4A7E7", "#FFA07A",
]

# 選考状況を追加したときに自動で割り当てる枠色のパレット
STATUS_COLOR_POOL = [
    "#F2CDCD", "#B5E8B0", "#8CD9E8", "#D9C2F0", "#F0D48C", "#8CA9F0",
    "#F0A0C2", "#A0F0D0", "#F0E08C", "#C2A0F0",
]

# あらかじめ用意しておく選考状況（名称, 枠色）。「インターン参加確定」も最初から用意する。
STATUS_PRESETS = [
    ("書類選考", "#89B4FA"),
    ("Webテスト", "#74C7EC"),
    ("GD（グループディスカッション）", "#94E2D5"),
    ("一次面接", "#A6E3A1"),
    ("二次面接", "#F9E2AF"),
    ("最終面接", "#FAB387"),
    ("内定", "#F38BA8"),
    ("インターン参加確定", "#CBA6F7"),
    ("お見送り", "#6C7086"),
]

# 通知タイミングの選択肢（締切/実施日の何日前に知らせるか）
NOTIFY_CHOICES = [(3, "3日前"), (1, "前日"), (0, "当日")]

COLORS = {
    "bg_base": "#1E1E2E",
    "card_bg": "#313244",
    "border": "#45475A",
    "primary": "#89B4FA",
    "accent": "#CBA6F7",
    "success": "#A6E3A1",
    "danger": "#F38BA8",
    "text_main": "#CDD6F4",
    "text_sub": "#A6ADC8",
}


def today_str():
    return date.today().isoformat()


class RecruitmentData:
    """企業マスタ・選考状況マスタ・予定データの読み込み/保存を担当する"""

    def __init__(self):
        self.companies = {}      # {企業名: 色コード}
        self.statuses = []       # [{"name":..., "color":..., "preset": bool}]
        self.events = []         # [{"id":, "company":, "status":, "date":, "memo":, "notify_days":[...]}]
        self.last_notify_check = ""
        self.load()

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

    def load(self):
        d = self._load_json_with_backup(DATA_FILE)
        if d:
            self.companies = d.get("companies", {})
            self.statuses = d.get("statuses", [])
            self.events = d.get("events", [])
            self.last_notify_check = d.get("last_notify_check", "")
        if not self.statuses:
            self.statuses = [{"name": n, "color": c, "preset": True} for n, c in STATUS_PRESETS]

    def save(self):
        data = {
            "companies": self.companies,
            "statuses": self.statuses,
            "events": self.events,
            "last_notify_check": self.last_notify_check,
        }
        tmp_path = DATA_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if os.path.exists(DATA_FILE):
            shutil.copy2(DATA_FILE, DATA_FILE + ".bak")
        os.replace(tmp_path, DATA_FILE)

    def add_company(self, name, color=None):
        if color is None:
            color = COMPANY_COLOR_PALETTE[len(self.companies) % len(COMPANY_COLOR_PALETTE)]
        self.companies[name] = color

    def add_status(self, name):
        color = STATUS_COLOR_POOL[len(self.statuses) % len(STATUS_COLOR_POOL)]
        self.statuses.append({"name": name, "color": color, "preset": False})

    def status_color(self, name):
        for s in self.statuses:
            if s["name"] == name:
                return s["color"]
        return COLORS["border"]

    def next_event_id(self):
        return (max((e["id"] for e in self.events), default=0)) + 1

    def events_on(self, day_iso):
        return [e for e in self.events if e["date"] == day_iso]

    def upcoming_events(self, within_days=7):
        result = []
        today = date.today()
        for e in self.events:
            try:
                d = datetime.strptime(e["date"], "%Y-%m-%d").date()
            except ValueError:
                continue
            days_left = (d - today).days
            if 0 <= days_left <= within_days:
                result.append((days_left, e))
        result.sort(key=lambda x: x[0])
        return result

    def due_notifications(self):
        """今日が、どれかの予定の通知タイミング（何日前）にちょうど一致するものを返す"""
        today = date.today()
        hits = []
        for e in self.events:
            try:
                d = datetime.strptime(e["date"], "%Y-%m-%d").date()
            except ValueError:
                continue
            days_left = (d - today).days
            if days_left in e.get("notify_days", []):
                hits.append(e)
        return hits


def color_chip_style(bg_color, border_color=None, text_color="#1E1E2E"):
    border = border_color or bg_color
    return f"""
        background-color: {bg_color};
        border: 3px solid {border};
        border-radius: 8px;
        color: {text_color};
        font-size: 11px;
        font-weight: 700;
        padding: 2px 6px;
    """


class StyledButton(QPushButton):
    def __init__(self, text, base_color, parent=None, compact=False):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        pad = "8px 16px" if compact else "12px 24px"
        font_size = "13px" if compact else "15px"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {base_color};
                color: #1E1E2E;
                font-weight: 700;
                font-size: {font_size};
                border: none;
                border-radius: 10px;
                padding: {pad};
            }}
            QPushButton:hover {{
                background-color: {base_color};
                opacity: 0.9;
            }}
        """)


class AddCompanyDialog(QDialog):
    """新規企業の登録（名称の自由入力＋自分で色を選べるカラーピッカー）"""

    def __init__(self, default_color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("企業を追加")
        self.setMinimumWidth(360)
        self.selected_color = default_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        layout.addWidget(QLabel("企業名"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例: ○○株式会社")
        layout.addWidget(self.name_edit)

        color_row = QHBoxLayout()
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(36, 36)
        self._refresh_preview()
        color_row.addWidget(self.color_preview)
        pick_btn = StyledButton("色を選ぶ", COLORS["primary"], compact=True)
        pick_btn.clicked.connect(self.pick_color)
        color_row.addWidget(pick_btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        btn_row = QHBoxLayout()
        cancel_btn = StyledButton("キャンセル", COLORS["border"], compact=True)
        cancel_btn.clicked.connect(self.reject)
        ok_btn = StyledButton("追加する", COLORS["success"], compact=True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _refresh_preview(self):
        self.color_preview.setStyleSheet(
            f"background-color:{self.selected_color}; border-radius:8px; border:1px solid #45475A;"
        )

    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.selected_color), self, "企業の色を選択")
        if c.isValid():
            self.selected_color = c.name()
            self._refresh_preview()

    def result_data(self):
        return self.name_edit.text().strip(), self.selected_color


class AddStatusDialog(QDialog):
    """新規選考状況の追加（名称のみ入力。色は自動で割り当てる）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("選考状況を追加")
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        layout.addWidget(QLabel("選考状況名（色は自動で割り当てられます）"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例: 適性検査、リクルーター面談 など")
        layout.addWidget(self.name_edit)

        btn_row = QHBoxLayout()
        cancel_btn = StyledButton("キャンセル", COLORS["border"], compact=True)
        cancel_btn.clicked.connect(self.reject)
        ok_btn = StyledButton("追加する", COLORS["success"], compact=True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def status_name(self):
        return self.name_edit.text().strip()


class EventDialog(QDialog):
    """予定（企業×選考状況×締切/実施日）の追加・編集"""

    def __init__(self, rdata: RecruitmentData, initial_date=None, event=None, parent=None):
        super().__init__(parent)
        self.rdata = rdata
        self.event = event
        self.setWindowTitle("予定を編集" if event else "予定を追加")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(QLabel("企業"))
        company_row = QHBoxLayout()
        self.company_combo = QComboBox()
        company_row.addWidget(self.company_combo, stretch=1)
        add_company_btn = StyledButton("＋新規企業", COLORS["accent"], compact=True)
        add_company_btn.clicked.connect(self.add_new_company)
        company_row.addWidget(add_company_btn)
        layout.addLayout(company_row)

        layout.addWidget(QLabel("選考状況"))
        status_row = QHBoxLayout()
        self.status_combo = QComboBox()
        status_row.addWidget(self.status_combo, stretch=1)
        add_status_btn = StyledButton("＋新規状況", COLORS["accent"], compact=True)
        add_status_btn.clicked.connect(self.add_new_status)
        status_row.addWidget(add_status_btn)
        layout.addLayout(status_row)

        layout.addWidget(QLabel("締切日 / 実施日（面接日・インターン参加日など）"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.date_edit)

        layout.addWidget(QLabel("メモ（任意）"))
        self.memo_edit = QLineEdit()
        layout.addWidget(self.memo_edit)

        layout.addWidget(QLabel("通知タイミング"))
        notify_row = QHBoxLayout()
        self.notify_checks = {}
        for days, label in NOTIFY_CHOICES:
            cb = QCheckBox(label)
            self.notify_checks[days] = cb
            notify_row.addWidget(cb)
        layout.addLayout(notify_row)

        btn_row = QHBoxLayout()
        cancel_btn = StyledButton("キャンセル", COLORS["border"], compact=True)
        cancel_btn.clicked.connect(self.reject)
        save_btn = StyledButton("保存する", COLORS["success"], compact=True)
        save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self.refresh_company_combo()
        self.refresh_status_combo()

        if initial_date:
            self.date_edit.setDate(QDate(initial_date.year, initial_date.month, initial_date.day))

        if event:
            idx = self.company_combo.findText(event["company"])
            if idx >= 0:
                self.company_combo.setCurrentIndex(idx)
            idx = self.status_combo.findText(event["status"])
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
            d = datetime.strptime(event["date"], "%Y-%m-%d").date()
            self.date_edit.setDate(QDate(d.year, d.month, d.day))
            self.memo_edit.setText(event.get("memo", ""))
            for days in event.get("notify_days", []):
                if days in self.notify_checks:
                    self.notify_checks[days].setChecked(True)

    def refresh_company_combo(self, select=None):
        self.company_combo.clear()
        self.company_combo.addItems(list(self.rdata.companies.keys()))
        if select:
            idx = self.company_combo.findText(select)
            if idx >= 0:
                self.company_combo.setCurrentIndex(idx)

    def refresh_status_combo(self, select=None):
        self.status_combo.clear()
        self.status_combo.addItems([s["name"] for s in self.rdata.statuses])
        if select:
            idx = self.status_combo.findText(select)
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)

    def add_new_company(self):
        next_color = COMPANY_COLOR_PALETTE[len(self.rdata.companies) % len(COMPANY_COLOR_PALETTE)]
        dialog = AddCompanyDialog(next_color, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            name, color = dialog.result_data()
            if not name:
                QMessageBox.warning(self, "エラー", "企業名を入力してください。")
                return
            if name in self.rdata.companies:
                QMessageBox.warning(self, "エラー", "同じ名前の企業が既に登録されています。")
                return
            self.rdata.add_company(name, color)
            self.refresh_company_combo(select=name)

    def add_new_status(self):
        dialog = AddStatusDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            name = dialog.status_name()
            if not name:
                QMessageBox.warning(self, "エラー", "選考状況名を入力してください。")
                return
            if any(s["name"] == name for s in self.rdata.statuses):
                QMessageBox.warning(self, "エラー", "同じ名前の選考状況が既に存在します。")
                return
            self.rdata.add_status(name)
            self.refresh_status_combo(select=name)

    def on_save(self):
        if self.company_combo.count() == 0:
            QMessageBox.warning(self, "エラー", "企業を登録してください。")
            return
        if self.status_combo.count() == 0:
            QMessageBox.warning(self, "エラー", "選考状況を選択してください。")
            return

        notify_days = [days for days, cb in self.notify_checks.items() if cb.isChecked()]
        record = {
            "id": self.event["id"] if self.event else self.rdata.next_event_id(),
            "company": self.company_combo.currentText(),
            "status": self.status_combo.currentText(),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "memo": self.memo_edit.text().strip(),
            "notify_days": notify_days,
        }

        if self.event:
            for i, e in enumerate(self.rdata.events):
                if e["id"] == self.event["id"]:
                    self.rdata.events[i] = record
                    break
        else:
            self.rdata.events.append(record)

        self.accept()


class DayDetailDialog(QDialog):
    """特定の日付に登録されている予定の一覧・追加・編集・削除"""

    def __init__(self, rdata: RecruitmentData, day: date, on_change, parent=None):
        super().__init__(parent)
        self.rdata = rdata
        self.day = day
        self.on_change = on_change
        self.setWindowTitle(f"{day.strftime('%Y年%m月%d日')} の予定")
        self.setMinimumWidth(420)

        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(20, 20, 20, 20)
        self.layout_main.setSpacing(10)

        self.list_area = QVBoxLayout()
        self.layout_main.addLayout(self.list_area)

        add_btn = StyledButton("＋この日に予定を追加", COLORS["accent"])
        add_btn.clicked.connect(self.add_event)
        self.layout_main.addWidget(add_btn)

        close_btn = StyledButton("閉じる", COLORS["border"], compact=True)
        close_btn.clicked.connect(self.accept)
        self.layout_main.addWidget(close_btn)

        self.refresh()

    def refresh(self):
        while self.list_area.count():
            child = self.list_area.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        events = self.rdata.events_on(self.day.isoformat())
        if not events:
            empty = QLabel("この日の予定はまだありません。")
            empty.setStyleSheet(f"color:{COLORS['text_sub']};")
            self.list_area.addWidget(empty)
            return

        for e in events:
            row = QFrame()
            row.setStyleSheet(
                f"background-color:{COLORS['card_bg']}; border-radius:10px; border:1px solid {COLORS['border']};"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)

            company_color = self.rdata.companies.get(e["company"], COLORS["border"])
            status_color = self.rdata.status_color(e["status"])
            chip = QLabel(f"{e['company']} / {e['status']}")
            chip.setStyleSheet(color_chip_style(company_color, status_color))
            row_layout.addWidget(chip)

            memo_lbl = QLabel(e.get("memo", ""))
            memo_lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:12px;")
            row_layout.addWidget(memo_lbl, stretch=1)

            edit_btn = QPushButton("編集")
            edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
            edit_btn.clicked.connect(lambda checked=False, ev=e: self.edit_event(ev))
            row_layout.addWidget(edit_btn)

            del_btn = QPushButton("削除")
            del_btn.setCursor(QCursor(Qt.PointingHandCursor))
            del_btn.clicked.connect(lambda checked=False, ev=e: self.delete_event(ev))
            row_layout.addWidget(del_btn)

            self.list_area.addWidget(row)

    def add_event(self):
        dialog = EventDialog(self.rdata, initial_date=self.day, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.rdata.save()
            self.refresh()
            self.on_change()

    def edit_event(self, event):
        dialog = EventDialog(self.rdata, event=event, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.rdata.save()
            self.refresh()
            self.on_change()

    def delete_event(self, event):
        ret = QMessageBox.question(
            self, "確認", f"「{event['company']} / {event['status']}」の予定を削除しますか？",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.rdata.events = [e for e in self.rdata.events if e["id"] != event["id"]]
            self.rdata.save()
            self.refresh()
            self.on_change()


class RecruitmentCalendarWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("就活選考カレンダー")
        self.resize(1100, 720)
        self.rdata = RecruitmentData()

        today = date.today()
        self.cur_year, self.cur_month = today.year, today.month

        self.init_style()
        self.init_ui()
        self.draw_calendar()
        self.refresh_side_panels()
        self.check_due_notifications()

    def init_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {COLORS['bg_base']}; }}
            QLabel {{ color: {COLORS['text_main']}; font-size: 13px; }}
            QLineEdit, QComboBox, QDateEdit {{
                background-color: {COLORS['card_bg']};
                color: {COLORS['text_main']};
                border: 2px solid {COLORS['border']};
                border-radius: 8px;
                padding: 6px 10px;
                min-height: 22px;
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
                border: 2px solid {COLORS['primary']};
            }}
            QScrollArea {{ border: none; background: transparent; }}
        """)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(16)

        # --- 中央: カレンダー ---
        center = QVBoxLayout()
        outer.addLayout(center, stretch=3)

        header = QHBoxLayout()
        title = QLabel("就活選考カレンダー")
        title.setStyleSheet(f"font-size:22px; font-weight:800; color:{COLORS['primary']};")
        header.addWidget(title)
        header.addStretch()
        add_btn = StyledButton("＋ 予定を追加", COLORS["accent"])
        add_btn.clicked.connect(self.open_add_event_from_header)
        header.addWidget(add_btn)
        center.addLayout(header)

        nav_row = QHBoxLayout()
        prev_btn = StyledButton("◀ 前月", COLORS["primary"], compact=True)
        prev_btn.clicked.connect(self.prev_month)
        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignCenter)
        self.month_label.setStyleSheet("font-size:17px; font-weight:700;")
        next_btn = StyledButton("次月 ▶", COLORS["primary"], compact=True)
        next_btn.clicked.connect(self.next_month)
        nav_row.addWidget(prev_btn)
        nav_row.addWidget(self.month_label, stretch=1)
        nav_row.addWidget(next_btn)
        center.addLayout(nav_row)

        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(6)
        calendar_card = QFrame()
        calendar_card.setStyleSheet(
            f"background-color:{COLORS['card_bg']}; border-radius:14px; border:1px solid {COLORS['border']};"
        )
        calendar_card.setLayout(self.calendar_grid)
        center.addWidget(calendar_card, stretch=1)

        # --- 右パネル: 通知 / 企業 / 選考状況 ---
        right = QVBoxLayout()
        outer.addLayout(right, stretch=1)

        notify_title = QLabel("直近7日以内の締切・予定")
        notify_title.setStyleSheet("font-weight:800; font-size:14px;")
        right.addWidget(notify_title)
        self.notify_scroll = QScrollArea()
        self.notify_scroll.setWidgetResizable(True)
        self.notify_scroll.setFixedHeight(200)
        self.notify_container = QWidget()
        self.notify_layout = QVBoxLayout(self.notify_container)
        self.notify_layout.setAlignment(Qt.AlignTop)
        self.notify_scroll.setWidget(self.notify_container)
        right.addWidget(self.notify_scroll)

        company_title = QLabel("登録済みの企業")
        company_title.setStyleSheet("font-weight:800; font-size:14px; margin-top:8px;")
        right.addWidget(company_title)
        self.company_scroll = QScrollArea()
        self.company_scroll.setWidgetResizable(True)
        self.company_scroll.setFixedHeight(160)
        self.company_container = QWidget()
        self.company_layout = QVBoxLayout(self.company_container)
        self.company_layout.setAlignment(Qt.AlignTop)
        self.company_scroll.setWidget(self.company_container)
        right.addWidget(self.company_scroll)

        status_title = QLabel("選考状況の一覧")
        status_title.setStyleSheet("font-weight:800; font-size:14px; margin-top:8px;")
        right.addWidget(status_title)
        self.status_scroll = QScrollArea()
        self.status_scroll.setWidgetResizable(True)
        self.status_container = QWidget()
        self.status_layout = QVBoxLayout(self.status_container)
        self.status_layout.setAlignment(Qt.AlignTop)
        self.status_scroll.setWidget(self.status_container)
        right.addWidget(self.status_scroll, stretch=1)

    # --- カレンダー描画 ---
    def draw_calendar(self):
        self.month_label.setText(f"{self.cur_year}年 {self.cur_month}月")

        while self.calendar_grid.count():
            child = self.calendar_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        weekday_colors = [COLORS["text_sub"]] * 5 + ["#74C7EC", "#F38BA8"]
        for i, wd in enumerate(weekdays):
            lbl = QLabel(wd)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"font-weight:700; color:{weekday_colors[i]};")
            self.calendar_grid.addWidget(lbl, 0, i)

        weeks = calendar.monthcalendar(self.cur_year, self.cur_month)
        today = date.today()

        for r, week in enumerate(weeks):
            for c, day_num in enumerate(week):
                if day_num == 0:
                    continue
                cell_date = date(self.cur_year, self.cur_month, day_num)
                is_today = (cell_date == today)

                cell = QFrame()
                cell.setMinimumSize(130, 90)
                cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                border_color = COLORS["primary"] if is_today else COLORS["border"]
                cell.setStyleSheet(
                    f"background-color:{COLORS['bg_base']}; border:2px solid {border_color}; border-radius:10px;"
                )
                cell.setCursor(QCursor(Qt.PointingHandCursor))
                cell_layout = QVBoxLayout(cell)
                cell_layout.setContentsMargins(6, 4, 6, 4)
                cell_layout.setSpacing(2)

                day_lbl = QLabel(str(day_num))
                day_lbl.setStyleSheet(
                    f"font-weight:800; color:{COLORS['primary'] if is_today else COLORS['text_main']}; border:none;"
                )
                cell_layout.addWidget(day_lbl)

                day_events = self.rdata.events_on(cell_date.isoformat())
                for e in day_events[:3]:
                    company_color = self.rdata.companies.get(e["company"], COLORS["border"])
                    status_color = self.rdata.status_color(e["status"])
                    chip = QLabel(e["company"])
                    chip.setStyleSheet(color_chip_style(company_color, status_color))
                    cell_layout.addWidget(chip)
                if len(day_events) > 3:
                    more_lbl = QLabel(f"+{len(day_events) - 3}件")
                    more_lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:11px; border:none;")
                    cell_layout.addWidget(more_lbl)

                cell_layout.addStretch()

                cell.mousePressEvent = lambda ev, d=cell_date: self.open_day_detail(d)
                self.calendar_grid.addWidget(cell, r + 1, c)

    def open_day_detail(self, day):
        dialog = DayDetailDialog(self.rdata, day, on_change=self.on_data_changed, parent=self)
        dialog.exec_()

    def open_add_event_from_header(self):
        dialog = EventDialog(self.rdata, initial_date=date(self.cur_year, self.cur_month, 1), parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.rdata.save()
            self.on_data_changed()

    def on_data_changed(self):
        self.draw_calendar()
        self.refresh_side_panels()

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

    # --- 右パネル描画 ---
    def refresh_side_panels(self):
        self._clear_layout(self.notify_layout)
        upcoming = self.rdata.upcoming_events(within_days=7)
        if not upcoming:
            lbl = QLabel("直近の締切・予定はありません。")
            lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:12px;")
            self.notify_layout.addWidget(lbl)
        for days_left, e in upcoming:
            when = "本日" if days_left == 0 else f"あと{days_left}日"
            lbl = QLabel(f"【{when}】{e['company']} / {e['status']}（{e['date']}）")
            company_color = self.rdata.companies.get(e["company"], COLORS["border"])
            status_color = self.rdata.status_color(e["status"])
            lbl.setStyleSheet(
                f"background-color:{COLORS['card_bg']}; border-left:6px solid {status_color}; "
                f"border-radius:6px; padding:6px 8px; margin-bottom:4px; color:{company_color};"
            )
            self.notify_layout.addWidget(lbl)

        self._clear_layout(self.company_layout)
        if not self.rdata.companies:
            lbl = QLabel("まだ企業が登録されていません。")
            lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:12px;")
            self.company_layout.addWidget(lbl)
        for name, color in self.rdata.companies.items():
            lbl = QLabel(name)
            lbl.setStyleSheet(color_chip_style(color) + "margin-bottom:4px;")
            self.company_layout.addWidget(lbl)

        self._clear_layout(self.status_layout)
        for s in self.rdata.statuses:
            preset_mark = "" if s.get("preset") else "（追加）"
            lbl = QLabel(f"{s['name']}{preset_mark}")
            lbl.setStyleSheet(
                f"border:3px solid {s['color']}; border-radius:6px; padding:4px 8px; margin-bottom:4px;"
            )
            self.status_layout.addWidget(lbl)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    # --- 通知チェック ---
    def check_due_notifications(self):
        if self.rdata.last_notify_check == today_str():
            return
        hits = self.rdata.due_notifications()
        self.rdata.last_notify_check = today_str()
        self.rdata.save()
        if hits:
            lines = [f"・{e['company']} / {e['status']}（{e['date']}）" for e in hits]
            QMessageBox.information(
                self, "締切・予定のお知らせ",
                "以下の予定の通知タイミングになりました。\n\n" + "\n".join(lines)
            )

    def closeEvent(self, event):
        self.rdata.save()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RecruitmentCalendarWindow()
    window.show()
    sys.exit(app.exec())
