# H2-Microgrid Simulation

Simulation eines PV-H2-WP-Mikrogrids mit zwei Strategien pro Szenario.

Das Projekt vergleicht, wie sich unterschiedliche Betriebsstrategien auf
Kosten, CO2, Autarkie, Netzbezug und H2-Speicherverlauf auswirken.

## Was der User macht

1. Szenarien in der GUI auswählen.
2. Auf "SIMULATIONEN STARTEN" klicken.
3. KPI-Tabelle und Log in der GUI anschauen.
4. CSV- und Plot-Dateien in `results/` verwenden.

## Was der User erwarten kann

- Pro ausgewähltem Szenario werden zwei Strategien gerechnet:
  `BaseStrategy` und `OptimizedStrategy`.
- Ergebnis als KPI-CSV je Szenario:
  `results/kpis_szenario_1.csv`, `results/kpis_szenario_2.csv`.
- H2-SOC-Plots als PNG in `results/`.
- Live-Log in der GUI während des Laufs.

## Einstiegspunkte

- GUI (empfohlen):

```bash
python .\gui\gui_main.py
```

- CLI-Variante (Standardszenario):

```bash
python main.py
```

## Technischer Ablauf (aktueller Code)

1. GUI startet in `gui/gui_main.py` über `main()` und ruft `launch()` auf.
2. `StrategyGUI` in `gui/gui.py` baut die Oberfläche und bietet zwei
	Szenario-Comboboxen.
3. Beim Start-Button ruft `_compare()` einen separaten Prozess auf
	(`_run_simulations_in_process`), damit die GUI responsiv bleibt.
4. Für jedes Szenario:
	- `ScenarioManager.get_by_name()` liefert `Scenario` + `SystemConfig`.
	- `load_profiles()` in `profiles.py` liest die CSV-Profile und erzeugt
	  den stundenweisen Input-DataFrame.
	- `simulate()` in `simulator.py` führt die Zeitschritt-Simulation aus.
	- `calculate_kpis()` in `analyzer.py` berechnet Kennzahlen.
	- `save_kpis_by_scenario()` speichert KPI-CSV.
	- `plot_h2_soc()` in `plots.py` erzeugt H2-Füllstand-Plots.
5. GUI lädt anschliessend die KPI-CSV und zeigt sie als Tabelle an.

## Wie Entscheidungen getroffen werden

`strategies.py` enthält die Betriebslogik:

- `BaseStrategy.decide(state, profile_t)`:
  regelbasiert (Wenn-Dann) für Elektrolyseur, Brennstoffzelle,
  Wärmepumpe und EV-Laden.
- `OptimizedStrategy.decide(state, profile_t)`:
  erweitert die Basislogik um preis- und SOC-basierte Entscheidungen
  (z.B. günstigen Strom einlagern, proaktiver FC-Einsatz,
  Smart Charging EV).

Rückgabe ist immer ein `Decision`-Objekt mit Sollleistungen in kW:
`P_ely_kw`, `P_fc_kw`, `P_hp_kw`, `P_ev_charge_kw`.

## Was im Simulator passiert

`simulate()` in `simulator.py` verbindet Strategie und Physik:

1. Erstellt `EnergySystemModel(config)`.
2. Holt den Anfangszustand über `initial_state()`.
3. Läuft über alle Zeitschritte:
	- Strategie entscheidet mit `decide(...)`.
	- Physik rechnet mit `step(...)`.
	- `step_log` wird gespeichert.
4. Gibt ein DataFrame zurück: Profilspalten + Simulationsspalten.

## Physikalisches Modell

`physics_model.py` ist das Rechenherz. `EnergySystemModel.step(...)`
aktualisiert pro Stunde:

- H2-Speicher (Massenbilanz)
- Raumtemperatur (vereinfachtes RC-Modell)
- thermischen Speicher
- EV-SOC
- Strombilanz (Netzimport/Netzeinspeisung)

Der Zustand wird in `SystemState` gehalten.
Strategieausgaben kommen als `Decision`.

## Daten und Speicherung

### Eingabedaten (`data/`)

- `electricity_demand_profile.csv`
- `heat_demand_profile.csv`
- `pv_yield_profile.csv`

`load_profiles()` mappt diese auf die Modellspalten:

- `load_el_kw`, `load_heat_kw`, `pv_kw`, `outdoor_temp_c`
- `ev_driven_kwh` (aktuell aus `_build_ev_profile`, standardmässig 0)
- `price_buy`, `price_sell`, `co2_intensity`, `dt_h`

### Ausgabedaten (`results/`)

- KPI-CSV je Szenario (`kpis_szenario_X.csv`)
- H2-Plot-PNG je Szenario und Strategie

## Wo der User typischerweise ändert

1. Szenarien anpassen oder erweitern:
	`scenario.py` (`SCENARIOS`)
2. Systemparameter ändern:
	`config.py` (`SystemConfig`)
3. Strategielogik ändern:
	`strategies.py`
4. EV-Profil modellieren:
	`profiles.py`, Funktion `_build_ev_profile()`

## Setup

```bash
pip install -r requirements.txt
```

Optional mit Conda-Umgebung (wie im Projekt genutzt):

```bash
conda activate trending
```

## Tests

```bash
pytest
```

Hinweis: In Tests wird der API-Preisabruf in der Regel deaktiviert,
damit die Tests reproduzierbar offline laufen.
