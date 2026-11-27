# Power BI Desktop report, 25 November 2026 UTC

The three-page report was built in Power BI Desktop on the owner's PC, saved as [gridflex_dashboard.pbix](../../../powerbi/gridflex_dashboard.pbix), closed, reopened and read back. Every acceptance figure in the [walkthrough](../../../powerbi/WALKTHROUGH.md) was observed in Desktop, on the pages and in DAX queries. The figures agree with the [CSV calculations of 23 November](../completion-2026-11-23/powerbi-data.txt).

Nouman Sameer owns the PC and the repository, supplied the report kit and granted this session control of Power BI Desktop and GitHub Desktop. Claude (Anthropic, Fable 5.2) operated Desktop through the Claude desktop app, wrote [the page generator](../../../powerbi/build_report_pages.py), read the values back and wrote this record. Values were read from screen captures of the Desktop window. Apart from the three page images, those captures are not kept.

## What ran

| Item | Value |
|---|---|
| Desktop | Power BI Desktop 2.160.1151.0 64-bit (November 2026), Microsoft Store build |
| Source | A clone of `main` at `16ed736c2de936ca190132c00a3c28771765dac8` |
| Inputs | [Carbon.csv](../../../powerbi/data/Carbon.csv), [Backtest.csv](../../../powerbi/data/Backtest.csv), [Charging.csv](../../../powerbi/data/Charging.csv), [measures.dax](../../../powerbi/measures.dax) and [gridflex-theme.json](../../../powerbi/gridflex-theme.json). Git had checked them out with CRLF line endings. With LF restored, all five equal the committed files byte for byte. |
| Report file | `powerbi/gridflex_dashboard.pbix`, 676,737 bytes, saved at 08:31, SHA-256 `fb1cb81bdfcda3ae3d8bd60eeb0ea16a690f35631ffc9070e88bcbac8e59666a` |
| Project files | [gridflex_dashboard.pbip](../../../powerbi/gridflex_dashboard.pbip) with its `.Report` and `.SemanticModel` folders, saved at 08:30. The `.pbix` was saved from the open project one minute later with no edit in between. |

## How the report was built

