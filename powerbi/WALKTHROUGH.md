# Rebuild the GridFlex report in Power BI Desktop

Use the three files in [data](data/), the [original DAX](measures.dax), and the [theme](gridflex-theme.json). The [CSV read-back](../docs/evidence/completion-2026-11-23/powerbi-data.txt) gives the comparison values. Desktop read-back and the three-page export are pending.

## Build the model

1. Open a blank report. Under **File → Options and settings → Options → Current file → Data Load**, turn off **Auto date/time** before building visuals. The report uses one calendar for all three tables.
2. Choose **Get data → Text/CSV** for each file, select its comma delimiter and choose **Transform data**. Name the queries exactly `Carbon`, `Backtest` and `Charging`, and set the types below in Power Query. Explicit typing preserves the half-hour horizon values and nullable interval flags even when the preview samples few rows.
3. Choose **Close & Apply**, then inspect each table in Table view. Check for 9,792 carbon rows, 40,320 forecast rows and 168 scenarios, and check that baseline `inside_interval` values are blank. A zero in that field is an observed interval miss, so filling the baseline blanks with zero would corrupt coverage.
4. Choose **Modelling → New table** and paste only the `DimDate` expression from the DAX file. It generates every date between the first and last observed carbon reading and adds the month and weekday labels. Set `DimDate[Date]` to Date and use **Mark as date table** with that column.
5. In Model view, create the three active relationships below. For each, set cardinality to **One to many (1:*)** and cross-filter direction to **Single** from `DimDate`. Check that these are the only relationships so that selecting a forecast fold cannot change the number of charging scenarios.
6. In Column tools, select `DimDate[Month]` and **Sort by column → Month no**. Sort `DimDate[Weekday]` by **Weekday no** in the same way. This yields chronological months within this single-year study and weekdays from Monday to Sunday.
7. Set the default summarisation of `Carbon[hour]`, `Backtest[fold]`, `Backtest[horizon_hours]` and `Charging[start_hour]` to **Don't summarise**. These values identify groups or positions on an axis, so adding them would give meaningless totals.
8. Select the relevant table, choose **New measure**, and paste one named expression at a time from the DAX file. Make five measures under Carbon, five under Backtest, and seven under Charging, using the names and formulas as supplied. Apply the formats below so a reader can compare values at the intended precision.
9. Open **View → Themes → Browse for themes** and load the supplied JSON. On cards set **Display units** to **None**, then set the shown decimal places to match each measure. This keeps 9,792 and 8,064 readable as exact counts.

### Import types

All timestamps labelled UTC already contain UTC clock times. Import the timestamp columns as Date/Time and leave their values on that clock.

| Query | Date/Time | Date | Whole number | Decimal number | Text |
|---|---|---|---|---|---|
| Carbon | `timestamp_utc` | `date` | `hour` | `actual_gco2_kwh`, `neso_forecast_gco2_kwh` | — |
| Backtest | `origin_utc`, `target_utc` | `target_date` | `fold`, `inside_interval` (nullable) | `horizon_hours`, `actual_gco2_kwh`, `predicted_gco2_kwh`, `error`, `abs_error`, `squared_error`, `interval_lower`, `interval_upper` | `model` |
| Charging | `scenario_start_utc` | `date` | `start_hour` | `immediate_kg`, `scheduled_kg`, `seven_day_mean_schedule_kg`, `perfect_information_kg`, `saving_kg` | `result` |

| One side | Many side | Meaning of a selected date |
|---|---|---|
| `DimDate[Date]` | `Carbon[date]` | Day the grid intensity was observed |
| `DimDate[Date]` | `Backtest[target_date]` | Day the model predicted, even when the forecast was issued earlier |
| `DimDate[Date]` | `Charging[date]` | Day the simulated session started |

## What each measure answers

Each measure runs again for the dates, groups or folds selected in the visual. Use these measures for the numerical fields on cards and charts.

| Carbon measure | Display | What it does and why |
|---|---|---|
| Average intensity | 1 decimal | Averages the observed gCO₂/kWh across the selected half-hours. In a cell for Saturday at noon it uses only those readings, which makes the weekday matrix interpretable. |
| Average NESO forecast | 1 decimal | Averages NESO's forecast for the same selected readings. Put it beside observed intensity to compare the two daily series on a common scale. |
| Readings | Whole number with separators | Counts selected half-hourly carbon rows. It shows how much data underlies the average when the month changes. |
| NESO forecast MAE | 1 decimal | Takes the absolute forecast error for each half-hour and then averages those errors. This prevents high and low forecasting errors from cancelling out. |
| Cleanest hour (UTC) | Whole number | Finds the hour with the lowest average observed intensity within the selection. If two or more hours tie, it returns the earliest one. |

