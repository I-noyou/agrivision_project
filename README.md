# AgriVision — Chhattisgarh Smart Crop Yield Optimization Engine

A runnable full-stack MVP with a responsive HTML/CSS/JavaScript dashboard and a Python FastAPI backend. It demonstrates Khasra lookup against one manually transcribed demo record, crop suitability screening, a budget-aware crop allocation engine, crop-zone allocation results, seed-price data, cultivation-cost estimates, and risk-adjusted planning.

## Run on Windows

1. Install Python 3.10 or newer.
2. Extract the project folder.
3. Double-click `start.bat` (or run it from Command Prompt).
4. Wait for dependencies to install and the server to start.
5. Open `http://127.0.0.1:8000` in your browser.
6. API docs: `http://127.0.0.1:8000/docs`.

## Run manually

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## API endpoints

- `GET /api/health`
- `GET /api/districts`
- `GET /api/crops`
- `GET /api/seed-prices`
- `GET /api/cultivation-costs`
- `POST /api/parcels/lookup`
- `POST /api/land/analyze`
- `POST /api/crops/recommend`
- `POST /api/optimize`
- `GET /api/weather?district=Durg&scenario=normal`

## Current data limitations

- **Chhattisgarh only.** One demo parcel is included: Temri, Bori, Durg, Khasra 122/1, 0.2400 ha (about 0.593 acres), with 0.2400 ha shown as irrigated in the supplied record.
- Parcel data is manually transcribed from the supplied Khasra Naksha PDF. There is no live government land-record lookup and no georeferenced boundary data.
- The map is a schematic visualization; crop-zone areas are allocation concepts, not surveyed polygons.
- Paddy, pigeon pea, and kodo seed prices are reported Kharif 2026 schedule references stored with notes; exact variety/category must be checked locally. Missing seed prices are not invented.
- Crop yields and cultivation-cost ranges are demo assumptions. Some selling prices use 2026–27 MSP benchmarks, which do not guarantee realized sale prices or procurement. Kodo market price is explicitly illustrative.
- The optimizer is a deterministic, risk-adjusted allocation heuristic using 0.05-acre units, not a calibrated stochastic agronomic model. Use only for software demonstration until district-level agronomic and economic data are validated.
- Weather scenarios are user-selected simulations; no live weather API is connected.

## Test

```bash
cd backend
pip install pytest httpx
pytest -q
```

## Next production steps

1. Connect official, authorized cadastral parcel data and georeferenced geometry.
2. Replace demo yield/cost data with current district, season, and variety data and document sources.
3. Connect verified weather, soil testing, mandi prices, and water data providers.
4. Calibrate crop suitability and yield uncertainty with local agronomists and historical data.
5. Add authentication, saved farms, database migrations, logging, and deployment configuration if needed.
