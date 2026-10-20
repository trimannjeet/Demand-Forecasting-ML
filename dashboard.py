
import io
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st


API_BASE_URL = os.getenv(
    "DEMAND_API_URL", "http://127.0.0.1:8000"
).rstrip("/")

st.set_page_config(
    page_title="DemandIQ | Forecasting",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.20);
        padding: 16px;
        border-radius: 14px;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_error(response):
    try:
        body = response.json()
        return body.get("detail", body)
    except Exception:
        return response.text or f"HTTP {response.status_code}"


def upload_file(uploaded_file):
    return {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }


def make_group_label(group):
    if not group:
        return "Overall"
    return " / ".join(
        f"{key}: {value}"
        for key, value in group.items()
    )


def load_uploaded_dataframe(uploaded_file):
    content = uploaded_file.getvalue()
    extension = uploaded_file.name.lower().rsplit(".", 1)[-1]

    if extension == "csv":
        return pd.read_csv(io.BytesIO(content))
    if extension in {"xlsx", "xls"}:
        return pd.read_excel(io.BytesIO(content))

    raise ValueError("Unsupported file format.")


def make_historical_data(
    df, date_column, target_column, group_columns, frequency
):
    work = df[[date_column, target_column] + group_columns].copy()

    work[date_column] = pd.to_datetime(
        work[date_column], errors="coerce", dayfirst=True
    )
    work[target_column] = pd.to_numeric(
        work[target_column], errors="coerce"
    )

    work = work.dropna(subset=[date_column, target_column])

    if work.empty:
        return pd.DataFrame(
            columns=["date", "value", "series", "kind"]
        )

    if frequency == "daily":
        work["date"] = work[date_column].dt.normalize()
    elif frequency == "weekly":
        work["date"] = (
            work[date_column].dt.to_period("W-SUN")
            .dt.end_time.dt.normalize()
        )
    else:
        work["date"] = (
            work[date_column].dt.to_period("M")
            .dt.end_time.dt.normalize()
        )

    keys = ["date"] + group_columns
    work = (
        work.groupby(keys, dropna=False, as_index=False)[target_column]
        .sum()
    )

    if group_columns:
        work["series"] = work[group_columns].apply(
            lambda row: " / ".join(
                f"{col}: {row[col]}"
                for col in group_columns
            ),
            axis=1,
        )
    else:
        work["series"] = "Overall"

    return work.rename(
        columns={target_column: "value"}
    )[["date", "value", "series"]].assign(kind="Actual")


def make_forecast_data(results):
    frames = []

    for item in results:
        if "error" in item:
            continue

        forecast = pd.DataFrame(item.get("forecast", []))
        if forecast.empty:
            continue

        forecast["date"] = pd.to_datetime(
            forecast["date"], errors="coerce"
        )
        forecast["value"] = pd.to_numeric(
            forecast["prediction"], errors="coerce"
        )
        forecast["series"] = make_group_label(
            item.get("group", {})
        )
        forecast["kind"] = "Forecast"

        frames.append(
            forecast[["date", "value", "series", "kind"]]
        )

    if not frames:
        return pd.DataFrame(
            columns=["date", "value", "series", "kind"]
        )

    return pd.concat(frames, ignore_index=True)


def money_or_number(value):
    if pd.isna(value):
        return "—"
    return f"{value:,.2f}"


# Sidebar
with st.sidebar:
    st.markdown("## 📈 DemandIQ")
    st.caption("Demand forecasting & business analytics")
    st.divider()

    st.markdown("### Workspace")
    st.caption("Upload your own business dataset.")
    uploaded_file = st.file_uploader(
        "Upload sales data",
        type=["csv", "xlsx", "xls"],
        help="Maximum upload size is controlled by the API.",
    )

    st.divider()
    st.markdown("### API status")

    try:
        health_response = requests.get(
            f"{API_BASE_URL}/health", timeout=3
        )
        if health_response.ok:
            st.success("API connected")
        else:
            st.error(f"API returned {health_response.status_code}")
    except requests.RequestException:
        st.error("API offline")
        st.caption("Start FastAPI in another terminal.")

    st.caption(f"Endpoint: {API_BASE_URL}")


