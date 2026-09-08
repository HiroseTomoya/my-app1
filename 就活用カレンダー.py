import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import Calendar
import json
from datetime import datetime
import queue

DATA_FILE = "job_calendar_data.json"

# ==========================================
# カラーパレット & デザイン定義
# ==========================================
COLOR_BG_LIGHT = "#F4F7F9"     # アプリ全体の背景
COLOR_BG_WHITE = "#FFFFFF"     # 各コンテンツの背景
COLOR_TEXT_MAIN = "#2D3748"    # メインの文字色

# タブごとのテーマカラー
COLOR_ES = "#2ECC71"           # ES管理：グリーン
COLOR_INTERVIEW = "#9B59B6"    # 面接管理：パープル
COLOR_EVENT = "#E67E22"        # イベント：オレンジ
COLOR_CALENDAR = "#2980B9"     # カレンダー：ブルー

# 特殊アクション用カラー（削除・修正など）
COLOR_DELETE = "#E74C3C"       # 削除：マイルドレッド
COLOR_EDIT = "#3498DB"         # 修正：スカイブルー

# ステータス・アラート用
COLOR_ALERT_RED = "#FF7675"    
COLOR_WARN_YELLOW = "#FFEAA7"  
COLOR_STATUS_WIP = "#DFF9FB"   
COLOR_STATUS_DONE = "#E2F0D9"  
COLOR_PAST_GRAY = "#DFE6E9"    


