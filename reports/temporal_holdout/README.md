# Later temporal holdout

A fixed residual LightGBM candidate was frozen using the original March–September data before fetching the additional 960 observations. The earlier walk-forward folds are development evidence, not an untouched test for this new candidate. The later period is a retrospective temporal holdout, not prospective operating performance.

The candidate models the correction to the seven-day same-clock mean, using the original history/calendar features plus the seasonal baselines and recent differences. Its development MAE improved to 33.59 from 35.46. On the later holdout it achieved 46.73, versus persistence at 46.22. Its nominal 90% intervals covered only 82.4% of targets. The predeclared promotion gate failed.

The original LightGBM's later MAE was 45.95, but interval coverage was only 78.6%; a small numerical advantage is not proof of robust superiority. This result does not replace the earlier evaluation or justify deploying either candidate as a reliable production model.

- `protocol.json`: fixed features, parameters, data/model digests, dates and gate.
- `candidate.txt`: native LightGBM model, trained before the holdout.
- `observations.csv`: 960 additional NESO intervals.
- `data/raw/neso/`: timestamped response snapshots.
- `predictions.csv`: every forecast/target pair, including all baselines.
- `results.json`: metrics, exploratory paired block interval and failed promotion decision.

There are 76 complete forecast origins and 3,648 forecast-target rows; these are overlapping horizons, not independent observations. The final available complete target window ends 10 October 2026 at 17:30 UTC. Historical actuals may have been revised. A short seasonal span and 19 issue days limit inference. The bootstrap interval is exploratory.

Verify the committed model predictions, six-model metrics and input digests without network access using `PYTHONPATH=src python scripts/holdout_study.py verify`. Reproduce candidate development with `PYTHONPATH=src python scripts/holdout_study.py develop --output reports/my-new-study`, then run `holdout --output reports/my-new-study`; later source revisions may change results. The script deliberately refuses to overwrite the frozen study. Install the project requirements first. The public demo continues to show the transparent seven-day baseline and reports this failed gate prominently.
