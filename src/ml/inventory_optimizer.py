"""
Inventory Optimization Engine — Phase 3

Implements classical inventory management formulas on top of ML forecasts:
  - Economic Order Quantity (EOQ)
  - Safety Stock (demand variability + lead time)
  - Reorder Point (ROP)
  - Alert classification (Critical / High / Medium / Low)

Run:  python scripts/run_optimization.py
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import date, timedelta
from scipy import stats

from src.api.database import get_db_context
from src.api.models import Product, Sale, Inventory, Prediction, AlertLevel

logger = logging.getLogger(__name__)


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class InventoryMetrics:
    """All computed inventory metrics for one product."""
    product_id: int
    product_name: str

    # Demand stats
    avg_daily_demand: float
    demand_std: float
    lead_time_days: int

    # Optimization results
    eoq: float               # Economic Order Quantity
    safety_stock: float      # Buffer stock
    reorder_point: float     # Trigger a new order when stock hits this level
    max_stock: float         # Upper bound (EOQ + safety stock)

    # Current status
    current_stock: int
    alert_level: AlertLevel
    days_of_stock_remaining: float
    stockout_risk_pct: float  # probability of stockout before next reorder


# ─── Core Formulas ────────────────────────────────────────────────────────────

def calculate_eoq(
    annual_demand: float,
    ordering_cost: float,
    holding_cost_per_unit: float,
) -> float:
    """
    Economic Order Quantity — Wilson's formula.

    EOQ = sqrt(2 * D * S / H)
      D = annual demand (units)
      S = fixed cost per order placed (₹)
      H = annual holding cost per unit (₹/unit/year)

    Minimizes total inventory cost (ordering + holding).
    """
    if annual_demand <= 0 or ordering_cost <= 0 or holding_cost_per_unit <= 0:
        return 0.0
    eoq = np.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)
    return round(eoq, 2)


def calculate_safety_stock(
    demand_std_daily: float,
    lead_time_days: int,
    service_level: float = 0.95,
) -> float:
    """
    Safety stock using normal distribution approximation.

    Safety Stock = Z * σ_demand * sqrt(lead_time)
      Z           = z-score for desired service level (0.95 → 1.645)
      σ_demand    = daily demand standard deviation
      lead_time   = supplier lead time in days

    Higher service level = more safety stock = fewer stockouts.
    """
    z_score = stats.norm.ppf(service_level)  # 0.95 → 1.645
    safety_stock = z_score * demand_std_daily * np.sqrt(lead_time_days)
    return round(max(0, safety_stock), 2)


def calculate_reorder_point(
    avg_daily_demand: float,
    lead_time_days: int,
    safety_stock: float,
) -> float:
    """
    Reorder Point — when to place a new order.

    ROP = (avg_daily_demand × lead_time) + safety_stock

    When current stock drops to ROP, place an order immediately.
    The order arrives just as safety stock starts being consumed.
    """
    rop = (avg_daily_demand * lead_time_days) + safety_stock
    return round(rop, 2)


def classify_alert(
    current_stock: int,
    reorder_point: float,
    safety_stock: float,
) -> AlertLevel:
    """
    Classify current stock level into alert tiers.

    CRITICAL → stock is 0 (stockout happening NOW)
    HIGH     → below safety stock (stockout imminent)
    MEDIUM   → below reorder point (need to order soon)
    LOW      → healthy stock level
    """
    if current_stock <= 0:
        return AlertLevel.CRITICAL
    elif current_stock <= safety_stock:
        return AlertLevel.HIGH
    elif current_stock <= reorder_point:
        return AlertLevel.MEDIUM
    else:
        return AlertLevel.LOW


def calculate_stockout_risk(
    current_stock: int,
    avg_daily_demand: float,
    demand_std: float,
    lead_time_days: int,
) -> float:
    """
    Probability of stockout during lead time (0.0 to 1.0).
    Uses normal distribution of demand during lead time.
    """
    if current_stock <= 0:
        return 1.0

    # Demand during lead time is normally distributed
    mean_ltd = avg_daily_demand * lead_time_days
    std_ltd  = demand_std * np.sqrt(lead_time_days)

    if std_ltd == 0:
        return 1.0 if current_stock < mean_ltd else 0.0

    # P(demand > current_stock) during lead time
    risk = 1 - stats.norm.cdf(current_stock, loc=mean_ltd, scale=std_ltd)
    return round(float(risk), 4)


# ─── Optimization Engine ──────────────────────────────────────────────────────

class InventoryOptimizer:
    """
    Runs the full optimization pipeline for all products.
    Reads demand history + ML predictions, writes results back to DB.
    """

    def __init__(self, service_level: float = 0.95, lookback_days: int = 90):
        self.service_level = service_level
        self.lookback_days = lookback_days   # days of history for demand stats

    def optimize_all(self) -> list[InventoryMetrics]:
        """Run optimization for all active products and update DB."""
        all_metrics = []

        with get_db_context() as db:
            products = db.query(Product).filter(Product.is_active == True).all()
            logger.info(f"Running optimization for {len(products)} products...")

            for product in products:
                try:
                    metrics = self._optimize_product(db, product)
                    self._update_inventory_db(db, metrics)
                    all_metrics.append(metrics)

                    logger.info(
                        f"  {product.name[:30]:<30} | "
                        f"Stock: {metrics.current_stock:>5} | "
                        f"ROP: {metrics.reorder_point:>6.1f} | "
                        f"EOQ: {metrics.eoq:>6.1f} | "
                        f"Alert: {metrics.alert_level.value.upper()}"
                    )

                except Exception as e:
                    logger.error(f"  Failed for product {product.id}: {e}")

        self._print_summary(all_metrics)
        return all_metrics

    def _optimize_product(self, db, product: Product) -> InventoryMetrics:
        """Compute all inventory metrics for a single product."""

        # ── 1. Get demand history ─────────────────────────────────────────────
        cutoff = date.today() - timedelta(days=self.lookback_days)
        sales = (
            db.query(Sale)
            .filter(Sale.product_id == product.id, Sale.date >= cutoff)
            .all()
        )

        if len(sales) == 0:
            # Fall back to full history if recent history is empty
            sales = db.query(Sale).filter(Sale.product_id == product.id).all()

        daily_demand = np.array([s.quantity_sold for s in sales], dtype=float)
        avg_daily    = float(np.mean(daily_demand)) if len(daily_demand) > 0 else 1.0
        demand_std   = float(np.std(daily_demand))  if len(daily_demand) > 1 else avg_daily * 0.2

        # ── 2. EOQ ────────────────────────────────────────────────────────────
        annual_demand        = avg_daily * 365
        holding_cost_per_unit = product.unit_cost * product.holding_cost_pct
        eoq = calculate_eoq(annual_demand, product.ordering_cost, holding_cost_per_unit)

        # ── 3. Safety Stock ───────────────────────────────────────────────────
        safety_stock = calculate_safety_stock(
            demand_std_daily=demand_std,
            lead_time_days=product.lead_time_days,
            service_level=self.service_level,
        )

        # ── 4. Reorder Point ──────────────────────────────────────────────────
        rop = calculate_reorder_point(avg_daily, product.lead_time_days, safety_stock)

        # ── 5. Current inventory status ───────────────────────────────────────
        inventory = db.query(Inventory).filter(
            Inventory.product_id == product.id
        ).first()
        current_stock = inventory.current_stock if inventory else 0

        # ── 6. Alert classification ───────────────────────────────────────────
        alert = classify_alert(current_stock, rop, safety_stock)

        # ── 7. Days of stock remaining ────────────────────────────────────────
        days_remaining = (current_stock / avg_daily) if avg_daily > 0 else 0

        # ── 8. Stockout risk ──────────────────────────────────────────────────
        stockout_risk = calculate_stockout_risk(
            current_stock, avg_daily, demand_std, product.lead_time_days
        )

        return InventoryMetrics(
            product_id=product.id,
            product_name=product.name,
            avg_daily_demand=round(avg_daily, 2),
            demand_std=round(demand_std, 2),
            lead_time_days=product.lead_time_days,
            eoq=eoq,
            safety_stock=safety_stock,
            reorder_point=rop,
            max_stock=round(eoq + safety_stock, 2),
            current_stock=current_stock,
            alert_level=alert,
            days_of_stock_remaining=round(days_remaining, 1),
            stockout_risk_pct=round(stockout_risk * 100, 1),
        )

    def _update_inventory_db(self, db, metrics: InventoryMetrics):
        """Write computed metrics back to the inventory table."""
        inventory = db.query(Inventory).filter(
            Inventory.product_id == metrics.product_id
        ).first()

        if inventory:
            inventory.reorder_point    = metrics.reorder_point
            inventory.safety_stock     = metrics.safety_stock
            inventory.optimal_order_qty = metrics.eoq
            inventory.alert_level      = metrics.alert_level
        else:
            db.add(Inventory(
                product_id=metrics.product_id,
                current_stock=0,
                reorder_point=metrics.reorder_point,
                safety_stock=metrics.safety_stock,
                optimal_order_qty=metrics.eoq,
                alert_level=metrics.alert_level,
            ))

    def _print_summary(self, all_metrics: list[InventoryMetrics]):
        """Print a clean summary of alert levels across all products."""
        counts = {level: 0 for level in AlertLevel}
        for m in all_metrics:
            counts[m.alert_level] += 1

        logger.info("\n" + "="*50)
        logger.info("INVENTORY OPTIMIZATION COMPLETE")
        logger.info("="*50)
        logger.info(f"🔴 CRITICAL (stockout):     {counts[AlertLevel.CRITICAL]:>3} products")
        logger.info(f"🟠 HIGH (below safety):     {counts[AlertLevel.HIGH]:>3} products")
        logger.info(f"🟡 MEDIUM (below ROP):      {counts[AlertLevel.MEDIUM]:>3} products")
        logger.info(f"🟢 LOW (healthy):           {counts[AlertLevel.LOW]:>3} products")

        # Products needing immediate action
        urgent = [m for m in all_metrics
                  if m.alert_level in (AlertLevel.CRITICAL, AlertLevel.HIGH)]
        if urgent:
            logger.info(f"\n⚠️  Immediate action needed ({len(urgent)} products):")
            for m in urgent[:5]:
                logger.info(
                    f"   {m.product_name[:35]:<35} | "
                    f"Stock: {m.current_stock} | "
                    f"Order: {m.eoq:.0f} units"
                )

    def get_alerts_dataframe(self, metrics: list[InventoryMetrics]) -> pd.DataFrame:
        """Convert metrics list to a DataFrame — used by the API."""
        return pd.DataFrame([{
            "product_id":             m.product_id,
            "product_name":           m.product_name,
            "current_stock":          m.current_stock,
            "avg_daily_demand":       m.avg_daily_demand,
            "days_remaining":         m.days_of_stock_remaining,
            "reorder_point":          m.reorder_point,
            "safety_stock":           m.safety_stock,
            "eoq":                    m.eoq,
            "alert_level":            m.alert_level.value,
            "stockout_risk_pct":      m.stockout_risk_pct,
            "recommended_order_qty":  m.eoq,
        } for m in metrics])