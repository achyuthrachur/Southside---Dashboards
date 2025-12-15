from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc, html
import dash_bootstrap_components as dbc

from wow_risk_dashboard.io.synthetic_bundle import generate_default_json
from wow_risk_dashboard.transforms.metrics import build_default_cohorts

DATA_PATH = Path(__file__).parent / "data" / "southside_demo.json"
APP_TITLE = "Southside Risk Studio"
RATING_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C"]
RATING_COLOR = {
    "AAA": "#6EE7B7",
    "AA": "#A7F3D0",
    "A": "#CFFAFE",
    "BBB": "#93C5FD",
    "BB": "#7C3AED",
    "B": "#FCD34D",
    "CCC": "#F97316",
    "CC": "#F43F5E",
    "C": "#991B1B",
}


def load_bundle(path: Path) -> Dict[str, pd.DataFrame]:
    """Load or create the synthetic demo bundle."""
    if not path.exists():
        generate_default_json(path)
    raw = json.loads(path.read_text())
    return {key: pd.DataFrame(rows) for key, rows in raw.items()}


BUNDLE = load_bundle(DATA_PATH)
PORTFOLIO_OPTIONS = sorted(BUNDLE["instrument_reference"]["portfolioIdentifier"].unique())
PROPERTY_OPTIONS = sorted(BUNDLE["instrument_reference"]["propertyStatus"].unique())
SCENARIO_OPTIONS = ["All"] + sorted(BUNDLE["instrument_reference"]["scenarioIdentifier"].unique())

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.SLATE, "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap"],
    suppress_callback_exceptions=True,
    title=APP_TITLE,
)
server = app.server


def _apply_filters(
    scenario: str,
    portfolios: List[str] | None,
    properties: List[str] | None,
    occupancy: str,
) -> Dict[str, pd.DataFrame]:
    ref = BUNDLE["instrument_reference"].copy()
    results = BUNDLE["instrument_result"].copy()
    risk = BUNDLE["instrument_risk_metric"].copy()
    chargeoff = BUNDLE["chargeoff"].copy()

    if scenario and scenario != "All":
        ref = ref[ref["scenarioIdentifier"] == scenario]
        results = results[results["scenarioIdentifier"] == scenario]
        risk = risk[risk["scenarioIdentifier"] == scenario]

    if portfolios:
        ref = ref[ref["portfolioIdentifier"].isin(portfolios)]
        results = results[results["portfolioIdentifier"].isin(portfolios)]
        risk = risk[risk["portfolioIdentifier"].isin(portfolios)]

    if properties:
        ref = ref[ref["propertyStatus"].isin(properties)]
        risk = risk[risk["propertyStatus"].isin(properties)]

    if occupancy and occupancy != "All":
        ref = ref[ref["occupancyStatus"] == occupancy]
        risk = risk[risk["occupancyStatus"] == occupancy]

    keep_ids = set(ref["instrumentIdentifier"])
    results = results[results["instrumentIdentifier"].isin(keep_ids)]
    risk = risk[risk["instrumentIdentifier"].isin(keep_ids)]
    chargeoff = chargeoff[chargeoff["instrumentIdentifier"].isin(keep_ids)]

    return {
        "reference": ref,
        "results": results,
        "risk": risk,
        "chargeoff": chargeoff,
    }


def _latest_risk(risk: pd.DataFrame) -> pd.DataFrame:
    if risk.empty:
        return pd.DataFrame(columns=risk.columns)
    risk = risk.copy()
    risk["reportingDate"] = pd.to_datetime(risk["reportingDate"])
    return risk.sort_values("reportingDate").groupby("instrumentIdentifier").tail(1)