# Header
st.title("Demand Forecasting Workspace")
st.write(
    "Explore historical demand, compare forecasting models, "
    "and estimate future sales using your own data."
)

if not uploaded_file:
    st.info(
        "Upload a CSV or Excel file in the sidebar to begin. "
        "The dashboard will profile your columns before forecasting."
    )

    left, right = st.columns(2)
    with left:
        st.markdown("#### What you can do")
        st.markdown(
            "- Inspect data quality and missing values\n"
            "- Choose date, target and grouping columns\n"
            "- Compare candidate forecasting models\n"
            "- Visualize actual and forecast values"
        )
    with right:
        st.markdown("#### Supported workflows")
        st.markdown(
            "- One overall sales time series\n"
            "- Multiple stores, products or regions\n"
            "- Daily, weekly and monthly observations\n"
            "- Downloadable forecast and evaluation files"
        )

    st.stop()


# Profile the uploaded file
try:
    with st.spinner("Inspecting your dataset..."):
        profile_response = requests.post(
            f"{API_BASE_URL}/profile",
            files=upload_file(uploaded_file),
            timeout=60,
        )

    if not profile_response.ok:
        st.error(f"Dataset profiling failed: {api_error(profile_response)}")
        st.stop()

    profile = profile_response.json()
    df = load_uploaded_dataframe(uploaded_file)

except requests.RequestException as exc:
    st.error(f"Could not reach the API: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Could not read the uploaded dataset: {exc}")
    st.stop()


# Dataset overview
st.subheader("Dataset overview")

metric_cols = st.columns(4)
metric_cols[0].metric("Rows", f"{profile['rows']:,}")
metric_cols[1].metric("Columns", f"{profile['columns_count']:,}")
metric_cols[2].metric(
    "Duplicate rows", f"{profile['duplicate_rows']:,}"
)
metric_cols[3].metric(
    "Missing cells",
    f"{sum(c['null_count'] for c in profile['columns']):,}",
)

with st.expander("Inspect column metadata", expanded=False):
    metadata = pd.DataFrame(profile["columns"])
    st.dataframe(metadata, use_container_width=True, hide_index=True)

with st.expander("Preview uploaded data", expanded=False):
    st.dataframe(df.head(100), use_container_width=True)


# Configuration
suggestions = profile.get("suggestions", {})
column_names = list(df.columns)

st.subheader("Forecast configuration")

date_default = suggestions.get("suggested_date_column")
target_default = suggestions.get("suggested_target_column")

date_index = (
    column_names.index(date_default)
    if date_default in column_names else 0
)

numeric_candidates = [
    col for col in column_names
    if pd.to_numeric(df[col], errors="coerce").notna().any()
]

target_options = numeric_candidates or column_names
target_index = (
    target_options.index(target_default)
    if target_default in target_options else 0
)

with st.form("forecast_configuration"):
    col1, col2 = st.columns(2)

    with col1:
        date_column = st.selectbox(
            "Date column",
            options=column_names,
            index=date_index,
        )

        target_column = st.selectbox(
            "Target column",
            options=target_options,
            index=target_index,
            help="Choose the numeric value you want to forecast.",
        )

    with col2:
        group_columns = st.multiselect(
            "Grouping columns (optional)",
            options=[
                col for col in column_names
                if col not in {date_column, target_column}
            ],
            help="For example: Store, Product or Region.",
        )

        frequency = st.selectbox(
            "Observation frequency",
            ["auto", "daily", "weekly", "monthly"],
            index=0,
        )

    missing_period = st.selectbox(
        "How should missing periods be handled?",
        options=["zero", "keep"],
        format_func=lambda x: (
            "Fill missing periods with zero"
            if x == "zero"
            else "Keep missing values (forecasting may be blocked)"
        ),
        help=(
            "Zero is appropriate only when missing periods mean "
            "no sales. Use caution with incomplete source data."
        ),
    )

    one_calendar_year = st.checkbox(
        "Forecast one calendar year",
        value=True,
    )

    horizon = None
    if not one_calendar_year:
        horizon = st.number_input(
            "Forecast horizon (observations)",
            min_value=1,
            max_value=5000,
            value=30,
            step=1,
        )

    submitted = st.form_submit_button(
        "Generate forecast",
        type="primary",
        use_container_width=True,
    )


