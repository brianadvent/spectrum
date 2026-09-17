# SPE wiederholen

Dieses Repository enthält 144 Handlungsbeschreibungen auf Deutsch und Englisch, hervorgegangen aus 48 Delphi-Prinzipien in acht Dimensionen. Erhobene Forschungsdaten bleiben im [SPE Explorer](https://spe-explorer.autenrieth-partner.de).

## Kostenfreier Einstieg

Python ab 3.12 und uv unter macOS/Linux beziehungsweise Windows mit WSL:

```sh
uv sync --frozen
uv run python tools/validate.py
uv run python tools/run_spe.py --provider openai
uv run python tools/run_spe.py --provider anthropic --language en
uv run python -m unittest discover -s tests -v
```

Diese Befehle starten keine Modellaufrufe. Die vollständigen Befehle für einen ausdrücklich aktivierten kostenpflichtigen Preflight, Vollrun und die Auswertung stehen in der [Hauptanleitung](../README.md).

Deutsch ist das Originalprotokoll. Englisch wurde redaktionell geprüft, ist aber eine eigene Sprachbedingung ohne belegte Messäquivalenz. IDs und Prinzipzuordnungen stimmen überein; JSON und CSV sind direkt nutzbar.

Ein Vollrun umfasst 10.296 Paare mit je zehn Entscheidungen und balancierter A/B-Anordnung. Die Anzahl physischer API-Versuche einschließlich Wiederholungen wird separat begrenzt. Modell, Sprache, Instrumenthash und Protokoll werden gespeichert; Wiederaufnahme verlangt dieselbe Konfiguration.

Nichtentscheidungen werden nicht als Wahl von B gewertet. Nur vollständige Paare werden ausgewertet; Gleichstände werden aus der gerichteten Genauigkeit und den strikten Transitivitätsvergleichen ausgeschlossen. Utilities drücken relative Präferenz innerhalb des Instruments aus, keine pädagogische Qualität.

Items und Dokumentation: CC BY 4.0. Eigener Code: MIT. Zitierinformationen stehen in `CITATION.cff`.
