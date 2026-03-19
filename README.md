# H2-Microgrid Energiesystem Simulation (OOP)

Eine moderne, objektorientierte Simulation eines Wasserstoff-Energiesystems mit PV, Elektrolyseur, Brennstoffzelle und Wärmepumpe.

## 🎯 Überblick

Diese Simulation modelliert ein komplexes Energiesystem für einen Wohnkomplex mit:

| Komponente | Kapazität | Funktion |
|-----------|-----------|----------|
| **PV-Anlage** | 87 kWp | Solarstromproduktion |
| **Elektrolyseur** | 33 kW | H₂-Produktion aus Strom |
| **H₂-Speicher** | 7650 kWh | Wasserstoff-Speicherung |
| **Brennstoffzelle** | 34 kW | Stromerzeugung aus H₂ |
| **Wärmepumpe** | 95 kW | Wärmeproduktion |
| **E-Auto** | 40 kWh | Batterie-Elektromobilität |

## 📁 Projektstruktur

```
Casestudy/
├── __init__.py           # Paketinitialisierung
├── main.py              # Benutzerfreundlicher Einstiegspunkt
├── config.py            # Systemkonfiguration & Parameter
├── components.py        # H2-System Komponenten
├── profiles.py          # Energie-Lastprofile-Generator
├── strategies.py        # Betriebsstrategien (Heuristik, Preis)
├── analyzer.py          # KPI-Berechnung & Visualisierung
├── scenario.py          # Szenarien-Definitionen
├── simulator.py         # Hauptsimulations-Engine
└── README.md           # Diese Datei
```

### 🏗️ Architektur-Übersicht

```
main.py (Einstiegspunkt)
    ↓
Simulator (Koordinator)
    ├─→ ProfileGenerator (Lastprofile)
    ├─→ Strategy (Heuristic/PriceBased)
    │   ├─→ Components (H2Storage, ELY, FC, HP)
    │   └─→ Profiles (Input-Daten)
    └─→ ResultAnalyzer (KPIs & Plots)
```

## 🚀 Schnelleinstieg

### 1. **Interaktiver Modus (Standard)**

```bash
python main.py
```

Das Programm führt Sie durch folgende Schritte:
1. Szenario-Auswahl (A, B oder C)
2. Profil-Generierung (Jahresprofile)
3. Strategie-Simulation (Heuristik & Preisbasis)
4. Ergebnis-Ausgabe (KPIs und Plots)
5. Automatischer Export (CSV)

### 2. **Programmatischer Modus (Python-Skript)**

```python
from main import run_scenario

# Schnell ein Szenario starten
simulator = run_scenario('A_reference')

# Ergebnisse abrufen
kpis = simulator.get_kpis_summary()
print(kpis)
```

### 3. **Alle Szenarien vergleichen**

```python
from main import compare_all_scenarios

# Führt A, B und C aus und vergleicht sie
simulators = compare_all_scenarios()
```

## 📊 Szenarien

### Szenario A: Referenz (Abend-Laden)
- **Strompreis:** 0.28 CHF/kWh (moderate Preise)
- **E-Auto Laden:** 18:00-22:00 Uhr (abends)
- **Beschreibung:** Baseline-Szenario mit moderaten Bedingungen

### Szenario B: Hohe Strompreise
- **Strompreis:** 0.38 CHF/kWh (erhöht)
- **Einspeisevergütung:** 0.16 CHF/kWh (bessere Vergütung)
- **E-Auto Laden:** Abends
- **Beschreibung:** Höhere Preisvolatilität → Mehr Speicheranreize

### Szenario C: Workplace Charging
- **Strompreis:** 0.28 CHF/kWh
- **E-Auto Laden:** 08:00-17:00 Uhr (tagsüber am Arbeitsplatz)
- **Beschreibung:** PV-optimiertes E-Auto Lademanagement

## 🎮 Betriebsstrategien

### Strategie 1: Heuristische Eigenverbrauchsoptimierung
```
Priorisierung:
1. PV → direkt an Last
2. Überschuss → Elektrolyseur (H₂ produzieren)
3. H₂ im Speicher → Brennstoffzelle (bei Defizit)
4. Noch fehlender Strom → vom Netz
```

