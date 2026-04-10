# H2-Microgrid Simulation

Schlanke Simulation für ein PV-H2-WP-System mit CSV-Lastprofilen.

## Kurzidee

Ein Standardszenario, zwei Strategien, eine gemeinsame Dispatch-Logik.

## Ablauf

1. `profiles.py` liest die CSV-Daten ein.
2. `strategies.py` entscheidet nur über den FC-Einsatz.
3. `dispatch.py` berechnet die physische Energiebilanz.
4. `analyzer.py` berechnet KPIs und Plots.
5. `simulator.py` orchestriert den Ablauf.
6. `main.py` startet das Standardszenario.

## Projektstruktur

```text
Casestudy/
|- main.py
|- simulator.py
|- config.py
|- scenario.py
|- profiles.py
|- strategies.py
|- dispatch.py
|- components.py
|- analyzer.py
|- data/
|- results/
```

## Aktive Bausteine

- `scenario.py`: ein Default-Szenario für den aktuellen Stand.
- `strategies.py`: `HeuristicStrategy` und `PriceBasedStrategy`.
- `dispatch.py`: Kernbilanz je Zeitschritt.
- `analyzer.py`: KPI-Berechnung und Visualisierung.

## Schnellstart

```bash
python main.py
```

## Wichtige Parameter

- `time_resolution`: `1h` oder `15min`
- `price_buy_chf` und `price_sell_chf`
- `h2_tank_volume_m3`, `h2_pressure_bar`, `h2_temperature_c`
- `fc_reserve_soc_target`, `fc_peak_shaving_kw`, `fc_dispatch_max_kw`

## CSV-Schema

Pflichtspalten:

- `datetime`
- `pv_kw`
- `load_el_kw`
- `load_heat_kw`
- `ev_demand_kw`

## Hinweis

Der Code ist bewusst reduziert. Wenn neue Szenarien oder MPC später wieder gebraucht werden, sollten sie als klar getrennte Erweiterung ergänzt werden.
