# Southside Bank Risk Dashboard

Streamlit-based analytics workspace for ingesting quarterly Southside Bank risk datasets,
harmonizing them across canonical schemas, and delivering five investigative
views:

1. **Real Estate PD Heatmap** - CBSA-level choropleth with occupancy and property segmentation.
2. **Risk Rating Migration** - 2023 to 2025 transition analysis and top movers.
3. **Backtest (Realizations in 2024)** - Expected vs realized loss diagnostics.
4. **Macro Linkage** - Macro correlations and regression insights.
5. **Defaulted Cohorts** - 36-month pre-default event study.

The implementation roadmap follows the specification provided by the Southside Bank team
and will be executed across multiple commits to highlight key milestones.

## Developer notes

- Upload panels validate required headers per page; the Explain Data expander lists the exact columns selected.
- Exports persist CSV/Parquet artifacts under `processed/` for downstream reuse.
- Synthetic inputs for demos/tests can be generated via `wow_risk_dashboard.io.sample` (see `sample_inputs_for_page`).
