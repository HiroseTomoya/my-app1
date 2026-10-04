import sys
import json
import os
import shutil
import time #時間関連の機能をモジュール
import hashlib
import uuid
import math
import struct
import re
from datetime import datetime
import calendar #カレンダー機能をモジュール

# PySide6 モジュールのインポート
from PySide6.QtCore import (
    Qt, QThread, Signal, Slot, QUrl, QEvent, QPoint, QPointF, QRect, QRectF, QSize,
    QByteArray, QBuffer, QIODevice, QTimer
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLayout,
    QLabel, QLineEdit, QPushButton, QStackedWidget, QTextEdit,
    QScrollArea, QDialog, QComboBox, QMessageBox, QGridLayout, QFileDialog,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSizePolicy, QFrame, QListWidget, QAbstractItemView,
    QListWidgetItem, QListView, QStyledItemDelegate, QStyle, QStackedLayout
)
from PySide6.QtGui import (
    QFont, QCursor, QImage, QDesktopServices, QColor, QPixmap, QPainter, QPen,
    QTextDocument, QTextCharFormat, QStandardItemModel, QStandardItem, QIcon,
    QTextCursor, QFontMetrics, QPainterPath, QBitmap, QRegion, QFontDatabase, QIntValidator
)
from PySide6.QtPrintSupport import QPrinter

# Windows環境用の音声再生 (Mac/Linux環境を考慮してtry-except)
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


def resource_path(relative_path):
    # PyInstallerでexe化(--onefile)された時は展開先(sys._MEIPASS)、
    # 通常のスクリプト実行時はこのファイルと同じ場所から読む
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


# タイトル画面（ホーム画面のロゴ・メニューカード）だけに使う特別なフォント。
# 英字用と日本語用を1つのfont-familyリストにまとめてしまうと、Arkipelago(英字の
# 手書き風フォント)がCJKグリフを持たないせいでQtの折り返し計算が崩れ、長いラベルの
# 文字が化けることがあったため、文字列の中身で英字用/日本語用を切り替える。
# タイトルカードの文字色(濃い茶色)
TITLE_TEXT_BROWN = "#4A2E1A"

# 共通ボタンの立体表現: 板の下に見える台座の色と、板の縁取りの色
BUTTON_BASE_COLOR = "#7A5230"
BUTTON_EDGE_COLOR = "#B9976F"

# ホーム画面のメニューボタンの色(全ボタン共通)
MENU_CARD_COLOR = "#A67C55"

# 【お試し】True: タイマー以外の各画面(TO DO/メモ/カレンダー/ノート/セキュリティメモ)も手書き風フォントにする
SCREEN_FONT_TRIAL = True

# タイトル(EverGrove)専用フォント。Charbroiledを優先し、未インストールならArkipelagoで代用する
TITLE_FONT_EN = "'Forest Regular', 'Forest', 'Arkipelago', 'Segoe UI', 'Meiryo UI', sans-serif"
# 「ふい字」のTTFは内部のフォント名が'HuiFontP'として登録されるため(名前テーブルの
# 日本語名レコードが文字化けしており、OSは英語名の'HuiFontP'を使う)、'HuiFontP'を先に書く
TITLE_FONT_JA = "'HuiFontP', 'ふい字', 'Meiryo UI', 'Yu Gothic UI', 'Hiragino Sans', sans-serif"


def title_font_family(text):
    # タイトルカード(MultiMemo・日付)以外は、英数字も含めて全部ふい字にする
    return TITLE_FONT_JA


def fui_font(point_size):
    # QFontで直接フォントを指定する箇所(メモ本文・PDF出力など)用のふい字優先フォント
    f = QFont()
    f.setFamilies(["HuiFontP", "ふい字", "Meiryo UI", "Yu Gothic UI"])
    f.setPointSize(point_size)
    return f


# --- タイマー音: 周波数パターンからWAVデータを合成 ---
# 各パターンは (周波数Hz, 長さms) のリスト。周波数0は無音。
SOUND_PATTERNS = {
    "🔔 ベル": [(988, 90), (0, 40), (988, 90), (0, 40), (740, 420)],
    "🎵 マリンバ": [(523, 110), (659, 110), (784, 110), (1047, 260)],
    "🎹 ピアノ風": [(659, 160), (587, 160), (494, 160), (587, 160), (659, 480)],
    "📢 アラーム": [(1000, 200), (0, 110), (1000, 200), (0, 110), (1000, 460)],
    "⏰ 目覚まし": [(1240, 80), (0, 70)] * 6,
    "🚨 サイレン": [(680, 200), (960, 200)] * 4,
    "💧 ピコン": [(1568, 70), (0, 30), (2093, 150)],
    "🐦 ことり": [(2200, 55), (2600, 55), (2200, 55), (2900, 130)],
    "🎯 ピッピッ": [(1800, 90), (0, 90)] * 4,
    "🌙 やさしいチャイム": [(784, 260), (0, 60), (1047, 260), (0, 60), (1319, 620)],
}


# --- 配色（ライトテーマ） ---
COLORS = {
    "page":         "#EDF0F5",   # ウィンドウ背景（やわらかいグレー）
    "bg_base":      "#FFFFFF",    # 入力欄・セルなどの面
    "bg_surface":   "#F8FAFC",
    "card_bg":      "#FFFFFF",    # カード（白＝影で浮かせる）
    "primary":      "#4F46E5",    # インディゴ
    "accent":       "#7C3AED",    # バイオレット
    "success":      "#0D9488",    # ティール
    "danger":       "#E11D48",    # ローズ
    "info":         "#0284C7",    # スカイブルー（ノート機能用）
    "neutral":      "#64748B",    # スレート
    "text_main":    "#0F172A",
    "text_sub":     "#64748B",
    "border":       "#E2E8F0",
    "on_accent":    "#FFFFFF",
    "tab_active":   "#4F46E5",
    "tab_inactive": "#E2E8F0",
    "btn_back":     "#64748B",
    "warn":         "#EA580C",
}

# 機能ごとのグラデーション（明→濃）。ボタンやアイコンチップに使う
GRADIENTS = {
    "primary": ("#6366F1", "#4F46E5"),
    "accent":  ("#A855F7", "#7C3AED"),
    "success": ("#14B8A6", "#0D9488"),
    "danger":  ("#FB7185", "#E11D48"),
    "warn":    ("#FB923C", "#EA580C"),
    "info":    ("#38BDF8", "#0284C7"),
    "neutral": ("#94A3B8", "#64748B"),
    "hero":    ("#6366F1", "#A855F7"),
}


def lighten_hex(color, amount=30):
    # amountが負なら暗くする（0〜255にクランプ）
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    r = max(0, min(255, r + amount))
    g = max(0, min(255, g + amount))
    b = max(0, min(255, b + amount))
    return f"#{r:02x}{g:02x}{b:02x}"


