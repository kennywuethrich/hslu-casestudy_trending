# H2-Microgrid Simulation

Schlanke Simulation fuer ein PV-H2-WP-System mit CSV-Lastprofilen.

Ziel: einfache Struktur, klare Verantwortlichkeiten, leichter Refactor.

## Projektstruktur

```text
Casestudy/
|- main.py         # Einstieg und Szenario-Runner
|- simulator.py    # Ablauf: Profile -> Strategien -> KPIs/Plots -> Export
|- config.py       # Zentrale Parameter und H2-Physik
|- scenario.py     # Vordefinierte Szenarien
|- profiles.py     # CSV-Import und Zeitachsen-Aufbereitung
|- strategies.py   # Strategie-Policies (nur Entscheidungsregeln)
|- dispatch.py     # Gemeinsame Dispatch-Engine (physische Bilanz)
|- components.py   # Komponentenmodelle (H2, ELY, FC, WP, thermischer Speicher)
|- analyzer.py     # KPI-Berechnung und Jahresplots
|- data/
|  |- generate_data.py
|  |- data_annaheer_1h.csv
|  |- data_annaheer_15min.csv
|- results/
```

## Architektur in 30 Sekunden

1. profiles.py liefert einheitliche Zeitschritt-Daten.
2. strategies.py waehlt nur noch, wann FC laufen darf.
3. dispatch.py macht die komplette Energiebilanz pro Zeitschritt.
4. analyzer.py berechnet KPIs und erzeugt Jahresplots.
5. simulator.py orchestriert alles und exportiert CSV-Dateien.

Damit liegt die komplexe Physik nur an einer Stelle: dispatch.py.

## Schnellstart

```bash
python main.py
```

Programmatisch:

```python
from main import run_scenario

simulator = run_scenario('A_reference', include_plots=True)
print(simulator.get_kpis_summary())
```

Alle Szenarien vergleichen:

```python
from main import compare_all_scenarios

compare_all_scenarios()
```

## Szenarien

- A_reference: Baseline.
- B_high_price: hoeherer Strompreis, bessere Einspeiseverguetung.
- C_workplace: alternative EV-Ladecharakteristik im Datenset.

## Aktive Visualisierungen

- H2-SOC Jahresverlauf (Tag-Min/Tag-Mittel/Tag-Max).
- Jahresuebersicht der Energiestroeme (monatlich und kumuliert).
- KPI-Vergleich bei Szenariovergleichen.

## Datenschema fuer CSV-Import

Pflichtspalten:

- datetime
- pv_kw
- load_el_kw
- load_heat_kw
- ev_demand_kw

Hinweis: datetime wird mit UTC geparst und nach Europe/Zurich konvertiert.

## Wichtigste Konfigurationspunkte

- time_resolution: 1h oder 15min.
- H2-Tank ueber Volumen, Druck, Temperatur.
- Optional Overwrites fuer H2-Dichte, H2-Masse oder H2-Kapazitaet.
- FC-Regeln ueber fc_reserve_soc_target, fc_peak_shaving_kw, fc_dispatch_max_kw.

## Design-Regeln im Code

- Neue Strategie: nur in strategies.py Policy ergaenzen.
- Keine physische Bilanz in strategies.py duplizieren.
- Dispatch-Anpassungen zentral in dispatch.py.
- KPI/Plot-Aenderungen nur in analyzer.py.

## Typische Befehle

```bash
python main.py
python -c "from main import run_scenario; run_scenario('A_reference', include_plots=True)"
python data/generate_data.py
```
