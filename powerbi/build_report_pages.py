"""Write the three GridFlex report pages as Power BI project (PBIR) files.

Usage from the repository root:
    python powerbi/build_report_pages.py powerbi/gridflex_dashboard.Report/definition/pages

The fields, order and wording follow WALKTHROUGH.md. Each visual uses the file structure that
Power BI Desktop 2.160 wrote for a sample visual of the same type (schema visualContainer/2.15.0).
The script overwrites the page files. Close the project in Desktop first, then reopen it, check
every page and save, because Desktop rewrites the files in its own layout when it saves.
"""

import hashlib
import json
import os
import sys

OUT = sys.argv[1]
VSCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.15.0/schema.json"
PSCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PGSCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
W, H = 1280, 720


def S(s):
    return {"expr": {"Literal": {"Value": "'" + s.replace("'", "''") + "'"}}}


def B(b):
    return {"expr": {"Literal": {"Value": "true" if b else "false"}}}


def D(x):
    return {"expr": {"Literal": {"Value": f"{x}D"}}}


def L(x):
    return {"expr": {"Literal": {"Value": f"{x}L"}}}


def COL(hexv):
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hexv}'"}}}}}


def col(table, name):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def mea(table, name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def proj(field, active=False, display=None):
    kind = "Column" if "Column" in field else "Measure"
    t = field[kind]["Expression"]["SourceRef"]["Entity"]
    n = field[kind]["Property"]
    p = {"field": field, "queryRef": f"{t}.{n}", "nativeQueryRef": n}
    if display:
        p["displayName"] = display
    if active:
        p["active"] = True
    return p


def vid(seed):
    return hashlib.sha1(seed.encode()).hexdigest()[:20]


def container(title=None, pad=(10, 8, 10, 8), show_title=True):
    o = {}
    if title is not None and show_title:
        o["title"] = [{"properties": {"show": B(True), "text": S(title), "fontSize": D(12)}}]
    else:
        o["title"] = [{"properties": {"show": B(False)}}]
    o["subTitle"] = [{"properties": {"show": B(False)}}]
    if pad:
        o["padding"] = [
            {"properties": {"left": D(pad[0]), "top": D(pad[1]), "right": D(pad[2]), "bottom": D(pad[3])}}
        ]
    return o


def visual(name, x, y, w, h, z, vtype, roles=None, sort=None, objects=None, vco=None):
    v = {"visualType": vtype}
    if roles is not None:
        q = {"queryState": {r: {"projections": ps} for r, ps in roles.items()}}
        if sort:
            q["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": False}
        v["query"] = q
    if objects:
        v["objects"] = objects
    if vco:
        v["visualContainerObjects"] = vco
    v["drillFilterOtherVisuals"] = True
    return {
        "$schema": VSCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": v,
    }


def textbox(name, x, y, w, h, z, paragraphs):
    paras = []
    for runs in paragraphs:
        paras.append({"textRuns": [{"value": t, **({"textStyle": st} if st else {})} for t, st in runs]})
    objects = {"general": [{"properties": {"paragraphs": paras}}]}
    vco = {"padding": [{"properties": {"left": D(10), "top": D(6), "right": D(10), "bottom": D(6)}}]}
    return visual(name, x, y, w, h, z, "textbox", None, None, objects, vco)


def card(name, x, y, w, h, z, field, display=None):
    objects = {"value": [{"properties": {"labelDisplayUnits": D(1)}, "selector": {"id": "default"}}]}
    return visual(
        name,
        x,
        y,
        w,
        h,
        z,
        "cardVisual",
        {"Data": [proj(field, display=display)]},
        None,
        objects,
        container(None, pad=(10, 6, 10, 6), show_title=False),
    )


def slicer(name, x, y, w, h, z, field, display=None):
    objects = {
        "data": [{"properties": {"mode": S("Basic")}}],
        "general": [{"properties": {"orientation": D(1)}}],
        "header": [{"properties": {"show": B(True)}}],
    }
    return visual(
        name,
        x,
        y,
        w,
        h,
        z,
        "slicer",
        {"Values": [proj(field, active=True, display=display)]},
        None,
        objects,
        None,
    )


def axis_objects(xtitle=None, ytitle=None, categorical=False, labels=False, legend=None, line=False):
    o = {}
    if line:
        o["lineStyles"] = [{"properties": {"lineChartType": S("linear"), "strokeWidth": L(2)}}]
    ca = {"showAxisTitle": B(xtitle is not None)}
    if xtitle:
        ca["titleText"] = S(xtitle)
    if categorical:
        ca["axisType"] = S("Categorical")
    o["categoryAxis"] = [{"properties": ca}]
    va = {"showAxisTitle": B(ytitle is not None)}
    if ytitle:
        va["titleText"] = S(ytitle)
    o["valueAxis"] = [{"properties": va}]
    if labels:
        o["labels"] = [{"properties": {"show": B(True)}}]
    if legend is not None:
        o["legend"] = [{"properties": {"show": B(legend)}}]
    return o


TITLE = {"fontWeight": "bold", "fontSize": "18pt"}
SUB = {"fontSize": "10pt"}
BODY = {"fontSize": "10pt"}
BOLD = {"fontWeight": "bold", "fontSize": "10pt"}

pages = []

# ---------------- Page 1: Grid carbon intensity ----------------
P1 = "8e2345bce3ad35730bff"
v1 = []
v1.append(
    textbox(
        "9a8b1068a25d3e350f21",
        16,
        8,
        600,
        64,
        0,
        [
            [("Grid carbon intensity", TITLE)],
            [("Great Britain, half-hourly, 1 March to 20 September 2026. Times are UTC.", SUB)],
        ],
    )
)
v1.append(slicer("d16faf23509764870ebb", 632, 8, 632, 64, 1, col("DimDate", "Month")))
cards1 = [
    ("1a517bcf34901b53df53", mea("Carbon", "Average intensity"), "Average intensity (gCO₂/kWh)"),
    ("36e8e89e89a20d77dd72", mea("Carbon", "Readings"), "Half-hourly readings"),
    ("5810bb96f80410cbabb8", mea("Carbon", "NESO forecast MAE"), "NESO forecast MAE (gCO₂/kWh)"),
    ("7138a32509f7fed23746", mea("Carbon", "Cleanest hour (UTC)"), None),
]
for i, (n, f, d) in enumerate(cards1):
    v1.append(card(n, 16 + i * 316, 80, 300, 88, 2 + i, f, d))
v1.append(
    visual(
        "dd1b9aee8ac923436f3d",
        16,
        176,
        616,
        240,
        6,
        "lineChart",
        {
            "Category": [proj(col("DimDate", "Date"), active=True)],
            "Y": [proj(mea("Carbon", "Average intensity")), proj(mea("Carbon", "Average NESO forecast"))],
        },
        None,
        axis_objects(None, "gCO₂/kWh", legend=True, line=True),
        container("Daily average intensity: observed and NESO forecast"),
    )
)
v1.append(
    visual(
        vid("p1-hourly"),
        648,
        176,
        616,
        240,
        7,
        "clusteredColumnChart",
        {
            "Category": [proj(col("Carbon", "hour"), active=True)],
            "Y": [proj(mea("Carbon", "Average intensity"))],
        },
        (col("Carbon", "hour"), "Ascending"),
        axis_objects("Hour of day (UTC)", "gCO₂/kWh", categorical=True, legend=False),
        container("Average intensity by hour of day"),
    )
)
matrix_objects = {
    "values": [
        {"properties": {"fontSize": D(9)}},
        {
            "properties": {
                "backColor": {
                    "solid": {
                        "color": {
                            "expr": {
                                "FillRule": {
                                    "Input": {"SelectRef": {"ExpressionName": "Carbon.Average intensity"}},
                                    "FillRule": {
                                        "linearGradient2": {
                                            "min": {"color": {"Literal": {"Value": "'#FFFFFF'"}}},
                                            "max": {"color": {"Literal": {"Value": "'#F08C4A'"}}},
                                            "nullColoringStrategy": {
                                                "strategy": {"Literal": {"Value": "'asZero'"}}
                                            },
                                        }
                                    },
                                }
                            }
                        }
                    }
                }
            },
            "selector": {
                "data": [{"dataViewWildcard": {"matchingOption": 1}}],
                "metadata": "Carbon.Average intensity",
            },
        },
    ],
    "columnHeaders": [{"properties": {"fontSize": D(9)}}],
    "rowHeaders": [{"properties": {"fontSize": D(9)}}],
    "grid": [{"properties": {"rowPadding": D(3)}}],
}
v1.append(
    visual(
        "a3b2d219cd68fad03006",
        16,
        424,
        1248,
        288,
        8,
        "pivotTable",
        {
            "Rows": [proj(col("DimDate", "Weekday"), active=True)],
            "Columns": [proj(col("Carbon", "hour"), active=True)],
            "Values": [proj(mea("Carbon", "Average intensity"))],
        },
        None,
        matrix_objects,
        container("Average intensity by weekday and hour of day (UTC), gCO₂/kWh. Darker cells are higher."),
    )
)
pages.append((P1, "Grid carbon intensity", v1))

# ---------------- Page 2: Forecast accuracy ----------------
P2 = vid("page-2-forecast-accuracy")
v2 = []
v2.append(
    textbox(
        vid("p2-title"),
        16,
        8,
        948,
        64,
        0,
        [
            [("Forecast accuracy", TITLE)],
            [
                (
                    "Retrospective back-test: 3 folds, 168 forecast issue times, 8,064 half-hourly targets per model. Errors are in gCO₂/kWh.",
                    SUB,
                )
            ],
        ],
    )
)
v2.append(slicer(vid("p2-fold"), 980, 8, 284, 64, 1, col("Backtest", "fold"), "Fold"))
v2.append(
    card(
        vid("p2-card-coverage"),
        16,
        80,
        308,
        96,
        2,
        mea("Backtest", "Interval coverage"),
        "Interval coverage (nominal 90%)",
    )
)
v2.append(card(vid("p2-card-count"), 332, 80, 308, 96, 3, mea("Backtest", "Forecasts per model"), None))
v2.append(
    textbox(
        vid("p2-decision"),
        648,
        80,
        616,
        96,
        4,
        [
            [("Release decision", BOLD)],
            [
                (
                    "The live demo uses the seven-day mean. LightGBM has higher overall MAE and its intervals fall short of nominal coverage. It remains a research candidate. The forecast horizons overlap, so model comparisons are descriptive.",
                    BODY,
                )
            ],
        ],
    )
)
v2.append(
    visual(
        vid("p2-bar"),
        16,
        184,
        616,
        252,
        5,
        "clusteredBarChart",
        {"Category": [proj(col("Backtest", "model"), active=True)], "Y": [proj(mea("Backtest", "MAE"))]},
        (mea("Backtest", "MAE"), "Ascending"),
        axis_objects(None, "MAE (gCO₂/kWh)", labels=True, legend=False),
        container("MAE by model, lowest first"),
    )
)
v2.append(
    visual(
        vid("p2-table"),
        648,
        184,
        616,
        252,
        6,
        "tableEx",
        {
            "Values": [
                proj(col("Backtest", "model")),
                proj(mea("Backtest", "MAE")),
                proj(mea("Backtest", "RMSE")),
                proj(mea("Backtest", "MAE vs live model")),
            ]
        },
        (mea("Backtest", "MAE"), "Ascending"),
        {"total": [{"properties": {"totals": B(False)}}]},
        container("Error by model (gCO₂/kWh)"),
    )
)
v2.append(
    visual(
        vid("p2-horizon"),
        16,
        448,
        1248,
        264,
        7,
        "lineChart",
        {
            "Category": [proj(col("Backtest", "horizon_hours"), active=True)],
            "Series": [proj(col("Backtest", "model"))],
            "Y": [proj(mea("Backtest", "MAE"))],
        },
        None,
        axis_objects("Forecast horizon (hours)", "MAE (gCO₂/kWh)", legend=True, line=True),
        container("MAE by forecast horizon"),
    )
)
pages.append((P2, "Forecast accuracy", v2))

# ---------------- Page 3: Smart charging back-test ----------------
P3 = vid("page-3-smart-charging")
v3 = []
v3.append(
    textbox(
        vid("p3-title"),
        16,
        8,
        616,
        64,
        0,
        [
            [("Smart charging back-test", TITLE)],
            [
                (
                    "168 simulated sessions, 9 August to 19 September 2026, starting at 0, 6, 12 and 18 UTC.",
                    SUB,
                )
            ],
        ],
    )
)
v3.append(
    textbox(
        vid("p3-note"),
        648,
        8,
        616,
        64,
        1,
        [
            [
                ("Note. ", BOLD),
                (
                    "Simulated on historical data with a fixed default battery. Not measured charging or avoided emissions.",
                    BODY,
                ),
            ]
        ],
    )
)
cards3 = [
    ("p3-card-scenarios", "Scenarios"),
    ("p3-card-saving", "Carbon saving %"),
    ("p3-card-win", "Win rate"),
    ("p3-card-share", "Share of best possible saving"),
]
for i, (seed, m) in enumerate(cards3):
    v3.append(card(vid(seed), 16 + i * 316, 80, 300, 96, 2 + i, mea("Charging", m)))
v3.append(
    visual(
        vid("p3-columns"),
        16,
        184,
        616,
        252,
        6,
        "clusteredColumnChart",
        {
            "Category": [proj(col("Charging", "start_hour"), active=True)],
            "Y": [proj(mea("Charging", "Avg immediate kg")), proj(mea("Charging", "Avg scheduled kg"))],
        },
        (col("Charging", "start_hour"), "Ascending"),
        axis_objects(
            "Start hour (UTC)", "Simulated proxy kg CO₂", categorical=True, labels=True, legend=True
        ),
        container("Average carbon proxy by start hour: immediate and scheduled"),
    )
)
v3.append(
    visual(
        vid("p3-donut"),
        648,
        184,
        616,
        252,
        7,
        "donutChart",
        {
            "Category": [proj(col("Charging", "result"), active=True)],
            "Y": [proj(mea("Charging", "Scenarios"))],
        },
        None,
        {
            "labels": [{"properties": {"labelStyle": S("Both"), "labelDisplayUnits": D(1)}}],
            "legend": [{"properties": {"show": B(False)}}],
        },
        container("Scenarios by result"),
    )
)
v3.append(
    visual(
        vid("p3-daily"),
        16,
        448,
        1248,
        264,
        8,
        "lineChart",
        {
            "Category": [proj(col("DimDate", "Date"), active=True)],
            "Y": [proj(mea("Charging", "Total saving kg"))],
        },
        None,
        axis_objects(None, "Simulated proxy kg CO₂", legend=False, line=True),
        container("Daily net simulated saving (immediate minus scheduled)"),
    )
)
pages.append((P3, "Smart charging back-test", v3))


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)


for pid, title, visuals in pages:
    dump(
        f"{OUT}/{pid}/page.json",
        {
            "$schema": PSCHEMA,
            "name": pid,
            "displayName": title,
            "displayOption": "FitToPage",
            "height": H,
            "width": W,
        },
    )
    names = set()
    for v in visuals:
        assert v["name"] not in names
        names.add(v["name"])
        p = v["position"]
        assert p["x"] >= 0 and p["y"] >= 0 and p["x"] + p["width"] <= W and p["y"] + p["height"] <= H, v[
            "name"
        ]
        dump(f"{OUT}/{pid}/visuals/{v['name']}/visual.json", v)
    print(pid, title, len(visuals), "visuals")
dump(
    f"{OUT}/pages.json",
    {"$schema": PGSCHEMA, "pageOrder": [p[0] for p in pages], "activePageName": pages[0][0]},
)