| Backtest measure | Display | What it does and why |
|---|---|---|
| MAE | 2 decimals | Averages the absolute errors for the selected forecast rows in gCO₂/kWh. A lower value means a smaller typical miss in this comparison. |
| RMSE | 2 decimals | Takes the square root of the mean squared error. Its units are gCO₂/kWh and large misses carry more weight than in MAE. |
| Interval coverage | Percentage, 1 decimal | Divides the number of hits by the number of nonblank interval flags. Only LightGBM has intervals, so the baseline rows contribute neither hits nor misses. |
| MAE vs live model | 2 decimals | Subtracts the seven-day mean's MAE from the selected model's MAE while keeping the current fold, horizon and date filters. Zero is the live-model row and a positive gap means the selected model had higher error. |
| Forecasts per model | Whole number with separators | Counts LightGBM target rows in the selected dates and folds. Each model forecasts the same targets, so this count gives the number per model and avoids counting the five copies of each target. |

The `MAE vs live model` comment in the supplied DAX file says +1.15. The two unrounded means on the imported rows are 36.6081150794 and 35.4635863095. The difference is 1.1445287698, which displays as **1.14**. Keep the formula as supplied. [Calculation against the imported rows and the original forecasts](../docs/evidence/completion-2026-11-23/powerbi-data.txt)

| Charging measure | Display | What it does and why |
|---|---|---|
| Scenarios | Whole number | Counts simulated session starts. On the donut it gives the number of scenarios in each result category. |
| Carbon saving % | Percentage, 2 decimals | Subtracts total scheduled proxy kg from total immediate proxy kg and divides by total immediate proxy kg. This weights scenarios by their contribution to the total. |
| Win rate | Percentage, 1 decimal | Counts scenarios labelled “Scheduled better” and divides by all selected scenarios. It shows how often the schedule improved the proxy, independently of how large those improvements were. |
| Share of best possible saving | Percentage, 1 decimal | Divides the aggregate scheduled saving by the aggregate saving available under perfect information. It measures how much of the historical opportunity the forecast-based schedule captured. |
| Avg immediate kg | 2 decimals | Averages the carbon proxy for the immediate-charge baseline. Group it by start hour to see how the baseline depends on when the session began. |
| Avg scheduled kg | 2 decimals | Averages the historical proxy achieved by the LightGBM-based schedule. Plot it beside immediate charging for the same start-hour group. |
| Total saving kg | 2 decimals | Adds each scenario's immediate proxy minus its scheduled proxy. A daily point is the net simulated saving across starts on that day, including sessions where the scheduled plan had a higher proxy. |

## Assemble the pages

Create three pages in the order below. Keep the Month and Fold slicers on their respective pages. For every line or column chart, choose the named measure for the value and a column for the category.

### 1. Grid carbon intensity

| Visual | Fields / settings |
|---|---|
| Month slicer | `DimDate[Month]`. Check its interaction filters the four cards, both charts and matrix. |
| Four cards | `[Average intensity]`, `[Readings]`, `[NESO forecast MAE]`, `[Cleanest hour (UTC)]`. Label intensity and error in gCO₂/kWh. |
| Daily line chart | X axis `DimDate[Date]` as the plain date, Y values `[Average intensity]` and `[Average NESO forecast]`. Use ascending date order. |
| Hourly column chart | X axis `Carbon[hour]`, Y value `[Average intensity]`. Sort by hour from 0 to 23 and label the axis UTC. |
| Weekday × hour matrix | Rows `DimDate[Weekday]`, columns `Carbon[hour]`, values `[Average intensity]`. Apply conditional background colour using a gradient from lowest to highest value and show one decimal. |

### 2. Forecast accuracy

| Visual | Fields / settings |
|---|---|
| Fold slicer | `Backtest[fold]` as a list or dropdown of distinct folds. Check its interactions with the cards, bar chart, table and horizon chart. |
| Two cards | `[Interval coverage]` and `[Forecasts per model]`. |
| Horizontal bar chart | Category `Backtest[model]`, value `[MAE]`. Sort by MAE ascending so the lowest-error model appears first. |
| Table | `Backtest[model]`, `[MAE]`, `[RMSE]`, `[MAE vs live model]`. Sort by MAE ascending and turn off the total row because it would pool errors across models. |
| Horizon line chart | Numeric X axis `Backtest[horizon_hours]` in ascending order, Y value `[MAE]`, legend `Backtest[model]`. Label the axes in hours and gCO₂/kWh. |
| Release decision, text box | “The live demo uses the seven-day mean. LightGBM has higher overall MAE and its intervals fall short of nominal coverage. It remains a research candidate. The forecast horizons overlap, so model comparisons are descriptive.” |

### 3. Smart charging back-test

