# 📦 Smart Inventory Management System - Complete Features & Usage Guide

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Installation & Setup](#installation--setup)
4. [Features in Detail](#features-in-detail)
5. [How to Use](#how-to-use)
6. [API Reference](#api-reference)
7. [Dashboard Guide](#dashboard-guide)
8. [Troubleshooting](#troubleshooting)

---

## Overview

An **AI-powered inventory forecasting and optimization system** that uses machine learning to:
- 🤖 Forecast product demand for the next 30 days
- 📊 Optimize inventory levels to minimize costs
- ⚠️ Generate intelligent stock alerts
- 📈 Provide analytics and insights
- 🔐 Secure access with JWT authentication

**Tech Stack:**
- Backend: FastAPI + PostgreSQL + SQLAlchemy
- ML: XGBoost + SARIMA + scikit-learn
- Frontend: React 18 + Recharts + Tailwind CSS
- DevOps: Docker, GitHub Actions, Render

---

## System Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    React Frontend                           │
│              (Dashboard @ localhost:5173)                   │
│  - Product list, forecasts, alerts, analytics              │
│  - JWT login, real-time charts                             │
└────────────────┬─────────────────────────────────────────┘
                 │ HTTP/REST
┌────────────────▼─────────────────────────────────────────┐
│                  FastAPI Backend                           │
│              (API @ localhost:8000)                        │
│  - Authentication, CRUD operations                        │
│  - Forecast retrieval, alert generation                   │
│  - Analytics endpoints                                    │
└────────────────┬─────────────────────────────────────────┘
                 │ SQLAlchemy ORM
┌────────────────▼─────────────────────────────────────────┐
│                 PostgreSQL Database                        │
│  - Products, Sales, Inventory, Predictions, Alerts        │
└────────────────────────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │   ML Pipeline           │
    │  - XGBoost Forecaster   │
    │  - SARIMA Baseline      │
    │  - EOQ Optimizer        │
    │  - Alert Generator      │
    └─────────────────────────┘
```

---

## Installation & Setup

### Option 1: Docker (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/ShreeharshaNL/Inventory_Management_ML.git
cd Inventory_Management_ML

# 2. Create environment file
cp .env.example .env
# Edit .env with your PostgreSQL credentials (optional for Docker)

# 3. Start everything with Docker Compose
docker-compose up --build

# Wait for logs to show:
# - inventory-frontend running on localhost:3000
# - inventory-api running on localhost:8000
# - PostgreSQL running on localhost:5432
```

**That's it!** Services will be available at:
- 🌐 **Frontend**: http://localhost:3000
- 🔌 **API Docs**: http://localhost:8000/docs
- 📊 **Analytics**: http://localhost:8000/redoc

---

### Option 2: Local Development

#### Prerequisites
- Python 3.11+
- PostgreSQL 12+
- Node.js 16+
- pip, npm

#### Step 1: Backend Setup

```bash
# Clone repository
git clone https://github.com/ShreeharshaNL/Inventory_Management_ML.git
cd Inventory_Management_ML

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# OR (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set Python path
set PYTHONPATH=%CD%  # Windows
export PYTHONPATH=$PWD  # Linux/Mac
```

#### Step 2: Database Setup

```bash
# Create PostgreSQL database
createdb inventory_db

# Update .env with your PostgreSQL credentials
# DATABASE_URL=postgresql://user:password@localhost:5432/inventory_db

# Run migrations (Alembic)
alembic upgrade head
```

#### Step 3: Generate Training Data & Train Models

```bash
# Generate 2 years of synthetic sales data
python scripts/generate_data.py
# Output: 50 products, 730 days of historical sales

# Train ML models (XGBoost + SARIMA)
python scripts/train_models.py
# Models saved in ./models/xgboost_product_*.joblib

# Run inventory optimization
python scripts/run_optimization.py
# Generates alerts and calculates EOQ, safety stock, ROP
```

#### Step 4: Start API Server

```bash
# Terminal 1: Start FastAPI backend
uvicorn src.api.main:app --reload --port 8000

# You should see:
# INFO:     Uvicorn running on http://127.0.0.1:8000
# Visit http://localhost:8000/docs for interactive API docs
```

#### Step 5: Start Frontend

```bash
# Terminal 2: Start React frontend
cd src/frontend
npm install
npm run dev

# You should see:
# VITE v4.x.x  ready in xxx ms
# ➜  Local:   http://localhost:5173/
```

---

## Features in Detail

### 1️⃣ ML-Powered Demand Forecasting

#### What It Does
Predicts product demand for the next 30 days using machine learning models trained on 2 years of historical sales data.

#### How It Works
- **Model**: XGBoost (primary) + SARIMA (baseline)
- **Training Data**: 730 days of historical sales per product
- **Accuracy**: ~25% MAPE (Mean Absolute Percentage Error)
- **Features Used**:
  - Calendar: day of week, month, quarter, holidays
  - Time-series: lag values (7, 14, 21, 30 days)
  - Statistics: rolling mean, std, min, max
  - Trend: demand trend over 7 and 30 days

#### Training Process
```
Raw Sales Data
    ↓
Feature Engineering (12+ features)
    ↓
Time Series Split (5 folds)
    ↓
XGBoost Model Training
    ↓
MLflow Experiment Tracking
    ↓
Model Serialization (joblib)
```

#### Example Output
```
Product: Laptop (SKU: ELEC-001)
Forecast for next 30 days:
├─ Week 1: ~45 units/day
├─ Week 2: ~52 units/day
├─ Week 3: ~48 units/day
└─ Week 4: ~55 units/day (holiday effect)
```

---

### 2️⃣ Inventory Optimization

#### Economic Order Quantity (EOQ)
**Formula**: EOQ = √(2 × D × S / H)

- **D** = Annual demand (units)
- **S** = Fixed cost per order (₹)
- **H** = Annual holding cost per unit (₹/year)

**Purpose**: Minimizes total inventory cost by finding optimal order quantity

**Example**:
```
Product: Shirt
├─ Annual Demand: 10,000 units
├─ Ordering Cost: ₹50 per order
├─ Holding Cost: 20% of unit cost (₹5/unit/year)
└─ EOQ: 447 units per order
```

#### Safety Stock
**Formula**: Safety Stock = Z × σ × √L

- **Z** = Service level factor (1.65 for 95%)
- **σ** = Standard deviation of daily demand
- **L** = Lead time (days)

**Purpose**: Buffer stock to prevent stockouts during demand spikes or supply delays

**Example**:
```
Product: Phone Charger
├─ Daily Demand Std Dev: 8 units
├─ Lead Time: 7 days
├─ Service Level: 95%
└─ Safety Stock: 46 units
```

#### Reorder Point (ROP)
**Formula**: ROP = (D × L) + SS

- **D** = Average daily demand
- **L** = Lead time (days)
- **SS** = Safety stock

**Purpose**: Triggers new purchase order when inventory falls below this level

**Example**:
```
Product: Keyboard
├─ Avg Daily Demand: 12 units
├─ Lead Time: 7 days
├─ Safety Stock: 24 units
└─ ROP: 108 units
   (When stock ≤ 108, place new order)
```

---

### 3️⃣ Smart Alert System

Automatically classifies inventory into 4 alert levels:

#### 🔴 CRITICAL Alert
- **When**: Stock = 0 or very low
- **Action**: Immediate purchase order needed
- **Risk**: Severe stockout imminent

#### 🟠 HIGH Alert
- **When**: Stock < Safety Stock
- **Action**: Monitor closely, expedite order if delayed
- **Risk**: Potential stockout within 2 weeks

#### 🟡 MEDIUM Alert
- **When**: Stock approaching Reorder Point
- **Action**: Plan new order
- **Risk**: Manageable, but order soon

#### 🟢 LOW Alert
- **When**: Stock is healthy
- **Action**: Normal operations
- **Risk**: None

#### Alert Example
```
┌─ Product: Laptop (SKU: ELEC-001)
├─ Current Stock: 15 units
├─ Safety Stock: 32 units
├─ Reorder Point: 68 units
├─ Alert Level: 🔴 CRITICAL
├─ Days Until Stockout: 2 days
├─ Recommended Action: PLACE ORDER IMMEDIATELY
└─ Forecast (30 days): ~45 units/day
```

---

### 4️⃣ Analytics & Insights

#### KPI Dashboard
- **Total Products**: 50
- **Total Revenue**: Year-to-date sales in ₹
- **Units Sold**: Year-to-date quantity
- **Avg Inventory Value**: Total value of current stock
- **Stockout Rate**: % of products with critical/high alerts
- **Forecast Accuracy**: MAPE % of models

#### Trend Analysis
- **Revenue Trend**: Weekly/monthly sales trend
- **Demand Pattern**: Seasonal peaks and valleys
- **Product Performance**: Top/bottom products by revenue
- **Category Breakdown**: Sales by category

#### Alerts Summary
- Total active alerts by level (Critical/High/Medium/Low)
- Products requiring immediate attention
- Historical alert resolution time

---

### 5️⃣ Security & Authentication

#### JWT Token-Based Auth
```bash
# Step 1: Login to get token
POST /api/auth/login
{
  "username": "user",
  "password": "password"
}

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}

# Step 2: Use token in requests
Authorization: Bearer <your_token_here>
```

#### Default Credentials
```
Username: admin
Password: admin123

Username: user
Password: user123
```

---

## How to Use

### Workflow: Daily Operations

#### Morning: Check Alerts
1. Open dashboard at http://localhost:3000
2. Login with credentials
3. Go to "Alerts" section
4. Action items:
   - 🔴 CRITICAL → Place emergency order
   - 🟠 HIGH → Follow up on delayed shipments
   - 🟡 MEDIUM → Schedule regular purchase order

#### Mid-Day: Review Forecasts
1. Click on any product
2. View 30-day demand forecast
3. Compare with current stock levels
4. Adjust orders if forecast changed significantly

#### End of Day: Update Sales
1. Go to "Inventory" section
2. Update stock levels with actual received shipments
3. System recalculates alerts automatically
4. Review any alerts that changed

---

### Workflow: Monthly Planning

#### Step 1: Access Analytics
```
Dashboard → Analytics Tab
```

#### Step 2: Review KPIs
- Stockout rate (should be < 2%)
- Forecast accuracy (MAPE ~ 25%)
- Revenue trend
- Category performance

#### Step 3: Adjust Optimization Parameters
If too many stockouts:
- ↑ Increase safety stock level
- ↓ Lower lead time (faster suppliers)

If excess inventory:
- ↓ Decrease safety stock level
- ↑ Increase ordering cost estimate (order less frequently)

#### Step 4: Retrain Models (Optional)
```bash
# If significant business changes occurred
python scripts/train_models.py
```

---

## API Reference

### Authentication

#### Login
```
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

---

### Products

#### Get All Products
```
GET /api/products
Authorization: Bearer <token>

Response:
[
  {
    "id": 1,
    "sku": "ELEC-001",
    "name": "Laptop",
    "category": "electronics",
    "unit_cost": 25000.0,
    "selling_price": 35000.0,
    "lead_time_days": 7,
    "is_active": true
  },
  ...
]
```

---

### Forecasting

#### Get 30-Day Forecast
```
GET /api/forecast/{product_id}
Authorization: Bearer <token>

Example: GET /api/forecast/1

Response:
{
  "product_id": 1,
  "product_name": "Laptop",
  "forecast_dates": ["2025-05-13", "2025-05-14", ...],
  "forecast_values": [45.2, 48.5, 52.1, ...],
  "model_used": "xgboost",
  "mape": 24.5
}
```

---

### Inventory Alerts

#### Get All Alerts
```
GET /api/inventory/alerts
Authorization: Bearer <token>

Response:
[
  {
    "product_id": 1,
    "product_name": "Laptop",
    "sku": "ELEC-001",
    "current_stock": 15,
    "safety_stock": 32,
    "reorder_point": 68,
    "alert_level": "critical",
    "days_until_stockout": 2,
    "forecast_next_30d": 1350
  },
  ...
]
```

#### Get Alerts by Level
```
GET /api/inventory/alerts?level=critical
Authorization: Bearer <token>

Returns only CRITICAL level alerts
```

---

### Inventory Management

#### Update Stock Level
```
POST /api/inventory/update
Authorization: Bearer <token>
Content-Type: application/json

{
  "product_id": 1,
  "new_stock_level": 150,
  "reason": "Received shipment from supplier"
}

Response:
{
  "product_id": 1,
  "product_name": "Laptop",
  "new_stock": 150,
  "alert_level": "low",
  "message": "Stock updated successfully"
}
```

---

### Analytics

#### Get Sales Trends
```
GET /api/analytics/trends?days=30
Authorization: Bearer <token>

Response:
{
  "dates": ["2025-04-12", "2025-04-13", ...],
  "revenue": [45000, 52000, 48000, ...],
  "units_sold": [120, 150, 140, ...],
  "avg_daily_revenue": 49500.0,
  "avg_daily_units": 145.0
}
```

#### Get Dashboard KPIs
```
GET /api/analytics/kpis
Authorization: Bearer <token>

Response:
{
  "total_products": 50,
  "total_revenue_ytd": 5245000.0,
  "total_units_ytd": 12450,
  "avg_inventory_value": 450000.0,
  "stockout_rate_pct": 1.2,
  "forecast_accuracy_mape": 24.5,
  "critical_alerts": 3,
  "high_alerts": 8,
  "medium_alerts": 12,
  "low_alerts": 27
}
```

---

## Dashboard Guide

### Login Page
```
URL: http://localhost:3000/login

Steps:
1. Enter username (default: admin)
2. Enter password (default: admin123)
3. Click "Login"
4. Token stored in browser localStorage
```

### Home / Dashboard
```
Shows:
├─ KPI Cards (Revenue, Units, Inventory Value)
├─ Stockout Rate
├─ Forecast Accuracy
└─ Quick Links to Features
```

### Products Page
```
Shows:
├─ List of 50 products with:
│  ├─ SKU
│  ├─ Name
│  ├─ Category
│  ├─ Current Stock
│  ├─ Selling Price
│  └─ Alert Level (with color)
├─ Search/Filter
└─ Click product → View Details
```

### Product Details
```
Shows:
├─ Product Information
│  ├─ Name, SKU, Category
│  ├─ Unit Cost, Selling Price
│  ├─ Lead Time
│  └─ Historical Performance
├─ Inventory Status
│  ├─ Current Stock
│  ├─ Safety Stock
│  ├─ Reorder Point
│  └─ Alert Level
├─ 30-Day Forecast (Chart)
│  ├─ Predicted daily demand
│  ├─ Trend line
│  └─ Confidence band
└─ Historical Sales (Chart)
   ├─ Last 90 days of sales
   └─ Comparison with forecast
```

### Alerts Page
```
Shows:
├─ Filter by Level
│  ├─ All
│  ├─ 🔴 Critical (1-5 products)
│  ├─ 🟠 High (5-10 products)
│  ├─ 🟡 Medium (8-15 products)
│  └─ 🟢 Low (20-30 products)
└─ For Each Alert:
   ├─ Product Name & SKU
   ├─ Current Stock / Reorder Point
   ├─ Days Until Stockout
   ├─ Recommended Action
   └─ "Mark as Resolved" Button
```

### Analytics Page
```
Shows:
├─ Revenue Trend (30-day line chart)
├─ Units Sold Trend (30-day line chart)
├─ Top 10 Products by Revenue (bar chart)
├─ Category Breakdown (pie chart)
├─ KPI Summary
│  ├─ Total YTD Revenue
│  ├─ Total YTD Units
│  ├─ Avg Inventory Value
│  └─ Forecast Accuracy
└─ Alert Summary
   ├─ Critical Count
   ├─ High Count
   ├─ Medium Count
   └─ Low Count
```

### Inventory Management Page
```
Shows:
├─ Current Inventory Grid
│  ├─ Product Name
│  ├─ Current Stock
│  ├─ Safety Stock
│  ├─ Reorder Point
│  └─ Last Updated
├─ Quick Update Form
│  ├─ Select Product
│  ├─ Enter New Stock Level
│  ├─ Add Reason
│  └─ Submit
└─ Recent Updates (Activity Log)
```

---

## Troubleshooting

### Issue: "Cannot connect to database"
**Solution**:
```bash
# Check PostgreSQL is running
# Windows: Services → PostgreSQL
# Linux: systemctl status postgresql

# Check connection string in .env
DATABASE_URL=postgresql://user:password@localhost:5432/inventory_db

# Test connection
psql -U postgres -d inventory_db
```

### Issue: "No models found"
**Solution**:
```bash
# Train models first
python scripts/generate_data.py
python scripts/train_models.py
python scripts/run_optimization.py

# Models should appear in ./models/ directory
```

### Issue: "ModuleNotFoundError"
**Solution**:
```bash
# Set PYTHONPATH
set PYTHONPATH=%CD%  # Windows

# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### Issue: "Port already in use"
**Solution**:
```bash
# Backend on different port
uvicorn src.api.main:app --port 8001

# Frontend on different port (edit vite.config.js)
npm run dev -- --port 5174
```

### Issue: "CORS errors" in frontend
**Solution**:
```bash
# Already configured in API, but if still issues:
# Edit src/api/main.py

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: "Forecast values seem wrong"
**Solution**:
```bash
# Check if models are trained for that product
ls ./models/xgboost_product_*.joblib

# If missing, retrain:
python scripts/train_models.py

# Check forecast accuracy (MAPE ~25% is normal)
```

### Issue: "Permission denied" on Docker
**Solution**:
```bash
# Run with elevated privileges
docker-compose up --build  # Usually works

# Or on Linux:
sudo docker-compose up --build
```

---

## Quick Reference: Common Tasks

### Task: View alerts for a product
```
Dashboard → Alerts → Search Product Name
```

### Task: Update current stock
```
Dashboard → Inventory → Select Product → Enter New Stock → Submit
```

### Task: Check 30-day forecast
```
Dashboard → Products → Click Product → View Forecast Chart
```

### Task: Download alerts report
```
API: GET /api/inventory/alerts
Export as CSV/JSON
```

### Task: Check system health
```
API: GET /
Expected: {"status": "ok", "version": "1.0.0"}
```

### Task: Restart everything
```bash
docker-compose down
docker-compose up --build
```

---

## Support & Resources

- 📖 **API Documentation**: http://localhost:8000/docs
- 📚 **API Reference**: http://localhost:8000/redoc
- 🐛 **GitHub Issues**: https://github.com/ShreeharshaNL/Inventory_Management_ML/issues
- 💬 **Discussion**: Create an issue with label "question"

---

**Last Updated**: May 2025
**Version**: 1.0.0