def _geo_summary(ref: pd.DataFrame, risk: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    latest = _latest_risk(risk)
    geo = ref.merge(
        latest[["instrumentIdentifier", "annualizedCumulativePD", "lgd", "ead"]],
        on="instrumentIdentifier",
        how="left",
    )
    geo["exposure"] = geo["amortizedCost"]
    state = (
        geo.groupby("borrowerState")
        .agg(
            avg_pd=("annualizedCumulativePD", "mean"),
            avg_lgd=("lgd", "mean"),
            exposure=("exposure", "sum"),
            instruments=("instrumentIdentifier", "nunique"),
        )
        .reset_index()
        .rename(columns={"borrowerState": "state"})
    )
    if not state.empty and state["exposure"].sum() > 0:
        state["exposure_share"] = state["exposure"] / state["exposure"].sum()
    else:
        state["exposure_share"] = 0.0

    cbsa = (
        geo.groupby(["cbsaName", "geographyCode"])
        .agg(
            avg_pd=("annualizedCumulativePD", "mean"),
            avg_lgd=("lgd", "mean"),
            exposure=("exposure", "sum"),
            instruments=("instrumentIdentifier", "nunique"),
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
        )
        .reset_index()
        .rename(columns={"geographyCode": "cbsaCode"})
    )
    if not cbsa.empty and cbsa["exposure"].sum() > 0:
        cbsa["exposure_share"] = cbsa["exposure"] / cbsa["exposure"].sum()
    else:
        cbsa["exposure_share"] = 0.0
    return state, cbsa


def _rating_views(results: pd.DataFrame) -> Tuple[go.Figure, go.Figure]:
    if results.empty:
        return go.Figure(), go.Figure()

    start = results[results["reportingDate"] == "2023-06-30"][["instrumentIdentifier", "riskClassification"]]
    end = results[results["reportingDate"] == "2025-06-30"][["instrumentIdentifier", "riskClassification"]]
    merged = start.merge(end, on="instrumentIdentifier", suffixes=("_start", "_end"))
    if merged.empty:
        return go.Figure(), go.Figure()

    matrix = (
        merged.groupby(["riskClassification_start", "riskClassification_end"])
        .size()
        .reset_index(name="count")
    )
    node_labels = [rating for rating in RATING_ORDER if rating in set(matrix["riskClassification_start"]).union(matrix["riskClassification_end"])]
    idx_map = {label: i for i, label in enumerate(node_labels)}

    sankey = go.Figure(
        go.Sankey(
            node=dict(
                pad=14,
                thickness=18,
                line=dict(color="#0b132b", width=0.5),
                label=node_labels,
                color=[RATING_COLOR.get(label, "#f8fafc") for label in node_labels],
            ),
            link=dict(
                source=[idx_map[row["riskClassification_start"]] for _, row in matrix.iterrows()],
                target=[idx_map[row["riskClassification_end"]] for _, row in matrix.iterrows()],
                value=matrix["count"].tolist(),
                color="rgba(126, 190, 255, 0.4)",
            ),
        )
    )
    sankey.update_layout(margin=dict(l=0, r=0, t=10, b=10), font=dict(color="#e8edf2"))

    heat = matrix.pivot_table(
        index="riskClassification_start",
        columns="riskClassification_end",
        values="count",
        fill_value=0,
    ).reindex(index=RATING_ORDER, columns=RATING_ORDER, fill_value=0)
    heat = heat.dropna(how="all").dropna(axis=1, how="all")
    heat_fig = px.imshow(
        heat,
        aspect="auto",
        color_continuous_scale="Purples",
        labels={"x": "End rating", "y": "Start rating", "color": "Count"},
    )
    heat_fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    return sankey, heat_fig


def _pd_trend(risk: pd.DataFrame) -> go.Figure:
    if risk.empty:
        return go.Figure()
    df = risk.copy()
    df["month"] = pd.to_datetime(df["reportingDate"]).dt.to_period("M").astype(str)
    trend = (
        df.groupby(["scenarioIdentifier", "month"])["annualizedCumulativePD"]
        .mean()
        .reset_index()
        .sort_values("month")
    )
    fig = px.line(
        trend,
        x="month",
        y="annualizedCumulativePD",
        color="scenarioIdentifier",
        markers=True,
        labels={"annualizedCumulativePD": "Average PD", "scenarioIdentifier": "Scenario"},
        color_discrete_sequence=["#7BD6F5", "#F7B267", "#C084FC"],
    )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    fig.update_traces(line=dict(width=3))
    return fig


def _loss_view(risk: pd.DataFrame, chargeoff: pd.DataFrame) -> go.Figure:
    if risk.empty:
        return go.Figure()
    risk = risk.copy()
    risk["reportingDate"] = pd.to_datetime(risk["reportingDate"])
    snapshot = risk[risk["reportingDate"] <= pd.Timestamp("2023-12-31")]
    snapshot = snapshot.sort_values("reportingDate").groupby("instrumentIdentifier").tail(1)
    snapshot["expected_loss"] = snapshot["annualizedCumulativePD"] * snapshot["lgd"] * snapshot["ead"]
    expected_total = snapshot["expected_loss"].sum()

    if chargeoff.empty:
        months = ["2024-{:02d}".format(m) for m in range(1, 13)]
        realized = pd.DataFrame({"month": months, "netChargeOffAmount": 0.0})
    else:
        df = chargeoff.copy()
        df["month"] = pd.to_datetime(df["chargeOffDate"]).dt.to_period("M").astype(str)
        realized = df.groupby("month")["netChargeOffAmount"].sum().reset_index()

    realized["expected"] = expected_total

    fig = go.Figure()
    fig.add_bar(
        x=realized["month"],
        y=realized["netChargeOffAmount"],
        name="Realized",
        marker_color="#ffb347",
    )
    fig.add_scatter(
        x=realized["month"],
        y=realized["expected"],
        name="Expected (Q4'23 snapshot)",
        mode="lines",
        line=dict(color="#7BD6F5", width=3, dash="dash"),
    )
    fig.update_layout(
        barmode="group",
        margin=dict(l=0, r=0, t=10, b=0),
        yaxis_title="Loss amount",
        xaxis_title="Month",
    )
    return fig


def _cohort_view(risk: pd.DataFrame, chargeoff: pd.DataFrame) -> Tuple[go.Figure, List[Dict[str, object]]]:
    outputs = build_default_cohorts(risk, chargeoff)
    if not outputs or outputs["pd_path"].empty:
        return go.Figure(), []
    pd_path = outputs["pd_path"].copy()
    pd_path["months_to_default"] = pd_path["months_to_default"].astype(int)
    cohort_fig = px.line(
        pd_path,
        x="months_to_default",
        y="pd_value",
        labels={"months_to_default": "Months to default", "pd_value": "Average PD"},
        markers=True,
        color_discrete_sequence=["#C084FC"],
    )
    cohort_fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))

    latest = outputs["latest_pd"].copy()
    latest["pd_before_default"] = latest["pd_before_default"].round(4)
    latest["event_date"] = pd.to_datetime(latest["event_date"]).dt.strftime("%Y-%m-%d")
    data = latest.rename(
        columns={
            "instrumentIdentifier": "Instrument",
            "pd_before_default": "PD before default",
            "event_date": "Default date",
        }
    ).to_dict(orient="records")
    return cohort_fig, data


