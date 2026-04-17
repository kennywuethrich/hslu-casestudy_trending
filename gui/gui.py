"""GUI für Strategie-Vergleich."""

import customtkinter as ctk
from tkinter import ttk
import threading
import sys
import pandas as pd
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
        
        self.results_dir = Path(__file__).parent.parent / "results"
        self.selected_result_scenario = None
        
        # === Main Grid ===
        main = ctk.CTkFrame(root)
        main.pack(fill="both", expand=True, padx=15, pady=15)
        main.grid_rowconfigure(2, weight=1)
        main.grid_rowconfigure(4, weight=1)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        
        # Title
        title_wrap = ctk.CTkFrame(main, fg_color="transparent")
        title_wrap.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        lbl_h = ctk.CTkLabel(title_wrap, text="H", font=("Segoe UI", 34, "bold"))
        lbl_2 = ctk.CTkLabel(title_wrap, text="2", font=("Segoe UI", 18, "bold"))
        lbl_txt = ctk.CTkLabel(title_wrap, text=" Strategie-Vergleich", font=("Segoe UI", 34, "bold"))

        lbl_h.grid(row=0, column=0, sticky="n")
        lbl_2.grid(row=0, column=1, sticky="s", pady=(14, 0))
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
        self.desc1 = ctk.CTkTextbox(main, height=100, width=400)
        self.desc1.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        self.desc1.configure(state="disabled")
        
        self.desc2 = ctk.CTkTextbox(main, height=100, width=400)
        self.desc2.grid(row=2, column=1, sticky="nsew", padx=(10, 0))
        self.desc2.configure(state="disabled")
        
        # Button + Status
        btn_frame = ctk.CTkFrame(main)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=15)
        
        self.btn = ctk.CTkButton(btn_frame, text="SIMULATIONEN STARTEN", command=self._compare, font=("Helvetica", 13))
        self.btn.pack(side="left", padx=(0, 15))
        
        self.status = ctk.CTkLabel(btn_frame, text="Bereit", text_color="gray")
        self.status.pack(side="left")
        
        # Results section label
        results_label = ctk.CTkLabel(main, text="ERGEBNISSE", font=("Helvetica", 14, "bold"))
        results_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=(15, 10))
        
        # Results view selector (dropdown to switch between scenarios)
        view_frame = ctk.CTkFrame(main)
        view_frame.grid(row=4, column=0, columnspan=2, sticky="e", pady=(15, 10))
        
        ctk.CTkLabel(view_frame, text="Anzeige Szenario:", font=("Helvetica", 12)).pack(side="left", padx=(0, 10))
        self.result_combo = ctk.CTkComboBox(view_frame, values=["Szenario 1", "Szenario 2"], width=200, command=self._load_result_csv)
        self.result_combo.pack(side="left")
        
        # Results table
        self.table_frame = ctk.CTkFrame(main)
        self.table_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)
        
        self._show_placeholder()
        self._update_desc1(None)
        self._update_desc2(None)
    
    def _show_placeholder(self):
        """Zeigt Placeholder-Text an."""
        for w in self.table_frame.winfo_children():
            w.destroy()
        
        placeholder = ctk.CTkLabel(
            self.table_frame,
            text="Klicken Sie auf 'SIMULATIONEN STARTEN', um Ergebnisse zu generieren.",
            text_color="gray"
        )
        placeholder.pack(expand=True)
    
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
        self.status.configure(text="⏳ Simulationen laufen...", text_color="orange")
        self._show_placeholder()
        threading.Thread(target=self._worker, daemon=True).start()
    
    def _worker(self):
        try:
            s1 = ScenarioManager.get_by_name(self.s1_combo.get())
            s2 = ScenarioManager.get_by_name(self.s2_combo.get())
            
            # Simuliere Szenario 1
            sim1 = Simulator(s1, scenario_number=1)
            profiles1 = sim1.generate_profiles()
            sim1.run_all_strategies(profiles1)
            
            # Simuliere Szenario 2
            sim2 = Simulator(s2, scenario_number=2)
            profiles2 = sim2.generate_profiles()
            sim2.run_all_strategies(profiles2)
            
            self.root.after(0, self._on_simulations_complete)
        except Exception as e:
            print(f"Fehler: {e}")
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self.status.configure(text=f"Fehler: {str(e)[:40]}", text_color="red"))
            self.root.after(0, lambda: self.btn.configure(state="normal"))
    
    def _on_simulations_complete(self):
        """Wird aufgerufen, wenn Simulationen fertig sind."""
        self.status.configure(text="✓ Fertig", text_color="green")
        self.btn.configure(state="normal")
    
    def _load_result_csv(self, scenario_display):
        """Lädt CSV für ausgewähltes Szenario.
        
        Args:
            scenario_display: "Szenario 1" oder "Szenario 2"
        """
        # Extrahiere die Nummer aus "Szenario 1" oder "Szenario 2"
        scenario_number = scenario_display.split()[-1]
        csv_path = self.results_dir / f"kpis_szenario_{scenario_number}.csv"
        
        if not csv_path.exists():
            self._show_placeholder()
            return
        
        try:
            df = pd.read_csv(csv_path)
            self._display_table(df)
        except Exception as e:
            print(f"Fehler beim Laden der CSV: {e}")
            self._show_placeholder()
    
    def _display_table(self, df: pd.DataFrame):
        """Zeigt DataFrame als Tabelle an."""
        for w in self.table_frame.winfo_children():
            w.destroy()
        
        columns = list(df.columns)
        tree = ttk.Treeview(self.table_frame, columns=columns, height=15)
        tree.column("#0", width=0)
        
        for col in columns:
            tree.column(col, width=200, anchor="center")
            tree.heading(col, text=col, anchor="center")
        
        for idx, row in df.iterrows():
            values = [row[col] for col in columns]
            tree.insert("", "end", values=values)
        
        tree.pack(fill="both", expand=True)


def launch():
    root = ctk.CTk()
    StrategyGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
