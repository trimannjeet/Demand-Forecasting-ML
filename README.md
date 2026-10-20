# Demand Forecasting & Business Analytics

An intelligent demand forecasting application that analyzes historical business data, compares time-series forecasting models, and predicts future demand. It helps users explore sales trends, evaluate model performance, and make more informed planning decisions.

## Project Overview

Demand Forecasting & Business Analytics accepts business datasets in CSV, XLSX, and XLS formats. It profiles uploaded data, suggests date and target columns, prepares time series, evaluates forecasting models, and generates future predictions.

The project includes a **FastAPI backend**, an interactive **Streamlit dashboard**, a **React + TypeScript frontend**, and a Jupyter notebook for exploring the forecasting workflow.

## Key Features

- **Dataset upload:** Supports CSV, XLSX, and XLS files.
- **Automated dataset profiling:** Reports row and column counts, missing values, unique values, duplicates, and sample data.
- **Column suggestions:** Recommends likely date and numeric target columns.
- **Time-series preparation:** Supports daily, weekly, and monthly forecasting frequencies.
- **Multi-group forecasting:** Forecasts selected stores, products, departments, regions, or other groups.
- **Model comparison:** Evaluates Seasonal Naive, Exponential Smoothing, and AutoReg forecasting models.
- **Rolling-origin backtesting:** Evaluates models using chronological validation windows.
- **Forecast horizon selection:** Supports a custom horizon or forecasting through the next calendar year.
- **Performance metrics:** Calculates MAE, RMSE, sMAPE, and WAPE.
- **Interactive dashboards:** Explore recorded and expected demand, plain-language forecast summaries, peak periods, data quality, and group demand.
- **CSV exports:** Download forecast results and group summaries.
- **Automated tests:** Covers the API, data preparation, and forecasting functionality.

## Technology Stack

| Component | Technologies |
| --- | --- |
| Programming language | Python |
| Backend API | FastAPI |
| Data processing | pandas, NumPy |
| Forecasting | statsmodels, scikit-learn |
| Interactive dashboard | Streamlit |
| Web frontend | React, TypeScript, Vite |
| Charts and icons | Recharts, Lucide React |
| Testing | pytest, FastAPI TestClient |

## Project Structure

```text
DemandForecasting/
├── backend/
│   ├── main.py
│   ├── schemas.py
│   └── services/
│       ├── data_processor.py
│       └── forecasting.py
├── data/
│   └── Walmart.csv
├── frontend/
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── notebooks/
│   └── notebook.ipynb
├── tests/
│   ├── test_api.py
│   ├── test_data_processor.py
│   └── test_forecasting.py
├── dashboard.py
└── requirements.txt
```

## How It Works

1. Upload a historical business dataset.
2. Review the dataset profile and suggested columns.
3. Select the date column, target column, optional grouping columns, and frequency.
4. Prepare the time series and choose how missing periods should be handled.
5. Compare forecasting models using chronological backtesting.
6. Select the best eligible model based on validation MAE and RMSE.
7. Generate predictions for the requested forecast horizon.
8. Review the forecast summary in plain language, explore demand by date and group, and export results as CSV.

## Forecasting Models

### Seasonal Naive

Uses the most recent seasonal pattern as a baseline for future predictions.

### Exponential Smoothing

Models historical level and, when enough data is available, trend and seasonality.

### AutoReg

Uses lagged observations to model relationships between past and future values.

### Evaluation Metrics

| Metric | Purpose |
| --- | --- |
| MAE | Measures the average absolute prediction error. |
| RMSE | Penalizes larger prediction errors more heavily. |
| sMAPE | Measures symmetric percentage prediction error. |
| WAPE | Measures total absolute error relative to total actual demand. |

The best eligible model is selected using validation MAE, with RMSE as a tie-breaker. The selected model is then refitted using the complete available series before future predictions are generated.

## Installation and Setup

### Prerequisites

- Python 3.11 or compatible version
- Node.js and npm for the React frontend
- Git

