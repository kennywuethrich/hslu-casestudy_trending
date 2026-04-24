"""GUI für Strategie-Vergleich."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import multiprocessing as mp
import queue
import sys
import traceback
from pathlib import Path
from tkinter import ttk
from typing import Any

import customtkinter as ctk
import pandas as pd

from plots import plot_h2_soc

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
) -> None:
    """Führt beide Simulationen in einem separaten Prozess aus."""
    log_writer = _LogQueueWriter(message_queue, sys.__stdout__, message_kind="log")
    results_dir = Path(results_dir_str)

    try:
        with redirect_stdout(log_writer), redirect_stderr(log_writer):
            print(f"Szenario 1: {scenario_1_name}")
            print(f"Szenario 2: {scenario_2_name}")

            scenario_1 = ScenarioManager.get_by_name(scenario_1_name)
            scenario_2 = ScenarioManager.get_by_name(scenario_2_name)

            simulations = [(scenario_1, 1), (scenario_2, 2)]

            for scenario, scenario_number in simulations:
                print(f"Starte Berechnung für Szenario {scenario_number}...")

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
                save_kpis_by_scenario(scenario_number, kpi_base, kpi_optimized)

                print(f"Erzeuge Plots für Szenario {scenario_number}...")
                strategy_results = {
                    "BaseStrategy": result_base,
                    "OptimizedStrategy": result_optimized,
                }
                for strat_key, result_df in strategy_results.items():
                    capacity_kwh = scenario.config.h2_capacity_kwh
                    scenario_name = scenario.name.replace(" ", "_")
                    file_name = f"plot_{scenario_name}_{strat_key}.png"
                    save_path = results_dir / file_name
                    plot_h2_soc(
                        result_df,
                        title=f"H2-Füllstand – {scenario.name} ({strat_key})",
                        save_path=str(save_path),
                        capacity_kwh=capacity_kwh,
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
        self._table_tree: ttk.Treeview | None = None
        self._table_columns: list[str] = []
        self._sim_process: mp.Process | None = None
        self._sim_process_queue: Any | None = None
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
        left_panel.grid_rowconfigure(2, weight=1)
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
        ctk.CTkLabel(selector_card, text="Szenario 1", font=self.FONT_TEXT).grid(
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

        ctk.CTkLabel(selector_card, text="Szenario 2", font=self.FONT_TEXT).grid(
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

        desc_card = ctk.CTkFrame(
            left_panel,
            corner_radius=12,
            fg_color=("#111726", "#111726"),
            border_width=1,
            border_color=("#2A314A", "#2A314A"),
        )
        desc_card.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
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

        tab_1 = self.desc_tabs.add("Szenario 1")
        tab_2 = self.desc_tabs.add("Szenario 2")
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

        self.desc_tabs.set("Szenario 1")

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
            values=["Szenario 1", "Szenario 2"],
            width=200,
            height=34,
            corner_radius=10,
            font=self.FONT_TEXT,
            dropdown_font=self.FONT_TEXT,
            command=self._load_result_csv,
        )
        self.result_combo.set("Szenario 1")
        self.result_combo.pack(side="left")

        log_frame = ctk.CTkFrame(
            results_panel,
            corner_radius=10,
            fg_color=("#0F1320", "#0F1320"),
            border_width=1,
            border_color=("#2A314A", "#2A314A"),
        )
        log_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
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
        self.table_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 14))
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
        self.desc_tabs.set("Szenario 1")

    def _update_desc2(self, _: Any) -> None:
        """Aktualisiert Beschreibung für das zweite Szenario."""
        self._update_desc(self.s2_combo, self.desc2)
        self.desc_tabs.set("Szenario 2")

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
        self._start_simulation_process()

    def _start_simulation_process(self) -> None:
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
            ),
            daemon=True,
        )
        self._sim_process.start()
        self.root.after(100, self._poll_process_events)

    def _on_simulations_complete(self) -> None:
        """Speichert Plots und zeigt die KPI-Tabelle nach Simulationsende."""
        self._set_status("Fertig", "#22C55E")
        self.btn.configure(state="normal")

        self._load_result_csv("Szenario 1")
        self._append_log("KPI-Tabelle geladen.")
        self._cleanup_sim_process()

    def _load_result_csv(self, scenario_display: str) -> None:
        """Lädt CSV-Datei für das ausgewählte Szenario und zeigt sie an.

        Args:
            scenario_display: "Szenario 1" oder "Szenario 2".
        """
        scenario_number = scenario_display.split()[-1]
        csv_path = self.results_dir / f"kpis_szenario_{scenario_number}.csv"

        if not csv_path.exists():
            self._show_placeholder()
            return

        try:
            results_df = pd.read_csv(csv_path)
            self._display_table(results_df)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Fehler beim Laden der CSV: {exc}")
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