def _format_currency(value: float) -> str:
    return f"${value:,.0f}"


def _format_percent(value: float) -> str:
    return f"{value:.1%}"


def _metric_cards(ref: pd.DataFrame, risk: pd.DataFrame, chargeoff: pd.DataFrame) -> Tuple[str, str, str, str]:
    exposure = ref["amortizedCost"].sum()
    latest = _latest_risk(risk)
    avg_pd = latest["annualizedCumulativePD"].mean() if not latest.empty else 0.0
    defaults = chargeoff["instrumentIdentifier"].nunique()
    portfolios = ref["portfolioIdentifier"].nunique()
    return (
        _format_currency(exposure),
        _format_percent(avg_pd),
        f"{defaults} defaults",
        f"{portfolios} portfolios",
    )


def _state_map(df: pd.DataFrame, metric: str) -> go.Figure:
    if df.empty:
        return go.Figure()
    metric_label = {"avg_pd": "Avg PD", "avg_lgd": "Avg LGD", "exposure_share": "Exposure share"}[metric]
    fig = px.choropleth(
        df,
        locations="state",
        locationmode="USA-states",
        color=metric,
        color_continuous_scale="Magma",
        scope="usa",
        hover_data={"avg_pd": ":.2%", "avg_lgd": ":.2%", "exposure_share": ":.1%", "exposure": ":,.0f"},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_colorbar=dict(title=metric_label))
    return fig