### 1. Clone the repository

```powershell
git clone https://github.com/trimannjeet/Demand-Forecasting-ML.git
cd Demand-Forecasting-ML
```

### 2. Create and activate a Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, allow it for the current terminal session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Start the FastAPI backend

From the repository root:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at:

- API root: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Interactive API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 5. Start the Streamlit dashboard

Open another terminal in the repository root, activate the virtual environment, and run:

```powershell
streamlit run dashboard.py
```

Streamlit prints the local dashboard URL in the terminal.

### 6. Start the React frontend

Open another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Vite prints the frontend URL, normally [http://localhost:5173/](http://localhost:5173/). API-dependent frontend features require the FastAPI backend to be running.

To use a different API URL with the React app, set `VITE_API_BASE_URL` before starting Vite. The Streamlit app reads `DEMAND_API_URL`.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/` | Returns API information and documentation path. |
| GET | `/health` | Checks API health. |
| POST | `/profile` | Uploads and profiles a dataset. |
| POST | `/forecast` | Prepares time-series data and generates forecasts. |

### Dataset Profiling

Send a multipart form request to `/profile` with a dataset file. The response includes the filename, row and column counts, column metadata, profiling statistics, and suggested columns.

### Forecast Generation

Send a multipart form request to `/forecast` with the following fields:

| Field | Description |
| --- | --- |
| `file` | Uploaded CSV, XLSX, or XLS dataset. |
| `date_column` | Column containing dates. |
| `target_column` | Numeric column to forecast. |
| `group_columns` | Optional comma-separated grouping columns. |
| `frequency` | `auto`, `daily`, `weekly`, or `monthly`. |
| `one_calendar_year` | Whether to forecast through the next calendar year. |
| `horizon` | Number of future periods for a custom forecast. |
| `missing_period` | `zero` or `keep`. |

For a custom horizon, set `one_calendar_year` to `false` and provide a positive `horizon`. See `/docs` for the live request schemas and response examples.

## Running Tests

Run the complete test suite from the repository root:

```powershell
python -m pytest -v
```

Run an individual test module:

```powershell
python -m pytest tests/test_api.py -v
python -m pytest tests/test_data_processor.py -v
python -m pytest tests/test_forecasting.py -v
```

The test suite covers API health, dataset profiling, forecast generation, time-series preparation, metric calculations, rolling-origin backtesting, invalid inputs, and forecast date validation.

## Data Validation and Limitations

- Uploads are restricted to CSV, XLSX, and XLS files.
- The API enforces a 25 MB upload limit.
- Forecast requests are limited to 45 groups per request.
- Forecasting requires sufficient valid historical observations.
- Model performance depends on data quality, history length, seasonality, and demand variability.
- Forecasts are estimates, not guarantees of future demand, and should be validated before operational use.

## Roadmap

- [x] Dataset upload, profiling, and column suggestions
- [x] Time-series preparation and forecasting models
- [x] Forecast evaluation metrics and rolling-origin backtesting
- [x] Automated backend and forecasting tests
- [x] Streamlit dashboard
- [x] React analytics dashboard with interactive visualizations
- [x] Forecast and group-summary CSV exports
- [ ] Inventory and replenishment recommendations
- [ ] Expanded forecasting strategies
- [ ] Deployment and production configuration

## Project Objectives

This project demonstrates practical skills in:

- Time-series analysis and forecasting
- Data cleaning and preprocessing
- Forecast model evaluation
- REST API development
- Interactive data visualization
- Frontend and backend integration
- Automated testing and software engineering

## Contributing

Contributions, suggestions, and improvements are welcome:

1. Fork the repository.
2. Create a feature branch.
3. Implement and test your changes.
4. Submit a pull request with a clear description.

## License

No license has been specified yet. Add a `LICENSE` file before distributing the project under an open-source license.

---

**Built with Python, FastAPI, time-series forecasting, and modern web technologies.**
