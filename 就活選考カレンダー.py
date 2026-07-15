import sys
import os
import json
import shutil
import calendar
import colorsys
from datetime import datetime, date, timedelta

from PySide6.QtCore import Qt, QDate, QTime
from PySide6.QtGui import QColor, QCursor, QFontMetrics
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QDateEdit, QTimeEdit, QCheckBox, QDialog,
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

# あらかじめ用意しておく選考状況（名称, 枠色）。「インターン参加確定」も最初から用意する。
STATUS_PRESETS = [
    ("書類選考", "#89B4FA"),
    ("Webテスト", "#74C7EC"),
    ("動画選考", "#F5C2E7"),
    ("AI面接", "#B4BEFE"),
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

# カレンダー上には表示せず、専用リストで表示する選考状況
OFFER_STATUS_NAME = "内定"
INTERN_CONFIRMED_STATUS_NAME = "インターン参加確定"

# --- カラーパレット（Catppuccin Latte ベースの、白を基調としたライトテーマ）---
COLORS = {
    "bg_base": "#F4F6FB",
    "bg_mantle": "#E9ECF3",
    "bg_crust": "#DCE0EA",
    "card_bg": "#FFFFFF",
    "surface1": "#D4D8E3",
    "surface2": "#B8BFD1",
    "border": "#D4D8E3",
    "overlay": "#9CA3B8",
    "primary": "#1E66F5",
    "accent": "#8839EF",
    "success": "#3FA34D",
    "danger": "#D20F39",
    "warning": "#FE640B",
    "text_main": "#3B3F51",
    "text_sub": "#6C7086",
    "text_sub2": "#8C90A4",
}


def today_str():
    return date.today().isoformat()


def clamp(v):
    return max(0, min(255, v))


def adjust_color(hex_color, amount):
    """16進カラーコードを明るく（正）/暗く（負）調整する"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"#{clamp(r + amount):02x}{clamp(g + amount):02x}{clamp(b + amount):02x}"


def contrasting_text_color(hex_color):
    """背景色の明るさに応じて、読みやすい文字色（黒系/白系）を自動で選ぶ"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#1E1E2E" if luminance > 0.6 else "#FFFFFF"


def hex_to_rgba(hex_color, alpha):
    """背景に薄く色を乗せるためのrgba()文字列に変換する"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def color_distance(hex1, hex2):
    """2つの色の見た目の近さを表す距離（大きいほど見分けやすい、redmean近似で人の目の感度に合わせて重み付け）"""
    h1, h2 = hex1.lstrip("#"), hex2.lstrip("#")
    r1, g1, b1 = int(h1[0:2], 16), int(h1[2:4], 16), int(h1[4:6], 16)
    r2, g2, b2 = int(h2[0:2], 16), int(h2[2:4], 16), int(h2[4:6], 16)
    rmean = (r1 + r2) / 2
    dr, dg, db = r1 - r2, g1 - g2, b1 - b2
    return ((2 + rmean / 256) * dr ** 2 + 4 * dg ** 2 + (2 + (255 - rmean) / 256) * db ** 2) ** 0.5


def generate_status_color(index):
    """黄金角で色相を回転させ、彩度・明度も少しずつ揺らしながら淡いトーンの色を無制限に生成する"""
    hue = (index * 0.6180339887) % 1.0
    lightness = 0.68 + 0.10 * ((index * 0.37) % 1.0)
    saturation = 0.5 + 0.3 * ((index * 0.53) % 1.0)
    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def pick_distinct_color(used_colors, min_distance=110, max_candidates=200):
    """既存の色となるべく被らない色を、色相・彩度・明度を揺らしながら探す（見つからなければ一番マシなものを返す）"""
    best_color, best_score = generate_status_color(0), -1
    for i in range(max_candidates):
        candidate = generate_status_color(i)
        if not used_colors:
            return candidate
        nearest = min(color_distance(candidate, c) for c in used_colors)
        if nearest >= min_distance:
            return candidate
        if nearest > best_score:
            best_score, best_color = nearest, candidate
    return best_color


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
        needs_save = self._migrate_events_to_date_list()
        if self._migrate_events_to_time_range():
            needs_save = True
        if self._resolve_status_color_conflicts():
            needs_save = True
        if needs_save:
            self.save()

    def _migrate_events_to_date_list(self):
        """旧形式（単一date、または連続したstart_date/end_date）の予定を、
        歯抜けのある複数日にも対応した日付リスト（dates）に変換する"""
        changed = False
        for e in self.events:
            if "dates" in e:
                continue
            if "start_date" in e and "end_date" in e:
                start = datetime.strptime(e.pop("start_date"), "%Y-%m-%d").date()
                end = datetime.strptime(e.pop("end_date"), "%Y-%m-%d").date()
                days = []
                d = start
                while d <= end:
                    days.append(d.isoformat())
                    d += timedelta(days=1)
                e["dates"] = days
            else:
                e["dates"] = [e.pop("date", today_str())]
            changed = True
        return changed

    def _migrate_events_to_time_range(self):
        """旧形式（単一のtime）の予定を、開始・終了時刻（time_start/time_end）に変換する"""
        changed = False
        for e in self.events:
            if "time" in e:
                e["time_start"] = e.pop("time")
                e["time_end"] = ""
                changed = True
            elif "time_start" not in e:
                e["time_start"] = ""
                e["time_end"] = ""
                changed = True
        return changed

    def _resolve_status_color_conflicts(self):
        """既存データに、見分けにくいほど近い色の選考状況がないか調べ、あれば追加分の色を振り直す"""
        changed = False
        assigned_colors = []
        for s in self.statuses:
            if not s.get("preset") and any(color_distance(s["color"], c) < 70 for c in assigned_colors):
                s["color"] = pick_distinct_color(assigned_colors)
                changed = True
            assigned_colors.append(s["color"])
        return changed

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

    def rename_company(self, old_name, new_name, color):
        """企業名・色を変更し、既存の予定に登録されている企業名も追従させる"""
        if old_name in self.companies:
            del self.companies[old_name]
        self.companies[new_name] = color
        if new_name != old_name:
            for e in self.events:
                if e["company"] == old_name:
                    e["company"] = new_name

    def remove_company(self, name):
        self.companies.pop(name, None)

    def events_with_company(self, name):
        return [e for e in self.events if e["company"] == name]

    def add_status(self, name):
        used_colors = [s["color"] for s in self.statuses]
        color = pick_distinct_color(used_colors)
        self.statuses.append({"name": name, "color": color, "preset": False})

    def remove_status(self, name):
        """ユーザーが追加した選考状況のみ削除できる（プリセットは削除不可）"""
        self.statuses = [s for s in self.statuses if not (s["name"] == name and not s.get("preset"))]

    def events_with_status(self, name):
        return [e for e in self.events if e["status"] == name]

    def status_color(self, name):
        for s in self.statuses:
            if s["name"] == name:
                return s["color"]
        return COLORS["border"]

    def next_event_id(self):
        return (max((e["id"] for e in self.events), default=0)) + 1

    def events_on(self, day_iso):
        """カレンダーに表示する、その日を含む予定（内定は専用リストにのみ表示するため除く）"""
        return [
            e for e in self.events
            if day_iso in e["dates"] and e["status"] != OFFER_STATUS_NAME
        ]

    def upcoming_events(self, within_days=7):
        result = []
        today = date.today()
        for e in self.events:
            if not e.get("dates"):
                continue
            d = datetime.strptime(min(e["dates"]), "%Y-%m-%d").date()
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
            if not e.get("dates"):
                continue
            d = datetime.strptime(min(e["dates"]), "%Y-%m-%d").date()
            days_left = (d - today).days
            if days_left in e.get("notify_days", []):
                hits.append(e)
        return hits


def prompt_add_company(rdata: "RecruitmentData", parent):
    """企業追加ダイアログを開き、確定された企業名を返す（キャンセル/無効入力時はNone）"""
    next_color = COMPANY_COLOR_PALETTE[len(rdata.companies) % len(COMPANY_COLOR_PALETTE)]
    dialog = AddCompanyDialog(next_color, parent=parent)
    if dialog.exec_() != QDialog.Accepted:
        return None
    name, color = dialog.result_data()
    if not name:
        QMessageBox.warning(parent, "エラー", "企業名を入力してください。")
        return None
    if name in rdata.companies:
        QMessageBox.warning(parent, "エラー", "同じ名前の企業が既に登録されています。")
        return None
    rdata.add_company(name, color)
    return name


def event_dates_text(event):
    """日付リストを、連続した日はまとめて「開始〜終了」、飛び飛びの日は読点区切りで表示する"""
    dates = sorted(event.get("dates", []))
    if not dates:
        return ""
    parsed = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]
    runs = []
    run_start = run_end = parsed[0]
    for d in parsed[1:]:
        if (d - run_end).days == 1:
            run_end = d
            continue
        runs.append((run_start, run_end))
        run_start = run_end = d
    runs.append((run_start, run_end))
    parts = [s.isoformat() if s == e else f"{s.isoformat()}〜{e.isoformat()}" for s, e in runs]
    return "、".join(parts)


def event_dates_and_time_text(event):
    """日付に加えて、時間（開始〜終了）が設定されていればそれも並べて表示する"""
    text = event_dates_text(event)
    start = event.get("time_start", "")
    end = event.get("time_end", "")
    if start:
        text += f" {start}〜{end}" if (end and end != start) else f" {start}〜"
    return text


def color_chip_style(bg_color, border_color=None, text_color=None):
    border = border_color or bg_color
    if text_color is None:
        text_color = contrasting_text_color(bg_color)
    return f"""
        background-color: {bg_color};
        border: 3px solid {border};
        border-radius: 10px;
        color: {text_color};
        font-size: 11px;
        font-weight: 700;
        padding: 3px 9px;
    """


class StyledButton(QPushButton):
    """角丸・ホバー時に自動で明るくなるボタン。gradient_to を渡すとグラデーション表示になる"""

    def __init__(self, text, base_color, parent=None, compact=False, gradient_to=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        pad = "9px 18px" if compact else "13px 26px"
        font_size = "13px" if compact else "14px"
        hover_color = adjust_color(base_color, 22)
        pressed_color = adjust_color(base_color, -18)
        text_color = contrasting_text_color(base_color)

        if gradient_to:
            bg = f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {base_color}, stop:1 {gradient_to})"
            bg_hover = f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {hover_color}, stop:1 {adjust_color(gradient_to, 22)})"
        else:
            bg = base_color
            bg_hover = hover_color

        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {text_color};
                font-weight: 700;
                font-size: {font_size};
                border: none;
                border-radius: 11px;
                padding: {pad};
            }}
            QPushButton:hover {{
                background: {bg_hover};
            }}
            QPushButton:pressed {{
                background: {pressed_color};
            }}
            QPushButton:disabled {{
                background: {COLORS['surface1']};
                color: {COLORS['text_sub2']};
            }}
        """)


