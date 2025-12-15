# Southside Risk Studio (Dash)

Design-forward Dash experience powered by a synthetic Southside loan book. The
app drops the Streamlit upload flow in favor of a self-contained JSON bundle and
showcases the key slices the business cares about: geography, ratings, loss
realizations, and default cohorts.

## What you get

- `data/southside_demo.json` – 360 instruments spanning 12 CBSAs with monthly PD paths, ratings (2023Q2 → 2025Q2), and 2024 charge-offs.
- Geography pulse – state heatmap plus CBSA bubbles sized by exposure.
- Rating migration – Sankey and transition heatmap to highlight upgrades/downgrades.
- Risk arc – PD trendlines by scenario and expected vs realized loss bars for 2024.
- Default cohorts – 36-month pre-default PD path and a table of latest PDs at default.

## Running the Dash app

```bash
poetry install  # or pip install dash dash-bootstrap-components pandas numpy plotly
poetry run python app.py  # launches at http://127.0.0.1:8501
```

## Regenerating the synthetic bundle

The bundle is deterministic; regenerate it anytime:

```bash
poetry run python -c "from wow_risk_dashboard.io.synthetic_bundle import generate_default_json; print(generate_default_json())"
```

## Filters and interactions

- Scenario, portfolio, property group, and occupancy filters reshape every view.
- Toggle between Avg PD, Avg LGD, and Exposure Share to recolor the map/bubbles.
- CBSA bars remain on the right for quick share/outlier spotting even when the map is in state mode.
