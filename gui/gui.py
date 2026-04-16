"""GUI für Szenario-Konfiguration mit customtkinter."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import customtkinter as ctk
import pandas as pd
import threading
from typing import Optional, Dict

from user_config import UserInputConfig
from scenario_builder import ScenarioBuilder
from simulator import Simulator
from profiles import ProfileGenerator
from analyzer import ResultAnalyzer
from config import SystemConfig


class SimulationGUI:
    """GUI für interaktive Szenario-Parametrisierung und Simulation."""
    
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("H2-Microgrid Simulator")
        self.root.geometry("900x1200")
        
        self.profile_generator = ProfileGenerator()
        self.profiles: Optional[pd.DataFrame] = None
        self.simulation_running = False
        self.last_results: Optional[Dict] = None
        
        self._build_ui()
        self._load_profiles()
    
    def _build_ui(self):
        """Erstellt UI-Elemente."""
        self.main_frame = ctk.CTkScrollableFrame(self.root, corner_radius=0)
        self.main_frame.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True, padx=0, pady=0)
        
        self._build_input_section()
        self._build_output_section()
    
    def _build_input_section(self):
        """Input-Bereich für Parameter."""
        input_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        input_frame.pack(fill=ctk.X, padx=20, pady=20)
        
        title = ctk.CTkLabel(input_frame, text="Szenario-Parameter", 
                            font=("Arial", 18, "bold"))
        title.pack(anchor=ctk.W, pady=(0, 20))
        
        self._build_ev_slider(input_frame)
        self._build_hp_checkbox(input_frame)
        self._build_smart_energy_checkbox(input_frame)
        self._build_price_section(input_frame)
        
        button_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        button_frame.pack(fill=ctk.X, pady=(30, 0))
        
        self.run_button = ctk.CTkButton(
            button_frame,
            text="📊 Simulation starten",
            command=self._on_run_simulation,
            font=("Arial", 14, "bold"),
            height=40,
            corner_radius=8
        )
        self.run_button.pack(side=ctk.LEFT, padx=(0, 10), fill=ctk.X, expand=True)
        
        self.status_label = ctk.CTkLabel(
            button_frame,
            text="",
            font=("Arial", 12),
            text_color="gray"
        )
        self.status_label.pack(side=ctk.LEFT, padx=10)
    
    def _build_ev_slider(self, parent):
        """Schieberegler für E-Auto-Anzahl."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill=ctk.X, pady=15)
        
        label = ctk.CTkLabel(frame, text="E-Autos", font=("Arial", 14, "bold"))
        label.pack(anchor=ctk.W, pady=(0, 8))
        
        slider_frame = ctk.CTkFrame(frame, fg_color="transparent")
        slider_frame.pack(fill=ctk.X)
        
        self.ev_slider = ctk.CTkSlider(
            slider_frame,
            from_=0,
            to=25,
            number_of_steps=25,
            command=self._update_ev_label,
            height=6
        )
        self.ev_slider.pack(side=ctk.LEFT, fill=ctk.X, expand=True)
        self.ev_slider.set(1)
        
        self.ev_label = ctk.CTkLabel(slider_frame, text="1", font=("Arial", 12, "bold"), width=30)
        self.ev_label.pack(side=ctk.LEFT, padx=(10, 0))
    
    def _update_ev_label(self, value):
        """Aktualisiert Label bei Slider-Bewegung."""
        self.ev_label.configure(text=str(int(float(value))))
    
    def _build_hp_checkbox(self, parent):
        """Checkbox für Wärmepumpen-Ausfall."""
        self.hp_var = ctk.BooleanVar(value=False)
        checkbox = ctk.CTkCheckBox(
            parent,
            text="Wärmepumpe ausgefallen",
            variable=self.hp_var,
            font=("Arial", 13),
            checkbox_height=20,
            checkbox_width=20
        )
        checkbox.pack(anchor=ctk.W, pady=15)
    
    def _build_smart_energy_checkbox(self, parent):
        """Checkbox für Smart Energy."""
        self.smart_energy_var = ctk.BooleanVar(value=False)
        checkbox = ctk.CTkCheckBox(
            parent,
            text="Smart Energy nutzen (30% Last zu PV-Spitzen)",
            variable=self.smart_energy_var,
            font=("Arial", 13),
            checkbox_height=20,
            checkbox_width=20
        )
        checkbox.pack(anchor=ctk.W, pady=15)
    
    def _build_price_section(self, parent):
        """Variable Strompreise mit Nacht/Tag-Tarif."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill=ctk.X, pady=15)
        
        self.var_price_var = ctk.BooleanVar(value=False)
        checkbox = ctk.CTkCheckBox(
            frame,
            text="Variable Strompreise aktivieren",
            variable=self.var_price_var,
            command=self._toggle_price_inputs,
            font=("Arial", 13),
            checkbox_height=20,
            checkbox_width=20
        )
        checkbox.pack(anchor=ctk.W)
        
        self.price_input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.price_input_frame.pack(fill=ctk.X, pady=(10, 0), padx=(20, 0))
        
        night_frame = ctk.CTkFrame(self.price_input_frame, fg_color="transparent")
        night_frame.pack(fill=ctk.X, pady=5)
        
        ctk.CTkLabel(night_frame, text="Nacht-Tarif (CHF/kWh):", font=("Arial", 12)).pack(side=ctk.LEFT)
        self.price_night_input = ctk.CTkEntry(night_frame, width=80, font=("Arial", 12))
        self.price_night_input.pack(side=ctk.LEFT, padx=(10, 0))
        self.price_night_input.insert(0, "0.15")
        self.price_night_input.configure(state=ctk.DISABLED)
        
        day_frame = ctk.CTkFrame(self.price_input_frame, fg_color="transparent")
        day_frame.pack(fill=ctk.X, pady=5)
        
        ctk.CTkLabel(day_frame, text="Tag-Tarif (CHF/kWh):", font=("Arial", 12)).pack(side=ctk.LEFT)
        self.price_day_input = ctk.CTkEntry(day_frame, width=80, font=("Arial", 12))
        self.price_day_input.pack(side=ctk.LEFT, padx=(10, 0))
        self.price_day_input.insert(0, "0.30")
        self.price_day_input.configure(state=ctk.DISABLED)
    
    def _toggle_price_inputs(self):
        """Aktiviert/deaktiviert Preis-Eingabefelder."""
        state = ctk.NORMAL if self.var_price_var.get() else ctk.DISABLED
        self.price_night_input.configure(state=state)
        self.price_day_input.configure(state=state)
    
    def _build_output_section(self):
        """Bereich für Ergebnisse."""
        self.output_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.output_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)
        
        title = ctk.CTkLabel(self.output_frame, text="Ergebnisse", 
                            font=("Arial", 18, "bold"))
        title.pack(anchor=ctk.W, pady=(0, 15))
        
        self.result_text = ctk.CTkTextbox(self.output_frame, height=300, corner_radius=8)
        self.result_text.pack(fill=ctk.BOTH, expand=True)
        self.result_text.configure(state=ctk.DISABLED)
        
        self.plot_frame = ctk.CTkFrame(self.output_frame, fg_color="gray20", corner_radius=8, height=300)
        self.plot_frame.pack(fill=ctk.BOTH, expand=True, pady=(15, 0))
    
    def _load_profiles(self):
        """Lädt Profile beim Start."""
        try:
            system_config = SystemConfig()
            self.profiles = self.profile_generator.load_simulation_profiles(system_config)
            self._update_status("✓ Profile geladen")
        except Exception as e:
            self._update_status(f"✗ Fehler beim Laden: {str(e)}")
    
    def _on_run_simulation(self):
        """Startet Simulation in separatem Thread."""
        if self.simulation_running or self.profiles is None:
            return
        
        self.simulation_running = True
        self.run_button.configure(state=ctk.DISABLED)
        self._update_status("⏳ Simulation läuft...")
        
        thread = threading.Thread(target=self._run_simulation_thread, daemon=True)
        thread.start()
    
    def _run_simulation_thread(self):
        """Führt Simulation aus (in Thread)."""
        try:
            user_config = self._get_user_config()
            
            scenario = ScenarioBuilder.build(user_config, self.profiles)
            simulator = Simulator(scenario)
            
            simulator.run_all_strategies(self.profiles)
            self.last_results = simulator.results
            
            self._display_results(simulator)
            self._update_status("✓ Simulation abgeschlossen")
            
        except Exception as e:
            self._update_status(f"✗ Fehler: {str(e)}")
        
        finally:
            self.simulation_running = False
            self.run_button.configure(state=ctk.NORMAL)
    
    def _get_user_config(self) -> UserInputConfig:
        """Liest Parameter aus GUI aus."""
        return UserInputConfig(
            num_evs=int(float(self.ev_slider.get())),
            hp_failure=self.hp_var.get(),
            smart_energy_enabled=self.smart_energy_var.get(),
            variable_prices_enabled=self.var_price_var.get(),
            price_night_chf_per_kwh=float(self.price_night_input.get() or "0.15"),
            price_day_chf_per_kwh=float(self.price_day_input.get() or "0.30"),
        )
    
    def _display_results(self, simulator: Simulator):
        """Zeigt Ergebnisse in GUI an."""
        self.result_text.configure(state=ctk.NORMAL)
        self.result_text.delete("1.0", ctk.END)
        
        kpis_summary = simulator.get_kpis_summary()
        
        for idx, kpi_dict in enumerate(kpis_summary, 1):
            self.result_text.insert(ctk.END, f"\n{'='*60}\n")
            self.result_text.insert(ctk.END, f"Strategie {idx}\n")
            self.result_text.insert(ctk.END, f"{'='*60}\n\n")
            
            for key, value in kpi_dict.items():
                if key != 'label':
                    self.result_text.insert(ctk.END, f"{key:<40} {value}\n")
        
        self.result_text.configure(state=ctk.DISABLED)
        
        self._plot_results(simulator)
    
    def _plot_results(self, simulator: Simulator):
        """Erstellt und zeigt Plots."""
        try:
            for strategy_key, result in simulator.results.items():
                result_df = result['result_df']
                
                title = f"{simulator.scenario.name} – {strategy_key} – H2-SOC"
                simulator.analyzer.plot_h2_soc_year(
                    result_df,
                    title=title,
                    save_path=f"h2_soc_{strategy_key.lower()}.png"
                )
        except Exception as e:
            print(f"Plot-Fehler: {e}")
    
    def _update_status(self, message: str):
        """Aktualisiert Status-Label (threadsafe)."""
        self.root.after(0, lambda: self.status_label.configure(text=message))


def launch_gui():
    """Startet die Anwendung."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    root = ctk.CTk()
    app = SimulationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