def _cbsa_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    top = df.sort_values("exposure", ascending=False).head(12)
    fig = px.bar(
        top,
        x="exposure",
        y="cbsaName",
        color="avg_pd",
        orientation="h",
        labels={"cbsaName": "CBSA", "exposure": "Amortized cost", "avg_pd": "Avg PD"},
        color_continuous_scale="Viridis",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    fig.update_traces(marker_line_color="#0b132b", marker_line_width=0.5)
    return fig


def _cbsa_map(df: pd.DataFrame, metric: str) -> go.Figure:
    if df.empty:
        return go.Figure()
    color_label = {"avg_pd": "Avg PD", "avg_lgd": "Avg LGD", "exposure_share": "Exposure share"}[metric]
    df = df.sort_values("exposure", ascending=False)
    fig = px.scatter_mapbox(
        df,
        lat="latitude",
        lon="longitude",
        size="exposure",
        color=metric,
        hover_name="cbsaName",
        hover_data={"avg_pd": ":.2%", "avg_lgd": ":.2%", "exposure_share": ":.1%", "exposure": ":,.0f"},
        color_continuous_scale="Magma",
        mapbox_style="carto-positron",
        zoom=3,
        height=500,
        size_max=38,
        labels={metric: color_label},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    return fig


app.layout = dbc.Container(
    [
        html.Div(
            [
                html.H1(APP_TITLE, className="hero-title"),
                html.P(
                    "A design-forward tour of Southside's credit universe using fully synthetic data. "
                    "Use the filters to reshape the book and watch geography, ratings, and loss curves respond.",
                    className="hero-body",
                ),
            ],
            className="hero",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Dropdown(
                        id="scenario-filter",
                        options=[{"label": opt, "value": opt} for opt in SCENARIO_OPTIONS],
                        value="All",
                        clearable=False,
                        className="control",
                    ),
                    md=3,
                ),
                dbc.Col(
                    dcc.Dropdown(
                        id="portfolio-filter",
                        options=[{"label": p, "value": p} for p in PORTFOLIO_OPTIONS],
                        value=[],
                        multi=True,
                        placeholder="Portfolios (all)",
                        className="control",
                    ),
                    md=3,
                ),
                dbc.Col(
                    dcc.Dropdown(
                        id="property-filter",
                        options=[{"label": p, "value": p} for p in PROPERTY_OPTIONS],
                        value=[],
                        multi=True,
                        placeholder="Property groups (all)",
                        className="control",
                    ),
                    md=3,
                ),
                dbc.Col(
                    dcc.Dropdown(
                        id="occupancy-filter",
                        options=[{"label": opt, "value": opt} for opt in ["All", "Owner-occupied", "Non-owner-occupied"]],
                        value="All",
                        clearable=False,
                        className="control",
                    ),
                    md=3,
                ),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(html.Div([html.Div("Total amortized cost"), html.Div(id="metric-exposure", className="metric-value")], className="metric-card"), md=3),
                dbc.Col(html.Div([html.Div("Portfolio-average PD"), html.Div(id="metric-pd", className="metric-value")], className="metric-card"), md=3),
                dbc.Col(html.Div([html.Div("Defaults in 2024"), html.Div(id="metric-defaults", className="metric-value")], className="metric-card"), md=3),
                dbc.Col(html.Div([html.Div("Active portfolios"), html.Div(id="metric-portfolios", className="metric-value")], className="metric-card"), md=3),
            ],
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    dcc.RadioItems(
                                        id="metric-selector",
                                        options=[
                                            {"label": "Avg PD", "value": "avg_pd"},
                                            {"label": "Avg LGD", "value": "avg_lgd"},
                                            {"label": "Exposure share", "value": "exposure_share"},
                                        ],
                                        value="avg_pd",
                                        inline=True,
                                        className="pill-group",
                                    ),
                                    md=8,
                                ),
                                dbc.Col(
                                    dcc.RadioItems(
                                        id="geo-level",
                                        options=[{"label": "State", "value": "state"}, {"label": "CBSA", "value": "cbsa"}],
                                        value="state",
                                        inline=True,
                                        className="pill-group",
                                    ),
                                    md=4,
                                    style={"textAlign": "right"},
                                ),
                            ]
                        ),
                        dcc.Graph(id="state-map", className="card"),
                    ],
                    md=7,
                ),
                dbc.Col(dcc.Graph(id="cbsa-bar", className="card"), md=5),
            ],
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="rating-sankey", className="card"), md=7),
                dbc.Col(dcc.Graph(id="rating-heatmap", className="card"), md=5),
            ],
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="pd-trend", className="card"), md=6),
                dbc.Col(dcc.Graph(id="loss-chart", className="card"), md=6),
            ],
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="cohort-chart", className="card"), md=6),
                dbc.Col(
                    dash_table.DataTable(
                        id="cohort-table",
                        columns=[
                            {"name": "Instrument", "id": "Instrument"},
                            {"name": "PD before default", "id": "PD before default"},
                            {"name": "Default date", "id": "Default date"},
                        ],
                        data=[],
                        style_table={"height": "360px", "overflowY": "auto"},
                        style_cell={"backgroundColor": "#0f172a", "color": "#e2e8f0", "border": "none"},
                        style_header={"backgroundColor": "#1e293b", "fontWeight": "600"},
                    ),
                    md=6,
                ),
            ]
        ),
    ],
    fluid=True,
    className="layout",
)


