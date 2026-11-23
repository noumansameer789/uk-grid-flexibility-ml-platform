# GridFlex GB Power BI report inputs

The three prepared tables reproduce the portfolio's retrospective back-test. Power BI Desktop authoring and validation are pending. The supplied kit contains the data, DAX and theme. There is no verified PBIX, PDF or page capture in this directory.

## What the data shows

| Planned report page | Result reproduced from the CSVs |
|---|---|
| Grid carbon intensity | Across 9,792 half-hours, mean GB intensity was 116.3 gCO₂/kWh. The lowest hourly mean was 78.6 at 12:00 UTC and the highest was 153.5 at 19:00 UTC. The April mean was 93.4. |
| Forecast accuracy | The seven-day mean had the lowest overall MAE, 35.46 gCO₂/kWh, against 36.61 for LightGBM. LightGBM's nominal 90% intervals covered 86.3% of targets. |
| Smart charging back-test | Across 168 historical simulations, the scheduled plan reduced the aggregate average-grid-intensity proxy by 30.75% versus immediate charging. It had a lower proxy in 148 scenarios and a higher proxy in 20. |

LightGBM had lower MAE than the seven-day mean at each half-hour horizon through 6.5 hours. At seven hours the two were close, 34.15 and 34.16 gCO₂/kWh respectively. From 7.5 through 24 hours, the seven-day mean had lower MAE at every horizon. Persistence had lower MAE than LightGBM through four hours. Issue times have overlapping target windows, so these are descriptive comparisons. The candidate failed its release gate and the live demo serves the seven-day mean. [Per-horizon calculations](../docs/evidence/completion-2026-11-23/powerbi-data.txt) · [Back-test results](../docs/evidence/RESULTS.md) · [Later holdout decision](../reports/temporal_holdout/results.json)

The charging comparison uses a fixed default battery and historical average grid intensity. It measures a carbon proxy in simulation. Physical charging, marginal emissions and commercial outcomes require separate evidence. [Charging evaluation](../docs/evidence/charging-evaluation.csv) · [Study limitations](../README.md)

## Build the three pages

Follow the [Desktop walkthrough](WALKTHROUGH.md) for the import types, relationships, 17 measures, visual fields, DAX checks and export steps. The [calculated table and measures](measures.dax) and [GridFlex theme](gridflex-theme.json) are supplied with the kit.

| Input | Rows | One row represents |
|---|---:|---|
| [Carbon.csv](data/Carbon.csv) | 9,792 | One UTC half-hour of observed and NESO-forecast GB carbon intensity |
| [Backtest.csv](data/Backtest.csv) | 40,320 | One issue time, target slot and model, across five models |
| [Charging.csv](data/Charging.csv) | 168 | One simulated charging start |
| `DimDate`, calculated in Desktop | 204 dates in the input range | One day, 1 March to 20 September 2026 inclusive |

## Reproduce the inputs

From the repository root, with pandas available, run the [supplied generator](make_powerbi_data.py).

```powershell
python powerbi/make_powerbi_data.py . powerbi/data
```

The inputs are the [reference carbon series](../data/reference/carbon.csv), [extended back-test](../docs/evidence/extended-backtest.csv.gz) and [charging scenarios](../docs/evidence/charging-evaluation.csv). The standard Windows run reproduced every field and wrote CRLF line endings. A second run of the same generator with LF selected reproduced every byte of the three supplied CSVs. Both sets of hashes, the command and the numerical checks are in the [verification output](../docs/evidence/completion-2026-11-23/powerbi-data.txt).

## How it was made

Nouman Sameer supplied the report kit. Its original notes credit AI assistance for the preparation script, DAX definitions and page plan. OpenAI Codex (GPT-6) rebuilt the tables, checked the numbers independently from the CSVs and wrote the Desktop walkthrough. The verification record identifies the source revision and distinguishes those calculations from a future read-back in Power BI Desktop. [Verification output](../docs/evidence/completion-2026-11-23/powerbi-data.txt)