| UTC | Step | Result |
|---|---|---|
| 07:16 to 07:35 | Blank report. Auto date/time turned off for the file. The three CSVs loaded through Get data, with the walkthrough's types set in each query's Changed Type step. | Table view showed 9,792, 40,320 and 168 rows. Desktop created no relationship by itself. |
| 07:39 to 07:47 | `DimDate` created from the supplied expression, set to Date and marked as the date table. Month sorted by Month no and Weekday by Weekday no. Three relationships added in Manage relationships. Four columns set to Don't summarise. | 204 dates. Each relationship is one-to-many, single direction and active. |
| 07:48 to 07:59 | The 17 measures created with New measure, each pasted from `measures.dax`, with the walkthrough's formats. | Five Carbon, five Backtest, seven Charging. The saved definitions equal `measures.dax` token for token. |
| 07:59 to 08:06 | Theme imported. Five DAX queries written, run and saved in the file. | See [Read-back](#read-back). |
| 08:13 to 08:18 | Eight sample visuals created in Desktop (card, slicer, line chart, matrix, table, donut, bar chart and text box) and the report saved as a Power BI project, to obtain the file structure Desktop itself writes. | Schema `visualContainer/2.15.0`. The column charts follow the bar chart's structure. The samples were then overwritten. |
| 08:20 to 08:30 | Pages written by `build_report_pages.py`, copied into the project and opened in Desktop. The first version had five faults, listed below. The second loaded cleanly. | 26 visuals on three pages and no load error. |
| 08:31 | Saved as `.pbix`, replacing the model-only file saved at 08:06. Desktop closed. | |
| 08:32 to 08:43 | The `.pbix` reopened. Pages checked, queries rerun, slicers exercised and cleared, PDF exported, pages captured. The reopened file was not saved again. | |

The first version of the pages showed 10K and 8K on two cards, a scroll bar on the hourly chart, a matrix that cut off Saturday and Sunday, donut labels without counts and a note that overflowed its box. The second version set the cards' display units to None, widened the hourly chart, gave the matrix more height, changed the donut label style and shortened the note. It also drew the line charts with straight segments, because the Desktop base theme smooths lines by default.

## Read-back

Observed on the reopened `.pbix` unless a row says otherwise. DAX query view shows two decimals, so its percentages were also read as counts or scaled values.

| Page | Check | Walkthrough | Observed | Read from |
|---|---|---|---|---|
| 1 | Average intensity | 116.3 | 116.3 | Card. Query 1 gives 116.34. |
| 1 | Readings | 9,792 | 9,792 | Card |
| 1 | NESO forecast MAE | 10.4 | 10.4 | Card. Query 1 gives 10.43. |
| 1 | Cleanest hour (UTC) | 12 | 12 | Card |
| 1 | Hourly chart at 12:00 and 19:00 | 78.6 and 153.5 | 78.6 and 153.5 | Chart tooltips before the save. On the reopened file, the matrix total row and Query 4 (78.57 and 153.52). |
| 1 | Matrix, Saturday 12:00 and Monday 19:00 | 65.9 and 164.8 | 65.9 and 164.8 | Matrix cells. Query 4 gives 65.9 and 164.78. |
| 1 | Apr 2026 selected | 93.4 | 93.4, from 1,440 readings | Card with the Month slicer set, then cleared |
| 2 | Interval coverage | 86.3% | 86.3% | Card. Query 4 gives 6,957 hits in 8,064 flags. |
| 2 | Forecasts per model | 8,064 | 8,064 | Card |
| 2 | Five model rows | Table in the walkthrough | Identical in all 15 cells | Table visual, bar labels and Query 2 |
| 2 | LightGBM at 0.5 h and 24 h | 26.58 and 39.52 | 26.58 and 39.52 | Chart tooltips before the save. Query 4 on the reopened file. |
| 2 | Fold 3 selected | LightGBM MAE 51.08, coverage 81.1% | 51.08 and 81.1%, with 2,688 forecasts per model | Bar chart, table and card with the Fold slicer set, then cleared |
| 3 | Four cards | 168, 30.75%, 88.1%, 80.1% | 168, 30.75%, 88.1%, 80.1% | Cards. Query 4 gives 0.307542, 0.88095 and 0.80106. |
| 3 | Columns at 18:00 | 4.77 immediate, 2.63 scheduled | 4.77 and 2.63 | Data labels |
| 3 | Donut | 148 Scheduled better, 20 Immediate better | 148 and 20 | Detail labels |
| 3 | Total saving | 195.41 kg | 195.41 | Query 3. The page has no visual that shows this total. |

The Month slicer changed the four cards, both charts and the matrix. The Fold slicer changed both cards, the bar chart, the table and the horizon chart. Fold 2 was also selected once and gave a LightGBM MAE of 28.10, as in the 23 November record. `MAE vs live model` shows 1.14 for LightGBM, as the walkthrough explains.

The five queries are saved in the file and in the [project's DAXQueries folder](../../../powerbi/gridflex_dashboard.SemanticModel/DAXQueries). Queries 1 to 3 are the walkthrough's. Query 4 adds the scaled values above. Query 5 lists the model: 17 measures with their format strings, exactly three relationships (many to one, active, one direction), Month sorted by Month no, Weekday sorted by Weekday no, and no summarisation on `hour`, `fold`, `horizon_hours` and `start_hour`.

## Exports

| File | Detail |
|---|---|
| [gridflex_dashboard.pdf](../../../powerbi/gridflex_dashboard.pdf) | 294,394 bytes, 3 pages, SHA-256 `42c228be8e08b54c78eff4751f3b769c1e7200547525594140835514b602d183`. Exported on 27 November from the unchanged `.pbix`. [Addendum](#27-november-addendum-the-pdf-export) |
| [page1-carbon.png](../../../powerbi/screenshots/page1-carbon.png) | 578,585 bytes, SHA-256 `bf6671abddda58fa3e936aae4068be5fdc9a0bff39c2a8926441f00b60fcc18d` |
| [page2-accuracy.png](../../../powerbi/screenshots/page2-accuracy.png) | 353,272 bytes, SHA-256 `44e9b507b1e03df18142114793eb87c14165058a33b78ae84b963520d5df045e` |
| [page3-charging.png](../../../powerbi/screenshots/page3-charging.png) | 290,708 bytes, SHA-256 `0249d9176d75cc9f7709674481f8e35964e1f1880a3174f1ce2fcd695264cb2d` |

The three images are captures of the reopened `.pbix` in Report view at 90% zoom with the panes collapsed and no slicer selected. The capture tool returned JPEG images of the Desktop window. Each was cropped to the page and saved as a 1,415 by 793 pixel PNG. Nothing else in the image was altered. Each file also carries a C2PA content credentials block of 5,758 bytes, added when the session's file store delivered it to the PC. The sizes and hashes above are those of the delivered files.

## Differences from the walkthrough

- The pages were written as project files by a script and loaded in Desktop. The walkthrough describes placing each visual by hand. The model and the measures were made through the Desktop interface as the walkthrough says.
- The cards are Desktop 2.160's card visual. Their display units are set to None in the page files.
- Each page has a title text box, which the walkthrough does not list. Four cards and the Fold slicer carry a display name set for that visual, such as `Average intensity (gCO₂/kWh)`.
- The pages are 1,280 by 720. Desktop 2.160 starts new reports at 1,920 by 1,080, where the default text is small on an exported page.
- The slicers use the tile style. The matrix keeps Desktop's row and column totals, so its total row repeats the hourly averages. Its gradient runs from white to orange.
- In Desktop 2.160 the theme is loaded from Design → Import theme. The walkthrough now says so.

## Not tested

- **Refresh.** The three queries read the CSVs from `C:\Users\Hp\Documents\GitHub\uk-grid-flexibility-ml-platform\powerbi\data`. The file opens with the data it was saved with. On another PC, change the three sources before refreshing.
- **The Power BI service.** Nothing was published. Mobile layout, alt text and tab order were not set or checked.
- **Other Desktop versions**, and opening the project files anywhere but on this PC.
- **A second run of the generator.** Its output was loaded once per version. A rebuild from the script needs Desktop to open and save the project again.

## 27 November addendum: the PDF export

Desktop's first export, at 08:35 on 25 November, went to a temporary folder that the session could not read. That copy was not kept.

On 27 November at 15:24 UTC the saved `.pbix` was opened again in Desktop 2.160.1151.0. Page 1 showed 116.3, 9,792, 10.4 and 12. File → Export → Export to PDF wrote the PDF at 15:25 and opened it in the default PDF viewer. The owner saved that copy and gave the session access to it. The session copied it into the repository unchanged. The `.pbix` was not saved again and its SHA-256 is still the one above.

| Check on `gridflex_dashboard.pdf` | Result |
|---|---|
| Pages | 3, each 996 by 576 points |
| Page 1 text | Holds 116.3, 9,792, 10.4 and 12, and the matrix values 65.9, 164.8, 78.6 and 153.5 |
| Page 2 text | Holds 86.3%, 8,064 and all 15 cells of the model table |
| Page 3 text | Holds 168, 30.75%, 88.1%, 80.1%, 4.77, 2.63, `Scheduled better 148` and `Immediate better 20` |
| Appearance | Each page was rendered and compared by eye with its page capture. The visuals and values are the same. |
| Document properties | Creation time and `PDFium` only. No name, account or file path. |

The text was extracted with pypdf and the pages were rendered with Poppler.