class JobCalendarApp:

    def __init__(self, root):
        self.root = root
        self.root.title("カラフル就活マネージャー ✨ (編集・削除機能つき)")
        self.root.geometry("1150x820")
        self.root.configure(bg=COLOR_BG_LIGHT)

        self.notify_queue = queue.Queue()

        # 編集中のデータのインデックスを保持する変数 (Noneの時は新規追加モード)
        self.editing_es_index = None
        self.editing_interview_index = None
        self.editing_event_index = None

        self.data = {
            "es": [],
            "interviews": [],
            "events": []
        }
        self.load_data()
        self.setup_styles()

        main_container = tk.Frame(root, bg=COLOR_BG_LIGHT, padx=15, pady=15)
        main_container.pack(fill="both", expand=True)

        title_lbl = tk.Label(
            main_container, 
            text=" 🚀 毎日の就活スケジュールをカラフルに管理！", 
            font=("Helvetica", 16, "bold"), 
            bg=COLOR_BG_LIGHT, 
            fg="#2C3E50"
        )
        title_lbl.pack(anchor="w", pady=(0, 12))

        self.notebook = ttk.Notebook(main_container, style="Colorful.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        self.es_frame = tk.Frame(self.notebook, bg=COLOR_BG_WHITE, padx=20, pady=20)
        self.interview_frame = tk.Frame(self.notebook, bg=COLOR_BG_WHITE, padx=20, pady=20)
        self.event_frame = tk.Frame(self.notebook, bg=COLOR_BG_WHITE, padx=20, pady=20)
        self.calendar_frame = tk.Frame(self.notebook, bg=COLOR_BG_WHITE, padx=20, pady=20)

        self.notebook.add(self.es_frame, text=" 📝 ESエントリー管理 ")
        self.notebook.add(self.interview_frame, text=" 🤝 面接選考スケジュール ")
        self.notebook.add(self.event_frame, text=" 🎉 説明会・イベント ")
        self.notebook.add(self.calendar_frame, text=" 📅 総合カレンダー ")

        self.create_es_tab()
        self.create_interview_tab()
        self.create_event_tab()
        self.create_calendar_tab()

        self.update_calendar_markers()
        self.check_notifications_loop()
        self.process_notify_queue()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Colorful.TNotebook", background=COLOR_BG_LIGHT, borderwidth=0)
        style.configure("Colorful.TNotebook.Tab", 
                        background="#DFE6E9", 
                        foreground="#636E72", 
                        font=("Helvetica", 11, "bold"), 
                        padding=[18, 8])
        
        style.map("Colorful.TNotebook.Tab", 
                  background=[("selected", COLOR_BG_WHITE)], 
                  foreground=[("selected", "#2980B9")])

        style.configure("Treeview", 
                        background=COLOR_BG_WHITE, 
                        foreground=COLOR_TEXT_MAIN, 
                        rowheight=30, 
                        fieldbackground=COLOR_BG_WHITE,
                        font=("Helvetica", 10))
        
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"), foreground="white")

        # 各種ボタンのスタイル設定
        style.configure("ES.TButton", background=COLOR_ES, foreground="white", font=("Helvetica", 10, "bold"), padding=[15, 6])
        style.map("ES.TButton", background=[("active", "#27AE60")])

        style.configure("Interview.TButton", background=COLOR_INTERVIEW, foreground="white", font=("Helvetica", 10, "bold"), padding=[15, 6])
        style.map("Interview.TButton", background=[("active", "#8E44AD")])

        style.configure("Event.TButton", background=COLOR_EVENT, foreground="white", font=("Helvetica", 10, "bold"), padding=[15, 6])
        style.map("Event.TButton", background=[("active", "#D35400")])

        # 汎用 編集・削除ボタンスタイル
        style.configure("Edit.TButton", background=COLOR_EDIT, foreground="white", font=("Helvetica", 9, "bold"), padding=[10, 4])
        style.map("Edit.TButton", background=[("active", "#2980B9")])
        style.configure("Delete.TButton", background=COLOR_DELETE, foreground="white", font=("Helvetica", 9, "bold"), padding=[10, 4])
        style.map("Delete.TButton", background=[("active", "#C0392B")])

    def create_section_header(self, parent, text, color):
        return tk.Label(parent, text=text, font=("Helvetica", 12, "bold"), fg=color, bg=COLOR_BG_WHITE)

    def create_colorful_input_row(self, parent, label_text, row, label_color, is_combobox=False, combo_values=None, width=30):
        lbl = tk.Label(parent, text=label_text, font=("Helvetica", 10, "bold"), bg=COLOR_BG_WHITE, fg=label_color)
        lbl.grid(row=row, column=0, sticky="w", pady=6, padx=(0, 15))
        
        if is_combobox:
            entry = ttk.Combobox(parent, values=combo_values, width=width-3, state="readonly")
        else:
            entry = tk.Entry(parent, width=width, font=("Helvetica", 10), bd=1, relief="solid")
            
        entry.grid(row=row, column=1, sticky="w", pady=6)
        return entry

    # ==========================================
    # 1. ES管理タブ（編集・削除対応）
    # ==========================================
    def create_es_tab(self):
        self.create_section_header(self.es_frame, "🔷 エントリーシート 新規登録 / 編集", COLOR_ES).pack(anchor="w", pady=(0, 10))

        input_frame = tk.Frame(self.es_frame, bg=COLOR_BG_WHITE)
        input_frame.pack(fill="x", anchor="n")

        self.es_company = self.create_colorful_input_row(input_frame, "🏢 企業名", 0, COLOR_TEXT_MAIN)
        self.es_deadline = self.create_colorful_input_row(input_frame, "📅 締切日 (YYYY-MM-DD)", 1, COLOR_TEXT_MAIN)
        self.es_status = self.create_colorful_input_row(input_frame, "💡 現在の状況", 2, COLOR_TEXT_MAIN, is_combobox=True, combo_values=["未着手", "作成中", "提出済"])
        self.es_priority = self.create_colorful_input_row(input_frame, "🔥 優先度", 3, COLOR_TEXT_MAIN, is_combobox=True, combo_values=["高", "中", "低"])

        self.es_status.current(0)
        self.es_priority.current(1)

        self.es_submit_btn = ttk.Button(input_frame, text="＋ このESを追加する", style="ES.TButton", command=self.add_es)
        self.es_submit_btn.grid(row=4, column=1, sticky="w", pady=15)

        # リスト表
        self.es_tree = ttk.Treeview(self.es_frame, columns=("company", "deadline", "status", "priority"), show="headings")
        self.es_tree.heading("company", text="🏢 企業名")
        self.es_tree.heading("deadline", text="📅 締切日")
        self.es_tree.heading("status", text="💡 状況")
        self.es_tree.heading("priority", text="🔥 優先度")
        
        self.es_tree.column("company", width=250, anchor="w")
        self.es_tree.column("deadline", width=150, anchor="center")
        self.es_tree.column("status", width=120, anchor="center")
        self.es_tree.column("priority", width=100, anchor="center")
        self.es_tree.pack(fill="both", expand=True, pady=(10, 5))

        self.es_tree.tag_configure("past", background=COLOR_PAST_GRAY, foreground="#7F8C8D")
        self.es_tree.tag_configure("today", background=COLOR_ALERT_RED, foreground="white")
        self.es_tree.tag_configure("warn", background=COLOR_WARN_YELLOW, foreground=COLOR_TEXT_MAIN)
        self.es_tree.tag_configure("wip", background=COLOR_STATUS_WIP, foreground=COLOR_TEXT_MAIN)
        self.es_tree.tag_configure("submitted", background=COLOR_STATUS_DONE, foreground="#27AE60")

        # 操作用ボタン用フレーム（表のすぐ下）
        action_frame = tk.Frame(self.es_frame, bg=COLOR_BG_WHITE)
        action_frame.pack(anchor="e", pady=5)
        ttk.Button(action_frame, text="✏️ 選択したESを修正", style="Edit.TButton", command=self.load_es_to_form).pack(side="left", padx=5)
        ttk.Button(action_frame, text="🗑️ 選択したESを削除", style="Delete.TButton", command=self.delete_es).pack(side="left", padx=5)

        self.refresh_es()

    def add_es(self):
        if not self.es_company.get() or not self.es_deadline.get():
            messagebox.showwarning("入力エラー", "企業名と締切日は必須項目です。")
            return
        
        item = {
            "company": self.es_company.get(),
            "deadline": self.es_deadline.get(),
            "status": self.es_status.get(),
            "priority": self.es_priority.get()
        }

        if self.editing_es_index is not None:
            # 修正モード時の上書き
            self.data["es"][self.editing_es_index] = item
            self.editing_es_index = None
            self.es_submit_btn.configure(text="＋ このESを追加する")
        else:
            # 通常の新規追加
            self.data["es"].append(item)

        self.save_data()
        self.refresh_es()
        self.update_calendar_markers()
        
        # フォーム初期化
        self.es_company.delete(0, tk.END)
        self.es_deadline.delete(0, tk.END)

    def load_es_to_form(self):
        selected = self.es_tree.selection()
        if not selected:
            messagebox.showwarning("選択エラー", "修正したい行を選んでください。")
            return
        
        # 選択されたインデックスの特定
        index = self.es_tree.index(selected[0])
        self.editing_es_index = index
        item = self.data["es"][index]

        # フォームに流し込む
        self.es_company.delete(0, tk.END)
        self.es_company.insert(0, item["company"])
        self.es_deadline.delete(0, tk.END)
        self.es_deadline.insert(0, item["deadline"])
        
        self.es_status.set(item["status"])
        self.es_priority.set(item["priority"])

        self.es_submit_btn.configure(text="💾 変更を保存（上書き）")

    def delete_es(self):
        selected = self.es_tree.selection()
        if not selected:
            messagebox.showwarning("選択エラー", "削除したい行を選んでください。")
            return
        
        if messagebox.askyesno("確認", "選択したESデータを削除してもよろしいですか？"):
            index = self.es_tree.index(selected[0])
            self.data["es"].pop(index)
            self.save_data()
            self.refresh_es()
            self.update_calendar_markers()
            
            # 編集中のデータを消された場合の安全策
            self.editing_es_index = None
            self.es_submit_btn.configure(text="＋ このESを追加する")

    def refresh_es(self):
        for row in self.es_tree.get_children():
            self.es_tree.delete(row)

        today = datetime.now().date()
        for es in self.data["es"]:
            tag = ""
            if es["status"] == "提出済":
                tag = "submitted"
            elif es["status"] == "作成中":
                tag = "wip"
            else:
                try:
                    deadline_date = datetime.strptime(es["deadline"], "%Y-%m-%d").date()
                    diff = (deadline_date - today).days
                    if diff < 0:
                        tag = "past"
                    elif diff == 0:
                        tag = "today"
                    elif diff <= 3:
                        tag = "warn"
                except ValueError:
                    pass

            self.es_tree.insert("", tk.END, values=(
                es['company'], es['deadline'], es['status'], es['priority']
            ), tags=(tag,))

    # ==========================================
    # 2. 面接管理タブ（編集・削除対応）
    # ==========================================
    def create_interview_tab(self):
        self.create_section_header(self.interview_frame, "🔷 選考・面接予定の新規登録 / 編集", COLOR_INTERVIEW).pack(anchor="w", pady=(0, 10))

        input_frame = tk.Frame(self.interview_frame, bg=COLOR_BG_WHITE)
        input_frame.pack(fill="x", anchor="n")

        self.int_company = self.create_colorful_input_row(input_frame, "🏢 企業名", 0, COLOR_TEXT_MAIN)
        self.int_datetime = self.create_colorful_input_row(input_frame, "⏰ 日時 (YYYY-MM-DD HH:MM)", 1, COLOR_TEXT_MAIN)
        self.int_type = self.create_colorful_input_row(input_frame, "🔍 面接種類 (1次面接、最終など)", 2, COLOR_TEXT_MAIN)
        self.int_place = self.create_colorful_input_row(input_frame, "📍 会場 / 実施方法", 3, COLOR_TEXT_MAIN)
        self.int_url = self.create_colorful_input_row(input_frame, "🌐 オンラインURL (Zoom等)", 4, COLOR_TEXT_MAIN, width=50)

        self.int_submit_btn = ttk.Button(input_frame, text="＋ 面接スケジュールを追加", style="Interview.TButton", command=self.add_interview)
        self.int_submit_btn.grid(row=5, column=1, sticky="w", pady=15)

        self.interview_tree = ttk.Treeview(self.interview_frame, columns=("company", "datetime", "type", "place", "url"), show="headings")
        self.interview_tree.heading("company", text="🏢 企業名")
        self.interview_tree.heading("datetime", text="⏰ 日時")
        self.interview_tree.heading("type", text="🔍 種類")
        self.interview_tree.heading("place", text="📍 場所/形式")
        self.interview_tree.heading("url", text="🌐 リンクURL")

        self.interview_tree.column("company", width=180, anchor="w")
        self.interview_tree.column("datetime", width=150, anchor="center")
        self.interview_tree.column("type", width=100, anchor="center")
        self.interview_tree.column("place", width=150, anchor="w")
        self.interview_tree.column("url", width=250, anchor="w")
        self.interview_tree.pack(fill="both", expand=True, pady=(10, 5))

        self.interview_tree.tag_configure("interview_row", background="#F5EEF8")

        action_frame = tk.Frame(self.interview_frame, bg=COLOR_BG_WHITE)
        action_frame.pack(anchor="e", pady=5)
        ttk.Button(action_frame, text="✏️ 選択した面接を修正", style="Edit.TButton", command=self.load_interview_to_form).pack(side="left", padx=5)
        ttk.Button(action_frame, text="🗑️ 選択した面接を削除", style="Delete.TButton", command=self.delete_interview).pack(side="left", padx=5)

        self.refresh_interviews()

    def add_interview(self):
        if not self.int_company.get() or not self.int_datetime.get():
            messagebox.showwarning("入力エラー", "企業名と選考日時は必須項目です。")
            return
        item = {
            "company": self.int_company.get(),
            "datetime": self.int_datetime.get(),
            "type": self.int_type.get(),
            "place": self.int_place.get(),
            "url": self.int_url.get()
        }

        if self.editing_interview_index is not None:
            self.data["interviews"][self.editing_interview_index] = item
            self.editing_interview_index = None
            self.int_submit_btn.configure(text="＋ 面接スケジュールを追加")
        else:
            self.data["interviews"].append(item)

        self.save_data()
        self.refresh_interviews()
        self.update_calendar_markers()

        for entry in [self.int_company, self.int_datetime, self.int_type, self.int_place, self.int_url]:
            entry.delete(0, tk.END)

    def load_interview_to_form(self):
        selected = self.interview_tree.selection()
        if not selected:
            messagebox.showwarning("選択エラー", "修正したい行を選んでください。")
            return
        
        index = self.interview_tree.index(selected[0])
        self.editing_interview_index = index
        item = self.data["interviews"][index]

        for entry, key in [(self.int_company, "company"), (self.int_datetime, "datetime"), 
                           (self.int_type, "type"), (self.int_place, "place"), (self.int_url, "url")]:
            entry.delete(0, tk.END)
            entry.insert(0, item.get(key, ""))

        self.int_submit_btn.configure(text="💾 変更を保存（上書き）")

    def delete_interview(self):
        selected = self.interview_tree.selection()
        if not selected:
            messagebox.showwarning("選択エラー", "削除したい行を選んでください。")
            return
        
        if messagebox.askyesno("確認", "選択した面接予定を削除してもよろしいですか？"):
            index = self.interview_tree.index(selected[0])
            self.data["interviews"].pop(index)
            self.save_data()
            self.refresh_interviews()
            self.update_calendar_markers()
            
            self.editing_interview_index = None
            self.int_submit_btn.configure(text="＋ 面接スケジュールを追加")

    def refresh_interviews(self):
        for row in self.interview_tree.get_children():
            self.interview_tree.delete(row)
        for i in self.data["interviews"]:
            self.interview_tree.insert("", tk.END, values=(
                i['company'], i['datetime'], i['type'], i['place'], i['url']
            ), tags=("interview_row",))


    # ==========================================
    # 3. イベント選考タブ（編集・削除対応）
    # ==========================================
    def create_event_tab(self):
        self.create_section_header(self.event_frame, "🔷 インターン・合同説明会等の登録 / 編集", COLOR_EVENT).pack(anchor="w", pady=(0, 10))

        input_frame = tk.Frame(self.event_frame, bg=COLOR_BG_WHITE)
        input_frame.pack(fill="x", anchor="n")

        self.event_name = self.create_colorful_input_row(input_frame, "📢 イベント名称", 0, COLOR_TEXT_MAIN)
        self.event_date = self.create_colorful_input_row(input_frame, "📅 開催日程 (YYYY-MM-DD)", 1, COLOR_TEXT_MAIN)

        self.event_submit_btn = ttk.Button(input_frame, text="＋ イベントをリストに追加", style="Event.TButton", command=self.add_event)
        self.event_submit_btn.grid(row=2, column=1, sticky="w", pady=15)

        self.event_tree = ttk.Treeview(self.event_frame, columns=("date", "name"), show="headings")
        self.event_tree.heading("date", text="📅 開催日")
        self.event_tree.heading("name", text="📢 イベント名")
        
        self.event_tree.column("date", width=150, anchor="center")
        self.event_tree.column("name", width=500, anchor="w")
        self.event_tree.pack(fill="both", expand=True, pady=(10, 5))

        self.event_tree.tag_configure("event_row", background="#FDF2E9")

        action_frame = tk.Frame(self.event_frame, bg=COLOR_BG_WHITE)
        action_frame.pack(anchor="e", pady=5)
        ttk.Button(action_frame, text="✏️ 選択したイベントを修正", style="Edit.TButton", command=self.load_event_to_form).pack(side="left", padx=5)
        ttk.Button(action_frame, text="🗑️ 選択したイベントを削除", style="Delete.TButton", command=self.delete_event).pack(side="left", padx=5)

        self.refresh_events()

    def add_event(self):
        if not self.event_name.get() or not self.event_date.get():
            messagebox.showwarning("入力エラー", "イベント名と日程は必須項目です。")
            return
        item = {"name": self.event_name.get(), "date": self.event_date.get()}

        if self.editing_event_index is not None:
            self.data["events"][self.editing_event_index] = item
            self.editing_event_index = None
            self.event_submit_btn.configure(text="＋ イベントをリストに追加")
        else:
            self.data["events"].append(item)

        self.save_data()
        self.refresh_events()
        self.update_calendar_markers()
        self.event_name.delete(0, tk.END)
        self.event_date.delete(0, tk.END)

    def load_event_to_form(self):
        selected = self.event_tree.selection()
        if not selected:
            messagebox.showwarning("選択エラー", "修正したい行を選んでください。")
            return
        
        index = self.event_tree.index(selected[0])
        self.editing_event_index = index
        item = self.data["events"][index]

        self.event_name.delete(0, tk.END)
        self.event_name.insert(0, item["name"])
        self.event_date.delete(0, tk.END)
        self.event_date.insert(0, item["date"])

        self.event_submit_btn.configure(text="💾 変更を保存（上書き）")

    def delete_event(self):
        selected = self.event_tree.selection()
        if not selected:
            messagebox.showwarning("選択エラー", "削除したい行を選んでください。")
            return
        
        if messagebox.askyesno("確認", "選択したイベントを削除してもよろしいですか？"):
            index = self.event_tree.index(selected[0])
            self.data["events"].pop(index)
            self.save_data()
            self.refresh_events()
            self.update_calendar_markers()
            
            self.editing_event_index = None
            self.event_submit_btn.configure(text="＋ イベントをリストに追加")

    def refresh_events(self):
        for row in self.event_tree.get_children():
            self.event_tree.delete(row)
        for e in self.data["events"]:
            self.event_tree.insert("", tk.END, values=(e['date'], e['name']), tags=("event_row",))


    # ==========================================
    # 4. カレンダータブ（共通）
    # ==========================================
    def create_calendar_tab(self):
        self.create_section_header(self.calendar_frame, "🔷 スケジュール視覚確認カレンダー", COLOR_CALENDAR).pack(anchor="w")
        
        guide_frame = tk.Frame(self.calendar_frame, bg=COLOR_BG_WHITE)
        guide_frame.pack(anchor="w", pady=5)
        
        tk.Label(guide_frame, text="■ ES締切日", fg=COLOR_ALERT_RED, bg=COLOR_BG_WHITE, font=("Helvetica", 9, "bold")).pack(side="left", padx=5)
        tk.Label(guide_frame, text="■ 面接選考日", fg=COLOR_INTERVIEW, bg=COLOR_BG_WHITE, font=("Helvetica", 9, "bold")).pack(side="left", padx=5)
        tk.Label(guide_frame, text="■ その他イベント", fg=COLOR_EVENT, bg=COLOR_BG_WHITE, font=("Helvetica", 9, "bold")).pack(side="left", padx=5)

        self.calendar = Calendar(
            self.calendar_frame,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            background=COLOR_CALENDAR,
            foreground="white",
            headersbackground="#1B4F72",
            headersforeground="white",
            selectbackground="#239B56",
            selectforeground="white",
            normalbackground=COLOR_BG_WHITE,
            normalforeground=COLOR_TEXT_MAIN,
            weekendbackground="#EBF5FB",
            weekendforeground=COLOR_CALENDAR
        )
        self.calendar.pack(pady=10, fill="both", expand=True)

    def update_calendar_markers(self):
        self.calendar.calevent_remove("all")
        
        # 1. ES締切
        for es in self.data.get("es", []):
            try:
                date_obj = datetime.strptime(es["deadline"], "%Y-%m-%d").date()
                if es["status"] != "提出済":
                    self.calendar.calevent_create(date_obj, f"ES: {es['company']}", "es_deadline")
            except ValueError:
                pass
                
        # 2. 面接
        for i in self.data.get("interviews", []):
            try:
                date_str = i["datetime"].split(" ")[0]
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                self.calendar.calevent_create(date_obj, f"面接: {i['company']}", "interview")
            except (ValueError, IndexError):
                pass

        # 3. イベント
        for e in self.data.get("events", []):
            try:
                date_obj = datetime.strptime(e["date"], "%Y-%m-%d").date()
                self.calendar.calevent_create(date_obj, e["name"], "event")
            except ValueError:
                pass

        self.calendar.tag_config("es_deadline", background=COLOR_ALERT_RED, foreground="white")
        self.calendar.tag_config("interview", background=COLOR_INTERVIEW, foreground="white")
        self.calendar.tag_config("event", background=COLOR_EVENT, foreground="white")


    # ==========================================
    # 通知・ファイルシステム（変更なし）
    # ==========================================
    def check_notifications_loop(self):
        today = datetime.now().date()
        for es in self.data.get("es", []):
            if es["status"] == "提出済":
                continue
            try:
                deadline = datetime.strptime(es["deadline"], "%Y-%m-%d").date()
                diff = (deadline - today).days
                if diff == 1:
                    self.notify_queue.put(f"🚨 【明日締切のESがあります！】\n企業名: {es['company']}")
                elif diff == 3:
                    self.notify_queue.put(f"⏳ 【ES締切3日前】\n企業名: {es['company']}\nそろそろ仕上げにかかりましょう！")
            except ValueError:
                pass
        self.root.after(3600000, self.check_notifications_loop)

    def process_notify_queue(self):
        try:
            while True:
                message = self.notify_queue.get_nowait()
                messagebox.showinfo("就活アラート 📢", message)
        except queue.Empty:
            pass
        self.root.after(1000, self.process_notify_queue)

    def save_data(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def load_data(self):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = JobCalendarApp(root)
    root.mainloop()