Ideal für: **Einfache, nachvollziehbare Steuerung**

### Strategie 2: Preisbasierte Optimierung
```
Logik:
- ELY: Nur bei Strompreis < Schwellenwert (0.20 CHF/kWh)
- BZ: Bevorzugt bei Strompreis > Schwellenwert (0.30 CHF/kWh)
- Ziel: Wirtschaftliche Optimierung
```

Ideal für: **Marktoptimierte Betriebsweise**

## 📈 Key Performance Indicators (KPIs)

Die Simulation berechnet automatisch:

| KPI | Einheit | Bedeutung |
|-----|---------|-----------|
| **Autarkiegrad** | % | Anteil Last ohne Netzbezug |
| **Netzbezug** | kWh/a | Gesamter Stromimport |
| **Netzeinspeisung** | kWh/a | Gesamte Stromexporte |
| **Energiekosten** | CHF/a | Jährliche Stromkosten |
| **CO₂-Emissionen** | tCO₂/a | Treibhausgasemissionen |
| **MAC** | CHF/tCO₂ | Vermeidungskosten pro Tonne CO₂ |
| **H₂-Erzeugung** | kWh/a | Wasserstoff-Produktion |

## 💻 Erweiterte Verwendung

### Custom Szenario erstellen

```python
from config import SystemConfig
from scenario import ScenarioManager, Scenario
from simulator import Simulator

# Custom Konfiguration
config = SystemConfig(
    pv_kwp=100,              # Größere PV
    price_buy_chf=0.30,      # Custom Preis
    hp_cop=4.0,              # Bessere WP
)

# Custom Szenario
scenario = ScenarioManager.create_custom(
    name="Mein Custom-Szenario",
    config=config,
    ev_mode='daytime',
    description="Erhöhte PV-Kapazität"
)

# Simulation starten
sim = Simulator(scenario)
profiles = sim.generate_profiles()
sim.run_all_strategies(profiles)
sim.print_results()
```

### Nur eine Strategie simulieren

```python
from config import SystemConfig
from strategies import HeuristicStrategy
from profiles import ProfileGenerator
from simulator import Simulator
from scenario import Scenario

config = SystemConfig()
scenario = Scenario("Test", config)
sim = Simulator(scenario)

# Profile generieren
profiles = sim.generate_profiles()

# Nur Heuristik
strategy = HeuristicStrategy(config)
results, kpis = sim.run_strategy(strategy, profiles)

print(kpis)
```

### Ergebnisse exportieren

```python
simulator.export_results(csv_filepath="meine_ergebnisse.csv")
```

Exportierte Dateien:
- `meine_ergebnisse_HeuristicStrategy.csv` – Stundenweise Werte
- `meine_ergebnisse_PriceBasedStrategy.csv` – Stundenweise Werte
- `alle_szenarien_kpi.csv` – Zusammenfassung KPIs

## 📊 Visualisierungen

Die Simulation erzeugt automatisch:

1. **Wochenprofil (Sommer)**
   - Strombilanz (PV, Last, Import/Export)
   - H₂-System (ELY, BZ, Abwärme)
   - H₂-Speicherstand

2. **Wochenprofil (Winter)**
   - Gleiche Diagramme für Winterwoche

3. **KPI-Vergleich**
   - 4-Panel Vergleich aller Strategien/Szenarien
   - Autarkiegrad, Kosten, CO₂, MAC

## 🔧 Konfigurationsparameter

Alle Parameter sind in `config.py` zentral definiert:

```python
@dataclass
class SystemConfig:
    # Anlagenleistungen [kW]
    pv_kwp: float = 87.0
    ely_kw_max: float = 33.0
    fc_kw_max: float = 34.0
    hp_kw_th_max: float = 95.0
    
    # Speicher
    h2_capacity_kwh: float = 7650.0
    h2_initial_soc: float = 0.3  # 30%
    h2_min_soc: float = 0.05     # 5% Reserve
    
    # Wirkungsgrade
    ely_eff_el: float = 0.65
    fc_eff_el: float = 0.50
    hp_cop: float = 3.5
    
    # Kosten & CO₂
    price_buy_chf: float = 0.28
    price_sell_chf: float = 0.10
    co2_grid_kg_kwh: float = 0.128
```