@app.callback(
    [
        Output("metric-exposure", "children"),
        Output("metric-pd", "children"),
        Output("metric-defaults", "children"),
        Output("metric-portfolios", "children"),
        Output("state-map", "figure"),
        Output("cbsa-bar", "figure"),
        Output("rating-sankey", "figure"),
        Output("rating-heatmap", "figure"),
        Output("pd-trend", "figure"),
        Output("loss-chart", "figure"),
        Output("cohort-chart", "figure"),
        Output("cohort-table", "data"),
    ],
    [
        Input("scenario-filter", "value"),
        Input("portfolio-filter", "value"),
        Input("property-filter", "value"),
        Input("occupancy-filter", "value"),
        Input("metric-selector", "value"),
        Input("geo-level", "value"),
    ],
)
def refresh_dashboard(
    scenario: str,
    portfolios: List[str],
    properties: List[str],
    occupancy: str,
    metric: str,
    geo_level: str,
):
    portfolios = portfolios or []
    properties = properties or []
    frames = _apply_filters(scenario, portfolios, properties, occupancy)
    ref = frames["reference"]
    results = frames["results"]
    risk = frames["risk"]
    chargeoff = frames["chargeoff"]

    state_summary, cbsa_summary = _geo_summary(ref, risk)
    map_fig = _state_map(state_summary, metric) if geo_level == "state" else _cbsa_map(cbsa_summary, metric)
    cbsa_fig = _cbsa_bar(cbsa_summary)

    sankey_fig, heat_fig = _rating_views(results)
    pd_trend_fig = _pd_trend(risk)
    loss_fig = _loss_view(risk, chargeoff)
    cohort_fig, cohort_table = _cohort_view(risk, chargeoff)

    k1, k2, k3, k4 = _metric_cards(ref, risk, chargeoff)
    return k1, k2, k3, k4, map_fig, cbsa_fig, sankey_fig, heat_fig, pd_trend_fig, loss_fig, cohort_fig, cohort_table


if __name__ == "__main__":
    app.run_server(debug=True, port=8501)