def rgba_hex(color, alpha):
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def tint_hex(color, ratio):
    # ratio=1.0 で白、0.0 で元の色（付箋のような淡い色を作る）
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    r = round(r + (255 - r) * ratio)
    g = round(g + (255 - g) * ratio)
    b = round(b + (255 - b) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def grad_css(key_or_pair, x2=0, y2=1):
    if isinstance(key_or_pair, (tuple, list)):
        a, b = key_or_pair
    else:
        a, b = GRADIENTS.get(key_or_pair, (COLORS.get(key_or_pair, key_or_pair),) * 2)
    return f"qlineargradient(x1:0, y1:0, x2:{x2}, y2:{y2}, stop:0 {a}, stop:1 {b})"


def synth_wav(segments, volume=0.38, sample_rate=22050):
    """(周波数, 長さms) のリストから 16bit モノラル WAV のバイト列を生成する。"""
    frames = bytearray()
    fade = max(1, sample_rate // 200)  # クリック音防止の短いフェード
    for freq, dur_ms in segments:
        n = max(0, int(sample_rate * dur_ms / 1000))
        for i in range(n):
            if freq <= 0:
                frames += struct.pack("<h", 0)
                continue
            env = min(1.0, i / fade, (n - i) / fade)
            sample = int(volume * env * 32767 * math.sin(2 * math.pi * freq * i / sample_rate))
            frames += struct.pack("<h", max(-32768, min(32767, sample)))
    data_size = len(frames)
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", data_size)
    return bytes(header) + bytes(frames)


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


# --- クリップボード画像の貼り付けに対応したテキストエディタ ---
class MemoTextEdit(QTextEdit):
    image_pasted = Signal(object)  # QImage

    def insertFromMimeData(self, source):
        if source.hasImage():
            img = QImage(source.imageData())
            if not img.isNull():
                self.image_pasted.emit(img)
                return
        # 貼り付けた文書の太字などの書式はそのまま反映する。
        # ただしQt標準の挙動だと、貼り付けた文字の書式がそのままカーソルの
        # 入力書式として残り続けて以降のタイプまで太字化してしまうため、
        # 貼り付け直後にカーソルの書式だけ標準に戻しておく。
        super().insertFromMimeData(source)
        cursor = self.textCursor()
        cursor.setCharFormat(QTextCharFormat())
        self.setTextCursor(cursor)


# --- ノート本文用エディタ：挿入したスケッチ/グラフ画像をダブルクリックで削除できるようにする ---
class NoteTextEdit(QTextEdit):
    def _image_cursor_at_index(self, index):
        # 指定位置の直前・直後どちらかの1文字が画像なら、その画像だけを
        # 選択したカーソルを返す（見つからなければNone）
        doc = self.document()
        for start in (index - 1, index):
            if 0 <= start < doc.characterCount() - 1:
                c = QTextCursor(doc)
                c.setPosition(start)
                c.setPosition(start + 1, QTextCursor.KeepAnchor)
                if c.charFormat().isImageFormat():
                    return c
        return None

    def _image_cursor_at(self, viewport_pos):
        return self._image_cursor_at_index(self.cursorForPosition(viewport_pos).position())

    def image_cursor_at_text_cursor(self):
        # ツールバーの「画像を削除」ボタンから、いま入力カーソルがある位置の
        # 画像を探すために使う
        return self._image_cursor_at_index(self.textCursor().position())

    def delete_image_with_confirm(self, image_cursor):
        ret = QMessageBox.question(
            self, "確認", "この画像（スケッチ／グラフ）を削除しますか？",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            image_cursor.removeSelectedText()
            return True
        return False

    def mouseDoubleClickEvent(self, event):
        image_cursor = self._image_cursor_at(event.pos())
        if image_cursor is not None:
            self.delete_image_with_confirm(image_cursor)
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        is_image = self._image_cursor_at(event.pos()) is not None
        self.viewport().setCursor(Qt.PointingHandCursor if is_image else Qt.IBeamCursor)
        super().mouseMoveEvent(event)


# --- 画像タイルを敷き詰めて描画する背景ウィジェット（QSSのbackground-repeatが不安定なため） ---
class TiledBackgroundWidget(QWidget):
    def __init__(self, pixmap=None, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap

    def setTilePixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        if self._pixmap and not self._pixmap.isNull():
            # 写真を敷き詰める(タイル)のではなく、アスペクト比を保ったまま
            # ウィンドウ全体を覆うように拡大・中央寄せして描画する(CSSのbackground-size:coverと同様)。
            # 高DPI環境でもぼやけないよう、物理ピクセル数で縮小してからdevicePixelRatioを教える
            painter = QPainter(self)
            target = self.rect()
            dpr = self.devicePixelRatioF()
            scaled = self._pixmap.scaled(target.size() * dpr, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(dpr)
            x = (target.width() - scaled.width() / dpr) // 2
            y = (target.height() - scaled.height() / dpr) // 2
            painter.drawPixmap(round(x), round(y), scaled)
            painter.end()
        super().paintEvent(event)


# --- 画びょう付きのノート画像(assets/notebook_pin.png)を背景に描くパネル(タイマー画面用) ---
class PinnedNotePanel(QWidget):
    # 画像の縦横比(幅:高さ)を保ったまま、幅に合わせて高さを決める
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self._pix = pixmap
        self.setAttribute(Qt.WA_StyledBackground, False)

    def hasHeightForWidth(self):
        return self._pix is not None and not self._pix.isNull()

    def heightForWidth(self, w):
        if not self.hasHeightForWidth():
            return -1
        return round(w * self._pix.height() / self._pix.width())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.hasHeightForWidth():
            h = self.heightForWidth(self.width())
            if h != self.height():
                self.setFixedHeight(h)

    def paintEvent(self, event):
        if self._pix is None or self._pix.isNull():
            return super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        dpr = self.devicePixelRatioF()
        scaled = self._pix.scaled(
            round(self.width() * dpr), round(self.height() * dpr),
            Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        painter.drawPixmap(0, 0, scaled)
        painter.end()


# --- レイアウト確定後に on_layout を呼ぶ紙ウィジェット(枝の位置合わせ用) ---
class AnchorPaper(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.on_layout = None

    def _run_anchor(self):
        if self.on_layout:
            self.on_layout()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._run_anchor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._run_anchor)


def _paint_wood_tint(painter, rect, wood_pixmap, tint_color, tint_alpha, radius, border_color=None, border_width=1, dpr=1.0):
    # 角丸にクリップした領域へ木目写真をcover-fitで描き、その上に色をのせて着色する。
    # QSSのborder-imageだと縮小時のスケーリング品質が不安定だったため、直接描画に統一する。
    # dprは画面の拡大率(devicePixelRatio)。これを掛けた物理ピクセル数で縮小してから
    # setDevicePixelRatioしておくことで、高DPI環境でもQtが二重に引き伸ばしてぼやけさせない
    painter.setRenderHint(QPainter.Antialiasing, True)
    rf = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
    path = QPainterPath()
    path.addRoundedRect(rf, radius, radius)
    painter.save()
    painter.setClipPath(path)
    if wood_pixmap and not wood_pixmap.isNull():
        physical_size = rect.size() * dpr
        scaled = wood_pixmap.scaled(physical_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        x = (rect.width() - scaled.width() / dpr) // 2
        y = (rect.height() - scaled.height() / dpr) // 2
        painter.drawPixmap(round(x), round(y), scaled)
    tint = QColor(tint_color)
    tint.setAlpha(tint_alpha)
    painter.fillRect(rect, tint)
    painter.restore()
    if border_color is not None:
        painter.save()
        painter.setPen(QPen(QColor(border_color), border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rf, radius, radius)
        painter.restore()


# --- 木目写真を色でステインした、角丸の静的パネル(タイトルカードなど) ---
class WoodPanel(QWidget):
    def __init__(self, wood_pixmap, tint_color, tint_alpha, radius, border_color=None, parent=None):
        super().__init__(parent)
        self._wood = wood_pixmap
        self._tint_color = tint_color
        self._tint_alpha = tint_alpha
        self._radius = radius
        self._border_color = border_color

    def paintEvent(self, event):
        painter = QPainter(self)
        _paint_wood_tint(
            painter, self.rect(), self._wood, self._tint_color, self._tint_alpha,
            self._radius, border_color=self._border_color, dpr=self.devicePixelRatioF(),
        )
        painter.end()
        super().paintEvent(event)


# --- 木目写真を色でステインした、角丸の押しボタン(ホバー/押下で濃さが変わる) ---
class WoodButton(QPushButton):
    def __init__(self, wood_pixmap, tint_color, tint_alpha, hover_tint_color, radius, parent=None):
        super().__init__(parent)
        self._wood = wood_pixmap
        self._tint_color = tint_color
        self._tint_alpha = tint_alpha
        self._hover_tint_color = hover_tint_color
        self._radius = radius
        self.setStyleSheet("border: none; background: transparent; text-align: left;")

    def paintEvent(self, event):
        painter = QPainter(self)
        color = self._hover_tint_color if (self.underMouse() or self.isDown()) else self._tint_color
        _paint_wood_tint(painter, self.rect(), self._wood, color, self._tint_alpha, self._radius, dpr=self.devicePixelRatioF())
        painter.end()
        super().paintEvent(event)


_BUTTON_WOOD_PIX = None


def get_button_wood_pixmap():
    # 全ボタン共通の木の板画像(assets/button_wood.jpg)。板と板の境目が中央に来るよう切り出し済み
    global _BUTTON_WOOD_PIX
    if _BUTTON_WOOD_PIX is None:
        path = resource_path(os.path.join("assets", "button_wood.jpg"))
        pix = QPixmap(path) if os.path.exists(path) else QPixmap()
        _BUTTON_WOOD_PIX = pix
    return _BUTTON_WOOD_PIX


# --- アプリ内の共通ボタン: 板の境目が中央に来る木目を貼り、文字を白で重ねる ---
class WoodSkinButton(QPushButton):
    def __init__(self, text="", radius=10, parent=None):
        super().__init__("", parent)
        self._skin_radius = radius
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setText(text)

    def setText(self, text):
        apply_glyph_icon(self, text)

    def paintEvent(self, event):
        # ホーム画面のボタンと同じ「台座の上に板が載った」立体的な見た目にする。
        # 下に濃い茶色の台座を見せ、押している間は板が沈み込む
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        depth = max(3, min(6, round(h * 0.09)))
        down = self.isDown()
        face_top = (depth - 1) if down else 0
        face_h = h - depth
        radius = min(self._skin_radius, face_h // 2)

        # 台座(板の下に見える濃い茶色)
        base = QRectF(0.5, depth + 0.5, w - 1, h - depth - 1)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(BUTTON_BASE_COLOR))
        painter.drawRoundedRect(base, radius, radius)

        # 木の板(押している間は下に下がる)
        pressed_or_hover = self.underMouse() or down
        tint, alpha = ("#000000", 22) if pressed_or_hover else ("#FFFFFF", 0)
        face_rect = QRect(0, face_top, w, face_h)
        _paint_wood_tint(
            painter, face_rect, get_button_wood_pixmap(), tint,
            alpha, radius, border_color=BUTTON_EDGE_COLOR, dpr=self.devicePixelRatioF(),
        )
        painter.end()
        super().paintEvent(event)


def make_symbol_icon(kind, color="#4A3426", size=40):
    # ▶ ■ ↺ ♪ などの記号を、フォントに頼らず図形として描いたアイコンにする。
    # (ふい字にはこれらの記号の字形がなく、小さな点としか表示されないため)
    dpr = 2
    s = size * dpr
    pm = QPixmap(s, s)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    col = QColor(color)
    p.setPen(Qt.NoPen)
    p.setBrush(col)
    m = s * 0.18
    if kind == "play":
        path = QPainterPath()
        path.moveTo(m + s * 0.06, m)
        path.lineTo(s - m, s / 2)
        path.lineTo(m + s * 0.06, s - m)
        path.closeSubpath()
        p.drawPath(path)
    elif kind == "stop":
        p.drawRoundedRect(QRectF(m, m, s - 2 * m, s - 2 * m), s * 0.08, s * 0.08)
    elif kind == "reset":
        pen = QPen(col, s * 0.11, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        rect = QRectF(m, m, s - 2 * m, s - 2 * m)
        p.drawArc(rect, 40 * 16, 290 * 16)      # 上の右寄りから反時計回りにほぼ一周
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        ax, ay = rect.center().x() + rect.width() / 2 * 0.77, rect.center().y() - rect.height() / 2 * 0.64
        head = QPainterPath()
        head.moveTo(ax - s * 0.02, ay - s * 0.20)
        head.lineTo(ax + s * 0.20, ay + s * 0.02)
        head.lineTo(ax - s * 0.14, ay + s * 0.10)
        head.closeSubpath()
        p.drawPath(head)
    elif kind == "note":
        p.drawEllipse(QRectF(s * 0.22, s * 0.58, s * 0.30, s * 0.24))
        p.drawRect(QRectF(s * 0.46, s * 0.20, s * 0.07, s * 0.54))
        flag = QPainterPath()
        flag.moveTo(s * 0.52, s * 0.20)
        flag.cubicTo(s * 0.78, s * 0.26, s * 0.78, s * 0.46, s * 0.68, s * 0.52)
        flag.cubicTo(s * 0.72, s * 0.40, s * 0.62, s * 0.34, s * 0.52, s * 0.34)
        flag.closeSubpath()
        p.drawPath(flag)
    else:
        _draw_line_glyph(p, kind, s, col)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def _draw_line_glyph(p, kind, s, col):
    # 40x40の座標系で描く線画アイコン(編集・削除・PDFなど。絵文字はふい字で出ないため図形で描く)
    p.save()
    p.scale(s / 40.0, s / 40.0)
    pen = QPen(col, 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if kind == "edit":
        p.translate(20, 20)
        p.rotate(45)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(-4, -16, 8, 20), 1.5, 1.5)
        tip = QPainterPath()
        tip.moveTo(-4, 5.5); tip.lineTo(4, 5.5); tip.lineTo(0, 15); tip.closeSubpath()
        p.drawPath(tip)
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.drawRect(QRectF(-5, -9.5, 10, 1.6))
    elif kind == "trash":
        p.drawLine(QPointF(8, 11), QPointF(32, 11))
        p.drawRoundedRect(QRectF(15.5, 6, 9, 5), 1.5, 1.5)
        body = QPainterPath()
        body.moveTo(11, 15); body.lineTo(12.5, 33); body.lineTo(27.5, 33); body.lineTo(29, 15)
        p.drawPath(body)
        p.drawLine(QPointF(16.5, 19), QPointF(16.5, 29))
        p.drawLine(QPointF(23.5, 19), QPointF(23.5, 29))
    elif kind == "menu":
        for y in (11, 20, 29):
            p.drawLine(QPointF(8, y), QPointF(32, y))
    elif kind == "doc":
        page = QPainterPath()
        page.moveTo(11, 5); page.lineTo(24, 5); page.lineTo(30, 11)
        page.lineTo(30, 35); page.lineTo(11, 35); page.closeSubpath()
        p.drawPath(page)
        p.drawLine(QPointF(24, 5), QPointF(24, 11)); p.drawLine(QPointF(24, 11), QPointF(30, 11))
        for y in (19, 25, 30):
            p.drawLine(QPointF(15.5, y), QPointF(25.5, y))
    elif kind == "clip":
        path = QPainterPath()
        path.moveTo(22, 25); path.lineTo(22, 14)
        path.arcTo(QRectF(15, 10.5, 7, 7), 0, 180)
        path.lineTo(15, 29)
        path.arcTo(QRectF(15, 22.5, 13, 13), 180, 180)
        path.lineTo(28, 11)
        p.drawPath(path)
    elif kind == "link":
        p.translate(20, 20)
        p.rotate(-45)
        p.drawRoundedRect(QRectF(-16, -5, 18, 10), 5, 5)
        p.drawRoundedRect(QRectF(-2, -5, 18, 10), 5, 5)
    elif kind == "paste":
        p.drawRoundedRect(QRectF(9, 9, 22, 26), 3, 3)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(14, 5, 12, 7), 2, 2)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(14, 21), QPointF(26, 21)); p.drawLine(QPointF(14, 27), QPointF(26, 27))
    elif kind == "graph":
        ax = QPainterPath()
        ax.moveTo(8, 6); ax.lineTo(8, 33); ax.lineTo(34, 33)
        p.drawPath(ax)
        line = QPainterPath()
        line.moveTo(12, 27); line.lineTo(19, 18); line.lineTo(24, 23); line.lineTo(32, 10)
        p.drawPath(line)
    elif kind == "check":
        pen.setWidthF(4.2); p.setPen(pen)
        chk = QPainterPath()
        chk.moveTo(9, 21); chk.lineTo(17, 29); chk.lineTo(31, 11)
        p.drawPath(chk)
    elif kind in ("eye", "eye_off"):
        eye = QPainterPath()
        eye.moveTo(4, 20); eye.quadTo(20, 3, 36, 20); eye.quadTo(20, 37, 4, 20)
        p.drawPath(eye)
        p.setPen(Qt.NoPen); p.setBrush(col)
        p.drawEllipse(QPointF(20, 20), 5, 5)
        if kind == "eye_off":
            p.setPen(pen)
            p.drawLine(QPointF(9, 33), QPointF(31, 7))
    elif kind in ("lock", "unlock"):
        shackle = QPainterPath()
        shackle.moveTo(14, 18)
        shackle.lineTo(14, 13)
        shackle.arcTo(QRectF(14, 6, 12, 12), 180, -180)
        if kind == "lock":
            shackle.lineTo(26, 18)
        p.drawPath(shackle)
        p.setPen(Qt.NoPen); p.setBrush(col)
        p.drawRoundedRect(QRectF(9, 18, 22, 16), 3, 3)
    p.restore()


# ボタン文字の頭にある絵文字・記号 → 描画アイコンの種類
GLYPH_ICON_KINDS = {
    "✏️": "edit", "✏": "edit", "🗑️": "trash", "🗑": "trash", "☰": "menu", "📄": "doc",
    "📎": "clip", "🔗": "link", "📋": "paste", "📈": "graph", "✓": "check",
    "👁": "eye", "🙈": "eye_off", "🔒": "lock", "🔓": "unlock",
}


def split_glyph(text):
    # "🗑 削除" → ("trash", "削除")。対応する記号が頭に無ければ (None, text)
    for g in sorted(GLYPH_ICON_KINDS, key=len, reverse=True):
        if text.startswith(g):
            return GLYPH_ICON_KINDS[g], text[len(g):].lstrip()
    return None, text


def apply_glyph_icon(btn, text, color="#4A3426", size=18):
    # ボタンに文字を設定する。頭に絵文字があれば描いたアイコンに置き換える
    kind, rest = split_glyph(text)
    if kind:
        btn.setIcon(make_symbol_icon(kind, color, 40))
        btn.setIconSize(QSize(size, size))
        QPushButton.setText(btn, rest)
    else:
        QPushButton.setText(btn, text)


# --- ボタンなどを幅に応じて自動的に折り返すレイアウト（小さいウィンドウでツールバーの
#     項目が見切れないようにするため。QtのFlowLayoutサンプルの定番実装） ---
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, h_spacing=6, v_spacing=6):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x, y = effective.x(), effective.y()
        line_height = 0

        for item in self._items:
            next_x = x + item.sizeHint().width() + self._h_spacing
            if next_x - self._h_spacing > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + self._v_spacing
                next_x = x + item.sizeHint().width() + self._h_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + bottom


# --- カスタムボタンスタイル ---
class StyledButton(WoodSkinButton):
    def __init__(self, text, base_color, parent=None, width=None, compact=False):
        super().__init__(text, radius=13, parent=parent)
        self.base_color = base_color
        if width:
            self.setFixedWidth(width)

        pad = "11px 22px" if compact else "14px 30px"
        font_size = "14px" if compact else "16px"
        # 背景は木目をpaintEventで描くので透明。色分けはせず全ボタン同じ木目にする
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: #4A3426;
                font-family: {TITLE_FONT_JA if SCREEN_FONT_TRIAL else "'Meiryo UI', 'Segoe UI', sans-serif"};
                font-size: {font_size};
                font-weight: 700;
                border-radius: 13px;
                padding: {pad};
                border: none;
                min-height: 38px;
            }}
        """)

    def lighten(self, color, amount=35):
        return lighten_hex(color, amount)


# --- メモをPDFファイルとして書き出す共通処理 ---
def export_note_to_pdf(parent, title, text):
    if not text or not text.strip():
        QMessageBox.warning(parent, "PDF書き出し", "メモが空のため、PDFを作成できません。")
        return

    safe_name = re.sub(r'[\\/:*?"<>|]', "_", title).strip() or "memo"
    path, _ = QFileDialog.getSaveFileName(parent, "PDFとして保存", f"{safe_name}.pdf", "PDF ファイル (*.pdf)")
    if not path:
        return
    if not path.lower().endswith(".pdf"):
        path += ".pdf"

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html_body = esc(text).replace("\n", "<br>")
    doc = QTextDocument()
    doc.setDefaultFont(fui_font(11))
    doc.setHtml(
        f"<h2 style='margin-bottom:10px;'>{esc(title)}</h2>"
        f"<div style='font-size:11pt; line-height:1.7;'>{html_body}</div>"
    )

    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    doc.print_(printer)

    QMessageBox.information(parent, "PDF書き出し", f"PDFとして保存しました:\n{path}")


# --- 関数のグラフ画像を描く（数式の入力→QPainterで軸・目盛り・曲線を描画） ---
_GRAPH_SAFE_NAMES = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
    "exp": math.exp, "pi": math.pi, "e": math.e,
    "abs": abs, "pow": pow, "floor": math.floor, "ceil": math.ceil,
}


def _graph_eval_at(expr, x):
    try:
        y = eval(expr, {"__builtins__": {}}, dict(_GRAPH_SAFE_NAMES, x=x))
        y = float(y)
        return y if math.isfinite(y) else None
    except Exception:
        return None


def render_function_graph(expr, x_min, x_max, width=520, height=340):
    # 戻り値: (QPixmap, None) 成功時 / (None, エラーメッセージ) 失敗時
    expr = (expr or "").strip()
    if not expr:
        return None, "式を入力してください"
    if x_min >= x_max:
        return None, "xの範囲が正しくありません（最小値 < 最大値）"

    samples = 400
    xs = [x_min + (x_max - x_min) * i / (samples - 1) for i in range(samples)]
    ys = [_graph_eval_at(expr, x) for x in xs]
    finite_ys = sorted(y for y in ys if y is not None)
    if not finite_ys:
        return None, "この式を計算できませんでした。入力を確認してください（例: x**2, sin(x), sqrt(x)）"

    n = len(finite_ys)
    y_lo = finite_ys[max(0, int(n * 0.05))]
    y_hi = finite_ys[min(n - 1, int(n * 0.95))]
    if y_lo == y_hi:
        y_lo, y_hi = y_lo - 1, y_hi + 1
    pad = (y_hi - y_lo) * 0.15
    y_min, y_max = y_lo - pad, y_hi + pad
    jump_limit = (y_max - y_min) * 1.4

    margin_l, margin_r, margin_t, margin_b = 46, 20, 18, 34
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    def px(x):
        return margin_l + (x - x_min) / (x_max - x_min) * plot_w

    def py(y):
        return margin_t + (y_max - y) / (y_max - y_min) * plot_h

    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("#FFFDF6"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # 目盛り線（グリッド）
    grid_pen = QPen(QColor("#E2E8F0"), 1)
    painter.setPen(grid_pen)
    tick_count = 8

    def nice_step(span):
        raw = span / tick_count
        mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
        for m in (1, 2, 2.5, 5, 10):
            if raw <= m * mag:
                return m * mag
        return 10 * mag

    x_step = nice_step(x_max - x_min)
    y_step = nice_step(y_max - y_min)

    font = fui_font(8)
    painter.setFont(font)
    fm = QFontMetrics(font)

    gx = math.ceil(x_min / x_step) * x_step
    while gx <= x_max:
        xp = px(gx)
        painter.setPen(grid_pen)
        painter.drawLine(QPointF(xp, margin_t), QPointF(xp, height - margin_b))
        painter.setPen(QColor("#94A3B8"))
        label = f"{gx:g}"
        painter.drawText(QPointF(xp - fm.horizontalAdvance(label) / 2, height - margin_b + 16), label)
        gx += x_step

    gy = math.ceil(y_min / y_step) * y_step
    while gy <= y_max:
        yp = py(gy)
        painter.setPen(grid_pen)
        painter.drawLine(QPointF(margin_l, yp), QPointF(width - margin_r, yp))
        painter.setPen(QColor("#94A3B8"))
        label = f"{gy:g}"
        painter.drawText(QPointF(margin_l - fm.horizontalAdvance(label) - 6, yp + 4), label)
        gy += y_step

    # 軸（0が範囲内にあれば太めの線で強調）
    axis_pen = QPen(QColor("#475569"), 1.5)
    painter.setPen(axis_pen)
    if x_min <= 0 <= x_max:
        xp = px(0)
        painter.drawLine(QPointF(xp, margin_t), QPointF(xp, height - margin_b))
    if y_min <= 0 <= y_max:
        yp = py(0)
        painter.drawLine(QPointF(margin_l, yp), QPointF(width - margin_r, yp))

    # 枠
    painter.setPen(QPen(QColor("#CBD5E1"), 1))
    painter.drawRect(QRectF(margin_l, margin_t, plot_w, plot_h))

    # 曲線本体（漸近線などで大きく飛ぶ区間は線をつながず途切れさせる）
    painter.setClipRect(QRectF(margin_l, margin_t, plot_w, plot_h))
    curve_pen = QPen(QColor("#0284C7"), 2.2)
    curve_pen.setCapStyle(Qt.RoundCap)
    curve_pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(curve_pen)
    prev_point = None
    prev_y = None
    for x, y in zip(xs, ys):
        if y is None:
            prev_point = None
            prev_y = None
            continue
        point = QPointF(px(x), py(y))
        if prev_point is not None and abs(y - prev_y) <= jump_limit:
            painter.drawLine(prev_point, point)
        prev_point = point
        prev_y = y
    painter.end()
    return pixmap, None


class SketchCanvas(QWidget):
    # マウスでノートに自由に手書きできる簡易キャンバス
    def __init__(self, width=560, height=360, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setCursor(Qt.CrossCursor)
        self._pixmap = QPixmap(width, height)
        self._pixmap.fill(QColor("#FFFDF6"))
        self._pen_color = QColor("#1F2937")
        self._pen_width = 3
        self._last_point = None
        self._drawing = False

    def set_pen(self, color, width):
        self._pen_color = QColor(color)
        self._pen_width = width

    def clear_canvas(self):
        self._pixmap.fill(QColor("#FFFDF6"))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drawing = True
            self._last_point = event.pos()

    def mouseMoveEvent(self, event):
        if self._drawing and self._last_point is not None:
            pos = event.pos()
            painter = QPainter(self._pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(self._pen_color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self._last_point, pos)
            painter.end()
            self._last_point = pos
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drawing = False
            self._last_point = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)

    def to_image(self):
        return self._pixmap.toImage()


class SketchDialog(QDialog):
    # 手書きでグラフや図形をスケッチしてノートに挿入するダイアログ
    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("手書きスケッチ")
        self.result_image = None
        self._colors_preset = ["#1F2937", "#E11D48", "#2563EB", "#0D9488", "#EA580C"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        hint = QLabel("マウスでドラッグして自由に描けます。グラフの軸や図形を手描きでメモできます。")
        hint.setStyleSheet(f"color: {colors['text_sub']}; font-size: 12.5px;")
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.canvas = SketchCanvas()

        for c in self._colors_preset:
            btn = QPushButton()
            btn.setFixedSize(26, 26)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setStyleSheet(f"QPushButton {{ background-color: {c}; border-radius: 13px; border: 2px solid white; }}")
            btn.clicked.connect(lambda checked=False, col=c: self.canvas.set_pen(col, self.canvas._pen_width))
            toolbar.addWidget(btn)

        toolbar.addSpacing(10)
        for label, w in (("細", 2), ("中", 4), ("太", 8)):
            btn = self._ghost_like_btn(label, colors)
            btn.clicked.connect(lambda checked=False, ww=w: self.canvas.set_pen(self.canvas._pen_color.name(), ww))
            toolbar.addWidget(btn)

        toolbar.addSpacing(10)
        eraser_btn = self._ghost_like_btn("消しゴム", colors)
        eraser_btn.clicked.connect(lambda: self.canvas.set_pen("#FFFDF6", 16))
        toolbar.addWidget(eraser_btn)

        clear_btn = self._ghost_like_btn("全消去", colors)
        clear_btn.clicked.connect(self.canvas.clear_canvas)
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        canvas_frame = QFrame()
        canvas_frame.setStyleSheet(f"QFrame {{ border: 1px solid {colors['border']}; border-radius: 10px; }}")
        cf_layout = QVBoxLayout(canvas_frame)
        cf_layout.setContentsMargins(1, 1, 1, 1)
        cf_layout.addWidget(self.canvas)
        layout.addWidget(canvas_frame)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = self._ghost_like_btn("キャンセル", colors)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        insert_btn = StyledButton("ノートに挿入", colors["info"], compact=True)
        insert_btn.clicked.connect(self._on_insert)
        btn_row.addWidget(insert_btn)
        layout.addLayout(btn_row)

    def _ghost_like_btn(self, text, colors):
        b = QPushButton(text)
        b.setCursor(QCursor(Qt.PointingHandCursor))
        b.setStyleSheet(f"""
            QPushButton {{
                color: {colors['text_sub']};
                background: transparent;
                border: 1px solid {colors['border']};
                border-radius: 9px;
                padding: 6px 12px;
                font-size: 12.5px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {colors['bg_surface']}; }}
        """)
        return b

    def _on_insert(self):
        self.result_image = self.canvas.to_image()
        self.accept()


class FunctionGraphDialog(QDialog):
    # y=f(x) の形の数式からグラフ画像を生成してノートに挿入するダイアログ
    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("関数グラフを挿入")
        self.result_image = None
        self._colors = colors

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        hint = QLabel("例: x**2 ／ sin(x) ／ sqrt(x)+1 ／ 1/x　（x の式として入力してください）")
        hint.setStyleSheet(f"color: {colors['text_sub']}; font-size: 12.5px;")
        layout.addWidget(hint)

        form_row = QHBoxLayout()
        form_row.setSpacing(8)
        form_row.addWidget(QLabel("y ="))
        self.expr_input = QLineEdit()
        self.expr_input.setPlaceholderText("x**2")
        form_row.addWidget(self.expr_input, stretch=1)
        form_row.addWidget(QLabel("x:"))
        self.xmin_input = QLineEdit("-10")
        self.xmin_input.setFixedWidth(60)
        form_row.addWidget(self.xmin_input)
        form_row.addWidget(QLabel("〜"))
        self.xmax_input = QLineEdit("10")
        self.xmax_input.setFixedWidth(60)
        form_row.addWidget(self.xmax_input)
        preview_btn = StyledButton("プレビュー", colors["info"], compact=True)
        preview_btn.clicked.connect(self._update_preview)
        form_row.addWidget(preview_btn)
        layout.addLayout(form_row)

        self.preview_label = QLabel("式を入力して「プレビュー」を押してください")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedSize(520, 340)
        self.preview_label.setStyleSheet(f"""
            QLabel {{
                background-color: #FFFDF6;
                border: 1px solid {colors['border']};
                border-radius: 10px;
                color: {colors['text_sub']};
                font-size: 13px;
            }}
        """)
        layout.addWidget(self.preview_label)

        self.expr_input.returnPressed.connect(self._update_preview)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                color: {colors['text_sub']}; background: transparent;
                border: 1px solid {colors['border']}; border-radius: 9px;
                padding: 8px 16px; font-size: 13px; font-weight: 600;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self.insert_btn = StyledButton("ノートに挿入", colors["info"], compact=True)
        self.insert_btn.setEnabled(False)
        self.insert_btn.clicked.connect(self._on_insert)
        btn_row.addWidget(self.insert_btn)
        layout.addLayout(btn_row)

        self._last_pixmap = None

    def _update_preview(self):
        try:
            x_min = float(self.xmin_input.text())
            x_max = float(self.xmax_input.text())
        except ValueError:
            QMessageBox.warning(self, "警告", "xの範囲は数値で入力してください")
            return
        pixmap, error = render_function_graph(self.expr_input.text(), x_min, x_max)
        if error:
            self._last_pixmap = None
            self.insert_btn.setEnabled(False)
            self.preview_label.setText(error)
            self.preview_label.setPixmap(QPixmap())
            return
        self._last_pixmap = pixmap
        self.preview_label.setPixmap(pixmap)
        self.insert_btn.setEnabled(True)

    def _on_insert(self):
        if self._last_pixmap is not None:
            self.result_image = self._last_pixmap.toImage()
            self.accept()


# --- カスタム入力ダイアログ ---
class StyledInputDialog(QDialog):
    def __init__(self, title, prompt, initial_value="", is_password=False,
                 multiline=False, accent=None, parent=None, pdf_title=None):
        super().__init__(parent)
        self.multiline = multiline
        self._accent = accent or COLORS['primary']
        self._pdf_title = pdf_title
        self.setModal(True)
        self.setWindowTitle(title)
        self.setStyleSheet(f"QDialog {{ background-color: {COLORS['bg_base']}; }}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(16)

        p = QLabel(prompt)
        p.setWordWrap(True)
        p.setStyleSheet(f"color: {COLORS['text_main']}; font-size: 16px; font-weight: 700; background: transparent; border: none;")
        lay.addWidget(p)

        # 入力欄: 枠は外側のコンテナだけに描かせ、中身のウィジェットは枠なしにする
        # （QTextEdit が持つ標準フレームと二重に見えるのを防ぐ）
        self._field = QFrame()
        self._field.setObjectName("dlgField")
        self._set_field_border(COLORS['border'])
        fl = QVBoxLayout(self._field)
        fl.setContentsMargins(12, 8, 12, 8)

        inner_css = f"""
            background: transparent;
            border: none;
            color: {COLORS['text_main']};
            font-family: 'HuiFontP', 'ふい字', 'Meiryo UI', 'Segoe UI', sans-serif;
            font-size: 15px;
            selection-background-color: #BFDBFE;
        """
        if multiline:
            self.entry = QTextEdit()
            self.entry.setPlainText(initial_value)
            self.entry.setMinimumSize(430, 150)
            self.entry.setFrameShape(QFrame.NoFrame)
            self.entry.setStyleSheet(
                f"QTextEdit {{ {inner_css} }}"
                f"QScrollBar:vertical {{ border: none; background: transparent; width: 8px; margin: 2px; }}"
                f"QScrollBar::handle:vertical {{ background: {COLORS['border']}; border-radius: 4px; min-height: 24px; }}"
                f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
            )
        else:
            self.entry = QLineEdit()
            self.entry.setText(initial_value)
            self.entry.setMinimumWidth(430)
            self.entry.setStyleSheet(f"QLineEdit {{ {inner_css} }}")
            if is_password:
                self.entry.setEchoMode(QLineEdit.Password)
            self.entry.returnPressed.connect(self.accept)
        self.entry.installEventFilter(self)
        fl.addWidget(self.entry)
        lay.addWidget(self._field)

        brow = QHBoxLayout()
        brow.setSpacing(10)
        if self._pdf_title is not None:
            pdf_btn = QPushButton()
            apply_glyph_icon(pdf_btn, "📄 PDFで保存", self._accent)
            pdf_btn.setCursor(QCursor(Qt.PointingHandCursor))
            pdf_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {self._accent};
                    background: transparent;
                    border: 1px solid {self._accent};
                    border-radius: 11px;
                    padding: 11px 18px;
                    font-size: 14px;
                    font-weight: 700;
                }}
                QPushButton:hover {{ background: {COLORS['bg_surface']}; }}
            """)
            pdf_btn.clicked.connect(self._export_pdf)
            brow.addWidget(pdf_btn)
        brow.addStretch()
        cancel = QPushButton("キャンセル")
        cancel.setCursor(QCursor(Qt.PointingHandCursor))
        cancel.setStyleSheet(f"""
            QPushButton {{
                color: {COLORS['text_sub']};
                background: transparent;
                border: 1px solid {COLORS['border']};
                border-radius: 11px;
                padding: 11px 20px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: {COLORS['bg_surface']}; color: {COLORS['text_main']}; }}
        """)
        cancel.clicked.connect(self.reject)
        brow.addWidget(cancel)

        ok = StyledButton("決定", self._accent, compact=True)
        ok.setMinimumHeight(44)
        ok.clicked.connect(self.accept)
        brow.addWidget(ok)
        lay.addLayout(brow)

        self.entry.setFocus()

    def _export_pdf(self):
        export_note_to_pdf(self, self._pdf_title, self.get_value())

    def _set_field_border(self, color):
        self._field.setStyleSheet(
            f"QFrame#dlgField {{ background-color: {COLORS['bg_base']}; "
            f"border: 2px solid {color}; border-radius: 12px; }}"
        )

    def eventFilter(self, obj, event):
        if obj is self.entry:
            if event.type() == QEvent.FocusIn:
                self._set_field_border(self._accent)
            elif event.type() == QEvent.FocusOut:
                self._set_field_border(COLORS['border'])
        return super().eventFilter(obj, event)

    def get_value(self):
        if self.multiline:
            return self.entry.toPlainText()
        return self.entry.text()


# --- メモ閲覧ダイアログ（読み取り専用） ---
class NoteViewDialog(QDialog):
    def __init__(self, title, text, accent=None, parent=None, enable_pdf=False):
        super().__init__(parent)
        self.action = None  # 'edit' / 'delete' / None
        accent = accent or COLORS['primary']
        self._title = title
        self._text = text
        self._enable_pdf = enable_pdf
        self.setModal(True)
        self.setWindowTitle(title)
        self.setStyleSheet(f"QDialog {{ background-color: {COLORS['bg_base']}; }}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(16)

        head = QLabel(title)
        head.setStyleSheet(f"color: {COLORS['text_main']}; font-size: 18px; font-weight: 800; background: transparent; border: none;")
        lay.addWidget(head)

        box = QFrame()
        box.setObjectName("noteBox")
        box.setStyleSheet(
            f"QFrame#noteBox {{ background-color: {COLORS['bg_surface']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 12px; }}"
        )
        bl = QVBoxLayout(box)
        bl.setContentsMargins(2, 2, 2, 2)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        body.setStyleSheet(
            f"color: {COLORS['text_main']}; font-size: 15px; line-height: 1.7; "
            f"background: transparent; border: none; padding: 14px 16px;"
        )
        scroll.setWidget(body)
        scroll.setMinimumSize(430, 170)
        bl.addWidget(scroll)
        lay.addWidget(box)

        brow = QHBoxLayout()
        brow.setSpacing(10)

        del_btn = QPushButton()
        apply_glyph_icon(del_btn, "🗑 削除", COLORS['danger'])
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet(f"""
            QPushButton {{
                color: {COLORS['danger']}; background: transparent;
                border: 1px solid {COLORS['border']}; border-radius: 11px;
                padding: 11px 18px; font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {COLORS['bg_surface']}; border-color: {COLORS['danger']}; }}
        """)
        del_btn.clicked.connect(self._do_delete)
        brow.addWidget(del_btn)

        if self._enable_pdf:
            pdf_btn = QPushButton()
            apply_glyph_icon(pdf_btn, "📄 PDFで保存", accent)
            pdf_btn.setCursor(QCursor(Qt.PointingHandCursor))
            pdf_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {accent}; background: transparent;
                    border: 1px solid {accent}; border-radius: 11px;
                    padding: 11px 18px; font-size: 14px; font-weight: 700;
                }}
                QPushButton:hover {{ background: {COLORS['bg_surface']}; }}
            """)
            pdf_btn.clicked.connect(self._export_pdf)
            brow.addWidget(pdf_btn)

        brow.addStretch()

        close_btn = QPushButton("閉じる")
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                color: {COLORS['text_sub']}; background: transparent;
                border: 1px solid {COLORS['border']}; border-radius: 11px;
                padding: 11px 20px; font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {COLORS['bg_surface']}; color: {COLORS['text_main']}; }}
        """)
        close_btn.clicked.connect(self.reject)
        brow.addWidget(close_btn)

        edit_btn = StyledButton("✏  編集", accent, compact=True)
        edit_btn.setMinimumHeight(44)
        edit_btn.clicked.connect(self._do_edit)
        brow.addWidget(edit_btn)
        lay.addLayout(brow)

    def _export_pdf(self):
        export_note_to_pdf(self, self._title, self._text)

    def _do_edit(self):
        self.action = "edit"
        self.accept()

    def _do_delete(self):
        self.action = "delete"
        self.accept()


# --- フォルダ選択プルダウンの各行に「☰」のドラッグハンドルを描画するデリゲート ---
# （プルダウンを開いた一覧そのものの中でドラッグして並び替えられるようにする）
class FolderDragDelegate(QStyledItemDelegate):
    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.colors = colors
        # 普段はFalse（☰は出さない）。「☰ 並び替え」ボタンを押した時だけ
        # Trueにして、ハンドルを表示する
        self.reorder_mode = False

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect
        # OSがダークテーマだと土台が黒くなり、そのまま文字色を重ねると
        # 真っ黒に文字が沈んで見えなくなるため、状態を問わず必ず自前で
        # 背景を塗ってから文字を描く（システムの配色に頼らない）
        if option.state & QStyle.State_Selected:
            painter.fillRect(rect, QColor(tint_hex(self.colors['success'], 0.82)))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(rect, QColor(tint_hex(self.colors['success'], 0.92)))
        else:
            painter.fillRect(rect, QColor(self.colors['bg_surface']))
        text_left = 10
        if self.reorder_mode:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(QColor(self.colors['text_sub']), 2, Qt.SolidLine, Qt.RoundCap))
            hx, cy = rect.left() + 12, rect.center().y()
            for dy in (-5, 0, 5):
                painter.drawLine(hx, cy + dy, hx + 14, cy + dy)
            text_left = 34
        painter.setPen(QColor(self.colors['text_main']))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect.adjusted(text_left, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, index.data(Qt.DisplayRole) or "")
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), 40))
        return size


