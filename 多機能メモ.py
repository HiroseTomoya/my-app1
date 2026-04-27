import tkinter as tk
from tkinter import messagebox
import time
import threading
import winsound
import calendar
import hashlib
import json
import os
from datetime import datetime

class MultiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("多機能メモツール ")
        self.root.geometry("700x850")

        self.DATA_FILE = "memo_pro_data.json"
        self.VAULT_FILE = "vault_pro_data.json"

        self.init_style()
        self.load_all_data()

        self.container = tk.Frame(root, bg=self.colors["bg_base"])
        self.container.pack(fill="both", expand=True)

        self.show_selector()

    def init_style(self):
        self.colors = {
            "bg_base": "#FFFFFF",      
            "card_bg": "#F5F5F5",      
            "primary": "#0047AB",      
            "accent": "#00A86B",      
            "success": "#2E8B57",      
            "danger": "#DC143C",       
            "neutral": "#757575",      
            "text_main": "#212121",    
            "text_sub": "#616161",     
            "tab_active": "#0047AB",   
            "tab_inactive": "#061310" 
        }
        self.FONT_MAIN = ("Segoe UI", 11)
        self.FONT_TITLE = ("Segoe UI", 32, "bold")
        self.FONT_BUTTON = ("Segoe UI", 12, "bold")
        self.FONT_TAB = ("Segoe UI", 10, "bold")
        self.FONT_CAL = ("Segoe UI", 10, "bold")

    # --- データ管理 ---
    
    def load_all_data(self):
        if os.path.exists(self.DATA_FILE):
            with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                self.todo_items = d.get("todo", [])
                self.memo_data = d.get("memo", {"メイン": ""})
                self.calendar_notes = d.get("calendar", {})
        else:
            self.todo_items, self.memo_data, self.calendar_notes = [], {"メイン": ""}, {}

        if os.path.exists(self.VAULT_FILE):
            with open(self.VAULT_FILE, "r", encoding="utf-8") as f:
                v = json.load(f)
                self.master_hash = v.get("hash")
                self.birth_hash = v.get("birth_hash")
                self.vault_items = v.get("items", [])
        else:
            self.master_hash, self.birth_hash, self.vault_items = None, None, []

        self.current_memo_folder = list(self.memo_data.keys())[0]
        self.is_authenticated = False
        self.timer_running = False
        self.remaining_seconds = 0
        self.cur_year, self.cur_month = datetime.now().year, datetime.now().month
        self.sounds = {"📢 警告音": "SystemHand", "🎵 標準音": "SystemAsterisk"}

    def save_all_data(self):
        data = {"todo": self.todo_items, "memo": self.memo_data, "calendar": self.calendar_notes}
        with open(self.DATA_FILE, "w", encoding="utf-8") as f: 
            json.dump(data, f, ensure_ascii=False, indent=4)
        vault = {"hash": self.master_hash, "birth_hash": self.birth_hash, "items": self.vault_items}
        with open(self.VAULT_FILE, "w", encoding="utf-8") as f: 
            json.dump(vault, f, ensure_ascii=False, indent=4)

    # --- 共通UI ---
    
    def styled_button(self, parent, text, command, color, width=None, pady=12):
        btn = tk.Label(parent, text=text, bg=color, fg="white", font=self.FONT_BUTTON, padx=20, pady=pady, cursor="hand2", bd=0, width=width)
        btn.bind("<Enter>", lambda e: btn.config(bg=self.lighten(color)))
        btn.bind("<Leave>", lambda e: btn.config(bg=color))
        btn.bind("<Button-1>", lambda e: command())
        return btn

    def lighten(self, color):
        ov = {
            "#0047AB": "#1E90FF", 
            "#00A86B": "#3CB371", 
            "#2E8B57": "#3CB371", 
            "#DC143C": "#FF4500", 
            "#757575": "#9E9E9E", 
            "#E0E0E0": "#F5F5F5"  
        }
        return ov.get(color, color)

    def clear_frame(self):
        self.save_all_data()
        for w in self.container.winfo_children(): w.destroy()

    def create_styled_input_dialog(self, title, prompt, initialvalue="", show=""):
        dialog = tk.Toplevel(self.root); dialog.title(title); dialog.geometry("400x250"); dialog.configure(bg=self.colors["bg_base"]); dialog.transient(self.root); dialog.grab_set()
        res = {"value": None}; main_f = tk.Frame(dialog, bg=self.colors["card_bg"], padx=20, pady=20); main_f.pack(expand=True, fill="both", padx=15, pady=15)
        tk.Label(main_f, text=prompt, font=self.FONT_MAIN, bg=self.colors["card_bg"], fg=self.colors["text_main"]).pack(pady=10)
        entry = tk.Entry(main_f, font=self.FONT_MAIN, width=25, bg="white", fg=self.colors["text_main"], insertbackground="black", borderwidth=0, highlightthickness=1, highlightbackground=self.colors["neutral"], show=show)
        entry.insert(0, initialvalue); entry.pack(pady=10, ipady=5); entry.focus_force()
        def ok(e=None): res["value"] = entry.get(); dialog.destroy()
        self.styled_button(main_f, "決定", ok, self.colors["primary"]).pack(pady=10)
        dialog.bind("<Return>", ok); self.root.wait_window(dialog)
        return res["value"]

    def show_selector(self):
        self.clear_frame()
        tk.Label(self.container, text="多機能メモツール", font=self.FONT_TITLE, bg=self.colors["bg_base"], fg=self.colors["primary"]).pack(pady=60)
        menu = tk.Frame(self.container, bg=self.colors["bg_base"]); menu.pack()
        opts = [("⏲ タイマー", self.show_timer, self.colors["primary"]), ("📝 TO DO リスト", self.show_todo, self.colors["accent"]), ("📄 メモ", self.show_memo, self.colors["success"]), ("📅 カレンダー", self.show_calendar, self.colors["neutral"]), ("🔒 セキュリティ強化メモ", self.show_vault, self.colors["danger"])]
        for t, c, col in opts: self.styled_button(menu, t, c, col, width=25).pack(pady=10)

    # --- タイマー ---
    
    def show_timer(self):
        self.clear_frame()
        self.styled_button(self.container, "戻る", self.show_selector, self.colors["tab_inactive"]).pack(anchor="w", padx=20, pady=20)
        self.timer_display = tk.Label(self.container, text="00:00", font=("Consolas", 80, "bold"), bg=self.colors["bg_base"], fg=self.colors["text_main"])
        self.timer_display.pack(pady=40)
        in_f = tk.Frame(self.container, bg=self.colors["bg_base"]); in_f.pack()
        self.e_min = tk.Entry(in_f, width=3, font=("Consolas", 24), bg="white", fg=self.colors["text_main"], justify="center", bd=0, highlightthickness=1, highlightbackground=self.colors["primary"]); self.e_min.insert(0, "0"); self.e_min.pack(side="left", padx=5)
        self.e_sec = tk.Entry(in_f, width=3, font=("Consolas", 24), bg="white", fg=self.colors["text_main"], justify="center", bd=0, highlightthickness=1, highlightbackground=self.colors["primary"]); self.e_sec.insert(0, "00"); self.e_sec.pack(side="left", padx=5)
        sound_f = tk.Frame(self.container, bg=self.colors["bg_base"]); sound_f.pack(pady=25)
        self.sound_var = tk.StringVar(value="📢 警告音")
        opt = tk.OptionMenu(sound_f, self.sound_var, *self.sounds.keys())
        opt.config(font=self.FONT_MAIN, bg=self.colors["primary"], fg="white", highlightthickness=0, bd=0, width=12)
        opt["menu"].config(bg="white", fg=self.colors["text_main"])
        opt.pack(side="left", padx=10)
        self.styled_button(sound_f, "♪ 試聴", self.preview_sound, self.colors["neutral"], pady=5).pack(side="left")
        btns = tk.Frame(self.container, bg=self.colors["bg_base"]); btns.pack(pady=20)
        self.styled_button(btns, "スタート", self.start_timer, self.colors["primary"]).pack(side="left", padx=10)
        self.styled_button(btns, "ストップ", self.stop_timer, self.colors["danger"]).pack(side="left", padx=10)
        self.styled_button(btns, "リセット", self.reset_timer, self.colors["neutral"]).pack(side="left", padx=10)

    def preview_sound(self):
        s_target = self.sounds[self.sound_var.get()]
        winsound.PlaySound(s_target, winsound.SND_ALIAS | winsound.SND_ASYNC)

    def start_timer(self):
        if self.timer_running: return
        try:
            self.remaining_seconds = int(self.e_min.get()) * 60 + int(self.e_sec.get())
            if self.remaining_seconds <= 0: return
            self.timer_running = True
            threading.Thread(target=self.run_timer_loop, daemon=True).start()
        except: pass

    def run_timer_loop(self):
        while self.remaining_seconds > 0 and self.timer_running:
            time.sleep(1); self.remaining_seconds -= 1
            self.root.after(0, lambda: self.timer_display.config(text=f"{self.remaining_seconds//60:02d}:{self.remaining_seconds%60:02d}"))
        if self.remaining_seconds == 0 and self.timer_running:
            self.timer_running = False
            s_target = self.sounds[self.sound_var.get()]
            winsound.PlaySound(s_target, winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_LOOP)
            messagebox.showinfo("Time Up", "時間になりました！")
            winsound.PlaySound(None, winsound.SND_PURGE)

    def stop_timer(self): 
        self.timer_running = False
        winsound.PlaySound(None, winsound.SND_PURGE)

    def reset_timer(self):
        self.stop_timer()
        self.remaining_seconds = 0
        self.timer_display.config(text="00:00")
        self.e_min.delete(0, tk.END); self.e_min.insert(0, "0")
        self.e_sec.delete(0, tk.END); self.e_sec.insert(0, "00")

    # --- メモ帳 ---
    
    def show_memo(self):
        self.clear_frame()
        self.styled_button(self.container, "戻る", self.show_selector, self.colors["tab_inactive"]).pack(anchor="w", padx=20, pady=10)
        top_bar = tk.Frame(self.container, bg=self.colors["bg_base"]); top_bar.pack(fill="x", padx=20)
        tk.Label(top_bar, text="右クリック: フォルダを削除", font=("Segoe UI", 9), bg=self.colors["bg_base"], fg=self.colors["text_sub"]).pack(side="left")
        self.styled_button(top_bar, "新しいフォルダを作成", self.add_folder, self.colors["accent"], pady=5).pack(side="right")
        self.tab_container = tk.Frame(self.container, bg=self.colors["bg_base"]); self.tab_container.pack(fill="x", padx=20)
        self.draw_tabs()
        self.memo_text = tk.Text(self.container, font=("Segoe UI", 12), bg="white", fg=self.colors["text_main"], padx=20, pady=20, relief="flat", insertbackground="black", undo=True, highlightthickness=1, highlightbackground=self.colors["primary"])
        self.memo_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.memo_text.insert(1.0, self.memo_data.get(self.current_memo_folder, "")); self.memo_text.bind("<KeyRelease>", self.save_memo_on_key)

    def draw_tabs(self):
        for w in self.tab_container.winfo_children(): w.destroy()
        for name in self.memo_data.keys():
            is_active = (name == self.current_memo_folder); 
            bg = self.colors["tab_active"] if is_active else self.colors["tab_inactive"]
            fg = "white" if is_active else self.colors["text_main"]
            lbl = tk.Label(self.tab_container, text=name.upper(), font=self.FONT_TAB, bg=bg, fg=fg, padx=15, pady=8, cursor="hand2")
            lbl.pack(side="left", padx=2, pady=(5, 0)); lbl.bind("<Button-1>", lambda e, n=name: self.change_folder(n)); lbl.bind("<Button-3>", lambda e, n=name: self.delete_folder(n))

    def change_folder(self, name):
        self.save_memo_content(); self.current_memo_folder = name; self.memo_text.delete(1.0, tk.END); self.memo_text.insert(1.0, self.memo_data.get(name, "")); self.draw_tabs()

    def add_folder(self):
        res = self.create_styled_input_dialog("新しいフォルダ", "フォルダ名を入力")
        if res and res not in self.memo_data: self.memo_data[res] = ""; self.change_folder(res)

    def delete_folder(self, name):
        if len(self.memo_data) <= 1: messagebox.showwarning("警告", "既存のメインフォルダは削除できません"); return
        if messagebox.askyesno("Confirm", f"フォルダ「{name}」を削除しますか？"):
            del self.memo_data[name]
            if self.current_memo_folder == name: self.current_memo_folder = list(self.memo_data.keys())[0]
            self.change_folder(self.current_memo_folder)

    def save_memo_on_key(self, e): self.save_memo_content(); self.save_all_data()
    def save_memo_content(self):
        if self.current_memo_folder in self.memo_data: self.memo_data[self.current_memo_folder] = self.memo_text.get(1.0, "end-1c")

    # --- セキュリティ強化メモ ---
    
    def show_vault(self):
        if self.is_authenticated:
            self.clear_frame()
            self.styled_button(self.container, "ログアウト & 戻る", self.vault_logout, self.colors["tab_inactive"]).pack(anchor="w", padx=20, pady=10)
            
            f_card = tk.Frame(self.container, bg=self.colors["card_bg"], padx=20, pady=20); f_card.pack(fill="both", expand=True, padx=20, pady=10)
            # アクセントカラーのグリーンを使用
            self.styled_button(f_card, "+ メモを追加", self.add_vault_item, self.colors["accent"]).pack(pady=10)
            self.vault_list = tk.Frame(f_card, bg=self.colors["card_bg"]); self.vault_list.pack(fill="both", expand=True); self.refresh_vault()
            return

        if not self.master_hash:
            self.setup_vault_first_time()
            return

        if self.birth_hash is None:
            b1 = self.create_styled_input_dialog("初期設定", "リセット用の生年月日を登録してください\n(8桁: 19950510等)")
            if b1 and len(b1) == 8 and b1.isdigit():
                self.birth_hash = hashlib.sha256(b1.encode()).hexdigest()
                self.save_all_data()
                messagebox.showinfo("成功", "生年月日を登録しました。")
                self.show_vault_auth_screen()
            else:
                messagebox.showwarning("警告", "正しい形式(8桁の数字)で入力してください。")
                self.show_selector()
            return

        self.show_vault_auth_screen()

    def setup_vault_first_time(self):
        p1 = self.create_styled_input_dialog("設定", "新しいパスワード", show="*")
        if not p1: self.show_selector(); return
        b1 = self.create_styled_input_dialog("設定", "生年月日 (8桁: 19950510等)")
        if b1 and len(b1) == 8 and b1.isdigit():
            self.master_hash = hashlib.sha256(p1.encode()).hexdigest()
            self.birth_hash = hashlib.sha256(b1.encode()).hexdigest()
            self.save_all_data()
            messagebox.showinfo("成功", "初期設定が完了しました。")
            self.show_vault()
        else:
            messagebox.showerror("エラー", "生年月日は8桁の数字で入力してください。")
            self.show_selector()

    def show_vault_auth_screen(self):
        self.clear_frame()
        self.styled_button(self.container, "戻る", self.show_selector, self.colors["tab_inactive"]).pack(anchor="w", padx=20, pady=10)
        auth_f = tk.Frame(self.container, bg=self.colors["card_bg"], padx=40, pady=40)
        auth_f.pack(pady=100)
        tk.Label(auth_f, text="パスワードを入力してください", font=self.FONT_BUTTON, bg=self.colors["card_bg"], fg=self.colors["text_main"]).pack(pady=10)
        pw_entry = tk.Entry(auth_f, font=self.FONT_MAIN, show="*", bg="white", fg=self.colors["text_main"], insertbackground="black", borderwidth=0, highlightthickness=1, highlightbackground=self.colors["primary"])
        pw_entry.pack(pady=15, ipady=5); pw_entry.focus_force()
        
        def check_pw(e=None):
            h = hashlib.sha256(pw_entry.get().encode()).hexdigest()
            if h == self.master_hash:
                self.is_authenticated = True
                self.show_vault()
            else:
                messagebox.showerror("エラー", "パスワードが違います")
        self.styled_button(auth_f, "ログイン", check_pw, self.colors["primary"], width=15).pack(pady=5)
        reset_btn = tk.Label(auth_f, text="パスワードを忘れた場合はこちら (生年月日でリセット)", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text_sub"], cursor="hand2")
        reset_btn.pack(pady=20)
        reset_btn.bind("<Button-1>", lambda e: self.reset_vault_password())
        self.root.bind("<Return>", check_pw)

    def reset_vault_password(self):
        b_input = self.create_styled_input_dialog("リセット", "登録した生年月日(8桁)を入力")
        if not b_input: return
        if hashlib.sha256(b_input.encode()).hexdigest() == self.birth_hash:
            new_p = self.create_styled_input_dialog("リセット", "新しいパスワードを再設定", show="*")
            if new_p:
                self.master_hash = hashlib.sha256(new_p.encode()).hexdigest()
                self.save_all_data()
                messagebox.showinfo("成功", "パスワードを更新しました。")
                self.is_authenticated = False
                self.show_vault()
        else:
            messagebox.showerror("エラー", "生年月日が一致しません")

    def vault_logout(self): self.is_authenticated = False; self.show_selector()
    def add_vault_item(self):
        t = self.create_styled_input_dialog("新規", "項目名")
        if t: s = self.create_styled_input_dialog("新規", "メモを入力"); self.vault_items.append({"title": t, "pass": s, "show": False}); self.refresh_vault()

    def refresh_vault(self):
        for w in self.vault_list.winfo_children(): w.destroy()
        for i, item in enumerate(self.vault_items):
            f = tk.Frame(self.vault_list, bg="white", pady=10); f.pack(fill="x", pady=2)
            tk.Label(f, text=f"  {item['title']}", bg="white", fg=self.colors["text_main"], width=15, anchor="w").pack(side="left", padx=10)
            p_disp = item["pass"] if item.get("show") else "********"
            tk.Label(f, text=p_disp, fg=self.colors["text_sub"], bg="white", width=20, font=("Consolas", 11)).pack(side="left")
            btn_f = tk.Frame(f, bg="white"); btn_f.pack(side="right", padx=10)
            v_btn = tk.Label(btn_f, text="表示", fg=self.colors["primary"], bg="white", cursor="hand2", font=("Segoe UI", 9, "bold")); v_btn.pack(side="left", padx=5); v_btn.bind("<Button-1>", lambda e, idx=i: [self.vault_items[idx].update({"show": not self.vault_items[idx]["show"]}), self.refresh_vault()])
            del_btn = tk.Label(btn_f, text="削除", fg=self.colors["danger"], bg="white", cursor="hand2", font=("Segoe UI", 9, "bold")); del_btn.pack(side="left", padx=5); del_btn.bind("<Button-1>", lambda e, idx=i: [self.vault_items.pop(idx), self.refresh_vault()])

    # --- ToDo リスト ---
    
    def show_todo(self):
        self.clear_frame()
        self.styled_button(self.container, "戻る", self.show_selector, self.colors["tab_inactive"]).pack(anchor="w", padx=20, pady=20)
        f_card = tk.Frame(self.container, bg=self.colors["card_bg"], padx=20, pady=20); f_card.pack(fill="both", expand=True, padx=20, pady=10)
        self.styled_button(f_card, "+ タスクを追加", self.add_todo_item, self.colors["accent"]).pack(pady=10)
        self.todo_list_frame = tk.Frame(f_card, bg=self.colors["card_bg"]); self.todo_list_frame.pack(fill="both", expand=True); self.refresh_todo()

    def add_todo_item(self):
        res = self.create_styled_input_dialog("タスク追加", "タスクを入力"); self.todo_items.append(res) if res else None; self.refresh_todo()

    def refresh_todo(self):
        for w in self.todo_list_frame.winfo_children(): w.destroy()
        for i, t in enumerate(self.todo_items):
            f = tk.Frame(self.todo_list_frame, bg="white", pady=12); f.pack(fill="x", pady=5)
            tk.Label(f, text=f"  {t}", font=self.FONT_MAIN, bg="white", fg=self.colors["text_main"]).pack(side="left")
            done = tk.Label(f, text="完了 ", font=("Segoe UI", 9, "bold"), fg=self.colors["accent"], bg="white", cursor="hand2"); done.pack(side="right", padx=15); done.bind("<Button-1>", lambda e, idx=i: [self.todo_items.pop(idx), self.refresh_todo()])

    # --- カレンダー ---
    
    def show_calendar(self):
        self.clear_frame()
        self.styled_button(self.container, "戻る", self.show_selector, self.colors["tab_inactive"]).pack(anchor="w", padx=20, pady=10)
        tk.Label(self.container, text="カレンダー", font=self.FONT_TITLE, bg=self.colors["bg_base"], fg=self.colors["primary"]).pack(pady=5)
        
        ctrl_f = tk.Frame(self.container, bg=self.colors["bg_base"]); ctrl_f.pack(pady=10)
        self.styled_button(ctrl_f, "＜", self.prev_month, self.colors["primary"], pady=5).pack(side="left", padx=10)
        self.cal_label = tk.Label(ctrl_f, text=f"{self.cur_year} / {self.cur_month}", font=("Segoe UI", 20, "bold"), bg=self.colors["bg_base"], fg=self.colors["text_main"], width=10)
        self.cal_label.pack(side="left", padx=10)
        self.styled_button(ctrl_f, "＞", self.next_month, self.colors["primary"], pady=5).pack(side="left", padx=10)

        f_card = tk.Frame(self.container, bg=self.colors["card_bg"], padx=15, pady=15); f_card.pack(pady=10); self.calendar_frame = tk.Frame(f_card, bg=self.colors["card_bg"]); self.calendar_frame.pack(); self.draw_calendar()

    def draw_calendar(self):
        self.cal_label.config(text=f"{self.cur_year} / {self.cur_month}")
        for w in self.calendar_frame.winfo_children(): w.destroy()
        days = ["月","火","水","木","金","土","日"]
        for i, d in enumerate(days): tk.Label(self.calendar_frame, text=d, font=self.FONT_CAL, bg=self.colors["card_bg"], fg=self.colors["text_sub"]).grid(row=0, column=i, padx=10, pady=10)
        cal = calendar.monthcalendar(self.cur_year, self.cur_month); today = datetime.now()
        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0: continue
                key = f"{self.cur_year}-{self.cur_month}-{day}"
                is_today = (day == today.day and self.cur_month == today.month and self.cur_year == today.year)
                if is_today: bg = self.colors["primary"]; fg = "white"
                elif key in self.calendar_notes: bg = self.colors["accent"]; fg = "white"
                else: bg = "white"; fg = self.colors["text_main"]
                btn = tk.Label(self.calendar_frame, text=str(day), font=self.FONT_CAL, bg=bg, fg=fg, width=5, height=2, cursor="hand2", highlightthickness=1, highlightbackground=self.colors["primary"]); btn.grid(row=r+1, column=c, padx=3, pady=3); btn.bind("<Button-1>", lambda e, d=day: self.edit_day_memo(d))


    def prev_month(self):
        if self.cur_month == 1: self.cur_month = 12; self.cur_year -= 1
        else: self.cur_month -= 1
        self.draw_calendar()

    def next_month(self):
        if self.cur_month == 12: self.cur_month = 1; self.cur_year += 1
        else: self.cur_month += \
        self.draw_calendar()

    def edit_day_memo(self, day):
        key = f"{self.cur_year}-{self.cur_month}-{day}"; old = self.calendar_notes.get(key, ""); res = self.create_styled_input_dialog(f"DATE: {day}", "メモ", old)
        if res is not None: [self.calendar_notes.pop(key) if res.strip()=="" else self.calendar_notes.update({key: res}), self.draw_calendar()]

if __name__ == "__main__":
    root = tk.Tk(); app = MultiApp(root); root.protocol("WM_DELETE_WINDOW", lambda: [app.save_all_data(), root.destroy()]); root.mainloop()