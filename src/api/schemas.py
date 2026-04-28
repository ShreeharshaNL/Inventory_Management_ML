"""
Pydantic v2 Schemas — API request and response models.
These define exactly what the API accepts and returns.
"""

from pydantic import BaseModel
from datetime import date
from typing import Optional


class Token(BaseModel):
    access_token: str
    token_type: str


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    category: str
    unit_cost: float
    selling_price: float
    lead_time_days: int
    is_active: bool

    class Config:
        from_attributes = True


class ForecastOut(BaseModel):
    product_id: int
    forecast_date: date
    predicted_demand: float
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    model_name: str

    class Config:
        from_attributes = True


class InventoryAlertOut(BaseModel):
    product_id: int
    product_name: str
    category: str
    current_stock: int
    reorder_point: float
    safety_stock: float
    optimal_order_qty: float
    alert_level: str
    days_remaining: float


class InventoryUpdateIn(BaseModel):
    product_id: int
    new_stock: int


class TrendOut(BaseModel):
    date: str
    total_units: int
    total_revenue: float