class IconButton(QPushButton):
    """月送りなどに使う円形のアイコンボタン"""

    def __init__(self, text, base_color=None, size=38, parent=None):
        super().__init__(text, parent)
        base_color = base_color or COLORS["surface1"]
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedSize(size, size)
        hover_color = adjust_color(base_color, 25)
        text_color = contrasting_text_color(base_color)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {base_color};
                color: {text_color};
                font-size: 16px;
                font-weight: 700;
                border: none;
                border-radius: {size // 2}px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """)


class OutlineButton(QPushButton):
    """一覧内の「編集」「削除」など、控えめな枠線だけのボタン"""

    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        hover_text_color = contrasting_text_color(color)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {color};
                font-weight: 700;
                font-size: 12px;
                border: 2px solid {color};
                border-radius: 9px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: {hover_text_color};
            }}
        """)


def build_event_summary_row(rdata, event, on_edit, on_delete):
    """内定・インターン参加確定リストなど、右パネルの予定サマリー行（企業/状況チップ＋日付＋編集・削除）を作る"""
    row = QFrame()
    row.setStyleSheet(
        f"background-color:{COLORS['bg_base']}; border-radius:12px; border:1px solid {COLORS['surface1']};"
    )
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(10, 6, 6, 6)
    row_layout.setSpacing(6)

    company_color = rdata.companies.get(event["company"], COLORS["border"])
    status_color = rdata.status_color(event["status"])
    chip = QLabel()
    metrics = QFontMetrics(chip.font())
    chip.setText(metrics.elidedText(event["company"], Qt.ElideRight, 92))
    chip.setStyleSheet(color_chip_style(company_color, status_color))
    row_layout.addWidget(chip)

    date_lbl = QLabel(event_dates_and_time_text(event))
    date_lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:10px; border:none;")
    date_lbl.setWordWrap(True)
    row_layout.addWidget(date_lbl, stretch=1)

    edit_btn = IconButton("✏️", COLORS["primary"], size=26)
    edit_btn.clicked.connect(lambda checked=False, ev=event: on_edit(ev))
    row_layout.addWidget(edit_btn)

    del_btn = IconButton("🗑", COLORS["danger"], size=26)
    del_btn.clicked.connect(lambda checked=False, ev=event: on_delete(ev))
    row_layout.addWidget(del_btn)

    return row


def section_card(title_text, icon, action_button=None):
    """右パネルのセクションカード（見出し行＋中身を入れる枠）を作る"""
    card = QFrame()
    card.setObjectName("sectionCard")
    card.setStyleSheet(f"""
        #sectionCard {{
            background-color: {COLORS['card_bg']};
            border: 1px solid {COLORS['surface1']};
            border-radius: 16px;
        }}
    """)
    outer = QVBoxLayout(card)
    outer.setContentsMargins(14, 12, 14, 14)
    outer.setSpacing(8)

    header_row = QHBoxLayout()
    header_row.setSpacing(6)
    title_lbl = QLabel(f"{icon}  {title_text}")
    title_lbl.setStyleSheet(f"font-weight:800; font-size:14px; color:{COLORS['text_main']}; border:none;")
    header_row.addWidget(title_lbl)
    header_row.addStretch()
    if action_button:
        header_row.addWidget(action_button)
    outer.addLayout(header_row)

    return card, outer


class AddCompanyDialog(QDialog):
    """新規企業の登録（名称の自由入力＋自分で色を選べるカラーピッカー）"""

    def __init__(self, default_color, initial_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("企業を編集" if initial_name else "企業を追加")
        self.setMinimumWidth(380)
        self.selected_color = default_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(14)

        heading = QLabel("✏️ 企業を編集" if initial_name else "🏢 新しい企業を登録")
        heading.setStyleSheet(f"font-size:16px; font-weight:800; color:{COLORS['primary']};")
        layout.addWidget(heading)

        layout.addWidget(QLabel("企業名"))
        self.name_edit = QLineEdit()
        self.name_edit.setText(initial_name)
        self.name_edit.setPlaceholderText("例: ○○株式会社")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("カレンダー上での企業カラー"))
        color_row = QHBoxLayout()
        color_row.setSpacing(10)
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(40, 40)
        self._refresh_preview()
        color_row.addWidget(self.color_preview)
        pick_btn = StyledButton("色を選ぶ", COLORS["primary"], compact=True)
        pick_btn.clicked.connect(self.pick_color)
        color_row.addWidget(pick_btn)
        color_row.addStretch()
        layout.addLayout(color_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        cancel_btn = StyledButton("キャンセル", COLORS["surface2"], compact=True)
        cancel_btn.clicked.connect(self.reject)
        ok_btn = StyledButton("保存する" if initial_name else "追加する", COLORS["success"], compact=True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _refresh_preview(self):
        self.color_preview.setStyleSheet(
            f"background-color:{self.selected_color}; border-radius:10px; border:2px solid {COLORS['surface1']};"
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
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(14)

        heading = QLabel("🏷️ 新しい選考状況を追加")
        heading.setStyleSheet(f"font-size:16px; font-weight:800; color:{COLORS['accent']};")
        layout.addWidget(heading)

        layout.addWidget(QLabel("選考状況名（色は自動で割り当てられます）"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例: 適性検査、リクルーター面談 など")
        layout.addWidget(self.name_edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        cancel_btn = StyledButton("キャンセル", COLORS["surface2"], compact=True)
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

    def __init__(self, rdata: RecruitmentData, initial_date=None, editing_event=None, parent=None):
        super().__init__(parent)
        self.rdata = rdata
        self.editing_event = editing_event
        self.setWindowTitle("予定を編集" if editing_event else "予定を追加")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(10)

        heading = QLabel("✏️ 予定を編集" if editing_event else "📌 新しい予定を追加")
        heading.setStyleSheet(f"font-size:17px; font-weight:800; color:{COLORS['primary']}; margin-bottom:4px;")
        layout.addWidget(heading)

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

        self.selected_dates = set()

        layout.addWidget(QLabel("日付（面接日・締切日など。複数日にわたるインターンは期間でまとめて追加でき、途中の空き日も個別に外せます）"))

        range_row = QHBoxLayout()
        range_row.setSpacing(6)
        self.range_start_edit = QDateEdit()
        self.range_start_edit.setCalendarPopup(True)
        self.range_start_edit.setDisplayFormat("yyyy-MM-dd")
        self.range_start_edit.dateChanged.connect(self._on_range_start_changed)
        self.range_end_edit = QDateEdit()
        self.range_end_edit.setCalendarPopup(True)
        self.range_end_edit.setDisplayFormat("yyyy-MM-dd")
        range_row.addWidget(self.range_start_edit, stretch=1)
        range_row.addWidget(QLabel("〜"))
        range_row.addWidget(self.range_end_edit, stretch=1)
        add_range_btn = StyledButton("＋期間で追加", COLORS["primary"], compact=True)
        add_range_btn.clicked.connect(self.add_date_range)
        range_row.addWidget(add_range_btn)
        layout.addLayout(range_row)

        layout.addWidget(QLabel("選択中の日付（×で個別に空き日を作れます）"))
        self.dates_scroll = QScrollArea()
        self.dates_scroll.setWidgetResizable(True)
        self.dates_scroll.setFixedHeight(120)
        self.dates_container = QWidget()
        self.dates_layout = QVBoxLayout(self.dates_container)
        self.dates_layout.setAlignment(Qt.AlignTop)
        self.dates_layout.setSpacing(4)
        self.dates_scroll.setWidget(self.dates_container)
        layout.addWidget(self.dates_scroll)

        layout.addWidget(QLabel("時間（任意。面接の開始〜終了時刻など）"))
        time_row = QHBoxLayout()
        time_row.setSpacing(8)
        self.time_checkbox = QCheckBox("時間を指定する")
        self.time_checkbox.toggled.connect(self._on_time_checkbox_toggled)
        time_row.addWidget(self.time_checkbox)
        self.time_start_edit = QTimeEdit()
        self.time_start_edit.setDisplayFormat("HH:mm")
        self.time_start_edit.setTime(QTime(10, 0))
        self.time_start_edit.setEnabled(False)
        self.time_start_edit.timeChanged.connect(self._on_time_start_changed)
        time_row.addWidget(self.time_start_edit)
        time_row.addWidget(QLabel("〜"))
        self.time_end_edit = QTimeEdit()
        self.time_end_edit.setDisplayFormat("HH:mm")
        self.time_end_edit.setTime(QTime(11, 0))
        self.time_end_edit.setEnabled(False)
        time_row.addWidget(self.time_end_edit)
        time_row.addStretch()
        layout.addLayout(time_row)

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
        notify_row.addStretch()
        layout.addLayout(notify_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        cancel_btn = StyledButton("キャンセル", COLORS["surface2"], compact=True)
        cancel_btn.clicked.connect(self.reject)
        save_btn = StyledButton("保存する", COLORS["success"], compact=True)
        save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self.refresh_company_combo()
        self.refresh_status_combo()

        if initial_date:
            qdate = QDate(initial_date.year, initial_date.month, initial_date.day)
            self.range_start_edit.setDate(qdate)
            self.range_end_edit.setDate(qdate)
            self.selected_dates.add(initial_date.isoformat())

        if editing_event:
            idx = self.company_combo.findText(editing_event["company"])
            if idx >= 0:
                self.company_combo.setCurrentIndex(idx)
            idx = self.status_combo.findText(editing_event["status"])
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
            self.selected_dates = set(editing_event.get("dates", []))
            self.memo_edit.setText(editing_event.get("memo", ""))
            for days in editing_event.get("notify_days", []):
                if days in self.notify_checks:
                    self.notify_checks[days].setChecked(True)
            if editing_event.get("time_start"):
                h, m = editing_event["time_start"].split(":")
                self.time_start_edit.setTime(QTime(int(h), int(m)))
                if editing_event.get("time_end"):
                    h2, m2 = editing_event["time_end"].split(":")
                    self.time_end_edit.setTime(QTime(int(h2), int(m2)))
                self.time_checkbox.setChecked(True)

        if not self.selected_dates:
            self.selected_dates.add(date.today().isoformat())
        self.refresh_dates_list()

    def _on_time_checkbox_toggled(self, checked):
        self.time_start_edit.setEnabled(checked)
        self.time_end_edit.setEnabled(checked)

    def _on_time_start_changed(self, qtime):
        """開始時刻を終了時刻より後にした場合、終了時刻も自動で合わせる"""
        if self.time_end_edit.time() < qtime:
            self.time_end_edit.setTime(qtime)

    def _on_range_start_changed(self, qdate):
        """開始日を終了日より後にした場合、終了日も自動で合わせる（期間の逆転を防ぐ）"""
        if self.range_end_edit.date() < qdate:
            self.range_end_edit.setDate(qdate)

    def add_date_range(self):
        start = self.range_start_edit.date()
        end = self.range_end_edit.date()
        if end < start:
            QMessageBox.warning(self, "エラー", "終了日は開始日以降にしてください。")
            return
        d = start
        while d <= end:
            self.selected_dates.add(d.toString("yyyy-MM-dd"))
            d = d.addDays(1)
        self.refresh_dates_list()

    def remove_date(self, iso_date):
        self.selected_dates.discard(iso_date)
        self.refresh_dates_list()

    def refresh_dates_list(self):
        while self.dates_layout.count():
            child = self.dates_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.selected_dates:
            empty = QLabel("日付が選択されていません。")
            empty.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:12px; border:none;")
            self.dates_layout.addWidget(empty)
            return

        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        for iso_date in sorted(self.selected_dates):
            d = datetime.strptime(iso_date, "%Y-%m-%d").date()
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 0, 4, 0)
            row_layout.setSpacing(6)
            lbl = QLabel(f"{iso_date}（{weekday_names[d.weekday()]}）")
            lbl.setStyleSheet(f"color:{COLORS['text_main']}; font-size:12px; border:none;")
            row_layout.addWidget(lbl, stretch=1)
            del_btn = IconButton("×", COLORS["danger"], size=20)
            del_btn.clicked.connect(lambda checked=False, dd=iso_date: self.remove_date(dd))
            row_layout.addWidget(del_btn)
            self.dates_layout.addWidget(row)

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
        name = prompt_add_company(self.rdata, self)
        if name:
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
        if not self.selected_dates:
            QMessageBox.warning(self, "エラー", "日付を1つ以上追加してください。")
            return
        if self.time_checkbox.isChecked() and self.time_end_edit.time() < self.time_start_edit.time():
            QMessageBox.warning(self, "エラー", "終了時刻は開始時刻以降にしてください。")
            return

        notify_days = [days for days, cb in self.notify_checks.items() if cb.isChecked()]
        time_start = self.time_start_edit.time().toString("HH:mm") if self.time_checkbox.isChecked() else ""
        time_end = self.time_end_edit.time().toString("HH:mm") if self.time_checkbox.isChecked() else ""
        record = {
            "id": self.editing_event["id"] if self.editing_event else self.rdata.next_event_id(),
            "company": self.company_combo.currentText(),
            "status": self.status_combo.currentText(),
            "dates": sorted(self.selected_dates),
            "time_start": time_start,
            "time_end": time_end,
            "memo": self.memo_edit.text().strip(),
            "notify_days": notify_days,
        }

        if self.editing_event:
            for i, e in enumerate(self.rdata.events):
                if e["id"] == self.editing_event["id"]:
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
        self.setMinimumWidth(440)

        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(24, 24, 24, 24)
        self.layout_main.setSpacing(12)

        heading = QLabel(f"🗓️ {day.strftime('%Y年%m月%d日')} の予定")
        heading.setStyleSheet(f"font-size:17px; font-weight:800; color:{COLORS['primary']};")
        self.layout_main.addWidget(heading)

        self.list_area = QVBoxLayout()
        self.list_area.setSpacing(8)
        self.layout_main.addLayout(self.list_area)

        add_btn = StyledButton("＋ この日に予定を追加", COLORS["accent"], gradient_to=COLORS["primary"])
        add_btn.clicked.connect(self.add_event)
        self.layout_main.addWidget(add_btn)

        close_btn = StyledButton("閉じる", COLORS["surface2"], compact=True)
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
            empty.setStyleSheet(f"color:{COLORS['text_sub']}; padding:6px 2px;")
            self.list_area.addWidget(empty)
            return

        for e in events:
            row = QFrame()
            row.setStyleSheet(
                f"background-color:{COLORS['bg_base']}; border-radius:12px; border:1px solid {COLORS['surface1']};"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 10, 10, 10)
            row_layout.setSpacing(10)

            company_color = self.rdata.companies.get(e["company"], COLORS["border"])
            status_color = self.rdata.status_color(e["status"])
            chip = QLabel(f"{e['company']} / {e['status']}")
            chip.setStyleSheet(color_chip_style(company_color, status_color))
            row_layout.addWidget(chip)

            detail_text = event_dates_and_time_text(e)
            if e.get("memo"):
                detail_text += f" ・ {e['memo']}"
            memo_lbl = QLabel(detail_text)
            memo_lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:12px; border:none;")
            row_layout.addWidget(memo_lbl, stretch=1)

            edit_btn = OutlineButton("✏️ 編集", COLORS["primary"])
            edit_btn.clicked.connect(lambda checked=False, ev=e: self.edit_event(ev))
            row_layout.addWidget(edit_btn)

            del_btn = OutlineButton("🗑 削除", COLORS["danger"])
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
        dialog = EventDialog(self.rdata, editing_event=event, parent=self)
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
        self.resize(1180, 760)
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
            QMainWindow, QDialog {{ background-color: {COLORS['bg_mantle']}; }}
            QWidget {{ font-family: 'Meiryo UI', 'Segoe UI', 'Yu Gothic UI', 'Hiragino Sans', sans-serif; }}
            QLabel {{ color: {COLORS['text_main']}; font-size: 13px; }}
            QLineEdit, QComboBox, QDateEdit {{
                background-color: {COLORS['bg_base']};
                color: {COLORS['text_main']};
                border: 2px solid {COLORS['surface1']};
                border-radius: 10px;
                padding: 8px 12px;
                min-height: 22px;
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
                border: 2px solid {COLORS['primary']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['card_bg']};
                color: {COLORS['text_main']};
                selection-background-color: {COLORS['surface1']};
                border: 1px solid {COLORS['surface1']};
                outline: none;
            }}
            QCheckBox {{ color: {COLORS['text_main']}; font-size: 13px; spacing: 6px; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px;
                border-radius: 5px;
                border: 2px solid {COLORS['surface2']};
                background: {COLORS['bg_base']};
            }}
            QCheckBox::indicator:checked {{
                background: {COLORS['accent']};
                border: 2px solid {COLORS['accent']};
            }}
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['surface2']};
                border-radius: 5px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QMessageBox {{ background-color: {COLORS['bg_mantle']}; }}
            QMessageBox QLabel {{ color: {COLORS['text_main']}; font-size: 13px; }}
            QMessageBox QPushButton {{
                background-color: {COLORS['primary']};
                color: {contrasting_text_color(COLORS['primary'])};
                min-width: 90px;
                min-height: 34px;
                border-radius: 9px;
                font-weight: 700;
                border: none;
            }}
        """)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(18)

        # --- 中央: カレンダー ---
        center = QVBoxLayout()
        center.setSpacing(14)
        outer.addLayout(center, stretch=3)

        header = QHBoxLayout()
        header.setSpacing(4)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("🗓️ 就活選考カレンダー")
        title.setStyleSheet(f"font-size:24px; font-weight:800; color:{COLORS['text_main']};")
        subtitle = QLabel("企業カラー × 選考状況の枠色で、選考の進み具合をひと目で把握")
        subtitle.setStyleSheet(f"font-size:12px; color:{COLORS['text_sub']};")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        add_btn = StyledButton("＋ 予定を追加", COLORS["accent"], gradient_to=COLORS["primary"])
        add_btn.clicked.connect(self.open_add_event_from_header)
        header.addWidget(add_btn)
        center.addLayout(header)

        nav_card = QFrame()
        nav_card.setStyleSheet(f"""
            background-color:{COLORS['card_bg']};
            border:1px solid {COLORS['surface1']};
            border-radius:14px;
        """)
        nav_row = QHBoxLayout(nav_card)
        nav_row.setContentsMargins(10, 8, 10, 8)
        prev_btn = IconButton("‹", COLORS["surface1"])
        prev_btn.clicked.connect(self.prev_month)
        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignCenter)
        self.month_label.setStyleSheet(f"font-size:18px; font-weight:800; color:{COLORS['text_main']};")
        next_btn = IconButton("›", COLORS["surface1"])
        next_btn.clicked.connect(self.next_month)
        today_btn = StyledButton("今日", COLORS["surface2"], compact=True)
        today_btn.clicked.connect(self.go_today)
        nav_row.addWidget(prev_btn)
        nav_row.addWidget(self.month_label, stretch=1)
        nav_row.addWidget(next_btn)
        nav_row.addSpacing(8)
        nav_row.addWidget(today_btn)
        center.addWidget(nav_card)

        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(8)
        calendar_card = QFrame()
        calendar_card.setStyleSheet(f"""
            background-color:{COLORS['card_bg']};
            border-radius:18px;
            border:1px solid {COLORS['surface1']};
        """)
        calendar_card_layout = QVBoxLayout(calendar_card)
        calendar_card_layout.setContentsMargins(14, 14, 14, 14)
        calendar_card_layout.addLayout(self.calendar_grid)
        center.addWidget(calendar_card, stretch=1)

        # --- 右パネル: 通知 / 企業 / 選考状況 ---
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFixedWidth(320)
        right_container = QWidget()
        right = QVBoxLayout(right_container)
        right.setContentsMargins(0, 0, 4, 0)
        right.setSpacing(14)
        right_scroll.setWidget(right_container)
        outer.addWidget(right_scroll)

        notify_card, self.notify_layout = section_card("直近7日の締切・予定", "🔔")
        self.notify_layout.setSpacing(6)
        right.addWidget(notify_card)

        offer_card, self.offer_layout = section_card("内定企業一覧", "🎉")
        self.offer_layout.setSpacing(6)
        right.addWidget(offer_card)

        intern_card, self.intern_layout = section_card("インターン参加確定リスト", "🏁")
        self.intern_layout.setSpacing(6)
        right.addWidget(intern_card)

        add_company_btn = StyledButton("＋ 企業を追加", COLORS["accent"], compact=True)
        add_company_btn.clicked.connect(self.open_add_company_standalone)
        company_card, self.company_layout = section_card("登録済みの企業", "🏢", action_button=add_company_btn)
        self.company_layout.setSpacing(6)
        right.addWidget(company_card)

        status_card, self.status_layout = section_card("選考状況の一覧", "🏷️")
        self.status_layout.setSpacing(6)
        right.addWidget(status_card)

        right.addStretch()

    # --- カレンダー描画 ---
    def draw_calendar(self):
        self.month_label.setText(f"{self.cur_year}年 {self.cur_month}月")

        while self.calendar_grid.count():
            child = self.calendar_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        weekday_colors = [COLORS["text_sub"]] * 5 + [COLORS["primary"], COLORS["danger"]]
        for i, wd in enumerate(weekdays):
            lbl = QLabel(wd)
            lbl.setAlignment(Qt.AlignCenter)
            tint = hex_to_rgba(weekday_colors[i], 0.16) if i >= 5 else "transparent"
            lbl.setStyleSheet(
                f"font-weight:800; font-size:12px; color:{weekday_colors[i]}; "
                f"background-color:{tint}; border-radius:8px; padding:4px 0;"
            )
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
                cell.setMinimumSize(140, 96)
                cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                if is_today:
                    bg = hex_to_rgba(COLORS["primary"], 0.14)
                    bg_hover = hex_to_rgba(COLORS["primary"], 0.24)
                    border_color = COLORS["primary"]
                    border_width = 2
                else:
                    bg = COLORS["bg_base"]
                    bg_hover = adjust_color(COLORS["bg_base"], -14)
                    border_color = COLORS["surface1"]
                    border_width = 1
                cell.setStyleSheet(f"""
                    QFrame {{
                        background-color: {bg};
                        border: {border_width}px solid {border_color};
                        border-radius: 12px;
                    }}
                    QFrame:hover {{
                        background-color: {bg_hover};
                        border: {border_width}px solid {COLORS['primary']};
                    }}
                """)
                cell.setCursor(QCursor(Qt.PointingHandCursor))
                cell_layout = QVBoxLayout(cell)
                cell_layout.setContentsMargins(8, 6, 8, 6)
                cell_layout.setSpacing(3)

                day_lbl = QLabel(str(day_num))
                day_lbl.setStyleSheet(
                    f"font-weight:800; font-size:13px; "
                    f"color:{COLORS['primary'] if is_today else COLORS['text_main']}; border:none; background:transparent;"
                )
                cell_layout.addWidget(day_lbl)

                day_events = self.rdata.events_on(cell_date.isoformat())
                for e in day_events[:3]:
                    company_color = self.rdata.companies.get(e["company"], COLORS["border"])
                    status_color = self.rdata.status_color(e["status"])
                    chip = QLabel()
                    metrics = QFontMetrics(chip.font())
                    chip.setText(metrics.elidedText(e["company"], Qt.ElideRight, 96))
                    chip.setStyleSheet(color_chip_style(company_color, status_color))
                    cell_layout.addWidget(chip)
                if len(day_events) > 3:
                    more_lbl = QLabel(f"+{len(day_events) - 3}件")
                    more_lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:11px; border:none; background:transparent;")
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

    def open_add_company_standalone(self):
        name = prompt_add_company(self.rdata, self)
        if name:
            self.rdata.save()
            self.refresh_side_panels()

    def edit_company(self, name):
        color = self.rdata.companies.get(name, COMPANY_COLOR_PALETTE[0])
        dialog = AddCompanyDialog(color, initial_name=name, parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        new_name, new_color = dialog.result_data()
        if not new_name:
            QMessageBox.warning(self, "エラー", "企業名を入力してください。")
            return
        if new_name != name and new_name in self.rdata.companies:
            QMessageBox.warning(self, "エラー", "同じ名前の企業が既に登録されています。")
            return
        self.rdata.rename_company(name, new_name, new_color)
        self.rdata.save()
        self.on_data_changed()

    def delete_company(self, name):
        affected = self.rdata.events_with_company(name)
        msg = f"企業「{name}」を削除しますか？"
        if affected:
            msg += f"\n\nこの企業が設定された予定が{len(affected)}件あります。予定自体は削除されず、企業名だけが一覧の選択肢から消えます。"
        ret = QMessageBox.question(self, "確認", msg, QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.rdata.remove_company(name)
            self.rdata.save()
            self.on_data_changed()

    def delete_status(self, name):
        affected = self.rdata.events_with_status(name)
        msg = f"選考状況「{name}」を削除しますか？"
        if affected:
            msg += f"\n\nこの状況が設定された予定が{len(affected)}件あります。予定自体は削除されず、状況名だけが一覧の選択肢から消えます。"
        ret = QMessageBox.question(self, "確認", msg, QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.rdata.remove_status(name)
            self.rdata.save()
            self.on_data_changed()

    def edit_event_from_window(self, event):
        """内定・インターン参加確定リストなど、カレンダー以外の場所から予定を編集する"""
        dialog = EventDialog(self.rdata, editing_event=event, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self.rdata.save()
            self.on_data_changed()

    def delete_event_from_window(self, event):
        ret = QMessageBox.question(
            self, "確認", f"「{event['company']} / {event['status']}」の予定を削除しますか？",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.rdata.events = [e for e in self.rdata.events if e["id"] != event["id"]]
            self.rdata.save()
            self.on_data_changed()

    def on_data_changed(self):
        self.draw_calendar()
        self.refresh_side_panels()

    def go_today(self):
        today = date.today()
        self.cur_year, self.cur_month = today.year, today.month
        self.draw_calendar()

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
        self._clear_layout(self.notify_layout, keep_first=1)
        upcoming = self.rdata.upcoming_events(within_days=7)
        if not upcoming:
            lbl = QLabel("直近の締切・予定はありません。")
            lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:12px; border:none;")
            self.notify_layout.addWidget(lbl)
        for days_left, e in upcoming:
            when = "本日" if days_left == 0 else f"あと{days_left}日"
            badge_color = COLORS["danger"] if days_left == 0 else (COLORS["warning"] if days_left <= 1 else COLORS["primary"])
            lbl = QLabel(f"【{when}】{e['company']} / {e['status']}（{event_dates_and_time_text(e)}）")
            status_color = self.rdata.status_color(e["status"])
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"background-color:{COLORS['bg_base']}; border-left:5px solid {status_color}; "
                f"border-radius:8px; padding:7px 10px; color:{badge_color}; font-size:12px; font-weight:600;"
            )
            self.notify_layout.addWidget(lbl)

        self._clear_layout(self.offer_layout, keep_first=1)
        offers = sorted(self.rdata.events_with_status(OFFER_STATUS_NAME), key=lambda e: min(e["dates"]))
        if not offers:
            lbl = QLabel("内定はまだありません。")
            lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:12px; border:none;")
            self.offer_layout.addWidget(lbl)
        for e in offers:
            row = build_event_summary_row(self.rdata, e, self.edit_event_from_window, self.delete_event_from_window)
            self.offer_layout.addWidget(row)

        self._clear_layout(self.intern_layout, keep_first=1)
        interns = sorted(self.rdata.events_with_status(INTERN_CONFIRMED_STATUS_NAME), key=lambda e: min(e["dates"]))
        if not interns:
            lbl = QLabel("参加確定したインターンはまだありません。")
            lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:12px; border:none;")
            self.intern_layout.addWidget(lbl)
        for e in interns:
            row = build_event_summary_row(self.rdata, e, self.edit_event_from_window, self.delete_event_from_window)
            self.intern_layout.addWidget(row)

        self._clear_layout(self.company_layout, keep_first=1)
        if not self.rdata.companies:
            lbl = QLabel("まだ企業が登録されていません。")
            lbl.setStyleSheet(f"color:{COLORS['text_sub']}; font-size:12px; border:none;")
            self.company_layout.addWidget(lbl)
        for name, color in self.rdata.companies.items():
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            lbl = QLabel(name)
            lbl.setStyleSheet(color_chip_style(color) + "border-radius:20px;")
            row_layout.addWidget(lbl)
            row_layout.addStretch()

            edit_btn = IconButton("✏️", COLORS["primary"], size=22)
            edit_btn.clicked.connect(lambda checked=False, n=name: self.edit_company(n))
            row_layout.addWidget(edit_btn)

            del_btn = IconButton("×", COLORS["danger"], size=22)
            del_btn.clicked.connect(lambda checked=False, n=name: self.delete_company(n))
            row_layout.addWidget(del_btn)

            self.company_layout.addWidget(row)

        self._clear_layout(self.status_layout, keep_first=1)
        for s in self.rdata.statuses:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            preset_mark = "" if s.get("preset") else " ・追加"
            lbl = QLabel(f"{s['name']}{preset_mark}")
            lbl.setStyleSheet(
                f"border:3px solid {s['color']}; border-radius:20px; padding:4px 10px; "
                f"font-size:11px; font-weight:700; color:{COLORS['text_main']}; "
                f"background-color:{hex_to_rgba(s['color'], 0.20)};"
            )
            row_layout.addWidget(lbl)

            if not s.get("preset"):
                del_btn = IconButton("×", COLORS["danger"], size=22)
                del_btn.clicked.connect(lambda checked=False, name=s["name"]: self.delete_status(name))
                row_layout.addWidget(del_btn)

            row_layout.addStretch()
            self.status_layout.addWidget(row)

    @staticmethod
    def _clear_layout(layout, keep_first=0):
        while layout.count() > keep_first:
            child = layout.takeAt(keep_first)
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
            lines = [f"・{e['company']} / {e['status']}（{event_dates_and_time_text(e)}）" for e in hits]
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
