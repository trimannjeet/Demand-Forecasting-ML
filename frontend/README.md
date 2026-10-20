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
2. Confirm the suggested date and demand columns, using the field hints if needed.
3. Optionally select a store or product grouping for separate forecasts.
4. Choose frequency, missing-period behavior, and forecast horizon.
5. Generate the forecast and compare expected demand with the same number of recent periods, overall and across the largest groups.
6. Use the group change chart to spot which stores or products may need attention, then review the peak period and data quality.
7. Export forecast values or the group comparison as CSV.

Forecasts are based on historical data returned by the API. The dashboard does not infer inventory, stockout, or service-level metrics.
