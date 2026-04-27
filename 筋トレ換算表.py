import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QComboBox, QLineEdit, QFrame, QSpacerItem, QSizePolicy)
from PySide6.QtCore import Qt

class UltimateVisibilityCalc(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("筋トレ重量換算 ")
        self.setFixedWidth(420)
        self.setFixedHeight(720)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #0F172A;
                font-family: 'Meiryo', sans-serif;
            }
            #MainCard {
                background-color: #1E293B;
                border-radius: 30px;
            }
            .Label {
                color: #94A3B8; 
                font-size: 13px;
                font-weight: bold;
                margin-left: 5px;
            }
            QLineEdit {
                border: 2px solid #334155;
                border-radius: 15px;
                padding: 10px;
                background-color: #0F172A;
                color: #F8FAFC; 
                font-size: 18px;
                font-weight: bold;
            }
            QComboBox {
                border: 2px solid #334155;
                border-radius: 15px;
                padding: 10px;
                background-color: #0F172A;
                color: #FFFFFF; 
                font-size: 16px;
                font-weight: bold;
            }
            QComboBox QAbstractItemView {
                background-color: #1E293B;
                color: #FFFFFF;
                selection-background-color: #38BDF8;
                border: 1px solid #334155;
            }
            
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #38BDF8;
            }

            #ResultBox {
                background-color: #020617; 
                border-radius: 25px;
                margin-top: 20px;
                border: 1px solid #334155;
            }
            #RMVal {
                color: #38BDF8;
                font-size: 72px; 
                font-weight: 900;
                margin: 0px;
            }
            #RMSub {
                color: #64748B;
                font-size: 13px;
                letter-spacing: 4px;
                margin-top: 10px;
            }
            #Msg {
                color: #F8FAFC;
                font-size: 20px;
                font-weight: bold;
                padding-bottom: 15px;
            }
        """)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        self.main_card = QFrame()
        self.main_card.setObjectName("MainCard")
        card_layout = QVBoxLayout(self.main_card)
        card_layout.setContentsMargins(30, 35, 30, 35)
        card_layout.setSpacing(10)

        def add_input(label_text, default, is_combo=False):
            l = QLabel(label_text)
            l.setProperty("class", "Label")
            card_layout.addWidget(l)
            if is_combo:
                w = QComboBox()
                w.addItems(["ベンチプレス", "ショルダープレス", "アームカール", "スクワット", "デッドリフト"])
            else:
                w = QLineEdit(default)
                w.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(w)
            return w

        self.ex_in = add_input("トレーニング種目", "", True)
        self.w_in = add_input("現在の重量 (kg)", "30")
        self.r_in = add_input("現在の回数 (回)", "10")
        self.tw_in = add_input("目標重量 (kg)", "40")

       
        card_layout.addStretch()

        self.res_box = QFrame()
        self.res_box.setObjectName("ResultBox")
        res_layout = QVBoxLayout(self.res_box)
        res_layout.setContentsMargins(10, 30, 10, 30)
        res_layout.setSpacing(5)

        sub = QLabel("推定 MAX重量")
        sub.setObjectName("RMSub")
        sub.setAlignment(Qt.AlignCenter)
        
        self.rm_val = QLabel("-")
        self.rm_val.setObjectName("RMVal")
        self.rm_val.setAlignment(Qt.AlignCenter)
        
        self.msg_val = QLabel("-")
        self.msg_val.setObjectName("Msg")
        self.msg_val.setAlignment(Qt.AlignCenter)

        res_layout.addWidget(sub)
        res_layout.addWidget(self.rm_val)
        res_layout.addWidget(self.msg_val)
        card_layout.addWidget(self.res_box)

        main_layout.addWidget(self.main_card)

        self.ex_in.currentIndexChanged.connect(self.calc)
        for i in [self.w_in, self.r_in, self.tw_in]:
            i.textChanged.connect(self.calc)
        self.calc()

    def calc(self):
        try:
            ex = self.ex_in.currentText()
            w = float(self.w_in.text())
            r = int(self.r_in.text())
            tw = float(self.tw_in.text())

            div = 33.3 if any(s in ex for s in ["スクワット", "デッド"]) else 40.0
            rm = w if r == 1 else (w * r / div) + w
            
            
            self.rm_val.setText(f"{rm:.1f}<span style='font-size:28px; color:#38BDF8;'> kg</span>")

            if tw <= rm:
                reps = max(1, int((rm / tw - 1) * div))
                self.msg_val.setText(f"🔥 {tw}kg を {reps}回 狙えます")
            else:
                self.msg_val.setText(f"🚀 あと {tw-rm:.1f} kg で達成")
        except:
            self.rm_val.setText("-")
            self.msg_val.setText("数値を入力してください")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    window = UltimateVisibilityCalc()
    window.show()
    sys.exit(app.exec())