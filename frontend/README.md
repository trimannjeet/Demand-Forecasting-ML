# DemandIQ frontend

The frontend is a React, TypeScript, and Vite dashboard for the demand forecasting API.

## Run locally

From the project root, start the API in one terminal:

```powershell
python backend\main.py
```

Start the dashboard from a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`. The API is expected at `http://127.0.0.1:8000`; set `VITE_API_BASE_URL` before starting Vite if it runs elsewhere.

## Workflow

1. Upload a CSV, XLSX, or XLS dataset.
2. Confirm the date and numeric target columns.
3. Optionally select one or more grouping columns.
4. Choose frequency, missing-period behavior, and forecast horizon.
5. Generate the forecast and review expected demand, changes from recent periods, peak periods, and demand by group.
6. Review missing values and duplicates, then export forecast values or the group summary as CSV.

Forecasts are based on historical data returned by the API. The dashboard does not infer inventory, stockout, or service-level metrics.
