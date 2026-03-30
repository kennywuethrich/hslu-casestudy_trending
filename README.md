# H2-Microgrid Simulation

Schlanke Simulation für ein PV-H2-WP-System mit CSV-Lastprofilen.

Ziel: einfache Struktur, klare Verantwortlichkeiten und gut lesbarer Code.

## Gesamtübersicht der Modellfunktionalität

Das Modell simuliert ein Jahr in diskreten Zeitschritten.

Pro Zeitschritt passiert immer die gleiche Reihenfolge:

1. Profile laden: PV, elektrische Last, Wärmebedarf, EV-Ladebedarf.
2. Strategieentscheidung: Darf die Brennstoffzelle genutzt werden oder nicht.
3. Elektrische Bilanz: PV-Überschuss in Elektrolyse, Defizit via Brennstoffzelle oder Netz.
4. Thermische Bilanz: Abwärme + thermischer Speicher + Wärmepumpe.
5. KPI-Auswertung: Netzbezug, Einspeisung, Kosten, CO2, MAC, Autarkie.

So bleibt klar getrennt:

- Strategien bestimmen nur Regeln.
- Dispatch macht die Physik und Bilanz.
- Analyzer macht KPI/Plots, Simulator macht Ausgabe und Export.

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
|  |- data_anna-heer_1h.csv
|  |- data_anna-heer_15min.csv
|- results/
```

## Übersicht fürs Verständnis

Wenn du neu im Projekt bist, lies die Dateien in dieser Reihenfolge:

1. config.py: Welche Parameter steuern das System.
2. scenario.py: Welche Szenarien vorhanden sind.
3. profiles.py: Welche Eingangsdaten wirklich in die Simulation gehen.
4. strategies.py: Was Heuristic und PriceBased unterscheiden.
5. dispatch.py: Kernbilanz pro Zeitschritt.
6. analyzer.py: Wie KPI und Plots erzeugt werden.
7. simulator.py und main.py: Orchestrierung, Ausgabe und Einstiegspunkte.

## Architektur in 30 Sekunden

1. profiles.py liefert einheitliche Zeitschritt-Daten.
2. strategies.py wählt nur noch, wann FC laufen darf.
3. dispatch.py macht die komplette Energiebilanz pro Zeitschritt.
4. analyzer.py berechnet KPIs und stellt Plot-Funktionen bereit.
5. simulator.py orchestriert Ablauf, Ausgabe und Export.

Damit liegt die komplexe Physik nur an einer Stelle: dispatch.py.

## Abkürzungs-Glossar

- H2: Wasserstoff
- SOC: State of Charge (Ladezustand)
- EV: Electric Vehicle (E-Auto)
- ELY: Elektrolyseur
- FC: Fuel Cell (Brennstoffzelle)
- HP / WP: Heat Pump / Wärmepumpe
- COP: Coefficient of Performance (Leistungszahl der Wärmepumpe)
- KPI: Key Performance Indicator
- MAC: Marginal Abatement Cost

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
- B_high_price: höherer Strompreis, bessere Einspeisevergütung.
- C_workplace: EV-Profil wird je Tag in das Fenster 08:00-17:00 umgelegt.

Hinweis: EV-Lastverlauf kommt derzeit direkt aus der gewählten CSV-Datei.
Im Modus daytime wird nur die zeitliche Verteilung pro Tag verschoben; die Tagesenergie bleibt gleich.

## Aktive Visualisierungen

- H2-SOC Jahresverlauf (Tag-Min/Tag-Mittel/Tag-Max).
- Jahresübersicht der Energieströme (monatlich und kumuliert).
- KPI-Vergleich bei Szenariovergleichen.

## Datenschema für CSV-Import

Pflichtspalten:

- datetime
- pv_kw
- load_el_kw
- load_heat_kw
- ev_demand_kw

Hinweis: _datetime_ wird mit UTC geparst und nach Europe/Zurich konvertiert.

## Modellgrenzen

- Das Modell ist regelbasiert, nicht optimierungsbasiert.
- Preisverlauf ist standardmässig konstant, ausser wenn Szenarien ihn ändern.
- EV-Logik ist Lastprofil-getrieben (kein fahrzeugindividuelles Flottenmodell).
- Thermik ist vereinfacht, aber bilanziell konsistent.

## Wichtigste Konfigurationspunkte

- time_resolution: 1h oder 15min.
- H2-Tank über Volumen, Druck, Temperatur.
- Optional Overwrites für H2-Dichte, H2-Masse oder H2-Kapazität.
- FC-Regeln über fc_reserve_soc_target, fc_peak_shaving_kw, fc_dispatch_max_kw.

## Design-Regeln im Code

- Neue Strategie: nur in strategies.py Policy ergänzen.
- Keine physische Bilanz in strategies.py duplizieren.
- Dispatch-Anpassungen zentral in dispatch.py.
- KPI/Plot-Änderungen nur in analyzer.py.

## Typische Befehle

```bash
python main.py
python -c "from main import run_scenario; run_scenario('A_reference', include_plots=True)"
python data/generate_data.py
```
