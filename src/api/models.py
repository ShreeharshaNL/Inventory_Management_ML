"""
Database models using SQLAlchemy ORM.
Mirrors the schema from the project spec:
  Products → Sales → Inventory → Predictions
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    ForeignKey, Text, Boolean, Enum as SAEnum
)
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


# ─── Enums ─────────────────────────────────────────────────────────────────────

class AlertLevel(str, enum.Enum):
    CRITICAL = "critical"   # stock = 0
    HIGH = "high"           # below safety stock
    MEDIUM = "medium"       # approaching reorder point
    LOW = "low"             # healthy stock


class ProductCategory(str, enum.Enum):
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    FOOD = "food"
    HOME = "home"
    SPORTS = "sports"
    BEAUTY = "beauty"


# ─── Models ────────────────────────────────────────────────────────────────────

class Product(Base):
    """Master product catalog."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(SAEnum(ProductCategory), nullable=False)
    unit_cost = Column(Float, nullable=False)       # cost to purchase/make
    selling_price = Column(Float, nullable=False)   # retail price
    lead_time_days = Column(Integer, default=7)     # supplier lead time
    holding_cost_pct = Column(Float, default=0.20)  # annual holding cost as % of unit cost
    ordering_cost = Column(Float, default=50.0)     # fixed cost per order placed
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sales = relationship("Sale", back_populates="product", lazy="dynamic")
    inventory = relationship("Inventory", back_populates="product", uselist=False)
    predictions = relationship("Prediction", back_populates="product", lazy="dynamic")

    def __repr__(self):
        return f"<Product(sku={self.sku}, name={self.name})>"


class Sale(Base):
    """Daily sales transactions per product."""
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    quantity_sold = Column(Integer, nullable=False)
    revenue = Column(Float, nullable=False)
    is_holiday = Column(Boolean, default=False)
    promotion_active = Column(Boolean, default=False)

    # Relationships
    product = relationship("Product", back_populates="sales")

    def __repr__(self):
        return f"<Sale(product_id={self.product_id}, date={self.date}, qty={self.quantity_sold})>"


class Inventory(Base):
    """Current stock levels and reorder thresholds per product."""
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), unique=True, nullable=False, index=True)
    current_stock = Column(Integer, nullable=False, default=0)
    reorder_point = Column(Float, nullable=True)    # calculated by optimization engine
    safety_stock = Column(Float, nullable=True)     # buffer against demand variability
    optimal_order_qty = Column(Float, nullable=True) # EOQ result
    alert_level = Column(SAEnum(AlertLevel), default=AlertLevel.LOW)
    last_restocked_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="inventory")

    def __repr__(self):
        return f"<Inventory(product_id={self.product_id}, stock={self.current_stock}, alert={self.alert_level})>"


class Prediction(Base):
    """Model-generated demand forecasts per product per day."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    forecast_date = Column(Date, nullable=False, index=True)   # the date being predicted
    generated_at = Column(DateTime, default=datetime.utcnow)   # when forecast was made
    predicted_demand = Column(Float, nullable=False)
    lower_bound = Column(Float, nullable=True)   # confidence interval lower
    upper_bound = Column(Float, nullable=True)   # confidence interval upper
    model_name = Column(String(50), nullable=False)  # "xgboost" | "sarima"
    model_version = Column(String(20), nullable=True)
    actual_demand = Column(Integer, nullable=True)   # filled in after the day passes
    mae = Column(Float, nullable=True)               # filled in post-actuals

    # Relationships
    product = relationship("Product", back_populates="predictions")

    def __repr__(self):
        return f"<Prediction(product_id={self.product_id}, date={self.forecast_date}, pred={self.predicted_demand:.1f})>"


class ModelRun(Base):
    """Audit log for every ML training run."""
    __tablename__ = "model_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), unique=True)       # MLflow run ID
    model_name = Column(String(50), nullable=False)
    model_version = Column(String(20))
    trained_at = Column(DateTime, default=datetime.utcnow)
    mae = Column(Float)
    rmse = Column(Float)
    mape = Column(Float)
    training_rows = Column(Integer)
    parameters = Column(Text)   # JSON string of hyperparameters
    is_production = Column(Boolean, default=False)

    def __repr__(self):
        return f"<ModelRun(model={self.model_name}, mape={self.mape:.2f}%, production={self.is_production})>"