# --- フォルダ並び替え用プルダウンの一覧ビュー ---
# Qt標準のドラッグ&ドロップだと「一番下まで移動できない」「ドラッグ中に
# 見た目が左右にもずれる」という問題があったため、☰ハンドルを掴んでいる間だけ
# マウスのY座標に応じてその場で行を入れ替える、縦方向専用の手作りドラッグにした
class FolderDragListView(QListView):
    HANDLE_WIDTH = 34

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)
        self._drag_row = -1
        # 普段は並び替えモードOFF（☰は出さない）。「☰ 並び替え」ボタンを
        # 押した時だけTrueにし、このプルダウンを閉じたら自動でFalseに戻す
        self.reorder_mode = False
        self.on_hide = None

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.on_hide:
            self.on_hide()

    def _row_at_y(self, y):
        model = self.model()
        count = model.rowCount() if model else 0
        if count == 0:
            return -1
        index = self.indexAt(QPoint(2, y))
        if index.isValid():
            return index.row()
        # 一覧の上端・下端をはみ出した位置でも、端の行として扱えるようにする
        # （これが無いと一番下の行までドラッグで到達できなかった）
        first_top = self.visualRect(model.index(0, 0)).top()
        last_bottom = self.visualRect(model.index(count - 1, 0)).bottom()
        if y <= first_top:
            return 0
        if y >= last_bottom:
            return count - 1
        return -1

    def mousePressEvent(self, event):
        if self.reorder_mode and event.button() == Qt.LeftButton:
            index = self.indexAt(event.pos())
            if index.isValid() and event.pos().x() - self.visualRect(index).left() <= self.HANDLE_WIDTH:
                self._drag_row = index.row()
                self.setCurrentIndex(index)
                event.accept()
                return
        self._drag_row = -1
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_row >= 0:
            target_row = self._row_at_y(event.pos().y())
            if target_row >= 0 and target_row != self._drag_row:
                model = self.model()
                row_items = model.takeRow(self._drag_row)
                model.insertRow(target_row, row_items)
                self._drag_row = target_row
                self.setCurrentIndex(model.index(target_row, 0))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_row >= 0:
            self._drag_row = -1
            event.accept()
            return
        super().mouseReleaseEvent(event)


# --- フォルダ並び替え用の「見た目はプルダウンと同じ」独立ポップアップ ---
# QComboBoxの標準ポップアップは内部クリックのたびに自動で閉じる仕様のため、
# Qt.Popupウィンドウを自前で用意し、一覧の外をクリックするまで閉じないようにする
class FolderReorderPopup(QFrame):
    def __init__(self, colors, parent=None):
        super().__init__(parent, Qt.Popup)
        self.colors = colors
        self.setStyleSheet(
            f"QFrame {{ background-color: {colors['bg_surface']}; "
            f"border: 1px solid {colors['border']}; border-radius: 12px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(0)

        self.model = QStandardItemModel(self)
        self.view = FolderDragListView(self)
        self.view.setModel(self.model)
        self.view.reorder_mode = True  # このポップアップは並び替え専用なので常に☰を出す
        self.delegate = FolderDragDelegate(colors, self.view)
        self.delegate.reorder_mode = True
        self.view.setItemDelegate(self.delegate)
        self.view.setFrameShape(QFrame.NoFrame)
        self.view.setStyleSheet("QListView { background: transparent; border: none; outline: none; }")
        lay.addWidget(self.view)

        finish_row = QHBoxLayout()
        finish_row.setContentsMargins(4, 6, 4, 2)
        finish_row.addStretch()
        finish_btn = StyledButton("✓ 完了", colors["success"], compact=True)
        finish_btn.clicked.connect(self.hide)
        finish_row.addWidget(finish_btn)
        lay.addLayout(finish_row)

    def set_folders(self, names):
        self.model.clear()
        for name in names:
            item = QStandardItem(name)
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.model.appendRow(item)
        # 件数に応じた高さにする（QListViewはデフォルトだと中身と関係なく
        # 余白いっぱいに伸びてしまうため、行数から高さを計算して固定する）
        row_height = 40
        self.view.setFixedHeight(min(max(len(names), 1) * row_height, 300))

    def order(self):
        return [self.model.item(i).text() for i in range(self.model.rowCount())]

    def open_below(self, anchor_widget):
        self.setFixedWidth(anchor_widget.width())
        self.move(anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()))
        self.show()