| Visual | Fields / settings |
|---|---|
| Four cards | `[Scenarios]`, `[Carbon saving %]`, `[Win rate]`, `[Share of best possible saving]`. |
| Clustered columns | X axis `Charging[start_hour]`, values `[Avg immediate kg]` and `[Avg scheduled kg]`. Sort by UTC start hour and label the Y axis as simulated proxy kg CO₂. |
| Daily line chart | X axis `DimDate[Date]` as the plain date, Y value `[Total saving kg]`. Use ascending date order and leave days without scenarios blank. |
| Donut | Legend `Charging[result]`, values `[Scenarios]`. Show the category and count in the detail labels. |
| Note, text box | “Simulated on historical data with a fixed default battery. Not measured charging or avoided emissions.” |

## Read the report back in Desktop

1. Clear the slicers and any active visual selections. On page 1 the cards should read **116.3**, **9,792**, **10.4** and **12**. Check the hourly chart at 12:00 and 19:00 for **78.6** and **153.5**, and the matrix at Saturday 12:00 and Monday 19:00 for **65.9** and **164.8**. Select **Apr 2026** and check that the intensity card changes to **93.4**, then clear it.
2. On page 2, check **86.3%** coverage and **8,064** forecasts per model, then compare the five model rows with the table below. Hover on the LightGBM horizon line at 0.5 and 24 hours for **26.58** and **39.52**. Select fold **3** and check for **51.08** LightGBM MAE and **81.1%** coverage, then clear the slicer.
3. On page 3 the cards should read **168**, **30.75%**, **88.1%** and **80.1%**. At 18:00 the clustered columns should show **4.77** immediate and **2.63** scheduled kg. The donut should show **148 Scheduled better** and **20 Immediate better**. The unfiltered total across the daily line should be **195.41 kg**.

| Model | MAE | RMSE | MAE vs live |
|---|---:|---:|---:|
| Seven-day mean (live) | 35.46 | 43.28 | 0.00 |
| LightGBM (candidate) | 36.61 | 45.49 | 1.14 |
| Daily seasonal | 41.14 | 51.92 | 5.67 |
| Persistence | 42.48 | 54.03 | 7.01 |
| Weekly seasonal | 47.51 | 58.87 | 12.04 |

For a read-back from the loaded model, open **DAX query view** and run the three queries below separately. Query view has its own filter context, so the queries apply April and fold 3 explicitly. Verify the report slicers separately to check the visual interactions.

```dax
EVALUATE
ROW (
    "Average intensity", [Average intensity],
    "Readings", [Readings],
    "NESO MAE", [NESO forecast MAE],
    "Cleanest hour", [Cleanest hour (UTC)],
    "April intensity", CALCULATE (
        [Average intensity],
        DATESBETWEEN ( DimDate[Date], DATE ( 2026, 4, 1 ), DATE ( 2026, 4, 30 ) )
    ),
    "Interval coverage", [Interval coverage],
    "Forecasts per model", [Forecasts per model],
    "Fold 3 LightGBM MAE", CALCULATE (
        [MAE], Backtest[fold] = 3, Backtest[model] = "LightGBM (candidate)"
    ),
    "Fold 3 interval coverage", CALCULATE ( [Interval coverage], Backtest[fold] = 3 )
)
```

```dax
EVALUATE
SUMMARIZECOLUMNS (
    Backtest[model],
    "Mean absolute error", [MAE],
    "Root mean squared error", [RMSE],
    "Difference from live", [MAE vs live model]
)
ORDER BY [Mean absolute error] ASC
```

```dax
EVALUATE
ROW (
    "Scenarios", [Scenarios],
    "Carbon saving", [Carbon saving %],
    "Win rate", [Win rate],
    "Share of best", [Share of best possible saving],
    "Total saving in kg", [Total saving kg],
    "18 UTC immediate kg", CALCULATE ( [Avg immediate kg], Charging[start_hour] = 18 ),
    "18 UTC scheduled kg", CALCULATE ( [Avg scheduled kg], Charging[start_hour] = 18 )
)
```

## Save and export

1. Save the report as `powerbi/gridflex_dashboard.pbix`, close it and reopen it in Desktop. Check every page for visual errors and repeat the read-back from the saved file. Save the observed values and the Desktop version in the dated verification record.
2. Clear the slicers and visual selections. Use **File → Export → Export to PDF** and save the result as `powerbi/gridflex_dashboard.pdf`. Open the PDF and check that it has three legible pages in report order.
3. Create `powerbi/screenshots/` if needed. Capture the report canvas directly from the reopened PBIX, one page at a time, and save the images as `page1-carbon.png`, `page2-accuracy.png` and `page3-charging.png`. Check each image against its Desktop page before marking the report complete.
