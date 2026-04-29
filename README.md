# 📦 AI-Powered Smart Inventory Forecasting System

> ML-driven demand forecasting and inventory optimization for retail/e-commerce businesses.

[![CI/CD](https://github.com/yourusername/inventory-forecasting/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/inventory-forecasting/actions)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb)](https://reactjs.org)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0-orange)](https://xgboost.readthedocs.io)

**Live Demo:** https://inventory-frontend.onrender.com  
**API Docs:** https://inventory-api.onrender.com/docs

---

## 🎯 What This Does

This system uses machine learning to:
- **Forecast demand** for 50 products over 30 days using XGBoost
- **Optimize inventory** using EOQ, safety stock, and reorder point formulas
- **Alert managers** when stock is critical, high risk, or approaching reorder point
- **Visualize everything** in a clean React dashboard with live charts

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   React Frontend │────▶│  FastAPI Backend  │────▶│   PostgreSQL DB  │
│  (Recharts, JWT) │     │  (REST API, Auth) │     │ (Products, Sales │
│  localhost:5173  │     │  localhost:8000   │     │  Predictions)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │        ML Pipeline         │
                    │  XGBoost + SARIMA Models   │
                    │  MLflow Experiment Tracking │
                    └───────────────────────────┘
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| **ML Models** | XGBoost, SARIMA (statsmodels), scikit-learn |
| **Experiment Tracking** | MLflow |
| **Backend** | FastAPI, SQLAlchemy, PostgreSQL, JWT Auth |
| **Frontend** | React 18, Recharts, Tailwind CSS |
| **DevOps** | Docker, GitHub Actions CI/CD, Render |

---

## 🚀 Quickstart

### Option 1 — Docker (Recommended)
```bash
git clone https://github.com/yourusername/inventory-forecasting.git
cd inventory-forecasting
cp .env.example .env
docker-compose up --build
```

**That's it!** Everything starts automatically:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2 — Local Development
```bash
# 1. Clone and setup
git clone https://github.com/yourusername/inventory-forecasting.git
cd inventory-forecasting
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# 3. Generate data & train models
set PYTHONPATH=%CD%
python scripts/generate_data.py
python scripts/train_models.py
python scripts/run_optimization.py

# 4. Start API
uvicorn src.api.main:app --reload --port 8000

# 5. Start Frontend (new terminal)
cd src/frontend
npm install && npm run dev
```

---

## 📊 ML Pipeline

### Data Generation
- 2 years of synthetic daily sales data (2022–2023)
- 50 products across 6 categories
- Realistic Indian holiday demand spikes (Diwali 2.5x, Christmas 1.9x)
- Weekly seasonality, promotions, and Gaussian noise

### Feature Engineering
| Feature Type | Examples |
|---|---|
| Calendar | day_of_week, month, quarter, is_weekend, is_holiday |
| Lag features | lag_7d, lag_14d, lag_21d, lag_30d |
| Rolling stats | rolling_mean_7d/14d/30d, rolling_std, rolling_min/max |
| Trend | demand_trend_7d, demand_trend_30d, cv_30d |

### Model Training
- **XGBoost** with TimeSeriesSplit cross-validation (5 folds)
- **SARIMA** baseline via pmdarima auto_arima
- Tracked with MLflow (parameters, metrics, artifacts)
- Avg MAPE: ~25% across all products

### Inventory Optimization
| Formula | Purpose |
|---|---|
| EOQ = √(2DS/H) | Optimal order quantity |
| Safety Stock = Z × σ × √L | Buffer against stockouts |
| ROP = (D × L) + SS | When to reorder |

---

## 🔐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | Get JWT token |
| GET | `/api/products` | List all products |
| GET | `/api/forecast/{id}` | 30-day demand forecast |
| GET | `/api/inventory/alerts` | Stock alerts by urgency |
| POST | `/api/inventory/update` | Update stock level |
| GET | `/api/analytics/trends` | Revenue & units trend |
| GET | `/api/analytics/kpis` | Dashboard KPIs |

Full interactive docs: http://localhost:8000/docs

---

## 📁 Project Structure

```
inventory-forecasting/
├── src/
│   ├── ml/
│   │   ├── preprocessing.py      # Feature engineering pipeline
│   │   ├── xgboost_model.py      # XGBoost forecaster
│   │   ├── sarima_model.py       # SARIMA baseline
│   │   ├── inventory_optimizer.py # EOQ + safety stock engine
│   │   └── evaluation.py         # Model comparison utilities
│   ├── api/
│   │   ├── main.py               # FastAPI app & routes
│   │   ├── models.py             # SQLAlchemy ORM models
│   │   ├── database.py           # DB connection & sessions
│   │   ├── auth.py               # JWT authentication
│   │   └── schemas.py            # Pydantic request/response
│   └── frontend/
│       └── src/
│           ├── App.jsx
│           ├── api.js
│           └── components/
│               ├── Dashboard.jsx
│               └── Login.jsx
├── scripts/
│   ├── generate_data.py          # Synthetic data generator
│   ├── train_models.py           # Model training orchestrator
│   └── run_optimization.py       # Inventory optimization
├── tests/
│   └── test_ml/
│       └── test_preprocessing.py
├── Dockerfile.api
├── docker-compose.yml
├── render.yaml
└── requirements.txt
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## 🌐 Deployment

This project deploys automatically to **Render** on every push to `main`:

1. GitHub Actions runs tests
2. Builds Docker images
3. Triggers Render deploy hooks

See `.github/workflows/ci.yml` for the full pipeline.

---

## 📈 Resume Bullet Points

> *"Built an end-to-end ML inventory forecasting system using XGBoost with TimeSeriesSplit cross-validation, achieving ~25% MAPE across 50 SKUs. Implemented inventory optimization engine (EOQ, safety stock, ROP). Developed FastAPI REST API with JWT auth and React dashboard. Deployed with Docker and GitHub Actions CI/CD."*

---

## 👤 Author

**Your Name** — [LinkedIn](https://linkedin.com) · [GitHub](https://github.com)