"""GUI für Strategie-Vergleich."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import multiprocessing as mp
import os
import queue
import sys
import traceback
from pathlib import Path
from tkinter import ttk
from typing import Any

import customtkinter as ctk
import pandas as pd
from PIL import Image, ImageTk

from plots import (
    plot_consumption_averages_comparison,
    plot_h2_soc_comparison,
    plot_stromkonsum_comparison,
)

sys.path.insert(0, str(Path(__file__).parent.parent))

from scenario import ScenarioManager
from simulator import simulate
from profiles import load_profiles
from strategies import BaseStrategy, OptimizedStrategy
from analyzer import calculate_kpis, save_kpis_by_scenario


class _LogQueueWriter:
    """Leitet Textausgaben zeilenweise in eine Thread-safe Queue um."""

    def __init__(
        self,
        output_queue: queue.Queue[str],
        mirror_stream: Any | None = None,
        message_kind: str | None = None,
    ) -> None:
        self._queue = output_queue
        self._mirror_stream = mirror_stream
        self._message_kind = message_kind
        self._buffer = ""

    def write(self, message: str) -> int:
        """Schreibt Text in den Puffer und emittiert vollständige Zeilen."""
        if not message:
            return 0

        if self._mirror_stream is not None:
            self._mirror_stream.write(message)

        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                if self._message_kind is None:
                    self._queue.put(line)
                else:
                    self._queue.put((self._message_kind, line))
        return len(message)

    def flush(self) -> None:
        """Leert den Restpuffer als letzte Zeile."""
        if self._buffer.strip():
            if self._message_kind is None:
                self._queue.put(self._buffer)
            else:
                self._queue.put((self._message_kind, self._buffer))
        if self._mirror_stream is not None:
            self._mirror_stream.flush()
        self._buffer = ""


def _run_simulations_in_process(
    scenario_1_name: str,
    scenario_2_name: str,
    results_dir_str: str,
    message_queue: Any,
    h2_capacity_override_kwh: float | None = None,
    h2_pressure_bar: float | None = None,
    pv_area_factor: float | None = None,
) -> None:
    """Führt beide Simulationen in einem separaten Prozess aus."""
    log_writer = _LogQueueWriter(message_queue, sys.__stdout__, message_kind="log")
    results_dir = Path(results_dir_str)

    try:
        with redirect_stdout(log_writer), redirect_stderr(log_writer):
            print(f"Szenario A => {scenario_1_name}")
            print(f"Szenario B => {scenario_2_name}")

            scenario_1 = ScenarioManager.get_by_name(scenario_1_name)
            scenario_2 = ScenarioManager.get_by_name(scenario_2_name)

            # Optional: Versuche, aktuelle Strompreise zu laden
            # Nur Szenario A lädt API-Preise, alle anderen bleiben fix konfiguriert.
            baseline_names = {"Szenario A", "Szenario 1"}
            if scenario_1.name in baseline_names:
                print("→ Lade aktuelle Strompreise für Baseline-Szenario...")
                scenario_1.config.fetch_price_from_api()
            if scenario_2.name in baseline_names:
                print("→ Lade aktuelle Strompreise für Baseline-Szenario...")
                scenario_2.config.fetch_price_from_api()

            simulations = [
                ("A", scenario_1),
                ("B", scenario_2),
            ]

            for slot_label, scenario in simulations:
                if h2_capacity_override_kwh is not None:
                    scenario.config.h2_capacity_override_kwh = h2_capacity_override_kwh
                if h2_pressure_bar is not None:
                    scenario.config.h2_pressure_bar = h2_pressure_bar
                if pv_area_factor is not None:
                    scenario.config.pv_area_factor = pv_area_factor

                print(f"Starte Berechnung für Szenario {slot_label}...")
                print(f"  Strompreis: {scenario.config.price_buy_chf:.4f} CHF/kWh")

                profiles_df = load_profiles(scenario.config)
                base_strategy = BaseStrategy(scenario.config)
                optimized_strategy = OptimizedStrategy(scenario.config)

                result_base = simulate(profiles_df, scenario.config, base_strategy)
                result_optimized = simulate(
                    profiles_df,
                    scenario.config,
                    optimized_strategy,
                )

                kpi_base = calculate_kpis(
                    result_base,
                    scenario.config,
                    label="BaseStrategy",
                )
                kpi_optimized = calculate_kpis(
                    result_optimized,
                    scenario.config,
                    label="OptimizedStrategy",
                )
                save_kpis_by_scenario(slot_label, kpi_base, kpi_optimized)

                print(f"Erzeuge Plots für Szenario {slot_label}...")
                capacity_kwh = scenario.config.h2_capacity_kwh

                h2_file_name = f"plot_szenario_{slot_label}_vergleich_h2.png"
                h2_save_path = results_dir / h2_file_name
                plot_h2_soc_comparison(
                    result_base,
                    result_optimized,
                    title=f"H2-Füllstand – Szenario {slot_label} (Vergleich)",
                    save_path=str(h2_save_path),
                    capacity_kwh=capacity_kwh,
                )

                consumption_file_name = (
                    f"plot_netzbezug_szenario_{slot_label}_vergleich.png"
                )
                consumption_save_path = results_dir / consumption_file_name
                plot_consumption_averages_comparison(
                    result_base,
                    result_optimized,
                    title=(
                        "Netzbezug-Mittelwerte – " f"Szenario {slot_label} (Vergleich)"
                    ),
                    save_path=str(consumption_save_path),
                )

                strom_file_name = f"plot_stromkonsum_szenario_{slot_label}_vergleich.png"
                strom_save_path = results_dir / strom_file_name
                plot_stromkonsum_comparison(
                    result_base,
                    result_optimized,
                    title=(
                        "Stromkonsum – " f"Szenario {slot_label} (Vergleich)"
                    ),
                    save_path=str(strom_save_path),
                )

            print("Simulationen abgeschlossen.")

        log_writer.flush()
        message_queue.put(("done", "ok"))
    except Exception as exc:  # pylint: disable=broad-except
        message_queue.put(("error", f"{exc}"))
        message_queue.put(("log", traceback.format_exc()))


class StrategyGUI:
    """UI für den Vergleich zweier Szenarien und ihrer Strategien."""

    WINDOW_SIZE = "1360x820"
    FONT_TITLE = ("Segoe UI", 33, "bold")
    FONT_SUBTITLE = ("Segoe UI", 12)
    FONT_SECTION = ("Segoe UI Semibold", 15)
    FONT_TEXT = ("Segoe UI", 12)
    FONT_BUTTON = ("Segoe UI Semibold", 13)
    FONT_LOG = ("Consolas", 11)

    def __init__(self, root: ctk.CTk) -> None:
        """Initialisiert Fenster, Eingaben und Ergebnisbereich.

        Args:
            root: Hauptfenster der Anwendung.
        """
        self.root = root
        self.root.title("H₂-Strategie Vergleich")
        self.root.geometry(self.WINDOW_SIZE)
        self.root.minsize(1180, 740)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.results_dir = Path(__file__).parent.parent / "results"
        self.selected_result_scenario: str | None = None
        self._current_result_view = "kpi"
        self._current_kpi_df: pd.DataFrame | None = None
        self._table_tree: ttk.Treeview | None = None
        self._table_columns: list[str] = []
        self._image_refs: dict[str, Any] = {}
        self._sim_process: mp.Process | None = None
        self._sim_process_queue: Any | None = None
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_existing_plots()
        self._configure_ttk_style()

        shell = ctk.CTkFrame(root, corner_radius=18, fg_color=("#121728", "#121728"))
        shell.pack(fill="both", expand=True, padx=18, pady=18)
        shell.grid_rowconfigure(0, weight=0)
        shell.grid_rowconfigure(1, weight=1)
        shell.grid_columnconfigure(0, weight=1)

        title_wrap = ctk.CTkFrame(
            shell,
            fg_color=("#181E32", "#181E32"),
            corner_radius=14,
            border_width=1,
            border_color=("#2A3350", "#2A3350"),
        )
        title_wrap.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 12))
        title_wrap.grid_columnconfigure(0, weight=1)
        title_wrap.grid_columnconfigure(1, weight=0)

        title_left = ctk.CTkFrame(title_wrap, fg_color="transparent")
        title_left.grid(row=0, column=0, sticky="w", padx=16, pady=14)

        lbl_h = ctk.CTkLabel(title_left, text="H", font=("Segoe UI", 34, "bold"))
        lbl_2 = ctk.CTkLabel(title_left, text="2", font=("Segoe UI", 18, "bold"))
        lbl_txt = ctk.CTkLabel(
            title_left,
            text=" Strategie-Vergleich",
            font=self.FONT_TITLE,
        )
        subtitle = ctk.CTkLabel(
            title_left,
            text="Vergleiche zwei Szenarien und ihre KPI-Ergebnisse in einem Lauf",
            text_color=("#9CA3AF", "#9CA3AF"),
            font=self.FONT_SUBTITLE,
        )

        lbl_h.grid(row=0, column=0, sticky="n")
        lbl_2.grid(row=0, column=1, sticky="s", pady=(14, 0))
        lbl_txt.grid(row=0, column=2, sticky="n")
        subtitle.grid(row=1, column=0, columnspan=3, pady=(6, 0))

        self.status_badge = ctk.CTkLabel(
            title_wrap,
            text="Bereit",
            font=("Segoe UI Semibold", 12),
            corner_radius=999,
            fg_color=("#1F2937", "#1F2937"),
            text_color=("#93C5FD", "#93C5FD"),
            padx=14,
            pady=6,
        )
        self.status_badge.grid(row=0, column=1, sticky="e", padx=16)

        content = ctk.CTkFrame(shell, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)

        left_panel = ctk.CTkFrame(
            content,
            width=380,
            corner_radius=14,
            fg_color=("#181E32", "#181E32"),
            border_width=1,
            border_color=("#2A3350", "#2A3350"),
        )
        left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        left_panel.grid_propagate(False)
        left_panel.grid_rowconfigure(0, weight=0)
        left_panel.grid_rowconfigure(1, weight=0)
        left_panel.grid_rowconfigure(2, weight=0)
        left_panel.grid_rowconfigure(3, weight=0)
        left_panel.grid_rowconfigure(4, weight=0)
        left_panel.grid_rowconfigure(5, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        setup_title = ctk.CTkLabel(
            left_panel,
            text="Simulation Setup",
            font=self.FONT_SECTION,
            text_color=("#E5E7EB", "#E5E7EB"),
        )
        setup_title.grid(row=0, column=0, sticky="w", padx=14, pady=(14, 10))

        selector_card = ctk.CTkFrame(
            left_panel,
            corner_radius=12,
            fg_color=("#111726", "#111726"),
            border_width=1,
            border_color=("#2A314A", "#2A314A"),
        )
        selector_card.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        selector_card.grid_columnconfigure(0, weight=1)

        scenarios = [scenario.name for scenario in ScenarioManager.get_all_scenarios()]
        ctk.CTkLabel(selector_card, text="Szenario A", font=self.FONT_TEXT).grid(
            row=0,
            column=0,
            sticky="w",
            padx=12,
            pady=(12, 6),
        )
        self.s1_combo = ctk.CTkComboBox(
            selector_card,
            values=scenarios,
            width=320,
            height=36,
            corner_radius=10,
            dropdown_font=self.FONT_TEXT,
            font=self.FONT_TEXT,
            command=self._update_desc1,
        )
        self.s1_combo.set(scenarios[0])
        self.s1_combo.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        ctk.CTkLabel(selector_card, text="Szenario B", font=self.FONT_TEXT).grid(
            row=2,
            column=0,
            sticky="w",
            padx=12,
            pady=(2, 6),
        )
        self.s2_combo = ctk.CTkComboBox(
            selector_card,
            values=scenarios,
            width=320,
            height=36,
            corner_radius=10,
            dropdown_font=self.FONT_TEXT,
            font=self.FONT_TEXT,
            command=self._update_desc2,
        )
        self.s2_combo.set(scenarios[1] if len(scenarios) > 1 else scenarios[0])
        self.s2_combo.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

        action_row = ctk.CTkFrame(selector_card, fg_color="transparent")
        action_row.grid(row=4, column=0, sticky="ew", padx=12, pady=(2, 12))
        action_row.grid_columnconfigure(0, weight=1)
        action_row.grid_columnconfigure(1, weight=0)

        self.btn = ctk.CTkButton(
            action_row,
            text="SIMULATIONEN STARTEN",
            command=self._compare,
            font=self.FONT_BUTTON,
            height=40,
            corner_radius=12,
            fg_color=("#2563EB", "#2563EB"),
            hover_color=("#1D4ED8", "#1D4ED8"),
        )
        self.btn.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.status = ctk.CTkLabel(
            action_row,
            text="Bereit",
            text_color=("#9CA3AF", "#9CA3AF"),
            font=self.FONT_TEXT,
            width=72,
        )
        self.status.grid(row=0, column=1, sticky="e")

        self.btn_toggle_parameters = ctk.CTkButton(
            left_panel,
            text="Parameter anzeigen",
            command=self._toggle_parameters,
            font=self.FONT_BUTTON,
            height=34,
            corner_radius=10,
            fg_color=("#2563EB", "#2563EB"),
            hover_color=("#1D4ED8", "#1D4ED8"),
        )
        self.btn_toggle_parameters.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))

        self.params_card = ctk.CTkFrame(
            left_panel,
            corner_radius=12,
            fg_color=("#111726", "#111726"),
            border_width=1,
            border_color=("#2A314A", "#2A314A"),
        )
        self.params_card.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.params_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.params_card,
            text="Modellparameter",
            font=self.FONT_SECTION,
            text_color=("#E5E7EB", "#E5E7EB"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 8))

        ctk.CTkLabel(self.params_card, text="H2-Kapazität [kWh]", font=self.FONT_TEXT).grid(
            row=1, column=0, sticky="w", padx=12, pady=(6, 4)
        )
        self.h2_capacity_entry = ctk.CTkEntry(
            self.params_card,
            width=320,
            height=34,
            corner_radius=10,
            font=self.FONT_TEXT,
        )
        self.h2_capacity_entry.insert(0, str(ScenarioManager.get_by_name(scenarios[0]).config.h2_capacity_kwh))
        self.h2_capacity_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(self.params_card, text="H2-Druck [bar]", font=self.FONT_TEXT).grid(
            row=3, column=0, sticky="w", padx=12, pady=(6, 4)
        )
        self.h2_pressure_entry = ctk.CTkEntry(
            self.params_card,
            width=320,
            height=34,
            corner_radius=10,
            font=self.FONT_TEXT,
        )
        self.h2_pressure_entry.insert(0, str(ScenarioManager.get_by_name(scenarios[0]).config.h2_pressure_bar))
        self.h2_pressure_entry.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(self.params_card, text="PV-Fläche Faktor", font=self.FONT_TEXT).grid(
            row=5, column=0, sticky="w", padx=12, pady=(6, 4)
        )
        self.pv_area_entry = ctk.CTkEntry(
            self.params_card,
            width=320,
            height=34,
            corner_radius=10,
            font=self.FONT_TEXT,
        )
        self.pv_area_entry.insert(0, str(ScenarioManager.get_by_name(scenarios[0]).config.pv_area_factor))
        self.pv_area_entry.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.params_card.grid_remove()

        desc_card = ctk.CTkFrame(
            left_panel,
            corner_radius=12,
            fg_color=("#111726", "#111726"),
            border_width=1,
            border_color=("#2A314A", "#2A314A"),
        )
        desc_card.grid(row=5, column=0, sticky="nsew", padx=12, pady=(0, 12))
        desc_card.grid_rowconfigure(1, weight=1)
        desc_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            desc_card,
            text="Szenario-Beschreibung",
            font=self.FONT_SECTION,
            text_color=("#E5E7EB", "#E5E7EB"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 8))

        self.desc_tabs = ctk.CTkTabview(
            desc_card,
            corner_radius=10,
            segmented_button_fg_color=("#1E293B", "#1E293B"),
            segmented_button_selected_color=("#2563EB", "#2563EB"),
            segmented_button_selected_hover_color=("#1D4ED8", "#1D4ED8"),
        )
        self.desc_tabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        tab_1 = self.desc_tabs.add("Szenario A")
        tab_2 = self.desc_tabs.add("Szenario B")
        tab_1.grid_rowconfigure(0, weight=1)
        tab_1.grid_columnconfigure(0, weight=1)
        tab_2.grid_rowconfigure(0, weight=1)
        tab_2.grid_columnconfigure(0, weight=1)

        self.desc1 = ctk.CTkTextbox(
            tab_1,
            font=self.FONT_TEXT,
            corner_radius=8,
            fg_color=("#0F1320", "#0F1320"),
        )
        self.desc1.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.desc1.configure(state="disabled")

        self.desc2 = ctk.CTkTextbox(
            tab_2,
            font=self.FONT_TEXT,
            corner_radius=8,
            fg_color=("#0F1320", "#0F1320"),
        )
        self.desc2.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.desc2.configure(state="disabled")

        self.desc_tabs.set("Szenario A")

        results_panel = ctk.CTkFrame(
            content,
            corner_radius=14,
            fg_color=("#181E32", "#181E32"),
            border_width=1,
            border_color=("#2A3350", "#2A3350"),
        )
        results_panel.grid(row=0, column=1, sticky="nsew")
        results_panel.grid_rowconfigure(0, weight=0)
        results_panel.grid_rowconfigure(1, weight=0)
        results_panel.grid_rowconfigure(2, weight=1)
        results_panel.grid_columnconfigure(0, weight=1)

        results_header = ctk.CTkFrame(results_panel, fg_color="transparent")
        results_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
        results_header.grid_columnconfigure(0, weight=1)
        results_header.grid_columnconfigure(1, weight=0)

        results_label = ctk.CTkLabel(
            results_header,
            text="ERGEBNISSE",
            font=self.FONT_SECTION,
            text_color=("#E5E7EB", "#E5E7EB"),
        )
        results_label.grid(row=0, column=0, sticky="w")

        view_frame = ctk.CTkFrame(results_header, fg_color="transparent")
        view_frame.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(view_frame, text="Anzeige Szenario:", font=self.FONT_TEXT).pack(
            side="left",
            padx=(0, 10),
        )
        self.result_combo = ctk.CTkComboBox(
            view_frame,
            values=["Szenario A", "Szenario B"],
            width=200,
            height=34,
            corner_radius=10,
            font=self.FONT_TEXT,
            dropdown_font=self.FONT_TEXT,
            command=self._load_result_csv,
        )
        self.result_combo.set("Szenario A")
        self.result_combo.pack(side="left")

        plot_button_frame = ctk.CTkFrame(results_header, fg_color="transparent")
        plot_button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        plot_button_frame.grid_columnconfigure(0, weight=1)
        plot_button_frame.grid_columnconfigure(1, weight=1)
        plot_button_frame.grid_columnconfigure(2, weight=1)
        plot_button_frame.grid_columnconfigure(3, weight=1)

        self.btn_plot_kpi = ctk.CTkButton(
            plot_button_frame,
            text="KPIs",
            command=lambda: self._set_result_view("kpi"),
            font=self.FONT_BUTTON,
            height=38,
            corner_radius=12,
            fg_color=("#2563EB", "#2563EB"),
            hover_color=("#1D4ED8", "#1D4ED8"),
        )
        self.btn_plot_kpi.grid(row=0, column=0, sticky="ew", padx=4)

        self.btn_plot_h2 = ctk.CTkButton(
            plot_button_frame,
            text="H2",
            command=lambda: self._set_result_view("h2"),
            font=self.FONT_BUTTON,
            height=38,
            corner_radius=12,
            fg_color=("#2563EB", "#2563EB"),
            hover_color=("#1D4ED8", "#1D4ED8"),
        )
        self.btn_plot_h2.grid(row=0, column=1, sticky="ew", padx=4)

        self.btn_plot_netz = ctk.CTkButton(
            plot_button_frame,
            text="Netzbezug",
            command=lambda: self._set_result_view("netzbezug"),
            font=self.FONT_BUTTON,
            height=38,
            corner_radius=12,
            fg_color=("#10B981", "#10B981"),
            hover_color=("#059669", "#059669"),
        )
        self.btn_plot_netz.grid(row=0, column=2, sticky="ew", padx=4)

        self.btn_plot_strom = ctk.CTkButton(
            plot_button_frame,
            text="Stromkonsum",
            command=lambda: self._set_result_view("stromkonsum"),
            font=self.FONT_BUTTON,
            height=38,
            corner_radius=12,
            fg_color=("#F59E0B", "#F59E0B"),
            hover_color=("#D97706", "#D97706"),
        )
        self.btn_plot_strom.grid(row=0, column=3, sticky="ew", padx=4)

        log_frame = ctk.CTkFrame(
            results_panel,
            corner_radius=10,
            fg_color=("#0F1320", "#0F1320"),
            border_width=1,
            border_color=("#2A314A", "#2A314A"),
        )
        log_frame.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 10))
        log_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_frame,
            text="Live-Log",
            font=("Segoe UI Semibold", 12),
            text_color=("#CBD5E1", "#CBD5E1"),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

        self.log_box = ctk.CTkTextbox(
            log_frame,
            height=110,
            font=self.FONT_LOG,
            corner_radius=8,
            fg_color=("#0B1020", "#0B1020"),
            text_color=("#93C5FD", "#93C5FD"),
        )
        self.log_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.log_box.configure(state="disabled")

        self.table_frame = ctk.CTkFrame(
            results_panel,
            corner_radius=10,
            fg_color=("#0F1320", "#0F1320"),
            border_width=0,
        )
        self.table_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(10, 14))
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)
        self.table_frame.bind("<Configure>", self._on_table_resize)

        self._show_placeholder()
        self._update_desc1(None)
        self._update_desc2(None)

    def _show_placeholder(self) -> None:
        """Zeigt Hinweistext an, solange keine Ergebnisse verfügbar sind."""
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self._table_tree = None
        self._table_columns = []

        placeholder = ctk.CTkLabel(
            self.table_frame,
            text="Klicken Sie auf 'SIMULATIONEN STARTEN', um Ergebnisse zu generieren.",
            text_color=("#9CA3AF", "#9CA3AF"),
            font=self.FONT_TEXT,
            wraplength=720,
            justify="center",
        )
        placeholder.pack(expand=True, padx=20, pady=20)

    def _toggle_parameters(self) -> None:
        """Zeigt oder versteckt die editierbaren Parameter."""
        if self.params_card.winfo_ismapped():
            self.params_card.grid_remove()
            self.btn_toggle_parameters.configure(text="Parameter anzeigen")
        else:
            self.params_card.grid()
            self.btn_toggle_parameters.configure(text="Parameter ausblenden")

    def _set_result_view(self, view: str) -> None:
        """Aktiviert eine Ansicht für KPIs oder einen Plot."""
        self._current_result_view = view
        self._refresh_result_view()

    def _refresh_result_view(self) -> None:
        """Aktualisiert den Ergebnisbereich entsprechend der aktuellen Auswahl."""
        if self._current_result_view == "kpi":
            self._display_kpi_table()
        else:
            self._display_plot_image(self._current_result_view)

    def _display_kpi_table(self) -> None:
        """Zeigt die KPI-Tabelle im Ergebnisbereich."""
        if self._current_kpi_df is None:
            self._show_placeholder()
            return

        self._display_table(self._current_kpi_df)

    def _display_plot_image(self, plot_type: str) -> None:
        """Zeigt ein gespeichertes Plot-PNG im Ergebnisbereich."""
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self._table_tree = None
        self._table_columns = []

        slot = {"Szenario A": "A", "Szenario B": "B"}.get(self.result_combo.get())
        if slot is None:
            self._show_placeholder()
            return

        plot_files = {
            "h2": f"plot_szenario_{slot}_vergleich_h2.png",
            "netzbezug": f"plot_netzbezug_szenario_{slot}_vergleich.png",
            "stromkonsum": f"plot_stromkonsum_szenario_{slot}_vergleich.png",
        }
        plot_name = plot_files.get(plot_type)
        if plot_name is None:
            self._show_placeholder()
            return

        plot_path = self.results_dir / plot_name
        if not plot_path.exists():
            label = ctk.CTkLabel(
                self.table_frame,
                text=f"Plot nicht gefunden: {plot_name}",
                text_color=("#FCA5A5", "#FCA5A5"),
                font=self.FONT_TEXT,
                wraplength=720,
                justify="center",
            )
            label.pack(expand=True, padx=20, pady=20)
            return

        image = self._load_plot_image(plot_path)
        if image is None:
            self._show_placeholder()
            return

        image_label = ctk.CTkLabel(
            self.table_frame,
            image=image,
            text="",
            fg_color="transparent",
        )
        image_label.image = image
        image_label.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)

    def _load_plot_image(self, plot_path: Path) -> ImageTk.PhotoImage | None:
        """Lädt ein PNG und skaliert es für den Ergebnisbereich."""
        try:
            image = Image.open(plot_path)
        except Exception:
            return None

        # Sicherstellen, dass die Widget-Geometrie aktuell ist
        try:
            self.table_frame.update_idletasks()
        except Exception:
            pass

        # Verfügbaren Platz (mit kleinem Padding) berechnen
        padding = 24
        max_width = max(100, self.table_frame.winfo_width() - padding)
        max_height = max(100, self.table_frame.winfo_height() - padding)

        # Proportionale Skalierung, damit das Bild den Bereich bestmöglich ausfüllt
        scale = min(max_width / image.width, max_height / image.height)
        if scale <= 0:
            scale = 1.0

        if scale != 1.0:
            new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
            image = image.resize(new_size, Image.LANCZOS)

        return ImageTk.PhotoImage(image)

    def _set_status(self, text: str, color: str) -> None:
        """Setzt Status in Sidebar und Header konsistent."""
        self.status.configure(text=text, text_color=color)
        self.status_badge.configure(text=text, text_color=color)

    def _append_log(self, message: str) -> None:
        """Hängt eine einzelne Logzeile im GUI-Logfenster an."""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _append_log_lines(self, lines: list[str]) -> None:
        """Hängt mehrere Logzeilen in einem UI-Update an."""
        if not lines:
            return
        self.log_box.configure(state="normal")
        self.log_box.insert("end", "\n".join(lines) + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        """Leert den Live-Log-Bereich vor einem neuen Simulationslauf."""
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _poll_process_events(self) -> None:
        """Liest Status-/Log-Nachrichten aus dem Simulationsprozess."""
        if self._sim_process_queue is None:
            return

        done_received = False
        error_received: str | None = None
        lines: list[str] = []

        for _ in range(50):
            try:
                kind, payload = self._sim_process_queue.get_nowait()
            except queue.Empty:
                break

            if kind == "done":
                done_received = True
            elif kind == "error":
                error_received = str(payload)
            elif kind == "log":
                lines.append(str(payload))

        self._append_log_lines(lines)

        if error_received is not None:
            self._set_status(f"Fehler: {error_received[:32]}", "#EF4444")
            self.btn.configure(state="normal")
            self._cleanup_sim_process()
            return

        if done_received:
            self._on_simulations_complete()
            return

        if self._sim_process is not None and self._sim_process.is_alive():
            self.root.after(100, self._poll_process_events)
        else:
            self.btn.configure(state="normal")
            self._set_status("Abgebrochen", "#EF4444")
            self._cleanup_sim_process()

    def _cleanup_sim_process(self) -> None:
        """Räumt Prozess- und Queue-Referenzen nach Simulationsende auf."""
        if self._sim_process is not None:
            self._sim_process.join(timeout=0.1)
        self._sim_process = None
        self._sim_process_queue = None

    def _configure_ttk_style(self) -> None:
        """Konfiguriert die visuelle Darstellung der KPI-Tabelle."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Modern.Treeview",
            background="#0F1320",
            fieldbackground="#0F1320",
            foreground="#E5E7EB",
            rowheight=38,
            bordercolor="#2A314A",
            borderwidth=0,
            font=("Segoe UI", 16),
        )
        style.configure(
            "Modern.Treeview.Heading",
            background="#1E293B",
            foreground="#F9FAFB",
            relief="flat",
            borderwidth=0,
            font=("Segoe UI Semibold", 24),
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", "#2563EB")],
            foreground=[("selected", "#FFFFFF")],
        )
        style.map(
            "Modern.Treeview.Heading",
            background=[("active", "#334155")],
        )

    def _cleanup_existing_plots(self) -> None:
        """Löscht vorhandene Plot-PNGs beim Start der GUI."""
        for plot_path in self.results_dir.glob("plot_*.png"):
            try:
                plot_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _update_desc(
        self,
        combo: ctk.CTkComboBox,
        textbox: ctk.CTkTextbox,
    ) -> None:
        """Aktualisiert den Beschreibungstext für das gewählte Szenario."""
        scenario = ScenarioManager.get_by_name(combo.get())
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.insert("1.0", scenario.description)
        textbox.configure(state="disabled")

    def _update_desc1(self, _: Any) -> None:
        """Aktualisiert Beschreibung für das erste Szenario."""
        self._update_desc(self.s1_combo, self.desc1)
        self.desc_tabs.set("Szenario A")

    def _update_desc2(self, _: Any) -> None:
        """Aktualisiert Beschreibung für das zweite Szenario."""
        self._update_desc(self.s2_combo, self.desc2)
        self.desc_tabs.set("Szenario B")

    def _compare(self) -> None:
        """Startet beide Simulationen in einem Background-Thread."""
        if self._sim_process is not None and self._sim_process.is_alive():
            return

        self.btn.configure(state="disabled")
        # Beschreibungselemente bleiben bewusst aktiv während der Simulation.
        self.s1_combo.configure(state="normal")
        self.s2_combo.configure(state="normal")
        self._set_status("Läuft", "#F59E0B")
        self._clear_log()
        self._append_log("Simulation gestartet...")
        self._show_placeholder()

        h2_capacity = self._parse_float(
            self.h2_capacity_entry.get(), "H2-Kapazität", min_value=0.0
        )
        if h2_capacity is None:
            self.btn.configure(state="normal")
            return

        h2_pressure = self._parse_float(
            self.h2_pressure_entry.get(), "H2-Druck", min_value=0.0
        )
        if h2_pressure is None:
            self.btn.configure(state="normal")
            return

        pv_area_factor = self._parse_float(
            self.pv_area_entry.get(), "PV-Fläche Faktor", min_value=0.0
        )
        if pv_area_factor is None:
            self.btn.configure(state="normal")
            return

        self._start_simulation_process(
            h2_capacity,
            h2_pressure,
            pv_area_factor,
        )

    def _parse_float(
        self,
        value: str,
        field_name: str,
        min_value: float = 0.0,
    ) -> float | None:
        """Parst einen numerischen Wert aus einem Eingabefeld."""
        try:
            parsed = float(value.strip())
        except ValueError:
            self._append_log(f"Ungültiger Wert für {field_name}: {value}")
            return None

        if parsed <= min_value:
            self._append_log(
                f"{field_name} muss größer als {min_value} sein: {parsed}"
            )
            return None

        return parsed

    def _start_simulation_process(
        self,
        h2_capacity_override_kwh: float,
        h2_pressure_bar: float,
        pv_area_factor: float,
    ) -> None:
        """Startet den Simulationslauf in einem separaten Prozess."""
        scenario_1_name = self.s1_combo.get()
        scenario_2_name = self.s2_combo.get()

        ctx = mp.get_context("spawn")
        self._sim_process_queue = ctx.Queue()
        self._sim_process = ctx.Process(
            target=_run_simulations_in_process,
            args=(
                scenario_1_name,
                scenario_2_name,
                str(self.results_dir),
                self._sim_process_queue,
                h2_capacity_override_kwh,
                h2_pressure_bar,
                pv_area_factor,
            ),
            daemon=True,
        )
        self._sim_process.start()
        self.root.after(100, self._poll_process_events)

    def _open_plot(self, plot_type: str) -> None:
        """Öffnet den gewünschten Plot als PNG-Datei."""
        scenario_map = {"Szenario A": "A", "Szenario B": "B"}
        slot = scenario_map.get(self.result_combo.get())
        if slot is None:
            self._append_log("Ungültiges Szenario ausgewählt.")
            return

        plot_files = {
            "h2": f"plot_szenario_{slot}_vergleich_h2.png",
            "netzbezug": f"plot_netzbezug_szenario_{slot}_vergleich.png",
            "stromkonsum": f"plot_stromkonsum_szenario_{slot}_vergleich.png",
        }
        plot_name = plot_files.get(plot_type)
        if plot_name is None:
            self._append_log(f"Unbekannter Plottyp: {plot_type}")
            return

        plot_path = self.results_dir / plot_name
        if not plot_path.exists():
            self._append_log(f"Plot nicht gefunden: {plot_name}")
            return

        try:
            os.startfile(plot_path)
            self._append_log(f"Öffne Plot: {plot_name}")
        except Exception as exc:
            self._append_log(f"Plot konnte nicht geöffnet werden: {exc}")

    def _on_simulations_complete(self) -> None:
        """Speichert Plots und zeigt die KPI-Tabelle nach Simulationsende."""
        self._set_status("Fertig", "#22C55E")
        self.btn.configure(state="normal")

        self._load_result_csv(self.result_combo.get())
        self._append_log("KPI-Tabelle geladen.")
        self._cleanup_sim_process()

    def _load_result_csv(self, scenario_display: str) -> None:
        """Lädt CSV-Datei für das ausgewählte Szenario und zeigt sie an.

        Args:
            scenario_display: "Szenario A" oder "Szenario B".
        """
        scenario_map = {"Szenario A": "a", "Szenario B": "b"}
        slot = scenario_map.get(scenario_display)
        if slot is None:
            self._current_kpi_df = None
            self._show_placeholder()
            return

        csv_path = self.results_dir / f"kpis_szenario_{slot}.csv"

        if not csv_path.exists():
            self._current_kpi_df = None
            self._show_placeholder()
            return

        try:
            self._current_kpi_df = pd.read_csv(csv_path)
            self._refresh_result_view()
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Fehler beim Laden der CSV: {exc}")
            self._current_kpi_df = None
            self._show_placeholder()

    def _display_table(self, df: pd.DataFrame) -> None:
        """Zeigt einen DataFrame in einer TreeView-Tabelle an."""
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        table_container = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        table_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        columns = list(df.columns)
        self._table_columns = columns
        tree = ttk.Treeview(
            table_container,
            columns=columns,
            height=15,
            style="Modern.Treeview",
        )
        tree.column("#0", width=0)

        for col in columns:
            tree.column(col, width=160, minwidth=120, anchor="center")
            tree.heading(col, text=col, anchor="center")

        for _, row in df.iterrows():
            values = [row[col] for col in columns]
            tree.insert("", "end", values=values)

        y_scrollbar = ttk.Scrollbar(
            table_container, orient="vertical", command=tree.yview
        )
        x_scrollbar = ttk.Scrollbar(
            table_container, orient="horizontal", command=tree.xview
        )
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        self._table_tree = tree
        self._fit_table_columns()

    def _on_table_resize(self, _: Any) -> None:
        """Passt Tabellenspalten an Fenstergröße an."""
        self._fit_table_columns()

    def _fit_table_columns(self) -> None:
        """Berechnet sinnvolle Spaltenbreiten für die KPI-Tabelle."""
        if self._table_tree is None or not self._table_columns:
            return

        available_width = max(self.table_frame.winfo_width() - 64, 640)
        col_width = max(140, int(available_width / len(self._table_columns)))

        for col in self._table_columns:
            self._table_tree.column(col, width=col_width, minwidth=120)


def launch() -> None:
    """Startet die Strategy-GUI."""
    root = ctk.CTk()
    StrategyGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
