"""GUI für Strategie-Vergleich."""

import customtkinter as ctk
from tkinter import ttk
import threading
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scenario import ScenarioManager
from simulator import Simulator


class StrategyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("H₂-Strategie Vergleich")
        self.root.geometry("1200x700")
        
        # === Config ===
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # === Main Grid ===
        main = ctk.CTkFrame(root)
        main.pack(fill="both", expand=True, padx=15, pady=15)
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        
        # Title
        title_wrap = ctk.CTkFrame(main, fg_color="transparent")
        title_wrap.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        lbl_h = ctk.CTkLabel(title_wrap, text="H", font=("Segoe UI", 34, "bold"))
        lbl_2 = ctk.CTkLabel(title_wrap, text="2", font=("Segoe UI", 18, "bold"))
        lbl_txt = ctk.CTkLabel(title_wrap, text=" Strategie-Vergleich", font=("Segoe UI", 34, "bold"))

        lbl_h.grid(row=0, column=0, sticky="n")
        lbl_2.grid(row=0, column=1, sticky="s", pady=(14, 0))  # nach unten schieben
        lbl_txt.grid(row=0, column=2, sticky="n")
        
        # Scenario selection
        sel_frame = ctk.CTkFrame(main)
        sel_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        
        scenarios = [s.name for s in ScenarioManager.get_all_scenarios()]
        ctk.CTkLabel(sel_frame, text="Szenario 1:", font=("Helvetica", 12)).pack(side="left", padx=(0, 10))
        self.s1_combo = ctk.CTkComboBox(sel_frame, values=scenarios, width=200, command=self._update_desc1)
        self.s1_combo.set(scenarios[0])
        self.s1_combo.pack(side="left", padx=(0, 40))
        
        ctk.CTkLabel(sel_frame, text="Szenario 2:", font=("Helvetica", 12)).pack(side="left", padx=(0, 10))
        self.s2_combo = ctk.CTkComboBox(sel_frame, values=scenarios, width=200, command=self._update_desc2)
        self.s2_combo.set(scenarios[1] if len(scenarios) > 1 else scenarios[0])
        self.s2_combo.pack(side="left")
        
        # Descriptions (side by side)
        self.desc1 = ctk.CTkTextbox(main, height=120, width=400)
        self.desc1.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        self.desc1.configure(state="disabled")
        
        self.desc2 = ctk.CTkTextbox(main, height=120, width=400)
        self.desc2.grid(row=2, column=1, sticky="nsew", padx=(10, 0))
        self.desc2.configure(state="disabled")
        
        # Button + Status
        btn_frame = ctk.CTkFrame(main)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=15)
        
        self.btn = ctk.CTkButton(btn_frame, text="VERGLEICHEN", command=self._compare, font=("Helvetica", 13))
        self.btn.pack(side="left", padx=(0, 15))
        
        self.status = ctk.CTkLabel(btn_frame, text="Bereit", text_color="gray")
        self.status.pack(side="left")
        
        # Results table
        self.table_frame = ctk.CTkFrame(main)
        self.table_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)
        
        self._update_desc1(None)
        self._update_desc2(None)
    
    def _update_desc(self, combo, textbox):
        s = ScenarioManager.get_by_name(combo.get())
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.insert("1.0", s.description)
        textbox.configure(state="disabled")
    
    def _update_desc1(self, _):
        self._update_desc(self.s1_combo, self.desc1)
    
    def _update_desc2(self, _):
        self._update_desc(self.s2_combo, self.desc2)
    
    def _compare(self):
        self.btn.configure(state="disabled")
        self.status.configure(text="⏳ Läuft...", text_color="orange")
        threading.Thread(target=self._worker, daemon=True).start()
    
    def _worker(self):
        try:
            s1 = ScenarioManager.get_by_name(self.s1_combo.get())
            s2 = ScenarioManager.get_by_name(self.s2_combo.get())
            
            sim1, sim2 = Simulator(s1), Simulator(s2)
            sim1.run_all_strategies(sim1.generate_profiles())
            sim2.run_all_strategies(sim2.generate_profiles())
            
            self.root.after(0, self._show, s1.name, s2.name, sim1.get_kpis_summary()[0], sim2.get_kpis_summary()[0])
        except Exception as e:
            print(f"Fehler: {e}")
            self.root.after(0, lambda: self.status.configure(text=f"Fehler: {str(e)[:40]}", text_color="red"))
            self.root.after(0, lambda: self.btn.configure(state="normal"))
    
    def _show(self, s1_name, s2_name, kpi1, kpi2):
        for w in self.table_frame.winfo_children():
            w.destroy()
        
        tree = ttk.Treeview(self.table_frame, columns=("KPI", s1_name, s2_name, "Δ"), height=12)
        tree.column("#0", width=0)
        tree.column("KPI", width=250, anchor="w")
        tree.column(s1_name, width=180, anchor="center")
        tree.column(s2_name, width=180, anchor="center")
        tree.column("Δ", width=100, anchor="center")
        
        tree.heading("KPI", text="KPI", anchor="w")
        tree.heading(s1_name, text=s1_name, anchor="center")
        tree.heading(s2_name, text=s2_name, anchor="center")
        tree.heading("Δ", text="Differenz", anchor="center")
        
        for key in kpi1.keys():
            if key == "label":
                continue
            v1, v2 = kpi1.get(key, "-"), kpi2.get(key, "-")
            try:
                delta = f"{float(v2) - float(v1):+.1f}"
            except:
                delta = "-"
            tree.insert("", "end", values=(key, v1, v2, delta))
        
        tree.pack(fill="both", expand=True)
        self.status.configure(text="✓ Fertig", text_color="green")
        self.btn.configure(state="normal")


def launch():
    root = ctk.CTk()
    StrategyGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