if submitted:
    form_data = {
        "date_column": date_column,
        "target_column": target_column,
        "group_columns": ",".join(group_columns),
        "frequency": frequency,
        "one_calendar_year": str(one_calendar_year).lower(),
        "missing_period": missing_period,
    }

    if not one_calendar_year:
        form_data["horizon"] = str(int(horizon))

    try:
        with st.spinner(
            "Preparing series, evaluating models and forecasting..."
        ):
            response = requests.post(
                f"{API_BASE_URL}/forecast",
                files=upload_file(uploaded_file),
                data=form_data,
                timeout=300,
            )

        if not response.ok:
            st.error(f"Forecast failed: {api_error(response)}")
            st.stop()

        st.session_state["forecast_response"] = response.json()
        st.session_state["forecast_source_name"] = uploaded_file.name
        st.session_state["forecast_config"] = {
            "date_column": date_column,
            "target_column": target_column,
            "group_columns": group_columns,
        }

    except requests.RequestException as exc:
        st.error(f"Could not complete the forecast request: {exc}")
        st.stop()


# Results
forecast_result = st.session_state.get("forecast_response")

if forecast_result:
    if st.session_state.get("forecast_source_name") != uploaded_file.name:
        st.warning(
            "The uploaded filename changed. Generate a new forecast "
            "to refresh the results."
        )
        st.stop()

    results = forecast_result.get("results", [])
    successful = [
        item for item in results if "error" not in item
    ]
    failed = [
        item for item in results if "error" in item
    ]

    if not successful:
        st.error("No forecasting series completed successfully.")
        st.stop()

    forecast_data = make_forecast_data(results)
    config = st.session_state["forecast_config"]

    try:
        historical = make_historical_data(
            df,
            config["date_column"],
            config["target_column"],
            config["group_columns"],
            forecast_result["frequency"],
        )
    except Exception as exc:
        historical = pd.DataFrame(
            columns=["date", "value", "series", "kind"]
        )
        st.warning(f"Historical chart could not be prepared: {exc}")

    st.divider()
    st.subheader("Forecast results")

    total_historical = (
        historical["value"].sum() if not historical.empty else float("nan")
    )
    total_forecast = (
        forecast_data["value"].sum()
        if not forecast_data.empty else float("nan")
    )

    first_model = successful[0]["best_model"]
    horizon_values = sorted(
        set(item["horizon"] for item in successful)
    )

    kpi = st.columns(4)
    kpi[0].metric(
        "Historical total",
        money_or_number(total_historical),
    )
    kpi[1].metric(
        "Forecast total",
        money_or_number(total_forecast),
    )
    kpi[2].metric("Selected model", first_model)
    kpi[3].metric(
        "Successful series",
        f"{len(successful)} / {len(results)}",
    )

    st.caption(
        f"Frequency: {forecast_result['frequency']} · "
        f"Forecast horizon: {', '.join(map(str, horizon_values))} "
        f"observations per successful series"
    )

    if failed:
        with st.expander(
            f"Review {len(failed)} unsuccessful series"
        ):
            st.json(failed)

    tab_overview, tab_models, tab_data = st.tabs(
        ["Forecast overview", "Model evaluation", "Data & exports"]
    )

    with tab_overview:
        st.markdown("#### Historical demand and forecast")

        if historical.empty:
            st.warning(
                "No historical values could be plotted. Check the "
                "date and target columns."
            )
        else:
            chart_data = pd.concat(
                [historical, forecast_data],
                ignore_index=True,
            )

            series_options = sorted(
                chart_data["series"].dropna().unique().tolist()
            )

            selected_series = st.multiselect(
                "Choose series to display",
                options=series_options,
                default=series_options[:10],
            )

            visible = chart_data[
                chart_data["series"].isin(selected_series)
            ]

            if not visible.empty:
                fig = px.line(
                    visible.sort_values("date"),
                    x="date",
                    y="value",
                    color="series",
                    line_dash="kind",
                    markers=False,
                    title="Actual vs forecast",
                    labels={
                        "date": "Date",
                        "value": config["target_column"],
                        "series": "Series",
                        "kind": "Data type",
                    },
                )
                fig.update_layout(
                    hovermode="x unified",
                    legend_title_text="Series / type",
                    margin=dict(l=10, r=10, t=55, b=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Select at least one series to display.")

        if not forecast_data.empty:
            st.markdown("#### Forecast trend")
            forecast_fig = px.line(
                forecast_data,
                x="date",
                y="value",
                color="series",
                title="Forecast by series",
                labels={
                    "date": "Date",
                    "value": config["target_column"],
                    "series": "Series",
                },
            )
            st.plotly_chart(
                forecast_fig, use_container_width=True
            )

    with tab_models:
        st.markdown("#### Model comparison")

        evaluation_rows = []
        for item in successful:
            for metric in item.get("evaluation", []):
                evaluation_rows.append({
                    "Series": make_group_label(item.get("group", {})),
                    **metric,
                })

        if evaluation_rows:
            evaluation_df = pd.DataFrame(evaluation_rows)
            st.dataframe(
                evaluation_df,
                use_container_width=True,
                hide_index=True,
            )

            metric_column = st.selectbox(
                "Compare models by",
                ["mae", "rmse", "smape_percent", "wape_percent"],
                format_func=lambda value: {
                    "mae": "MAE",
                    "rmse": "RMSE",
                    "smape_percent": "sMAPE (%)",
                    "wape_percent": "WAPE (%)",
                }[value],
            )

            plot_df = evaluation_df.dropna(
                subset=[metric_column]
            )

            if not plot_df.empty:
                metric_fig = px.bar(
                    plot_df,
                    x="model",
                    y=metric_column,
                    color="Series",
                    barmode="group",
                    title=f"Model comparison — {metric_column}",
                )
                st.plotly_chart(
                    metric_fig, use_container_width=True
                )
        else:
            st.info("No model evaluation metrics are available.")

        st.caption(
            "These metrics come from a chronological holdout, not "
            "from the future forecast. Lower error is generally better."
        )

    with tab_data:
        st.markdown("#### Forecast data")
        st.dataframe(
            forecast_data.sort_values(["series", "date"]),
            use_container_width=True,
            hide_index=True,
        )

        forecast_csv = forecast_data.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "Download forecast CSV",
            data=forecast_csv,
            file_name="demand_forecast.csv",
            mime="text/csv",
            use_container_width=True,
        )

        if "evaluation_df" in locals() and not evaluation_df.empty:
            st.download_button(
                "Download model evaluation CSV",
                data=evaluation_df.to_csv(index=False).encode("utf-8"),
                file_name="model_evaluation.csv",
                mime="text/csv",
                use_container_width=True,
            )

        if not historical.empty:
            st.download_button(
                "Download historical series CSV",
                data=historical.to_csv(index=False).encode("utf-8"),
                file_name="historical_series.csv",
                mime="text/csv",
                use_container_width=True,
            )

    st.caption(
        "Forecasts are estimates, not guarantees. Validate data quality "
        "and model performance before making inventory or purchasing decisions."
    )
