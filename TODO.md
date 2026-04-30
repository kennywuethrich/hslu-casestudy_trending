# TODO Trending
config: überprüfen der Daten (Datenblätter teams) [Felix] _erledigt_

allgemein: wieso 35 % auslastung in H2 [Nick] _check_


Strategy: heurastic mit casadi ersetzen [Kenny]
GUI erstellen [Kenny]
Output sinnvoller gestalten, mit Grafiken welche etwas aussagen

readme: updaten

allgemein: Klassendiagramm [Anna]

### Szenario:
in scenario.py

## 16.04.2026:

- [ ] Strompreise als API (bei EKZ) [Felix]
- [ ] Daten updaten. [Nick] _check_
- [ ] config.py kann eventuell auch noch angepasst werden. Berechnung der H2-Zelle muss nicht dort drin sein.
- [ ] profiles.py kann noch angepasst werden. EV-Berechnung muss nicht dort sein. ev. in components.py verschieben...?
- [ ] plots.py muss noch erstellt werden. <-- erste Probe gemacht 

GUI: 

EV: as_is oder daytime in szenario (GUI) einbauen. also daten der elektro autos.



analyzer.py _check_
profiles.py _check_    <-- Muss eventuell nochmals überarbeiten werden wegen EV
scenario.py _check_   <-- Aktuell 2 Szenarien drin. kann beliebig erweitert werden. 
dispatch.py _check_ 
strategies.py _check_
simulator.py _check_

Aktuell vergleichen wir die beiden Szenarien, ist aber nicht das Ziel. wir wollen je szenario die Strategien vergleichen... muss noch implementiert werden ~kenny <-- Habe ich umgebaut. aktuell vergleichen wir die beiden Strategien pro 

## 23.04.2026
- config.py entkoppeln, damit die API-Abfrage nicht mehr im Konstruktor läuft und keine Seiteneffekte bei jedem Import entstehen._check_
- scenario.py und simulator.py bereinigen, damit Szenarien, Strategien und Ergebnisobjekte klarer getrennt sind. _check_
- Ein kleines Verifikations-Setup ergänzen, damit Pylint, Tests und eventuell ein einfacher Smoke-Test regelmäßig laufen _check_

## 07.05.2026

Alles Funktionsfähig. Code soweit fertig
Wochentage ändern (Anna)
Plots darstellen: (Felix)
H2 Verlauf Jahr
Netzbezug Jahr
reiter gui (Nick)


## 23.05.2026

Abgabe Doku

## 28.05.2026

Präsentation