## 🐛 Troubleshooting

### "Modul nicht gefunden"
```bash
# Stelle sicher, dass du im Casestudy-Verzeichnis bin
cd c:\Users\Kenny\Documents\HSLU\Semester_4\TRENDING\02_Code\Casestudy
```

### Plots werden nicht angezeigt
```python
import matplotlib
matplotlib.use('TkAgg')  # Oder 'Qt5Agg'
```

### H₂-Speicher läuft leer
→ Ist die Elektrisierung groß genug? Wechsel zu Szenario B (höhere Preise) oder erhöhe PV-Kapazität.

## 📚 Klassenbeschreibungen

### `Simulator`
- Hauptkoordinator für Simulation
- Verwaltet Profile, Strategien und Ergebnisse
- `run_all_strategies()` – Alle Strategien ausführen

### `Scenario`
- Definiert ein Simulationsszenario
- Enthält Config + EV-Mode + Beschreibung

### `Strategy` (Abstract)
- Basis für alle Betriebsstrategien
- Konkrete Klassen: `HeuristicStrategy`, `PriceBasedStrategy`

### `ResultAnalyzer`
- Berechnet KPIs
- Erstellt Visualisierungen
- Exportiert Ergebnisse

### `ProfileGenerator`
- Generiert synthetische Jahresprofile
- `generate_annual_profiles()` – PV, Last, Wärme, Preise

### Komponenten (`components.py`)
- `H2Storage` – Wasserstoff-Speicher
- `Electrolyzer` – Elektrolyseur
- `FuelCell` – Brennstoffzelle
- `HeatPump` – Wärmepumpe

## 📝 Beispielskripte

### Beispiel 1: Einfache Simulation
```python
#!/usr/bin/env python
from main import run_scenario

# Szenario A ausführen
sim = run_scenario('A_reference')
print("Simulation abgeschlossen!")
```

### Beispiel 2: Sensitivitätsanalyse
```python
from config import SystemConfig
from scenario import Scenario
from simulator import Simulator

for hp_cop in [2.5, 3.0, 3.5, 4.0]:
    config = SystemConfig(hp_cop=hp_cop)
    scenario = Scenario(f"HP-COP:{hp_cop}", config)
    sim = Simulator(scenario)
    profiles = sim.generate_profiles()
    sim.run_all_strategies(profiles)
    kpis = sim.get_kpis_summary()
    print(f"COP {hp_cop}: Autarky {kpis[0]['Autarkiegrad [%]']}%")
```

### Beispiel 3: Alle Szenarien parallel vergleichen
```python
from main import compare_all_scenarios

compare_all_scenarios(export=True)
```

## 🎓 Was du gelernt hast

Diese OOP-Struktur zeigt Best Practices:

✅ **Separation of Concerns** – Jede Klasse hat eine Aufgabe  
✅ **Wiederverwendbarkeit** – Code ist modular und erweiterbar  
✅ **Testbarkeit** – Einzelne Komponenten können isoliert getestet werden  
✅ **Wartbarkeit** – Änderungen beeinflussen nicht den ganzen Code  
✅ **Skalierbarkeit** – Neue Strategien/Szenarien leicht hinzufügbar  

## 📖 Ressourcen

- **Energieeffizeiz:** Schweizer Stromnetzmix ~128 g CO₂/kWh
- **Wasserstoff:** LHV ~3.0 kWh/Nm³
- **Wärmepumpen:** COP typischerweise 3-4

## 🔄 Zukünftige Erweiterungen

- [ ] Anbindung echter Wetterdaten
- [ ] Mehrjahresanalyse mit Degradation
- [ ] Probabilistische Analysen
- [ ] Marktpreisimport (EPEX)
- [ ] Web-Interface
- [ ] Unit-Tests

## 📧 Support

Bei Fragen oder Verbesserungsvorschlägen: Kontaktiere deinen Betreuer.

---

**Version:** 1.0.0  
**Datum:** März 2026  
**Autor:** H2-Microgrid Team