# --- メインアプリケーションクラス ---
class MultiApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi Memo")
        self.resize(900, 750)
        self.setMinimumSize(600, 500)
        
        # PyInstallerでexe化した場合、__file__はexeを展開した一時フォルダを指してしまい、
        # そこにデータを保存すると起動のたびに消えてしまう。exe化されている時は
        # 実行ファイル自体の場所を使うようにする
        if getattr(sys, "frozen", False):
            BASE_DIR = os.path.dirname(sys.executable)
        else:
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.DATA_FILE = os.path.join(BASE_DIR, "memo_pro_data.json")
        self.VAULT_FILE = os.path.join(BASE_DIR, "vault_pro_data.json")
        self.ATTACH_DIR = os.path.join(BASE_DIR, "attachments")
        self.SOUND_DIR = os.path.join(BASE_DIR, ".sounds")
        self.ASSET_DIR = os.path.join(BASE_DIR, ".assets")

        self.init_style()
        self.load_all_data()

        # 画面管理用のスタックウィジェット
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.timer_worker = None
        self._selector_scale = 1.0

        # 全ての画面レイアウトをはじめに構築して固定配置（バグの根本原因の修正）
        self.screens = {}
        self.create_all_screens()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # ウィンドウを大きく（全画面など）した時、スタート画面をひとまわり拡大する
        if hasattr(self, "stacked_widget") and hasattr(self, "screens"):
            self._update_selector_scale()

    def init_style(self):
        self.colors = dict(COLORS)
        self.setStyleSheet(f"""
            * {{
                font-family: 'HuiFontP', 'ふい字', 'Meiryo UI', 'Segoe UI', 'Yu Gothic UI', 'Hiragino Sans', sans-serif;
                font-size: 15px;
            }}
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #EDEFF8, stop:0.55 #EFEFF7, stop:1 #F1ECF8);
            }}
            QStackedWidget {{
                background: transparent;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QTextEdit {{
                background-color: {self.colors['bg_base']};
                color: {self.colors['text_main']};
                font-size: 16px;
                line-height: 1.7;
                border: 2px solid {self.colors['border']};
                border-radius: 14px;
                padding: 18px;
                selection-background-color: #BFDBFE;
                selection-color: {self.colors['text_main']};
            }}
            QTextEdit:focus {{
                border: 2px solid {self.colors['primary']};
            }}
            QLineEdit {{
                background-color: {self.colors['bg_base']};
                color: {self.colors['text_main']};
                font-size: 15px;
                border: 2px solid {self.colors['border']};
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
                border: 2px solid {self.colors['border']};
                border-radius: 12px;
                background: {self.colors['bg_base']};
                color: {self.colors['text_main']};
                min-height: 24px;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {self.colors['bg_base']};
                color: {self.colors['text_main']};
                selection-background-color: #BFDBFE;
                selection-color: {self.colors['text_main']};
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
                background: {grad_css('primary')};
                color: {self.colors['on_accent']};
                min-width: 100px;
                min-height: 40px;
                padding: 10px 24px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 14px;
                border: none;
            }}
        """)

    @staticmethod
    def _rgba(hexstr, a):
        h = hexstr.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r}, {g}, {b}, {a})"

    def _add_shadow(self, widget, blur=26, dy=5, alpha=34, color=None):
        # カードやパネルを浮かせるドロップシャドウ（colorを渡すとその色味の影に）
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setXOffset(0)
        effect.setYOffset(dy)
        if color:
            c = QColor(color)
            c.setAlpha(alpha)
            effect.setColor(c)
        else:
            effect.setColor(QColor(15, 23, 42, alpha))
        widget.setGraphicsEffect(effect)

    PAPER_BG = "#FFFDF6"
    PAPER_BORDER = "#EAE2CF"
    PAPER_RULE = "#D6E0F1"
    PAPER_MARGIN = "rgba(225, 29, 72, 0.42)"

    def _get_wood_pixmap(self):
        # 背景の木目は実写真(assets/wood_bg.jpg)を使う。一度読み込んだら使い回す
        if not hasattr(self, "_wood_pixmap_cache"):
            path = resource_path(os.path.join("assets", "wood_bg.jpg"))
            pix = QPixmap(path) if os.path.exists(path) else None
            self._wood_pixmap_cache = pix if (pix and not pix.isNull()) else None
        return self._wood_pixmap_cache

    def _get_button_wood_pixmap(self):
        # ホーム画面のメニューボタン用の木の板の画像(assets/button_wood.jpg)
        if not hasattr(self, "_button_wood_cache"):
            path = resource_path(os.path.join("assets", "button_wood.jpg"))
            pix = QPixmap(path) if os.path.exists(path) else None
            self._button_wood_cache = pix if (pix and not pix.isNull()) else None
        return self._button_wood_cache

    def _new_screen(self, object_name="screenBg"):
        # 各画面のルートウィジェット。木目の壁紙を全画面共通で敷く
        # 【お試し】全画面のフォントを手書き風(ふい字)優先にする。戻す時はSCREEN_FONT_TRIALをFalseに
        font_css = f"* {{ font-family: {TITLE_FONT_JA}; }}" if SCREEN_FONT_TRIAL else ""
        pix = self._get_wood_pixmap()
        if pix:
            w = TiledBackgroundWidget(pix)
            if font_css:
                w.setStyleSheet(font_css)
            return w
        w = QWidget()
        w.setObjectName(object_name)
        w.setStyleSheet(f"QWidget#{object_name} {{ background-color: {self.colors['page']}; }} {font_css}")
        return w

    def _panel(self, name, radius=16):
        # ノート（メモ帳）風のカード
        w = QWidget()
        w.setObjectName(name)
        w.setStyleSheet(f"""
            QWidget#{name} {{
                background-color: {self.PAPER_BG};
                border: 1px solid {self.PAPER_BORDER};
                border-radius: {radius}px;
            }}
        """)
        return w

    def _ring_binding(self, count=15, pad=24, scale=1.0):
        # 上部のリングとじ
        hole_size = round(10 * scale)
        w = QWidget()
        w.setFixedHeight(round(19 * scale))
        lay = QHBoxLayout(w)
        lay.setContentsMargins(round(pad * scale), round(7 * scale), round(pad * scale), 0)
        lay.setSpacing(0)
        lay.addStretch()
        for _ in range(count):
            hole = QLabel()
            hole.setFixedSize(hole_size, hole_size)
            hole.setStyleSheet(f"background: {grad_css(('#C4C9D6', '#949BAE'))}; border-radius: {hole_size // 2}px;")
            lay.addWidget(hole)
            lay.addStretch()
        return w

    def _notebook_panel(self, name, rings=True, margin=True, radius=16):
        # リングとじ＋赤マージン線つきのノート風パネル。(panel, content_layout) を返す
        panel = self._panel(name, radius=radius)
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        if rings:
            v.addWidget(self._ring_binding())
        body = QWidget()
        bh = QHBoxLayout(body)
        bh.setContentsMargins(16, 10 if rings else 14, 14, 14)
        bh.setSpacing(12)
        if margin:
            ml = QFrame()
            ml.setFixedWidth(3)
            ml.setStyleSheet(f"background-color: {self.PAPER_MARGIN}; border: none;")
            bh.addWidget(ml)
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)
        bh.addLayout(content, 1)
        v.addWidget(body, 1)
        self._add_shadow(panel, blur=26, dy=9, alpha=22)
        return panel, content

    def _ghost_btn(self, text, color=None, compact=True):
        # 副次的な操作用の控えめなボタン（枠線＋ホバーで軽く着色）
        c = color or self.colors['text_sub']
        b = WoodSkinButton(text, radius=10)
        pad = "8px 14px" if compact else "11px 20px"
        fs = "13px" if compact else "14px"
        b.setStyleSheet(f"""
            QPushButton {{
                color: #4A3426;
                background: transparent;
                border: none;
                border-radius: 10px;
                padding: {pad};
                font-size: {fs};
                font-weight: 600;
            }}
        """)
        return b

    def _grad_pair(self, color):
        for name, hexv in COLORS.items():
            if hexv == color and name in GRADIENTS:
                return GRADIENTS[name]
        return (lighten_hex(color, 26), color)

    def _grad(self, color):
        return grad_css(self._grad_pair(color))

    def _load_feature_icon(self, icon_file, size):
        # icons/配下のイラストアイコンを指定サイズの正方形QPixmapに変換（結果はキャッシュ）
        if not icon_file or size <= 0:
            return None
        cache = getattr(self, "_icon_pixmap_cache", None)
        if cache is None:
            cache = self._icon_pixmap_cache = {}
        key = (icon_file, size)
        if key in cache:
            return cache[key]
        path = resource_path(os.path.join("icons", f"{icon_file}.png"))
        pix = None
        if os.path.exists(path):
            loaded = QPixmap(path)
            if not loaded.isNull():
                pix = loaded.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        cache[key] = pix
        return pix

    def _load_writing_hand_pixmap(self):
        # タイトルを書く手のイラスト(assets/writing_hand.png)。無ければNone
        if not hasattr(self, "_writing_hand_cache"):
            path = resource_path(os.path.join("assets", "writing_hand.png"))
            pix = QPixmap(path) if os.path.exists(path) else None
            self._writing_hand_cache = pix if (pix and not pix.isNull()) else None
        return self._writing_hand_cache

    def _load_pencil_pixmap(self, height):
        # タイトルカード右上の鉛筆イラスト(assets/pencil.png)を指定の高さにあわせて縮小する
        if height <= 0:
            return None
        cache = getattr(self, "_pencil_pixmap_cache", None)
        if cache is None:
            cache = self._pencil_pixmap_cache = {}
        if height in cache:
            return cache[height]
        path = resource_path(os.path.join("assets", "pencil.png"))
        pix = None
        if os.path.exists(path):
            loaded = QPixmap(path)
            if not loaded.isNull():
                pix = loaded.scaledToHeight(height, Qt.SmoothTransformation)
        cache[height] = pix
        return pix

    def _load_wood_bar_pixmap(self, width):
        # タイトル下の木の棒(assets/wood_bar.png)を指定の幅に合わせて縮小する(縦横比は維持)
        if width <= 0:
            return None
        cache = getattr(self, "_wood_bar_cache", None)
        if cache is None:
            cache = self._wood_bar_cache = {}
        if width in cache:
            return cache[width]
        # 枝の画像(title_branch.png)を優先し、無ければ木の棒(wood_bar.png)
        path = resource_path(os.path.join("assets", "title_branch.png"))
        if not os.path.exists(path):
            path = resource_path(os.path.join("assets", "wood_bar.png"))
        pix = None
        if os.path.exists(path):
            loaded = QPixmap(path)
            if not loaded.isNull():
                pix = loaded.scaledToWidth(width, Qt.SmoothTransformation)
        cache[width] = pix
        return pix

    def _load_notebook_pixmap(self, width, height):
        # タイトルカードの背景イラスト(assets/notebook_paper.png)を指定のサイズに
        # 合わせる。元画像の縦横比のままだと横長にするほど縦も伸びてしまうため、
        # cover-fitで拡大してから中央を指定サイズに切り出す(横長の比率にできる)
        if width <= 0 or height <= 0:
            return None
        cache = getattr(self, "_notebook_pixmap_cache", None)
        if cache is None:
            cache = self._notebook_pixmap_cache = {}
        key = (width, height)
        if key in cache:
            return cache[key]
        pix = None
        # 画びょうで留めたノートの切り抜き(assets/notebook_pin.png)が最優先。
        # 縦横比を保ったまま幅に合わせる(切り抜きなので周りは透明で、木目背景に直接乗る)
        pin_path = resource_path(os.path.join("assets", "notebook_pin.png"))
        if os.path.exists(pin_path):
            loaded = QPixmap(pin_path)
            if not loaded.isNull():
                cache[key] = loaded.scaledToWidth(width, Qt.SmoothTransformation)
                return cache[key]
        path = resource_path(os.path.join("assets", "notebook_paper.png"))
        if os.path.exists(path):
            loaded = QPixmap(path)
            if not loaded.isNull():
                scaled = loaded.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                x = (scaled.width() - width) // 2
                # 縦方向は中央ではなく上寄りから切り出す。下端のマスキングテープが
                # 中途半端に切れて見えないよう、はみ出す分はなるべく上側から削る
                y = round((scaled.height() - height) * 0.65)
                pix = scaled.copy(x, y, width, height)
        cache[key] = pix
        return pix

    def _make_header(self, icon, title, accent, back_slot=None, back_text="←  戻る", icon_file=None):
        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(2, 2, 2, 2)
        h.setSpacing(12)

        back = WoodSkinButton(back_text, radius=10)
        back.setStyleSheet("""
            QPushButton {
                color: #4A3426;
                background: transparent;
                border: none;
                border-radius: 10px;
                padding: 9px 16px;
                font-size: 13px;
                font-weight: 700;
            }
        """)
        back.clicked.connect(back_slot or self.back_to_selector)
        h.addWidget(back)

        chip = QLabel()
        chip.setFixedSize(40, 40)
        chip.setAlignment(Qt.AlignCenter)
        pix = self._load_feature_icon(icon_file, 28)
        if pix is not None:
            # 線画アイコン(濃い茶色の線)は暗い木目の上だと見えないので、白木色の下地に載せる
            chip.setStyleSheet("background: rgba(250, 245, 236, 0.95); border: none; border-radius: 13px;")
            chip.setPixmap(pix)
        else:
            chip.setStyleSheet(f"""
                background: {self._grad(accent)};
                font-size: 19px;
                border: none;
                border-radius: 13px;
            """)
            chip.setText(icon)
            self._add_shadow(chip, blur=16, dy=4, alpha=90, color=accent)
        h.addWidget(chip)

        ttl = QLabel(title)
        # 暗い木目の上で読めるよう、ボタンと同じ白木色にする
        ttl.setStyleSheet(f"color: #FAF5EC; font-size: 20px; font-weight: 800; border: none; background: transparent;")
        h.addWidget(ttl)
        h.addStretch()
        return bar

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
            self.todo_items = self._normalize_todo_items(d.get("todo", []))
            self.memo_data = d.get("memo", {"メイン": ""})
            self.calendar_notes = d.get("calendar", {})
            self.memo_attachments = d.get("attachments", {})
            self.note_data = d.get("note", {"新しい科目": []})
        else:
            self.todo_items, self.memo_data, self.calendar_notes = [], {"メイン": ""}, {}
            self.memo_attachments = {}
            self.note_data = {"新しい科目": []}

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
        if not self.note_data:
            self.note_data = {"新しい科目": []}
        self.current_note_subject = list(self.note_data.keys())[0]
        self.current_note_entry_index = None
        self.is_authenticated = False
        self.cur_year, self.cur_month = datetime.now().year, datetime.now().month
        self.sounds = SOUND_PATTERNS
        self._sound_files = {}   # 名前 -> 生成済みWAVファイルのパス

    def _normalize_todo_items(self, raw):
        # 旧形式(文字列のリスト)と新形式(辞書のリスト)の両方を受け付ける
        normalized = []
        for item in raw:
            if isinstance(item, dict):
                normalized.append({
                    "text": item.get("text", ""),
                    "done": bool(item.get("done", False)),
                    "done_at": item.get("done_at"),
                })
            else:
                normalized.append({"text": str(item), "done": False, "done_at": None})
        return normalized

    def _save_json_safe(self, filepath, data):
        tmp_path = filepath + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        if os.path.exists(filepath):
            shutil.copy2(filepath, filepath + ".bak")
        os.replace(tmp_path, filepath)

    def save_all_data(self):
        self.save_current_note_entry_content()
        data = {"todo": self.todo_items, "memo": self.memo_data,
                "calendar": self.calendar_notes, "attachments": self.memo_attachments,
                "note": self.note_data}
        self._save_json_safe(self.DATA_FILE, data)
        vault = {"hash": self.master_hash, "birth_hash": self.birth_hash, "items": self.vault_items}
        self._save_json_safe(self.VAULT_FILE, vault)

    def change_screen(self, screen_key):
        self.save_all_data()
        
        # 画面切り替え時、特定の画面なら動的に要素をリフレッシュする
        if screen_key == "memo":
            self.draw_tabs()
            self.load_current_memo_text()
            self.refresh_attachments()
        elif screen_key == "todo":
            self.refresh_todo()
        elif screen_key == "calendar":
            self.draw_calendar()
        elif screen_key == "note":
            self.draw_note_subjects()
            self.refresh_note_entry_list()
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
        self.create_note_screen()
        self.create_calendar_screen()
        self.create_vault_auth_screen()
        self.create_vault_inside_screen()

    # --- メニューセレクター画面 ---
    def _make_menu_card(self, icon, label, desc, color, slot, wide=False, scale=1.0, icon_file=None):
        # タイトルのノートカードに合わせつつ、機能ごとの色でにぎやかに（scaleで全体サイズを拡縮）
        def sz(v):
            return round(v * scale)

        light, dark = self._grad_pair(color)
        # ボタンは機能ごとに色分けせず、全部同じ木目に馴染む落ち着いた色(ウォールナット調)に統一する。
        # 機能の見分けはアイコンと名前で行う
        face = MENU_CARD_COLOR
        dark = face  # 台座の影の色にも使う
        face_hover = lighten_hex(face, 10)
        base_color = lighten_hex(face, -40)  # 同系色でさらに濃い「台座」の色
        radius = sz(46 if wide else 42)    # 写真のピル型に近づけて大きく丸める
        depth = sz(8)

        # 濃い同系色の台座の上にカラフルな本体を重ねて、写真のような
        # 立体的なピル型ボタンにする
        base = QWidget()
        base.setObjectName("menuCardBase")
        base.setStyleSheet(f"QWidget#menuCardBase {{ background-color: {base_color}; border-radius: {radius}px; }}")
        base_layout = QVBoxLayout(base)
        base_layout.setContentsMargins(0, 0, 0, depth)
        base_layout.setSpacing(0)
        base.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # ボタン本体は単色ではなく、機能ごとの色で着色した木目テクスチャにする
        # (QSSのborder-imageはスケーリング品質が不安定だったため、直接描画するWoodButtonを使う)
        # ボタン専用の板の画像(assets/button_wood.jpg)をそのまま見せる。
        # 色は載せず、ホバー時だけ白を薄く重ねて明るくする(無い場合は従来の着色木目)
        button_wood = self._get_button_wood_pixmap()
        if button_wood is not None:
            card = WoodButton(button_wood, "#FFFFFF", 0, "#000000", radius)
        else:
            card = WoodButton(self._get_wood_pixmap(), face, 220, face_hover, radius)
        card.setObjectName("menuCard")
        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.clicked.connect(slot)

        # 押した瞬間だけ台座の見え幅を詰めて、実際に沈み込む動きをつける
        def _press():
            base_layout.setContentsMargins(0, 0, 0, max(1, depth - sz(6)))

        def _release():
            base_layout.setContentsMargins(0, 0, 0, depth)

        card.pressed.connect(_press)
        card.released.connect(_release)

        chip_size = sz(52) if wide else sz(42)
        chip = QLabel()
        chip.setFixedSize(chip_size, chip_size)
        chip.setAlignment(Qt.AlignCenter)
        # 線画アイコンは背景の丸なしで、白木のボタンに直接なじませる
        chip.setStyleSheet(f"""
            background: transparent;
            font-size: {sz(24 if wide else 21)}px;
            border: none;
        """)
        pix = self._load_feature_icon(icon_file, round(chip_size * 0.82))
        if pix is not None:
            chip.setPixmap(pix)
        else:
            chip.setText(icon)

        name = QLabel(label)
        # 「セキュリティメモ」のような長めのラベルが2列レイアウトの狭い幅で
        # 見切れないよう、折り返し可能にした上で最小幅の制約もなくしておく
        name.setWordWrap(True)
        name.setMinimumWidth(0)
        name.setStyleSheet(f"""
            color: #4A3426;
            font-family: {title_font_family(label)};
            font-size: {sz(23 if wide else 17)}px;
            font-weight: 800;
            letter-spacing: 0.5px;
            border: none;
            background: transparent;
        """)
        sub = QLabel(desc)
        sub.setWordWrap(True)
        sub.setMinimumWidth(0)
        sub.setStyleSheet(f"""
            color: rgba(74, 52, 38, 0.85);
            font-family: {title_font_family(desc)};
            font-size: {sz(13)}px;
            border: none;
            background: transparent;
        """)

        # 木目の濃淡で文字が読みにくくならないよう、ラベルに軽い落ち影を入れてコントラストを補う
        self._add_shadow(name, blur=round(6 * scale), dy=1, alpha=70, color="#FFFFFF")
        self._add_shadow(sub, blur=round(5 * scale), dy=1, alpha=60, color="#FFFFFF")

        # 全カード共通：横並び（アイコン＋テキスト）の“背の低い”カードが基本だが、
        # 「セキュリティメモ」のように文字が2行に折り返す場合は上限を設けず
        # カードを伸ばして文字が重ならないようにする(最大高さの指定はしない)
        card.setMinimumHeight(sz(82 if wide else 76))
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        h = QHBoxLayout(card)
        h.setContentsMargins(sz(30) if wide else sz(18), sz(12), sz(34) if wide else sz(18), sz(12))
        h.setSpacing(sz(16) if wide else sz(10))
        h.addWidget(chip)

        text = QVBoxLayout()
        text.setSpacing(sz(3))
        text.addStretch()
        text.addWidget(name)
        text.addWidget(sub)
        text.addStretch()
        h.addLayout(text, 1)
        if wide:
            h.addStretch()

        base_layout.addWidget(card)
        self._add_shadow(base, blur=round(20 * scale), dy=round(8 * scale), alpha=36, color=dark)
        return base

    def _render_title_pixmap(self, scale=1.0, max_width=None):
        # 「Multi」「Memo」を装飾フォント(Arkipelago)で描画したQPixmapを作る。
        # 筆記体フォントはスワッシュ(飾り)が通常の文字送り幅からはみ出すことがあり、
        # CSSのpadding予測では見切れを防ぎきれなかったため、実際に大きめのキャンバスへ
        # 描画してからインクが乗っている範囲だけを自動で切り出す(測って決める)方式にした。
        cache = getattr(self, "_title_pixmap_cache", None)
        if cache is None:
            cache = self._title_pixmap_cache = {}
        key = (round(scale * 100), max_width)
        if key in cache:
            return cache[key]

        point_size = max(1, round(52 * scale))
        font = QFont()
        font.setFamilies([f.strip(" '") for f in TITLE_FONT_EN.split(",")])
        font.setPointSize(point_size)
        font.setBold(True)
        font.setLetterSpacing(QFont.AbsoluteSpacing, max(0.0, 1.0 * scale))

        fm = QFontMetrics(font)
        # 先頭の「E」と「G」は頭文字なので、1.3倍に大きくして大文字だと分かるようにする
        # (Charbroiledは頭文字がはっきり大文字の形なので、強調するのは筆記体のArkipelagoで代用している間だけ)
        # Forest Regularは頭文字の大文字が元々はっきりしているので強調は不要。
        # 筆記体のArkipelagoで代用している間だけ強調する
        _fams = [f.lower().replace(" ", "") for f in QFontDatabase.families()]
        CAP = 1.0 if "forestregular" in _fams else 1.2
        pieces = [("E", CAP), ("ver", 1.0), ("G", CAP), ("rove", 1.0)]
        cap_font = QFont(font)
        cap_font.setPointSize(max(1, round(point_size * CAP)))
        cap_fm = QFontMetrics(cap_font)
        parts = [(t, TITLE_TEXT_BROWN, cap_font if s != 1.0 else font) for t, s in pieces]
        natural_w = sum((cap_fm if f is cap_font else fm).horizontalAdvance(t) for t, _, f in parts)
        margin = max(24, point_size)  # スワッシュ用の逃げ代。文字サイズに応じて多めに確保する
        canvas_w = natural_w + margin * 2
        canvas_h = cap_fm.height() + margin * 2

        img = QImage(canvas_w, canvas_h, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        x = margin
        baseline = margin + cap_fm.ascent()   # 大きい文字に合わせた共通のベースライン
        for text, color, f in parts:
            painter.setFont(f)
            painter.setPen(QColor(color))
            painter.drawText(x, baseline, text)
            x += (cap_fm if f is cap_font else fm).horizontalAdvance(text)
        painter.end()

        # 実際にインクが乗っている範囲(アルファ>0)だけを切り出す
        bitmap = QBitmap.fromImage(img.createAlphaMask())
        bbox = QRegion(bitmap).boundingRect()
        if bbox.isValid():
            pad = max(2, round(4 * scale))
            bbox = bbox.adjusted(-pad, -pad, pad, pad).intersected(img.rect())
            img = img.copy(bbox)

        pix = QPixmap.fromImage(img)
        # フォントによっては文字幅が大きく、紙の幅や手の置き場所をはみ出す。
        # 上限(max_width)を超えるときは、縦横比を保ったまま縮小して収める
        if max_width and pix.width() > max_width:
            pix = pix.scaledToWidth(max_width, Qt.SmoothTransformation)
        cache[key] = pix
        return pix

    def _build_memo_masthead(self, scale=1.0):
        # ノート（メモ帳）風のタイトルカード（イラスト背景、scaleで拡縮）
        # カード全体をひとまわり小さくするための専用の縮小率。
        # 以前あった「色付きインデックスタブ」は、傾いたイラストの上では
        # 浮いて見えてしまうため廃止した
        card_scale = scale * 0.44

        def csz(v):
            return round(v * card_scale)

        # 文字(日付・タイトル・サブタイトル)はカード自体より大きめの縮小率で描く。
        # カードを小さく保って1画面に収めつつ、文字だけは読みやすいサイズにするため
        text_scale = scale * 0.95

        def tsz(v):
            return round(v * text_scale)

        wrap = QWidget()
        wv = QVBoxLayout(wrap)
        wv.setContentsMargins(0, 0, 0, 0)
        wv.setSpacing(0)

        # アプリ名(タイトル)のカードは、イラスト(assets/notebook_paper.png)を背景に敷き、
        # その上に日付・タイトル等を重ねる。イラスト側にすでにリング穴・赤い罫線・
        # マスキングテープが描かれているので、コードで描いていた分は不要になった
        paper = AnchorPaper()
        paper.setObjectName("memoPaper")
        # 横幅は広めに、縦幅は抑えめに(cover-fitで切り出すので元画像の縦横比に縛られない)
        paper_width = csz(1000)
        paper_height = csz(720)
        notebook_pix = self._load_notebook_pixmap(paper_width, paper_height)
        stack = QStackedLayout(paper)
        stack.setStackingMode(QStackedLayout.StackAll)
        stack.setContentsMargins(0, 0, 0, 0)

        bg_label = QLabel()
        bg_label.setStyleSheet("background: transparent; border: none;")
        bg_label.setAlignment(Qt.AlignCenter)
        if notebook_pix is not None:
            bg_label.setPixmap(notebook_pix)
            paper.setFixedHeight(notebook_pix.height())
        # 紙は透かさず、そのままの濃さで表示する
        stack.addWidget(bg_label)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        bh = QHBoxLayout(body)
        # 上の余白はリング穴にかぶらないよう広めに取る(イラスト上部のリング穴を避ける)
        # 左余白(タイトル・キャッチコピーを右へ寄せる量)。右余白は紙の端に合わせて少し詰める
        LEFT_M, RIGHT_M = csz(185), csz(120)
        bh.setContentsMargins(LEFT_M, csz(200), RIGHT_M, csz(80))
        bh.setSpacing(csz(20))

        txt = QVBoxLayout()
        txt.setSpacing(0)

        # 日付スタンプ
        date_lbl = QLabel(datetime.now().strftime("%Y . %m . %d"))
        date_lbl.setStyleSheet(f"color: {TITLE_TEXT_BROWN}; font-family: {TITLE_FONT_JA}; font-size: {tsz(19)}px; font-weight: 700; letter-spacing: 2px;")
        txt.addWidget(date_lbl)
        txt.addSpacing(tsz(14))   # 「E」「G」の飾りが日付に重ならないよう間隔を空ける

        # タイトルは「だいたいこれくらい余白があれば足りるはず」という推測のpaddingではなく、
        # 実際に描画した結果から文字のインクが乗っている範囲を測って切り出す(見切れを原理的に防ぐ)
        title = QLabel()
        # 上限幅 = 紙の幅 - 左右の余白 - 手を置く場所(右側)
        title_pix = self._render_title_pixmap(
            text_scale, max_width=max(80, paper_width - LEFT_M - RIGHT_M - csz(60)))
        title.setPixmap(title_pix)
        txt.addWidget(title)

        # 蛍光ペンで引いたようなライン + ノートの罫線。
        # 列幅いっぱいに伸ばすと、傾いた紙の右端からはみ出すことがあるため、
        # タイトル文字の実際の幅に合わせる
        line_width = max(1, title_pix.width())
        txt.addSpacing(tsz(6))
        # タイトル下の線は、黄色のハイライトではなく木の棒の画像(assets/wood_bar.png)にする
        bar_pix = self._load_wood_bar_pixmap(line_width)
        if bar_pix is not None:
            # レイアウト内には同じ大きさの空き枠だけ置き、枝そのものは紙の上に直接配置する。
            # 枝の左端を、傾いた紙の左の縁にぴったり合わせるため(下のanchor_branchで位置決め)
            hl = QWidget()
            hl.setFixedSize(bar_pix.size())
            hl.setStyleSheet("background: transparent;")
            branch_label = QLabel(paper)
            branch_label.setStyleSheet("background: transparent; border: none;")
            branch_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            notebook_img = notebook_pix.toImage() if notebook_pix is not None else None

            def anchor_branch():
                if notebook_img is None:
                    return
                top_left = hl.mapTo(paper, QPoint(0, 0))
                # 枝の左端(太い根元)の高さでの、紙の左端のx座標を画像の透明度から探す
                cy = min(max(top_left.y() + round(hl.height() * 0.6), 0), notebook_img.height() - 1)
                # 紙の画像は(幅の広い)枠の中で中央寄せされているので、その左の余白分を足す
                img_x0 = max(0, (paper.width() - notebook_img.width()) // 2)
                edge_x = img_x0
                for x in range(notebook_img.width()):
                    if notebook_img.pixelColor(x, cy).alpha() > 128:
                        edge_x = img_x0 + x
                        break
                end_x = top_left.x() + hl.width()
                w = max(1, end_x - edge_x)
                pix = self._load_wood_bar_pixmap(w)
                if pix is None:
                    return
                branch_label.setPixmap(pix)
                branch_label.setGeometry(edge_x, top_left.y(), pix.width(), pix.height())
                branch_label.raise_()
                branch_label.show()

            paper.on_layout = anchor_branch
        else:
            hl = QFrame()
            hl.setFixedHeight(tsz(9))
            hl.setFixedWidth(line_width)
            hl.setStyleSheet("background-color: rgba(250, 204, 21, 0.55); border: none; border-radius: 3px;")
        txt.addWidget(hl)
        txt.addSpacing(tsz(7))
        # 枝の下の線は表示しない

        txt.addSpacing(tsz(2))
        sub = QLabel("ひとつひとつがあなたの森になる")
        sub.setWordWrap(False)  # キャッチコピーは1行で表示する(紙の幅に収まる長さ)
        sub.setStyleSheet(f"""
            color: {TITLE_TEXT_BROWN};
            font-family: {TITLE_FONT_JA};
            font-size: {tsz(21)}px;
            letter-spacing: 1px;
            padding-left: {tsz(46)}px;
        """)
        txt.addWidget(sub)

        bh.addLayout(txt, stretch=1)

        # タイトルを書いている手のイラスト(assets/writing_hand.png)。
        # ペン先をタイトル末尾に合わせ、手首は紙の右端で切れるよう紙の形で切り抜いて重ねる
        hand_src = self._load_writing_hand_pixmap()
        if hand_src is not None:
            hand_label = QLabel(paper)
            hand_label.setStyleSheet("background: transparent; border: none;")
            hand_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            prev_on_layout = paper.on_layout

            def place_hand():
                if prev_on_layout:
                    prev_on_layout()
                if notebook_pix is None or paper.width() <= 0:
                    return
                tl = title.mapTo(paper, QPoint(0, 0))
                hand_h = max(36, tsz(70))   # 手の大きさはタイトルの文字サイズに左右されない固定値
                hand = hand_src.scaledToHeight(hand_h, Qt.SmoothTransformation)
                tip_y = tl.y() + title_pix.height() * 0.45   # 文字の中ほどの高さにペン先
                hx = tl.x() + title_pix.width() + 2 + tsz(16)   # 手を少しだけ右へ
                hy = round(tip_y - hand_h * 0.97)            # 画像内のペン先は下端(約97%の高さ)
                canvas = QPixmap(paper.size())
                canvas.fill(Qt.transparent)
                p = QPainter(canvas)
                p.drawPixmap(hx, hy, hand)
                p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
                p.drawPixmap(max(0, (paper.width() - notebook_pix.width()) // 2), 0, notebook_pix)
                p.end()
                hand_label.setPixmap(canvas)
                hand_label.setGeometry(0, 0, paper.width(), paper.height())
                hand_label.raise_()
                hand_label.show()

            paper.on_layout = place_hand
            # 右側の空きは「紙の幅 - 左余白 - タイトル/キャッチコピーの広い方 - 右余白」で決める。
            # 幅の広いフォント(Forest Regularなど)でも、中身が紙の幅をはみ出してカードが広がらない
            _content_w = max(title_pix.width(), 0)
            _sub_w = sub.fontMetrics().horizontalAdvance(sub.text()) + tsz(46) + 8
            _content_w = max(_content_w, _sub_w)
            _spare = paper_width - LEFT_M - RIGHT_M - _content_w
            bh.addSpacing(max(0, _spare))
            # 紙の幅より中身が広い場合は、紙の幅そのものを基準にカードの最小幅を確保する
            # (フォントごとにタイトルの幅が変わっても、カード全体の幅が変わらないようにする)
            paper.setMinimumWidth(paper_width)
        else:
            pencil = QLabel()
            pencil.setStyleSheet("background: transparent; border: none;")
            pencil.setAlignment(Qt.AlignTop | Qt.AlignRight)
            pencil_pix = self._load_pencil_pixmap(csz(130))
            if pencil_pix is not None:
                pencil.setPixmap(pencil_pix)
            bh.addWidget(pencil)

        stack.addWidget(body)
        stack.setCurrentWidget(body)  # StackAllでも「カレント」を最前面にする必要がある
        wv.addWidget(paper)
        return wrap

    def create_selector_screen(self, scale=1.0):
        def sz(v):
            return round(v * scale)

        # 既存のセレクター画面があれば、後で差し替えるために覚えておく（全画面時の拡大用）
        old_screen = self.screens.get("selector")
        was_current = old_screen is not None and self.stacked_widget.currentWidget() is old_screen

        screen = self._new_screen("selectorScreen")
        screen_layout = QVBoxLayout(screen)
        screen_layout.setContentsMargins(0, 0, 0, 0)

        # ウィンドウが小さい時はスクロールできるようにして、カードがつぶれないようにする
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setStyleSheet("background: transparent;")
        screen_layout.addWidget(scroll)

        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        outer_layout = QVBoxLayout(holder)
        outer_layout.setContentsMargins(0, sz(4), 0, sz(8))
        outer_layout.addStretch()

        container = QWidget()
        container.setMaximumWidth(sz(820))
        container.setMinimumWidth(max(520, round(sz(620))))
        layout = QVBoxLayout(container)
        layout.setContentsMargins(sz(38), sz(10), sz(38), sz(14))
        layout.setSpacing(0)

        layout.addWidget(self._build_memo_masthead(scale=scale))
        layout.addSpacing(sz(12))

        grid = QGridLayout()
        grid.setHorizontalSpacing(sz(22))
        grid.setVerticalSpacing(sz(12))

        opts = [
            ("⏱️", "timer", "タイマー", "集中時間を計る", lambda: self.change_screen("timer"), self.colors["primary"]),
            ("📝", "todo", "TO DO", "タスクを管理する", lambda: self.change_screen("todo"), self.colors["accent"]),
            ("📄", "memo", "メモ", "アイデアを書き留める", lambda: self.change_screen("memo"), self.colors["success"]),
            ("📅", "calendar", "カレンダー", "予定を記録する", lambda: self.change_screen("calendar"), self.colors["warn"]),
            ("📓", "notebook", "ノート", "科目ごとに講義を記録する", lambda: self.change_screen("note"), self.colors["info"]),
            ("🔒", "security_memo", "セキュリティメモ", "パスワードで保護されたメモ", self.handle_vault_navigation, self.colors["danger"]),
        ]
        for idx, (icon, icon_file, label, desc, slot, color) in enumerate(opts):
            grid.addWidget(
                self._make_menu_card(icon, label, desc, color, slot, scale=scale, icon_file=icon_file),
                idx // 2, idx % 2,
            )
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        outer_layout.addWidget(container, alignment=Qt.AlignHCenter)
        outer_layout.addStretch()

        scroll.setWidget(holder)
        self.stacked_widget.addWidget(screen)
        self.screens["selector"] = screen

        # 古いセレクター画面を後始末（全画面切り替えなどでの再生成時）
        if old_screen is not None:
            self.stacked_widget.removeWidget(old_screen)
            old_screen.deleteLater()
            if was_current:
                self.stacked_widget.setCurrentWidget(screen)

    def _selector_scale_for_size(self, width, height):
        # 基準サイズ(900x750)に対する幅・高さ比の小さい方を使い、
        # ウィンドウの形（横長／縦長どちらでも）に臨機応変に追従して拡大する
        w_ratio = width / 900.0
        h_ratio = height / 750.0
        scale = max(1.0, min(2.0, min(w_ratio, h_ratio)))
        return round(scale * 20) / 20  # 0.05刻みに丸めて再構築の頻度を抑える

    def _update_selector_scale(self):
        scale = self._selector_scale_for_size(self.width(), self.height())
        if scale != getattr(self, "_selector_scale", 1.0):
            self._selector_scale = scale
            self.create_selector_screen(scale=scale)

    # --- 1. タイマー機能 ---
    def create_timer_screen(self):
        screen = self._new_screen("timerScreenBg")
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(16)

        layout.addWidget(self._make_header("⏱️", "タイマー", self.colors["primary"], icon_file="timer"))

        layout.addStretch(2)

        # 中央のタイマーカード。画びょう付きのノート画像(assets/notebook_pin.png)を背景に敷く。
        # 画像が無い場合は従来のクリーム色のノート風パネルにする
        _pin_path = resource_path(os.path.join("assets", "notebook_pin.png"))
        _pin_pix = QPixmap(_pin_path) if os.path.exists(_pin_path) else None
        if _pin_pix is not None and not _pin_pix.isNull():
            card = PinnedNotePanel(_pin_pix)
            card.setObjectName("timerCard")
            card.setMaximumWidth(640)
            card.setMinimumWidth(480)
            # 画像(1229x984)の紙の内側: 左は赤い罫線の右、上は破れ目の下、右下は紙の端の内側に収める
            cv = QVBoxLayout(card)
            cv.setContentsMargins(78, 80, 62, 66)
            cv.setSpacing(8)
        else:
            card, cv = self._notebook_panel("timerCard", margin=False)
            card.setMaximumWidth(560)
            cv.setContentsMargins(30, 8, 30, 26)
            cv.setSpacing(20)

        self.timer_display = QLabel("00:00")
        self.timer_display.setStyleSheet(f"""
            font-family: {TITLE_FONT_JA};
            font-size: 70px;
            font-weight: 800;
            color: {self.colors['text_main']};
            border: none;
            background: transparent;
        """)
        self.timer_display.setAlignment(Qt.AlignCenter)
        # 数字は紙の上端と入力欄の間の、やや下寄りに置く(上の余白:下の余白 = 5:2)
        cv.addStretch(5)
        cv.addWidget(self.timer_display)
        cv.addStretch(2)

        in_layout = QHBoxLayout()
        in_layout.setSpacing(6)
        self.e_hour = QLineEdit("0")
        self.e_min = QLineEdit("0")
        self.e_sec = QLineEdit("00")
        for entry in (self.e_hour, self.e_min, self.e_sec):
            entry.setFixedSize(60, 44)
            entry.setAlignment(Qt.AlignCenter)
            entry.setMaxLength(3)
            entry.setValidator(QIntValidator(0, 999, entry))   # 数字だけ入力できる
            entry.setStyleSheet(f"""
                font-family: {TITLE_FONT_JA};
                font-size: 21px;
                font-weight: 700;
                border: 2px solid {self.colors['border']};
                border-radius: 11px;
                background: {self.colors['bg_base']};
                color: {self.colors['text_main']};
            """)
            # 入力した時点で、上の大きな数字にすぐ反映する(スタートを押す前でも)
            entry.textChanged.connect(self._on_timer_input_changed)
            # 入力欄から離れたら「90秒→1分30秒」のように繰り上げて整える
            entry.editingFinished.connect(self._normalize_timer_inputs)
        hour_lbl = QLabel("時間"); min_lbl = QLabel("分"); sec_lbl = QLabel("秒")
        for l in (hour_lbl, min_lbl, sec_lbl):
            l.setStyleSheet(f"font-family: {TITLE_FONT_JA}; font-size: 15px; font-weight: 700; color: {self.colors['text_sub']}; border: none;")
        in_layout.addStretch()
        in_layout.addWidget(self.e_hour); in_layout.addWidget(hour_lbl)
        in_layout.addSpacing(8)
        in_layout.addWidget(self.e_min); in_layout.addWidget(min_lbl)
        in_layout.addSpacing(8)
        in_layout.addWidget(self.e_sec); in_layout.addWidget(sec_lbl)
        in_layout.addStretch()
        cv.addLayout(in_layout)

        sound_layout = QHBoxLayout()
        sound_layout.setSpacing(10)
        self.sound_combo = QComboBox()
        for _key in self.sounds.keys():
            # 先頭の絵文字はふい字で表示できないので、見える名前からは外す(音の名前そのものは_keyで保持)
            self.sound_combo.addItem(re.sub(r"^\S+\s+", "", _key), _key)
        self.sound_combo.setFixedWidth(200)
        self.sound_combo.setFixedHeight(36)
        self.sound_combo.setStyleSheet("QComboBox { min-height: 0px; padding: 6px 14px; }")
        preview_btn = self._ghost_btn("試聴", self.colors["primary"])
        preview_btn.setIcon(make_symbol_icon("note"))
        preview_btn.setIconSize(QSize(18, 18))
        preview_btn.clicked.connect(self.preview_sound)
        sound_layout.addStretch()
        sound_layout.addWidget(self.sound_combo)
        sound_layout.addWidget(preview_btn)
        sound_layout.addStretch()
        cv.addLayout(sound_layout)

        # 操作ボタン（カード内に配置・3つとも同じ塗りボタン）
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        # ▶ ■ ↺ は文字ではなく描いたアイコンにする(ふい字では記号が表示されないため)
        start_btn = StyledButton("スタート", self.colors["primary"])
        start_btn.setIcon(make_symbol_icon("play"))
        start_btn.clicked.connect(self.start_timer)
        stop_btn = StyledButton("ストップ", self.colors["danger"])
        stop_btn.setIcon(make_symbol_icon("stop"))
        stop_btn.clicked.connect(self.stop_timer)
        reset_btn = StyledButton("リセット", self.colors["neutral"])
        reset_btn.setIcon(make_symbol_icon("reset"))
        reset_btn.clicked.connect(self.reset_timer)
        for b in (start_btn, stop_btn, reset_btn):
            b.setIconSize(QSize(18, 18))
            b.setFixedHeight(44)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn_layout.addWidget(b)
        cv.addLayout(btn_layout)

        card_row = QHBoxLayout()
        card_row.addStretch()
        card_row.addWidget(card)
        card_row.addStretch()
        layout.addLayout(card_row)
        if not isinstance(card, PinnedNotePanel):   # 画像の紙には最初から影があるので不要
            self._add_shadow(card, blur=32, dy=12, alpha=34, color=self.colors["primary"])

        layout.addStretch(3)

        self.stacked_widget.addWidget(screen)
        self.screens["timer"] = screen

    def _sound_file(self, name, loop=False):
        # winsound は非同期のメモリ再生に非対応のため、WAVファイルを生成して再生する
        key = name + ("::loop" if loop else "")
        path = self._sound_files.get(key)
        if path and os.path.exists(path):
            return path
        segs = self.sounds.get(name)
        if not segs:
            return None
        if loop:
            segs = list(segs) + [(0, 850)]  # ループ再生時は末尾に無音を入れて間隔をあける
        try:
            os.makedirs(self.SOUND_DIR, exist_ok=True)
            path = os.path.join(self.SOUND_DIR, hashlib.md5(key.encode("utf-8")).hexdigest() + ".wav")
            with open(path, "wb") as f:
                f.write(synth_wav(segs))
            self._sound_files[key] = path
            return path
        except OSError:
            return None

    def _play_sound(self, name, loop=False):
        if not HAS_WINSOUND:
            return
        path = self._sound_file(name, loop=loop)
        if not path:
            return
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        if loop:
            flags |= winsound.SND_LOOP
        try:
            winsound.PlaySound(path, flags)
        except RuntimeError:
            pass

    def _stop_sound(self):
        if HAS_WINSOUND:
            winsound.PlaySound(None, winsound.SND_PURGE)

    def preview_sound(self):
        self._play_sound(self.sound_combo.currentData())

    TIMER_MAX_SECONDS = 99 * 3600 + 59 * 60 + 59

    @staticmethod
    def _format_timer(secs):
        # 1時間以上は「1:45:04」、1時間未満は「05:30」の形で表示する
        secs = max(0, int(secs))
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    def _timer_input_seconds(self):
        # 時間・分・秒の入力欄の合計秒数(空欄や数字でないものは0扱い)
        def val(edit):
            try:
                return max(0, int(edit.text()))
            except ValueError:
                return 0
        total = val(self.e_hour) * 3600 + val(self.e_min) * 60 + val(self.e_sec)
        return min(total, self.TIMER_MAX_SECONDS)

    def _timer_is_running(self):
        # stop直後はスレッドが終わるまで最大1秒かかるので、停止要求済みなら「カウント中」とみなさない
        return bool(self.timer_worker and self.timer_worker.isRunning() and self.timer_worker.is_running)

    def _on_timer_input_changed(self, *_):
        # カウント中でなければ、入力した数値をすぐ大きな表示に反映する
        if self._timer_is_running():
            return
        self.timer_display.setText(self._format_timer(self._timer_input_seconds()))

    def _normalize_timer_inputs(self):
        # 「90秒」などを「1分30秒」に繰り上げて、3つの欄をそろえる(カウント中は触らない)
        if self._timer_is_running():
            return
        total = self._timer_input_seconds()
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        for edit, text in ((self.e_hour, str(h)), (self.e_min, str(m)), (self.e_sec, f"{s:02d}")):
            if edit.text() != text:
                edit.blockSignals(True)
                edit.setText(text)
                edit.blockSignals(False)
        self.timer_display.setText(self._format_timer(total))

    def start_timer(self):
        if self._timer_is_running():
            return
        self._normalize_timer_inputs()
        seconds = self._timer_input_seconds()
        if seconds <= 0:
            return
        self.timer_display.setText(self._format_timer(seconds))
        self.timer_worker = TimerWorker(seconds)
        self.timer_worker.tick_signal.connect(self.update_timer_display)
        self.timer_worker.timeout_signal.connect(self.timer_timeout)
        self.timer_worker.start()

    def update_timer_display(self, secs):
        self.timer_display.setText(self._format_timer(secs))

    def timer_timeout(self):
        self.timer_display.setText("00:00")
        self._play_sound(self.sound_combo.currentData(), loop=True)
        # QMessageBox.information はWindowsのシステム音を鳴らし、選択した通知音と
        # 重なって「毎回同じ音」に聞こえるため、アイコン無し(=システム音なし)で表示する
        box = QMessageBox(self)
        box.setWindowTitle("Time Up")
        box.setText("時間になりました！")
        box.setIcon(QMessageBox.NoIcon)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()
        self._stop_sound()

    def stop_timer(self):
        if self.timer_worker:
            self.timer_worker.stop()
        self._stop_sound()

    def reset_timer(self):
        self.stop_timer()
        for edit, text in ((self.e_hour, "0"), (self.e_min, "0"), (self.e_sec, "00")):
            edit.blockSignals(True)
            edit.setText(text)
            edit.blockSignals(False)
        self.timer_display.setText("00:00")


    # --- 2. メモ帳機能 ---
    def create_memo_screen(self):
        screen = self._new_screen("memoScreenBg")
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(self._make_header("📄", "メモ", self.colors["success"], icon_file="memo"))

        # フォルダ選択行: ドロップダウン + 並び替えボタン + 新規ボタン
        folder_row = QWidget()
        folder_row.setFixedHeight(46)
        folder_row_layout = QHBoxLayout(folder_row)
        folder_row_layout.setContentsMargins(0, 0, 0, 0)
        folder_row_layout.setSpacing(6)

        self.folder_combo = QComboBox()
        self.folder_combo.setFixedHeight(44)
        self.folder_combo.setCursor(QCursor(Qt.PointingHandCursor))
        self.folder_combo.setMaxVisibleItems(20)
        # アプリ全体のQSS(padding大)を打ち消して指定した高さで収める
        self.folder_combo.setStyleSheet("QComboBox { min-height: 0px; padding: 6px 14px; }")
        self.folder_combo.currentIndexChanged.connect(self.on_folder_combo_changed)
        folder_row_layout.addWidget(self.folder_combo, stretch=1)

        reorder_btn = self._icon_btn("☰", self.colors["success"], self._open_folder_reorder_popup, label="並び替え")
        reorder_btn.setToolTip("プルダウンを開いて「☰」をドラッグすると並び替えられます")
        folder_row_layout.addWidget(reorder_btn)

        add_btn = WoodSkinButton("＋", radius=13)
        add_btn.setFixedSize(44, 44)
        add_btn.setToolTip("フォルダを追加")
        add_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #4A3426;
                font-size: 19px;
                font-weight: 800;
                border: none;
                border-radius: 13px;
            }
        """)
        add_btn.clicked.connect(self.add_folder)
        folder_row_layout.addWidget(add_btn)
        layout.addWidget(folder_row)

        # フォルダ並び替え用の「見た目はプルダウンと同じ」独立ポップアップ。
        # QComboBox自体の標準ポップアップだと、内部でのクリック（ドラッグの
        # 指離し含む）のたびに自動で閉じてしまい1個しか並び替えられなかったため、
        # Qt.Popupの独立ウィンドウにして「一覧の外をクリックするまで閉じない」
        # ようにした（見た目・開く位置はプルダウンと同じにしている）
        self.folder_reorder_popup = FolderReorderPopup(self.colors, self)
        self.folder_reorder_popup.model.rowsMoved.connect(self._sync_folder_popup_order)
        self.folder_reorder_popup.model.rowsInserted.connect(self._sync_folder_popup_order)
        self.folder_reorder_popup.view.clicked.connect(self._on_folder_popup_item_clicked)

        # テキストエリア（ノート風パネルに載せる = メモ帳らしく）
        paper, paper_content = self._notebook_panel("memoPage")
        self.memo_text_widget = MemoTextEdit()
        self.memo_text_widget.setFont(fui_font(15))
        self.memo_text_widget.setPlaceholderText("ここにメモを入力...（画像はCtrl+Vで添付できます）")
        self.memo_text_widget.setFrameShape(QFrame.NoFrame)
        self.memo_text_widget.setStyleSheet(f"""
            QTextEdit {{ background-color: {self.PAPER_BG}; border: none; padding: 4px 8px; }}
            QScrollBar:vertical {{ border: none; background: transparent; width: 9px; margin: 3px; }}
            QScrollBar::handle:vertical {{ background: {self.PAPER_BORDER}; border-radius: 4px; min-height: 28px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self.memo_text_widget.textChanged.connect(self.save_memo_content)
        self.memo_text_widget.image_pasted.connect(self._save_pasted_image)
        paper_content.addWidget(self.memo_text_widget)
        layout.addWidget(paper, stretch=1)

        # 添付ファイル一覧（添付がある時だけ表示）
        self.attach_scroll = QScrollArea()
        self.attach_scroll.setWidgetResizable(True)
        self.attach_scroll.setMaximumHeight(140)
        self.attach_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.attach_container = QWidget()
        self.attach_layout = QVBoxLayout(self.attach_container)
        self.attach_layout.setAlignment(Qt.AlignTop)
        self.attach_layout.setContentsMargins(2, 2, 2, 2)
        self.attach_layout.setSpacing(6)
        self.attach_scroll.setWidget(self.attach_container)
        self.attach_scroll.hide()
        layout.addWidget(self.attach_scroll)

        # 下部ツールバー: フォルダ操作
        bottom_bar = self._panel("memoBar", radius=14)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(12, 10, 12, 10)
        bottom_layout.setSpacing(8)

        attach_btn = self._ghost_btn("📎 ファイルを添付")
        attach_btn.clicked.connect(self.attach_file_to_memo)
        url_btn = self._ghost_btn("🔗 URLを添付")
        url_btn.clicked.connect(self.add_url_to_memo)
        paste_btn = self._ghost_btn("📋 画像を添付")
        paste_btn.clicked.connect(self.paste_image_from_clipboard)
        rename_btn = self._ghost_btn("✏ 名前変更")
        rename_btn.clicked.connect(self.rename_current_folder)
        pdf_btn = self._ghost_btn("📄 メモをPDFで保存")
        pdf_btn.clicked.connect(self.export_current_memo_to_pdf)
        delete_btn = self._ghost_btn("🗑 削除", self.colors["danger"])
        delete_btn.clicked.connect(lambda: self.delete_folder(self.current_memo_folder))
        for b in (attach_btn, url_btn, paste_btn, rename_btn, pdf_btn, delete_btn):
            bottom_layout.addWidget(b)
        bottom_layout.addStretch()

        layout.addWidget(bottom_bar)
        self._add_shadow(bottom_bar, blur=20, dy=4, alpha=18)

        self.stacked_widget.addWidget(screen)
        self.screens["memo"] = screen

    def draw_tabs(self):
        # フォルダ一覧をドロップダウンに反映（シグナルを止めて再帰的な切り替えを防ぐ）
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        self.folder_combo.addItems(list(self.memo_data.keys()))
        idx = self.folder_combo.findText(self.current_memo_folder)
        if idx >= 0:
            self.folder_combo.setCurrentIndex(idx)
        self.folder_combo.blockSignals(False)

    def on_folder_combo_changed(self, index):
        if index < 0:
            return
        name = self.folder_combo.itemText(index)
        if name and name != self.current_memo_folder:
            self.change_folder(name)

    def _open_folder_reorder_popup(self):
        # プルダウンと同じ見た目・同じ位置に専用ポップアップを開く。
        # クリックで外に出るまで閉じないので、続けて何個でも並び替えできる
        self._suppress_folder_popup_sync = True
        self.folder_reorder_popup.set_folders(list(self.memo_data.keys()))
        self._suppress_folder_popup_sync = False
        self.folder_reorder_popup.open_below(self.folder_combo)

    def _sync_folder_popup_order(self, *args):
        # ドラッグ（FolderDragListView内でのtakeRow+insertRow）で並びが変わる
        # たびに呼ばれ、その場で実データにもプルダウン表示にも反映する
        if getattr(self, "_suppress_folder_popup_sync", False):
            return
        order = self.folder_reorder_popup.order()
        order = [k for k in order if k in self.memo_data]
        for k in self.memo_data:
            if k not in order:
                order.append(k)
        if order != list(self.memo_data.keys()):
            self.memo_data = {k: self.memo_data[k] for k in order}
            self.draw_tabs()

    def _on_folder_popup_item_clicked(self, index):
        # 名前部分（☰以外）をクリックしたら、通常のプルダウンと同じく
        # そのフォルダに切り替えてポップアップを閉じる
        name = index.data(Qt.DisplayRole)
        if name and name != self.current_memo_folder:
            self.change_folder(name)
        self.folder_reorder_popup.hide()

    def load_current_memo_text(self):
        try:
            self.memo_text_widget.textChanged.disconnect(self.save_memo_content)
        except RuntimeError:
            pass
        saved = self.memo_data.get(self.current_memo_folder, "")
        # 太字などの書式を保存できるようHTMLで保存するようにしたが、
        # 過去のプレーンテキスト保存データも問題なく読み込めるようにする
        if "<html" in saved.lower() or "<!doctype html" in saved.lower():
            self.memo_text_widget.setHtml(saved)
        else:
            self.memo_text_widget.setPlainText(saved)
        self.memo_text_widget.textChanged.connect(self.save_memo_content)

    def change_folder(self, name):
        self.current_memo_folder = name
        self.draw_tabs()
        self.load_current_memo_text()
        self.refresh_attachments()

    def save_memo_content(self):
        if hasattr(self, 'memo_text_widget'):
            self.memo_data[self.current_memo_folder] = self.memo_text_widget.toHtml()

    def export_current_memo_to_pdf(self):
        text = self.memo_text_widget.toPlainText()
        export_note_to_pdf(self, self.current_memo_folder, text)

    def add_folder(self):
        dialog = StyledInputDialog("新しいフォルダ", "フォルダ名を入力してください", accent=self.colors["success"], parent=self)
        if dialog.exec_() == QDialog.Accepted:
            res = dialog.get_value().strip()
            if res and res not in self.memo_data:
                self.memo_data[res] = ""
                self.current_memo_folder = res
                self.draw_tabs()
                self.load_current_memo_text()
                self.refresh_attachments()

    def rename_current_folder(self):
        old_name = self.current_memo_folder
        dialog = StyledInputDialog("フォルダ名の変更", f"「{old_name}」の新しい名前", old_name, accent=self.colors["success"], parent=self)
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
                if old_name in self.memo_attachments:
                    self.memo_attachments[res] = self.memo_attachments.pop(old_name)
                self.current_memo_folder = res
                self.draw_tabs()

    def delete_folder(self, name):
        if len(self.memo_data) <= 1:
            QMessageBox.warning(self, "警告", "最後のフォルダは削除できません")
            return

        ret = QMessageBox.question(self, "確認", f"フォルダ「{name}」を削除しますか？", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            del self.memo_data[name]
            for entry in self.memo_attachments.pop(name, []):
                self._cleanup_attachment_file(entry.get("file"))
            if self.current_memo_folder == name:
                self.current_memo_folder = list(self.memo_data.keys())[0]
            self.draw_tabs()
            self.load_current_memo_text()
            self.refresh_attachments()

    # --- メモ添付ファイル ---
    def refresh_attachments(self):
        if not hasattr(self, 'attach_layout'):
            return
        while self.attach_layout.count():
            child = self.attach_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        entries = self.memo_attachments.get(self.current_memo_folder, [])
        if not entries:
            self.attach_scroll.hide()
            return
        self.attach_scroll.show()

        for i, entry in enumerate(entries):
            row = QWidget()
            row.setStyleSheet(f"""
                QWidget {{
                    background-color: {self.colors['bg_base']};
                    border-radius: 8px;
                    border: 1px solid {self.colors['border']};
                }}
            """)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 6, 8, 6)
            rl.setSpacing(8)

            is_url = entry.get("type") == "url"
            icon = "🔗" if is_url else "📄"
            label = entry.get("name") or entry.get("url") or "(名前なし)"
            name_btn = QPushButton()
            apply_glyph_icon(name_btn, f"{icon}  {label}", self.colors['primary'], 16)
            name_btn.setCursor(QCursor(Qt.PointingHandCursor))
            if is_url:
                name_btn.setToolTip(entry.get("url", ""))
            name_btn.setStyleSheet(f"""
                QPushButton {{
                    text-align: left;
                    font-size: 13px;
                    color: {self.colors['primary']};
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    padding: 4px 6px;
                }}
                QPushButton:hover {{ background: {self.colors['primary']}; color: #FFFFFF; }}
            """)
            if is_url:
                name_btn.clicked.connect(lambda checked=False, u=entry.get("url"): self._open_url(u))
            else:
                name_btn.clicked.connect(lambda checked=False, f=entry.get("file"): self.open_attachment(f))
            rl.addWidget(name_btn, stretch=1)

            del_btn = QPushButton()
            apply_glyph_icon(del_btn, "🗑", self.colors['danger'], 16)
            del_btn.setCursor(QCursor(Qt.PointingHandCursor))
            del_btn.setFixedHeight(30)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {self.colors['danger']};
                    font-size: 13px;
                    background: transparent;
                    border: 1px solid {self.colors['danger']};
                    border-radius: 7px;
                    padding: 4px 10px;
                }}
                QPushButton:hover {{ background: {self.colors['danger']}; color: #FFFFFF; }}
            """)
            del_btn.clicked.connect(lambda checked=False, idx=i: self.remove_attachment(idx))
            rl.addWidget(del_btn)

            self.attach_layout.addWidget(row)

    def attach_file_to_memo(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "添付するファイルを選択")
        if not paths:
            return
        os.makedirs(self.ATTACH_DIR, exist_ok=True)
        lst = self.memo_attachments.setdefault(self.current_memo_folder, [])
        for src in paths:
            base = os.path.basename(src)
            stored = f"{uuid.uuid4().hex[:8]}_{base}"
            try:
                shutil.copy2(src, os.path.join(self.ATTACH_DIR, stored))
                lst.append({"name": base, "file": stored})
            except OSError as e:
                QMessageBox.warning(self, "警告", f"コピーできませんでした: {base}\n{e}")
        self.refresh_attachments()
        self.save_all_data()

    def add_url_to_memo(self):
        d = StyledInputDialog("URLを追加", "URL を入力してください（例: https://example.com）", parent=self)
        if d.exec_() != QDialog.Accepted:
            return
        url = d.get_value().strip()
        if not url:
            return
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://', url):
            url = "https://" + url
        t = StyledInputDialog("表示名", "表示名（空欄ならURLをそのまま表示）", parent=self)
        title = t.get_value().strip() if t.exec_() == QDialog.Accepted else ""
        self.memo_attachments.setdefault(self.current_memo_folder, []).append(
            {"type": "url", "name": title or url, "url": url}
        )
        self.refresh_attachments()
        self.save_all_data()

    def _open_url(self, url):
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def paste_image_from_clipboard(self):
        img = QApplication.clipboard().image()
        if img is None or img.isNull():
            QMessageBox.information(self, "情報", "クリップボードに画像がありません")
            return
        self._save_pasted_image(img)

    def _save_pasted_image(self, image):
        if image is None or image.isNull():
            return
        os.makedirs(self.ATTACH_DIR, exist_ok=True)
        stored = f"paste_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.png"
        if image.save(os.path.join(self.ATTACH_DIR, stored), "PNG"):
            self.memo_attachments.setdefault(self.current_memo_folder, []).append(
                {"name": stored, "file": stored}
            )
            self.refresh_attachments()
            self.save_all_data()
        else:
            QMessageBox.warning(self, "警告", "画像を保存できませんでした")

    def open_attachment(self, stored_name):
        if not stored_name:
            return
        path = os.path.join(self.ATTACH_DIR, stored_name)
        if not os.path.exists(path):
            QMessageBox.warning(self, "警告", "ファイルが見つかりません（移動または削除された可能性があります）")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def remove_attachment(self, index):
        lst = self.memo_attachments.get(self.current_memo_folder, [])
        if not (0 <= index < len(lst)):
            return
        entry = lst[index]
        ret = QMessageBox.question(
            self, "確認", f"添付「{entry.get('name')}」を一覧から削除しますか？",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            lst.pop(index)
            self._cleanup_attachment_file(entry.get("file"))
            self.refresh_attachments()
            self.save_all_data()

    def _cleanup_attachment_file(self, stored_name):
        # 他のフォルダから参照されていなければ実体ファイルを削除する
        if not stored_name:
            return
        for entries in self.memo_attachments.values():
            for e in entries:
                if e.get("file") == stored_name:
                    return
        try:
            path = os.path.join(self.ATTACH_DIR, stored_name)
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    # --- ノート機能（科目ごとに講義の記録を残す、大学の授業向け） ---
    def create_note_screen(self):
        screen = self._new_screen("noteScreenBg")
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(self._make_header("📓", "ノート", self.colors["info"], icon_file="notebook"))

        # 科目選択行: ドロップダウン + 新規科目ボタン
        subject_row = QWidget()
        subject_row.setFixedHeight(46)
        subject_row_layout = QHBoxLayout(subject_row)
        subject_row_layout.setContentsMargins(0, 0, 0, 0)
        subject_row_layout.setSpacing(6)

        self.note_subject_combo = QComboBox()
        self.note_subject_combo.setFixedHeight(44)
        self.note_subject_combo.setCursor(QCursor(Qt.PointingHandCursor))
        self.note_subject_combo.setMaxVisibleItems(20)
        self.note_subject_combo.setStyleSheet("QComboBox { min-height: 0px; padding: 6px 14px; }")
        self.note_subject_combo.currentIndexChanged.connect(self.on_note_subject_combo_changed)
        subject_row_layout.addWidget(self.note_subject_combo, stretch=1)

        add_subject_btn = WoodSkinButton("＋", radius=13)
        add_subject_btn.setFixedSize(44, 44)
        add_subject_btn.setToolTip("科目を追加")
        add_subject_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #4A3426;
                font-size: 19px;
                font-weight: 800;
                border: none;
                border-radius: 13px;
            }
        """)
        add_subject_btn.clicked.connect(self.add_note_subject)
        subject_row_layout.addWidget(add_subject_btn)
        layout.addWidget(subject_row)

        # 本体: 左＝講義回の一覧、右＝選択した回の内容
        body_row = QHBoxLayout()
        body_row.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        add_entry_btn = StyledButton("＋ 新しい回を追加", self.colors["info"])
        add_entry_btn.clicked.connect(self.add_note_entry)
        left_col.addWidget(add_entry_btn)

        self.note_entry_list = QListWidget()
        self.note_entry_list.setFixedWidth(220)
        self.note_entry_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {self.PAPER_BG};
                border: 1px solid {self.PAPER_BORDER};
                border-radius: 14px;
                padding: 6px;
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 10px 8px;
                border-radius: 9px;
                color: {self.colors['text_main']};
            }}
            QListWidget::item:selected {{
                background-color: {self._rgba(self.colors['info'], 0.16)};
                color: {self.colors['info']};
                font-weight: 700;
            }}
        """)
        self._add_shadow(self.note_entry_list, blur=20, dy=6, alpha=20)
        self.note_entry_list.currentRowChanged.connect(self.on_note_entry_row_changed)
        left_col.addWidget(self.note_entry_list, stretch=1)

        body_row.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        title_date_row = QHBoxLayout()
        title_date_row.setSpacing(8)
        self.note_title_input = QLineEdit()
        self.note_title_input.setPlaceholderText("この回のタイトル（例: 第3回 微分積分）")
        self.note_title_input.setFixedHeight(40)
        self.note_title_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.PAPER_BG};
                border: 1px solid {self.PAPER_BORDER};
                border-radius: 10px;
                padding: 0 12px;
                font-size: 15px;
                font-weight: 700;
                color: {self.colors['text_main']};
            }}
        """)
        self.note_title_input.editingFinished.connect(self.on_note_title_edited)
        title_date_row.addWidget(self.note_title_input, stretch=1)

        self.note_date_input = QLineEdit()
        self.note_date_input.setPlaceholderText("YYYY-MM-DD")
        self.note_date_input.setFixedSize(120, 40)
        self.note_date_input.setAlignment(Qt.AlignCenter)
        self.note_date_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.PAPER_BG};
                border: 1px solid {self.PAPER_BORDER};
                border-radius: 10px;
                font-size: 13px;
                color: {self.colors['text_sub']};
            }}
        """)
        self.note_date_input.editingFinished.connect(self.on_note_date_edited)
        title_date_row.addWidget(self.note_date_input)
        right_col.addLayout(title_date_row)

        paper, paper_content = self._notebook_panel("notePage")
        self.note_content_widget = NoteTextEdit()
        self.note_content_widget.setFont(fui_font(15))
        self.note_content_widget.setPlaceholderText("この回の講義内容やメモを入力...")
        self.note_content_widget.setToolTip("挿入したスケッチ／グラフはダブルクリックで削除できます")
        self.note_content_widget.setFrameShape(QFrame.NoFrame)
        self.note_content_widget.setStyleSheet(f"""
            QTextEdit {{ background-color: {self.PAPER_BG}; border: none; padding: 4px 8px; }}
            QScrollBar:vertical {{ border: none; background: transparent; width: 9px; margin: 3px; }}
            QScrollBar::handle:vertical {{ background: {self.PAPER_BORDER}; border-radius: 4px; min-height: 28px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self.note_content_widget.textChanged.connect(self.save_current_note_entry_content)
        paper_content.addWidget(self.note_content_widget)
        right_col.addWidget(paper, stretch=1)

        note_bottom_bar = self._panel("noteBar", radius=14)
        # ボタンが多いツールバーなので、小さいウィンドウでは折り返して
        # 全項目が見切れず表示されるようにする
        note_bottom_layout = FlowLayout(note_bottom_bar, margin=10, h_spacing=8, v_spacing=8)

        sketch_btn = self._ghost_btn("✏️ 手書きスケッチ", self.colors["info"])
        sketch_btn.clicked.connect(self.open_sketch_dialog)
        graph_btn = self._ghost_btn("📈 グラフを挿入", self.colors["info"])
        graph_btn.clicked.connect(self.open_function_graph_dialog)
        delete_image_btn = self._ghost_btn("🗑 スケッチ／グラフを削除", self.colors["danger"])
        delete_image_btn.setToolTip("削除したい画像をクリックしてカーソルを合わせてから押してください")
        delete_image_btn.clicked.connect(self.delete_note_image_at_cursor)
        pdf_btn = self._ghost_btn("📄 この回をPDFで保存")
        pdf_btn.clicked.connect(self.export_current_note_to_pdf)
        rename_subject_btn = self._ghost_btn("✏ 科目名を変更")
        rename_subject_btn.clicked.connect(self.rename_note_subject)
        delete_subject_btn = self._ghost_btn("🗑 科目を削除", self.colors["danger"])
        delete_subject_btn.clicked.connect(self.delete_note_subject)
        self.delete_note_entry_btn = self._ghost_btn("🗑 この回を削除", self.colors["danger"])
        self.delete_note_entry_btn.clicked.connect(self.delete_note_entry)
        for b in (sketch_btn, graph_btn, delete_image_btn, pdf_btn, rename_subject_btn, delete_subject_btn, self.delete_note_entry_btn):
            note_bottom_layout.addWidget(b)
        right_col.addWidget(note_bottom_bar)
        self._add_shadow(note_bottom_bar, blur=20, dy=4, alpha=18)

        body_row.addLayout(right_col, stretch=1)
        layout.addLayout(body_row, stretch=1)

        self.stacked_widget.addWidget(screen)
        self.screens["note"] = screen

    def draw_note_subjects(self):
        self.note_subject_combo.blockSignals(True)
        self.note_subject_combo.clear()
        self.note_subject_combo.addItems(list(self.note_data.keys()))
        idx = self.note_subject_combo.findText(self.current_note_subject)
        if idx >= 0:
            self.note_subject_combo.setCurrentIndex(idx)
        self.note_subject_combo.blockSignals(False)

    def on_note_subject_combo_changed(self, index):
        if index < 0:
            return
        name = self.note_subject_combo.itemText(index)
        if name and name != self.current_note_subject:
            self.save_current_note_entry_content()
            self.current_note_subject = name
            self.refresh_note_entry_list()

    def refresh_note_entry_list(self):
        if not hasattr(self, "note_entry_list"):
            return
        entries = self.note_data.get(self.current_note_subject, [])
        self.note_entry_list.blockSignals(True)
        self.note_entry_list.clear()
        # 新しい回ほど上に来るよう、日付の新しい順に並べる
        order = sorted(range(len(entries)), key=lambda i: entries[i].get("date", ""), reverse=True)
        self._note_entry_display_order = order
        for i in order:
            e = entries[i]
            item = QListWidgetItem(f"{e.get('date', '')}\n{e.get('title', '')}")
            self.note_entry_list.addItem(item)
        self.note_entry_list.blockSignals(False)

        if order:
            self.note_entry_list.setCurrentRow(0)
        else:
            self.load_note_entry(None)

    def on_note_entry_row_changed(self, row):
        # 内容はtextChangedのたびに逐次self.note_dataへ保存済みなので、
        # ここで改めて保存すると科目切替直後にインデックスがずれて
        # 別の科目のデータを上書きしてしまう恐れがあるため呼ばない
        if row is None or row < 0 or not getattr(self, "_note_entry_display_order", None):
            self.load_note_entry(None)
            return
        real_index = self._note_entry_display_order[row]
        self.load_note_entry(real_index)

    def load_note_entry(self, index):
        self.current_note_entry_index = index
        entries = self.note_data.get(self.current_note_subject, [])
        has_entry = index is not None and 0 <= index < len(entries)

        self.note_title_input.setEnabled(has_entry)
        self.note_date_input.setEnabled(has_entry)
        self.note_content_widget.setEnabled(has_entry)
        self.delete_note_entry_btn.setEnabled(has_entry)

        try:
            self.note_content_widget.textChanged.disconnect(self.save_current_note_entry_content)
        except RuntimeError:
            pass

        if has_entry:
            e = entries[index]
            self.note_title_input.setText(e.get("title", ""))
            self.note_date_input.setText(e.get("date", ""))
            content = e.get("content", "")
            if "<html" in content.lower() or "<!doctype html" in content.lower():
                self.note_content_widget.setHtml(content)
            else:
                self.note_content_widget.setPlainText(content)
        else:
            self.note_title_input.clear()
            self.note_date_input.clear()
            self.note_content_widget.clear()
            self.note_content_widget.setPlaceholderText(
                "この科目にはまだ講義の記録がありません。「＋ 新しい回を追加」から始めましょう。"
            )

        self.note_content_widget.textChanged.connect(self.save_current_note_entry_content)

    def save_current_note_entry_content(self):
        if not hasattr(self, "note_content_widget"):
            return
        if self.current_note_entry_index is None:
            return
        entries = self.note_data.get(self.current_note_subject, [])
        if 0 <= self.current_note_entry_index < len(entries):
            entries[self.current_note_entry_index]["content"] = self.note_content_widget.toHtml()

    def on_note_title_edited(self):
        if self.current_note_entry_index is None:
            return
        entries = self.note_data.get(self.current_note_subject, [])
        if 0 <= self.current_note_entry_index < len(entries):
            entries[self.current_note_entry_index]["title"] = self.note_title_input.text().strip()
            self.refresh_note_entry_list()
            self._reselect_note_entry(self.current_note_entry_index)

    def on_note_date_edited(self):
        if self.current_note_entry_index is None:
            return
        text = self.note_date_input.text().strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            QMessageBox.warning(self, "警告", "日付は YYYY-MM-DD の形式で入力してください")
            entries = self.note_data.get(self.current_note_subject, [])
            if 0 <= self.current_note_entry_index < len(entries):
                self.note_date_input.setText(entries[self.current_note_entry_index].get("date", ""))
            return
        entries = self.note_data.get(self.current_note_subject, [])
        if 0 <= self.current_note_entry_index < len(entries):
            entries[self.current_note_entry_index]["date"] = text
            target_index = self.current_note_entry_index
            self.refresh_note_entry_list()
            self._reselect_note_entry(target_index)

    def _reselect_note_entry(self, real_index):
        # refresh_note_entry_list()の直後は一覧の並びが変わっている可能性があり、
        # setCurrentRow(0)で別の回が自動的に読み込まれてしまっているため、
        # 選択位置を戻すだけでなく編集欄も明示的に読み直して一致させる
        order = getattr(self, "_note_entry_display_order", [])
        if real_index in order:
            self.note_entry_list.blockSignals(True)
            self.note_entry_list.setCurrentRow(order.index(real_index))
            self.note_entry_list.blockSignals(False)
            self.load_note_entry(real_index)

    def add_note_entry(self):
        self.save_current_note_entry_content()
        entries = self.note_data.setdefault(self.current_note_subject, [])
        new_entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "title": f"第{len(entries) + 1}回",
            "content": "",
        }
        entries.append(new_entry)
        new_index = len(entries) - 1
        self.refresh_note_entry_list()
        self._reselect_note_entry(new_index)
        self.note_title_input.setFocus()
        self.note_title_input.selectAll()

    def delete_note_entry(self):
        if self.current_note_entry_index is None:
            return
        entries = self.note_data.get(self.current_note_subject, [])
        if not (0 <= self.current_note_entry_index < len(entries)):
            return
        title = entries[self.current_note_entry_index].get("title", "") or "この回"
        ret = QMessageBox.question(self, "確認", f"「{title}」を削除しますか？", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            del entries[self.current_note_entry_index]
            self.current_note_entry_index = None
            self.refresh_note_entry_list()

    def add_note_subject(self):
        dialog = StyledInputDialog("新しい科目", "科目名を入力してください", accent=self.colors["info"], parent=self)
        if dialog.exec_() == QDialog.Accepted:
            res = dialog.get_value().strip()
            if res and res not in self.note_data:
                self.note_data[res] = []
                self.current_note_subject = res
                self.draw_note_subjects()
                self.refresh_note_entry_list()

    def rename_note_subject(self):
        old_name = self.current_note_subject
        dialog = StyledInputDialog("科目名の変更", f"「{old_name}」の新しい名前", old_name, accent=self.colors["info"], parent=self)
        if dialog.exec_() == QDialog.Accepted:
            res = dialog.get_value().strip()
            if res and res != old_name:
                if res in self.note_data:
                    QMessageBox.warning(self, "警告", "既に同じ名前の科目が存在します")
                    return
                new_note_data = {}
                for k, v in self.note_data.items():
                    new_note_data[res if k == old_name else k] = v
                self.note_data = new_note_data
                self.current_note_subject = res
                self.draw_note_subjects()

    def delete_note_subject(self):
        if len(self.note_data) <= 1:
            QMessageBox.warning(self, "警告", "最後の科目は削除できません")
            return
        name = self.current_note_subject
        ret = QMessageBox.question(self, "確認", f"科目「{name}」を削除しますか？\n中の講義記録もすべて削除されます。", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            del self.note_data[name]
            self.current_note_subject = list(self.note_data.keys())[0]
            self.current_note_entry_index = None
            self.draw_note_subjects()
            self.refresh_note_entry_list()

    def export_current_note_to_pdf(self):
        if self.current_note_entry_index is None:
            QMessageBox.warning(self, "PDF書き出し", "書き出す回を選択してください。")
            return
        entries = self.note_data.get(self.current_note_subject, [])
        if not (0 <= self.current_note_entry_index < len(entries)):
            return
        title = entries[self.current_note_entry_index].get("title", "") or self.current_note_subject
        text = self.note_content_widget.toPlainText()
        export_note_to_pdf(self, f"{self.current_note_subject}_{title}", text)

    def _insert_image_into_note(self, image):
        # data URIとしてHTMLに直接埋め込むことで、外部ファイルに頼らず
        # toHtml()/setHtml()の保存・読込だけで画像もそのまま保持されるようにする
        if image is None or image.isNull():
            return
        buf = QByteArray()
        buffer = QBuffer(buf)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        b64 = bytes(buf.toBase64()).decode("ascii")
        cursor = self.note_content_widget.textCursor()
        cursor.insertHtml(f'<br><img src="data:image/png;base64,{b64}"><br>')
        self.note_content_widget.setTextCursor(cursor)
        self.note_content_widget.setFocus()
        self.save_current_note_entry_content()

    def open_sketch_dialog(self):
        if self.current_note_entry_index is None:
            QMessageBox.warning(self, "警告", "先に講義の回を選択（または追加）してください。")
            return
        dialog = SketchDialog(self.colors, parent=self)
        if dialog.exec_() == QDialog.Accepted and dialog.result_image is not None:
            self._insert_image_into_note(dialog.result_image)

    def open_function_graph_dialog(self):
        if self.current_note_entry_index is None:
            QMessageBox.warning(self, "警告", "先に講義の回を選択（または追加）してください。")
            return
        dialog = FunctionGraphDialog(self.colors, parent=self)
        if dialog.exec_() == QDialog.Accepted and dialog.result_image is not None:
            self._insert_image_into_note(dialog.result_image)

    def delete_note_image_at_cursor(self):
        if self.current_note_entry_index is None:
            QMessageBox.warning(self, "警告", "先に講義の回を選択してください。")
            return
        image_cursor = self.note_content_widget.image_cursor_at_text_cursor()
        if image_cursor is None:
            QMessageBox.information(
                self, "画像の削除",
                "削除したいスケッチ／グラフをクリックしてカーソルを合わせてから、もう一度このボタンを押してください。"
            )
            return
        if self.note_content_widget.delete_image_with_confirm(image_cursor):
            self.save_current_note_entry_content()

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
        screen = self._new_screen("vaultAuthScreenBg")
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)

        layout.addWidget(self._make_header("🔒", "セキュリティメモ", self.colors["danger"], icon_file="security_memo"))

        layout.addStretch()

        auth_card = self._panel("authCard", radius=18)
        auth_card.setMaximumWidth(420)
        auth_card.setMinimumWidth(300)
        auth_layout = QVBoxLayout(auth_card)
        auth_layout.setContentsMargins(34, 36, 34, 32)
        auth_layout.setSpacing(18)
        auth_layout.setAlignment(Qt.AlignCenter)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(make_symbol_icon("lock", self.colors['danger'], 34).pixmap(34, 34))
        icon_lbl.setFixedSize(60, 60)
        icon_lbl.setStyleSheet(f"font-size: 28px; border: none; border-radius: 18px; background-color: {self._rgba(self.colors['danger'], 0.14)};")
        icon_lbl.setAlignment(Qt.AlignCenter)
        auth_layout.addWidget(icon_lbl, alignment=Qt.AlignCenter)

        lbl = QLabel("パスワードを入力")
        lbl.setStyleSheet(f"font-size: 19px; font-weight: 800; color: {self.colors['text_main']}; border: none;")
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
        self._add_shadow(auth_card, blur=32, dy=12, alpha=32, color=self.colors["danger"])
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
        screen = self._new_screen("vaultInsideScreenBg")
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        def logout():
            self.is_authenticated = False
            self.back_to_selector()

        layout.addWidget(self._make_header("🔒", "セキュリティメモ", self.colors["danger"],
                                           back_slot=logout, back_text="🔓  ログアウト", icon_file="security_memo"))

        list_frame, frame_layout = self._notebook_panel("vaultFrame")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.vault_list_widget = QWidget()
        self.vault_list_widget.setObjectName("vaultList")
        self.vault_list_widget.setStyleSheet(f"QWidget#vaultList {{ background-color: {self.PAPER_BG}; }}")
        self.vault_list_layout = QVBoxLayout(self.vault_list_widget)
        self.vault_list_layout.setAlignment(Qt.AlignTop)
        self.vault_list_layout.setSpacing(8)
        self.vault_list_layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(self.vault_list_widget)
        frame_layout.addWidget(scroll)
        layout.addWidget(list_frame, stretch=1)

        add_btn = StyledButton("＋  セキュリティメモを追加", self.colors["danger"])
        add_btn.setFixedHeight(52)
        add_btn.clicked.connect(self.add_vault_item)
        layout.addWidget(add_btn)

        self.stacked_widget.addWidget(screen)
        self.screens["vault_inside"] = screen

    def add_vault_item(self):
        t_diag = StyledInputDialog("新しい項目", "項目名を入力", accent=self.colors["danger"], parent=self)
        if t_diag.exec_() == QDialog.Accepted and t_diag.get_value():
            p_diag = StyledInputDialog("暗号化メモ", "保存する内容を入力", accent=self.colors["danger"], parent=self)
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
            row.setObjectName("vaultRow")
            row.setStyleSheet(f"""
                QWidget#vaultRow {{
                    background-color: #FFFFFF;
                    border-radius: 11px;
                    border: 1px solid {self.PAPER_BORDER};
                }}
            """)
            row.setMinimumHeight(58)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 8, 10, 8)
            row_layout.setSpacing(12)

            text_box = QVBoxLayout()
            text_box.setSpacing(2)
            lbl_title = QLabel(item['title'])
            lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {self.colors['text_main']}; border: none;")
            p_disp = item["pass"] if item.get("show") else "••••••••••"
            lbl_pass = QLabel(p_disp)
            lbl_pass.setStyleSheet(f"font-family: {TITLE_FONT_JA}; color: {self.colors['text_sub']}; font-size: 13px; border: none;")
            text_box.addWidget(lbl_title)
            text_box.addWidget(lbl_pass)
            row_layout.addLayout(text_box, stretch=1)

            def toggle_show(checked=False, idx=i):
                self.vault_items[idx]["show"] = not self.vault_items[idx]["show"]
                self.refresh_vault()

            def rename_item(checked=False, idx=i):
                d = StyledInputDialog("項目名の変更", "新しい項目名を入力", self.vault_items[idx]["title"], accent=self.colors["danger"], parent=self)
                if d.exec_() == QDialog.Accepted and d.get_value().strip():
                    self.vault_items[idx]["title"] = d.get_value()
                    self.refresh_vault()

            def delete_item(checked=False, idx=i):
                ret = QMessageBox.question(self, "確認", f"「{self.vault_items[idx]['title']}」を削除しますか？", QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.Yes:
                    self.vault_items.pop(idx)
                    self.refresh_vault()

            eye_label = "隠す" if item.get("show") else "表示"
            row_layout.addWidget(self._icon_btn("🙈" if item.get("show") else "👁", self.colors["primary"], toggle_show, label=eye_label))
            row_layout.addWidget(self._icon_btn("✏", self.colors["primary"], rename_item, label="編集"))
            row_layout.addWidget(self._icon_btn("🗑", self.colors["danger"], delete_item, label="削除"))

            self.vault_list_layout.addWidget(row)
        self.save_all_data()


    # --- 4. TO DO リスト機能 ---
    def create_todo_screen(self):
        screen = self._new_screen("todoScreenBg")
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(self._make_header("📝", "TO DO", self.colors["accent"], icon_file="todo"))

        list_frame, frame_layout = self._notebook_panel("todoFrame")

        # ノート(紙)の左上に「タスク」の見出しを書く
        todo_title = QLabel("タスク")
        # 文字の大きさ・太さ・フォントは「完了済み (n)」の見出しと同じ(色だけ濃いまま)
        todo_title.setStyleSheet(
            f"color: {self.colors['text_main']}; font-size: 13px; font-weight: 700; "
            f"border: none; background: transparent; padding: 0px 0px 0px 10px;")
        frame_layout.addWidget(todo_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.todo_list_widget = QWidget()
        self.todo_list_widget.setObjectName("todoList")
        self.todo_list_widget.setStyleSheet(f"QWidget#todoList {{ background-color: {self.PAPER_BG}; }}")
        self.todo_list_layout = QVBoxLayout(self.todo_list_widget)
        self.todo_list_layout.setAlignment(Qt.AlignTop)
        self.todo_list_layout.setSpacing(8)
        self.todo_list_layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(self.todo_list_widget)
        frame_layout.addWidget(scroll)
        layout.addWidget(list_frame, stretch=1)

        add_btn = StyledButton("＋  タスクを追加", self.colors["accent"])
        add_btn.setFixedHeight(52)
        add_btn.clicked.connect(self.add_todo_item)
        layout.addWidget(add_btn)

        self.stacked_widget.addWidget(screen)
        self.screens["todo"] = screen

    def add_todo_item(self):
        dialog = StyledInputDialog("タスクの追加", "タスク内容を入力してください", accent=self.colors["accent"], parent=self)
        if dialog.exec_() == QDialog.Accepted and dialog.get_value().strip():
            self.todo_items.append({"text": dialog.get_value().strip(), "done": False, "done_at": None})
            self.refresh_todo()

    def toggle_todo_done(self, index, done):
        if 0 <= index < len(self.todo_items):
            self.todo_items[index]["done"] = done
            self.todo_items[index]["done_at"] = datetime.now().strftime("%m/%d %H:%M") if done else None
            self.refresh_todo()

    def edit_todo(self, index):
        if not (0 <= index < len(self.todo_items)):
            return
        old_text = self.todo_items[index].get("text", "")
        dialog = StyledInputDialog("タスクの編集", "タスク内容を編集してください", old_text, accent=self.colors["accent"], parent=self)
        if dialog.exec_() == QDialog.Accepted:
            new_text = dialog.get_value().strip()
            if new_text and new_text != old_text:
                self.todo_items[index]["text"] = new_text
                self.refresh_todo()

    def delete_todo(self, index):
        if 0 <= index < len(self.todo_items):
            self.todo_items.pop(index)
            self.refresh_todo()

    def clear_completed_todos(self):
        remaining = [t for t in self.todo_items if not t.get("done")]
        if len(remaining) == len(self.todo_items):
            return
        ret = QMessageBox.question(self, "確認", "完了済みのタスクをすべて削除しますか？", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.todo_items = remaining
            self.refresh_todo()

    def _icon_btn(self, glyph, hover_color, slot, label=None):
        # 明確にボタンと分かるよう、常時うっすら背景＋枠をつける
        b = WoodSkinButton(f"{glyph}  {label}" if label else glyph, radius=9)
        if label:
            b.setMinimumHeight(32)
        else:
            b.setFixedSize(34, 32)
        b.setStyleSheet(f"""
            QPushButton {{
                color: #4A3426;
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 600;
                border-radius: 9px;
                padding: {'5px 12px' if label else '0px'};
            }}
        """)
        b.clicked.connect(slot)
        return b

    def _make_todo_row(self, index, task):
        is_done = task.get("done", False)
        row = QWidget()
        row.setObjectName("todoRow")
        row.setStyleSheet(f"""
            QWidget#todoRow {{
                background-color: #FFFFFF;
                border-radius: 11px;
                border: 1px solid {self.PAPER_BORDER};
            }}
        """)
        row.setMinimumHeight(56)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 10, 8)
        row_layout.setSpacing(12)

        check = QPushButton()
        if is_done:
            apply_glyph_icon(check, "✓", "#FFFFFF", 14)
        check.setFixedSize(26, 26)
        check.setCursor(QCursor(Qt.PointingHandCursor))
        if is_done:
            check.setStyleSheet(f"""
                QPushButton {{ background: {self.colors['success']}; color: #FFFFFF;
                    border: none; border-radius: 13px; font-size: 13px; font-weight: 800; }}
            """)
        else:
            check.setStyleSheet(f"""
                QPushButton {{ background: transparent; border: 2px solid {self.colors['border']}; border-radius: 13px; }}
                QPushButton:hover {{ border-color: {self.colors['success']}; }}
            """)
        check.clicked.connect(lambda checked=False, idx=index, d=(not is_done): self.toggle_todo_done(idx, d))
        row_layout.addWidget(check)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        lbl = QLabel(task.get("text", ""))
        lbl.setWordWrap(True)
        if is_done:
            lbl.setStyleSheet(f"font-size: 15px; color: {self.colors['text_sub']}; border: none; text-decoration: line-through;")
        else:
            lbl.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {self.colors['text_main']}; border: none;")
        text_box.addWidget(lbl)
        if is_done and task.get("done_at"):
            date_lbl = QLabel("完了 " + task["done_at"])
            date_lbl.setStyleSheet(f"font-size: 11px; color: {self.colors['text_sub']}; border: none;")
            text_box.addWidget(date_lbl)
        row_layout.addLayout(text_box, stretch=1)

        row_layout.addWidget(self._icon_btn("✏", self.colors["primary"],
                                            lambda checked=False, idx=index: self.edit_todo(idx), label="編集"))
        row_layout.addWidget(self._icon_btn("🗑", self.colors["danger"],
                                            lambda checked=False, idx=index: self.delete_todo(idx), label="削除"))
        return row

    def refresh_todo(self):
        while self.todo_list_layout.count():
            child = self.todo_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        active = [(i, t) for i, t in enumerate(self.todo_items) if not t.get("done")]
        done = [(i, t) for i, t in enumerate(self.todo_items) if t.get("done")]

        if not active and not done:
            empty = QLabel("まだタスクはありません\n下の「＋」から追加してみよう")
            empty.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 15px; font-weight: 600; padding: 48px; line-height: 1.6;")
            empty.setAlignment(Qt.AlignCenter)
            self.todo_list_layout.addWidget(empty)

        for i, task in active:
            self.todo_list_layout.addWidget(self._make_todo_row(i, task))

        if done:
            header = QWidget()
            header.setStyleSheet("background: transparent; border: none;")
            h_layout = QHBoxLayout(header)
            h_layout.setContentsMargins(6, 14, 6, 2)

            h_lbl = QLabel(f"完了済み ({len(done)})")
            h_lbl.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 13px; font-weight: 700; border: none;")
            h_layout.addWidget(h_lbl)
            h_layout.addStretch()

            clear_btn = QPushButton("すべて削除")
            clear_btn.setCursor(QCursor(Qt.PointingHandCursor))
            clear_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {self.colors['text_sub']};
                    font-size: 12px;
                    font-weight: 600;
                    background: transparent;
                    border: none;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{ color: {self.colors['danger']}; }}
            """)
            clear_btn.clicked.connect(self.clear_completed_todos)
            h_layout.addWidget(clear_btn)

            self.todo_list_layout.addWidget(header)

            for i, task in done:
                self.todo_list_layout.addWidget(self._make_todo_row(i, task))

        self.save_all_data()


    # --- 5. カレンダー機能 ---
    def _cal_nav_btn(self, text, slot, width=None):
        b = QPushButton(text)
        b.setCursor(QCursor(Qt.PointingHandCursor))
        b.setFixedHeight(40)
        if width:
            b.setFixedWidth(width)
        b.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.colors['text_sub']};
                border: 1px solid {self.colors['border']};
                border-radius: 10px;
                padding: 6px 14px;
                font-size: 14px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background: {self.colors['bg_surface']};
                color: {self.colors['text_main']};
                border-color: {self.colors['neutral']};
            }}
        """)
        b.clicked.connect(slot)
        return b

    def go_today(self):
        now = datetime.now()
        self.cur_year, self.cur_month = now.year, now.month
        self.draw_calendar()

    def create_calendar_screen(self):
        screen = self._new_screen("calendarScreenBg")
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(self._make_header("📅", "カレンダー", self.colors["warn"], icon_file="calendar"))

        # 月ナビゲーション
        ctrl_f = self._panel("calCtrl", radius=14)
        ctrl_layout = QHBoxLayout(ctrl_f)
        ctrl_layout.setContentsMargins(12, 10, 12, 10)
        ctrl_layout.setSpacing(8)

        prev_btn = self._cal_nav_btn("‹", self.prev_month, width=42)
        next_btn = self._cal_nav_btn("›", self.next_month, width=42)
        today_btn = self._cal_nav_btn("今日", self.go_today)

        self.cal_label = QLabel()
        self.cal_label.setStyleSheet(f"""
            font-size: 17px;
            font-weight: 800;
            color: {self.colors['text_main']};
            border: none;
            padding-left: 6px;
        """)

        ctrl_layout.addWidget(prev_btn)
        ctrl_layout.addWidget(next_btn)
        ctrl_layout.addWidget(self.cal_label)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(today_btn)
        layout.addWidget(ctrl_f)

        # カレンダーグリッド（ノート風パネル）
        card, grid_content = self._notebook_panel("calCard", margin=False)
        grid_host = QWidget()
        self.calendar_grid_layout = QGridLayout(grid_host)
        self.calendar_grid_layout.setSpacing(7)
        self.calendar_grid_layout.setContentsMargins(6, 4, 6, 6)
        grid_content.addWidget(grid_host)
        layout.addWidget(card, stretch=1)

        self._add_shadow(ctrl_f, blur=20, dy=4, alpha=22)

        self.stacked_widget.addWidget(screen)
        self.screens["calendar"] = screen

    def draw_calendar(self):
        self.cal_label.setText(f"{self.cur_year}年 {self.cur_month}月")

        while self.calendar_grid_layout.count():
            child = self.calendar_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        days = ["月", "火", "水", "木", "金", "土", "日"]
        day_colors = [self.colors["text_sub"]] * 5 + [self.colors["primary"], self.colors["danger"]]
        for i, d in enumerate(days):
            lbl = QLabel(d)
            lbl.setMinimumHeight(34)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            lbl.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {day_colors[i]}; border: none;")
            lbl.setAlignment(Qt.AlignCenter)
            self.calendar_grid_layout.addWidget(lbl, 0, i)

        cal = calendar.monthcalendar(self.cur_year, self.cur_month)
        today = datetime.now()

        for r in range(1, 8):
            self.calendar_grid_layout.setRowStretch(r, 0)
        for c in range(7):
            self.calendar_grid_layout.setColumnStretch(c, 1)

        for r, week in enumerate(cal):
            self.calendar_grid_layout.setRowStretch(r + 1, 1)
            for c, day in enumerate(week):
                if day == 0:
                    continue
                key = f"{self.cur_year}-{self.cur_month}-{day}"
                is_today = (day == today.day and self.cur_month == today.month and self.cur_year == today.year)
                has_note = key in self.calendar_notes

                is_sat, is_sun = (c == 5), (c == 6)
                if has_note:
                    bg = self._rgba(self.colors["accent"], 0.09)
                    border = f"1px solid {self._rgba(self.colors['accent'], 0.5)}"
                elif is_sun:
                    bg, border = self._rgba(self.colors["danger"], 0.05), f"1px solid {self.colors['border']}"
                elif is_sat:
                    bg, border = self._rgba(self.colors["primary"], 0.05), f"1px solid {self.colors['border']}"
                else:
                    bg, border = self.colors["bg_base"], f"1px solid {self.colors['border']}"
                if is_today:
                    border = f"2px solid {self.colors['primary']}"

                cell = QPushButton()
                cell.setMinimumSize(46, 54)
                cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                cell.setCursor(QCursor(Qt.PointingHandCursor))
                cell.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        border: {border};
                        border-radius: 12px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        border: 2px solid {self.colors['primary']};
                        background-color: {self._rgba(self.colors['primary'], 0.07)};
                    }}
                """)
                cell.clicked.connect(lambda checked=False, d=day: self.open_day_memo(d))

                cl = QVBoxLayout(cell)
                cl.setContentsMargins(8, 6, 8, 6)
                cl.setSpacing(3)

                num = QLabel(str(day))
                num.setAlignment(Qt.AlignCenter)
                if is_today:
                    num.setFixedSize(24, 24)
                    num.setStyleSheet(f"color: #FFFFFF; background: {self.colors['primary']}; font-size: 12px; font-weight: 800; border: none; border-radius: 12px;")
                else:
                    num.setFixedHeight(20)
                    num.setStyleSheet(f"color: {self.colors['danger'] if is_sun else (self.colors['primary'] if is_sat else self.colors['text_main'])}; font-size: 13px; font-weight: 800; border: none; background: transparent; padding-left: 2px;")
                    num.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                cl.addWidget(num, alignment=Qt.AlignLeft | Qt.AlignTop)

                if has_note:
                    note_txt = self.calendar_notes[key]
                    if len(note_txt) > 46:
                        note_txt = note_txt[:45] + "…"
                    prev = QLabel(note_txt)
                    prev.setWordWrap(True)
                    prev.setMaximumHeight(50)
                    prev.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                    prev.setStyleSheet(f"color: {self.colors['accent']}; font-size: 10px; font-weight: 700; border: none; background: transparent;")
                    cl.addWidget(prev, stretch=1)
                else:
                    cl.addStretch()
                self.calendar_grid_layout.addWidget(cell, r + 1, c)

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

    def open_day_memo(self, day):
        # メモがあれば「閲覧」画面 → そこから編集/削除。無ければ直接「編集(追加)」画面。
        key = f"{self.cur_year}-{self.cur_month}-{day}"
        note = self.calendar_notes.get(key, "")
        title = f"{self.cur_year}年 {self.cur_month}月{day}日"

        if not note:
            self._edit_day_memo(day)
            return

        viewer = NoteViewDialog(title, note, accent=self.colors["warn"], parent=self)
        viewer.exec_()
        if viewer.action == "edit":
            self._edit_day_memo(day)
        elif viewer.action == "delete":
            if QMessageBox.question(self, "確認", "このメモを削除しますか？",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self.calendar_notes.pop(key, None)
                self.draw_calendar()

    def _edit_day_memo(self, day):
        key = f"{self.cur_year}-{self.cur_month}-{day}"
        old_val = self.calendar_notes.get(key, "")

        dialog = StyledInputDialog(
            f"{self.cur_year}年 {self.cur_month}月{day}日  ｜  メモを編集",
            "この日のメモ（空にすると削除）", old_val,
            multiline=True, accent=self.colors["warn"], parent=self,
        )
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
    icon_path = resource_path("icon.ico")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    window = MainWindowContainer()
    if os.path.exists(icon_path):
        window.setWindowIcon(app_icon)
    window.show()
    sys.exit(app.exec_())
