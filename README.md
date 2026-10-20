# Demand Forecasting

A demand forecasting application for exploring historical sales, comparing forecasting models, and generating predictions for stores, products, or other groups. Upload a CSV or Excel dataset, inspect its data quality, configure the forecast, and review interactive charts and downloadable results.

## Features

- CSV and Excel upload with automatic column suggestions and data-quality profiling.
- Daily, weekly, and monthly time-series preparation, with optional grouping.
- Forecast model evaluation and holdout metrics.
- Interactive React dashboard and a Streamlit interface.
- Forecast charts, group summaries, and CSV exports.
- A Jupyter notebook for exploring the forecasting workflow.

## Technology

- **API:** Python, FastAPI, pandas, NumPy, and statsmodels
- **Frontend:** React, TypeScript, Vite, and Recharts
- **Additional interface:** Streamlit

## Requirements

- Python 3.11 or newer
- Node.js and npm

## Run locally (Windows PowerShell)

Create and activate a virtual environment, then install the Python dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start the API in one terminal:

```powershell
python backend\main.py
```

Start the React dashboard in a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`. The API runs at `http://127.0.0.1:8000`; interactive API documentation is available at `http://127.0.0.1:8000/docs`.

To run the Streamlit interface instead, start it in another terminal while the API is running:

```powershell
streamlit run dashboard.py
```

To run the test suite from the project root:

```powershell
python -m pytest tests
```

To use a different API URL with the React app, set `VITE_API_BASE_URL` before starting Vite. The Streamlit app reads `DEMAND_API_URL`.

## Forecast workflow

1. Upload a CSV, XLSX, or XLS dataset.
2. Confirm the date and numeric target columns suggested by the profiler.
3. Optionally choose grouping columns such as store or product.
4. Select frequency, missing-period behavior, and forecast horizon.
5. Generate a forecast, compare model metrics, inspect charts and data-quality signals, and export results as CSV.

## Example data

`data/Walmart.csv` is included as an example dataset. You can upload your own CSV or Excel file through either dashboard.

Forecast accuracy depends on the quality and history of the supplied data. Forecasts are estimates and should be validated before operational use.
