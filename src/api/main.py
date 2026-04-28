"""
FastAPI Application Entry Point — Phase 4

Endpoints:
  GET  /                        → health check
  GET  /api/products            → list all products
  GET  /api/forecast/{id}       → 30-day demand forecast
  GET  /api/inventory/alerts    → all inventory alerts
  POST /api/inventory/update    → update stock level
  GET  /api/analytics/trends    → sales trends summary
  POST /api/auth/login          → get JWT token

Run:  uvicorn src.api.main:app --reload --port 8000
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
import logging

from src.api.database import get_db, check_connection, create_tables
from src.api.models import Product, Inventory, Sale, Prediction
from src.api.auth import (
    authenticate_user, create_access_token,
    get_current_user, FAKE_USERS_DB
)
from src.api.schemas import (
    ProductOut, ForecastOut, InventoryAlertOut,
    InventoryUpdateIn, TrendOut, Token
)
from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Smart Inventory Forecasting API",
    description="ML-powered demand forecasting and inventory optimization",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    logger.info("Starting up...")
    create_tables()
    if not check_connection():
        raise RuntimeError("Cannot connect to database!")
    logger.info("API ready.")


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login", response_model=Token, tags=["Auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(FAKE_USERS_DB, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer"}


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "version": "1.0.0"}


# ─── Products ─────────────────────────────────────────────────────────────────

@app.get("/api/products", response_model=list[ProductOut], tags=["Products"])
def get_products(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    products = db.query(Product).filter(Product.is_active == True).all()
    return products


@app.get("/api/products/{product_id}", response_model=ProductOut, tags=["Products"])
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ─── Forecasts ────────────────────────────────────────────────────────────────

@app.get("/api/forecast/{product_id}", response_model=list[ForecastOut], tags=["Forecasts"])
def get_forecast(
    product_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get ML demand forecast for a product (next N days)."""
    from datetime import date
    predictions = (
        db.query(Prediction)
        .filter(
            Prediction.product_id == product_id,
            Prediction.forecast_date >= date(2024, 1, 1),
        )
        .order_by(Prediction.forecast_date)
        .limit(days)
        .all()
    )
    if not predictions:
        raise HTTPException(
            status_code=404,
            detail="No forecast found. Run train_models.py first."
        )
    return predictions


# ─── Inventory ────────────────────────────────────────────────────────────────

@app.get("/api/inventory/alerts", response_model=list[InventoryAlertOut], tags=["Inventory"])
def get_alerts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get inventory alerts for all products, sorted by urgency."""
    from sqlalchemy import case
    from src.api.models import AlertLevel

    alert_order = case(
        (Inventory.alert_level == AlertLevel.CRITICAL, 1),
        (Inventory.alert_level == AlertLevel.HIGH,     2),
        (Inventory.alert_level == AlertLevel.MEDIUM,   3),
        (Inventory.alert_level == AlertLevel.LOW,      4),
        else_=5,
    )

    results = (
        db.query(Inventory, Product)
        .join(Product, Inventory.product_id == Product.id)
        .order_by(alert_order)
        .all()
    )

    return [
        InventoryAlertOut(
            product_id=inv.product_id,
            product_name=prod.name,
            category=prod.category.value,
            current_stock=inv.current_stock,
            reorder_point=inv.reorder_point or 0,
            safety_stock=inv.safety_stock or 0,
            optimal_order_qty=inv.optimal_order_qty or 0,
            alert_level=inv.alert_level.value if inv.alert_level else "low",
            days_remaining=round(
                inv.current_stock / max(1, inv.reorder_point or 1), 1
            ),
        )
        for inv, prod in results
    ]


@app.post("/api/inventory/update", tags=["Inventory"])
def update_stock(
    update: InventoryUpdateIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Manually update stock level for a product."""
    inventory = db.query(Inventory).filter(
        Inventory.product_id == update.product_id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    inventory.current_stock = update.new_stock
    db.commit()
    return {"message": "Stock updated", "product_id": update.product_id, "new_stock": update.new_stock}


# ─── Analytics ────────────────────────────────────────────────────────────────

@app.get("/api/analytics/trends", tags=["Analytics"])
def get_trends(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Sales trends — total revenue and units sold per day."""
    from datetime import date, timedelta
    from sqlalchemy import func

    start = date(2023, 11, 1)  # use our synthetic data range  

    results = (
        db.query(
            Sale.date,
            func.sum(Sale.quantity_sold).label("total_units"),
            func.sum(Sale.revenue).label("total_revenue"),
        )
        .filter(Sale.date >= start)
        .group_by(Sale.date)
        .order_by(Sale.date)
        .all()
    )

    return [
        {
            "date": str(r.date),
            "total_units": int(r.total_units),
            "total_revenue": round(float(r.total_revenue), 2),
        }
        for r in results
    ]


@app.get("/api/analytics/kpis", tags=["Analytics"])
def get_kpis(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Key performance indicators for the dashboard header."""
    from sqlalchemy import func
    from src.api.models import AlertLevel

    total_products = db.query(Product).filter(Product.is_active == True).count()
    critical = db.query(Inventory).filter(Inventory.alert_level == AlertLevel.CRITICAL).count()
    high     = db.query(Inventory).filter(Inventory.alert_level == AlertLevel.HIGH).count()
    total_stock = db.query(func.sum(Inventory.current_stock)).scalar() or 0

    # Average forecast accuracy from predictions with actuals
    predictions_with_actuals = db.query(Prediction).filter(
        Prediction.actual_demand.isnot(None),
        Prediction.mae.isnot(None),
    ).all()

    avg_mape = None
    if predictions_with_actuals:
        maes = [p.mae for p in predictions_with_actuals if p.mae]
        avg_mape = round(sum(maes) / len(maes), 2) if maes else None

    return {
        "total_products": total_products,
        "critical_alerts": critical,
        "high_alerts": high,
        "total_stock_units": int(total_stock),
        "avg_forecast_mape": avg_mape,
        "stockout_risk_products": critical + high,
    }