# Model card explanation

The authoritative numerical card is [`models/production/model_card.json`](../models/production/model_card.json).

**Task:** direct half-hour GB average carbon-intensity forecasts over a 24-hour horizon.

**Intended use:** portfolio demonstration, reproducible comparison, and exploratory flexible-charging plans. It is not a dispatch controller or a commercial carbon-accounting method.

**Data:** 9,792 NESO half-hour rows, 1 March–20 September 2026. These are retrospectively downloaded values and may contain historical revisions. The training reference is committed. SHA-256 hashes identify source payloads, input data and the model.

**Predictors:** eligible latest/day/week history, preceding-day summary and trend, target's week-ago actual, local-time calendar cycles and forecast horizon. The observation delay is two hours. No current target actuals, historical provider forecasts or future/reanalysis weather are included as predictors.

**Evaluation:** three purged chronological folds. Each test period covers 14 days of six-hourly origins. Forecast horizons overlap within and around folds; this correlation prevents treating every forecast row as an independent sample. No random train/test split is used. No statistical significance claim is made.

**Results:** MAE 36.61 gCO₂/kWh, versus persistence 42.48, weekly seasonal 47.51, daily seasonal 41.14 and seven-day mean 35.46. LightGBM loses to the strongest simple baseline. Interval coverage is 86.3%, below the 90% nominal level. The final candidate uses a fresh 14-day calibration block excluded from model fitting. No test-driven hyperparameter search was conducted. Added baselines and horizon/charging diagnostics were specified after the initial build and did not alter the model; they are post-build diagnostics, not a preregistered comparison.

**Candidate check:** aggregate MAE must beat all four simple baselines and observed coverage must reach the nominal 90%. The earlier 80% rule was too permissive and has been removed. This candidate fails both conditions. The `models/production` directory is a legacy serving path, not an approval label. Passing a retrospective check alone would still not establish prospective reliability.

**Historical replay:** the saved forecast originates on 21 September 2026, after all data used in fitting/calibration. It is generated retrospectively from eligible historical observations; it is not claimed to have been issued operationally on that date. Its actuals are shown for comparison. Historical NESO forecast values may have been revised and are not treated as an as-issued competitor score.

**Monitoring:** live issue-time predictions and available baseline values are stored before labels arrive. Early metrics are descriptive. Performance status requires at least 28 distinct forecast origins spanning seven target days; overlapping rows are not independent evidence. Drift uses PSI on recent unique origins, with at least 48 origins; 0.25 is a heuristic threshold. Alerts trigger investigation rather than automatic retraining/promotion. Reports older than eight hours are marked stale.

**Limitations:** seasonality and regime shifts; possible retrospective revisions; uncertain publication latency; broad intervals; an incomplete annual cycle; no capacity-weighted weather forecasting; correlated forecast errors; no prospective performance record at initial release. Average intensity does not establish marginal emissions avoided by shifting demand.

**Next evidence needed:** accumulate several weeks of issued forecasts and labels; extend the supplied horizon-specific metrics across seasons; obtain archived weather forecasts with issue timestamps; evaluate a new candidate on a new untouched period. Do not tune repeatedly against the released test windows and claim the result is independent.
