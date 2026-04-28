"""
Synthetic data generator for the Inventory Forecasting system.

Generates 2 years of realistic daily sales data for 50 products with:
  - Seasonality (weekly + yearly cycles)
  - Upward/downward trends per product
  - Holiday demand spikes (Diwali, Christmas, New Year, etc.)
  - Random promotional boosts
  - Gaussian noise to simulate real-world variance
  - Category-specific demand patterns

Run:  python scripts/generate_data.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
from faker import Faker
from datetime import date, timedelta
import logging
from sqlalchemy.orm import Session

from src.api.database import get_db_context, create_tables
from src.api.models import Product, Sale, Inventory, ProductCategory

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

fake = Faker("en_IN")   # Indian locale for realistic product names/context
np.random.seed(42)      # reproducibility


# ─── Config ────────────────────────────────────────────────────────────────────

START_DATE = date(2022, 1, 1)
END_DATE = date(2023, 12, 31)
N_PRODUCTS = 50

# Indian holidays with demand multipliers
HOLIDAYS = {
    # (month, day): multiplier
    (1, 1): 1.8,   # New Year
    (1, 26): 1.4,  # Republic Day
    (3, 8): 1.3,   # Holi (approx)
    (8, 15): 1.5,  # Independence Day
    (10, 2): 1.2,  # Gandhi Jayanti
    (10, 24): 2.2, # Diwali (approx)
    (10, 25): 2.5, # Diwali peak
    (10, 26): 2.0, # Diwali
    (12, 25): 1.9, # Christmas
    (12, 31): 1.7, # New Year's Eve
}

# Category-level demand profiles
CATEGORY_PROFILES = {
    ProductCategory.ELECTRONICS: {
        "base_demand": (15, 60),
        "trend": 0.0003,         # slight growth (tech adoption)
        "seasonality_strength": 0.3,
        "holiday_sensitivity": 1.8,
        "price_range": (500, 50000),
        "cost_margin": 0.35,
    },
    ProductCategory.CLOTHING: {
        "base_demand": (20, 80),
        "trend": 0.0001,
        "seasonality_strength": 0.5,   # strong seasonal (summer/winter lines)
        "holiday_sensitivity": 2.0,
        "price_range": (200, 3000),
        "cost_margin": 0.50,
    },
    ProductCategory.FOOD: {
        "base_demand": (50, 200),       # highest volume
        "trend": 0.0002,
        "seasonality_strength": 0.2,
        "holiday_sensitivity": 1.5,
        "price_range": (30, 500),
        "cost_margin": 0.25,
    },
    ProductCategory.HOME: {
        "base_demand": (10, 40),
        "trend": 0.0001,
        "seasonality_strength": 0.3,
        "holiday_sensitivity": 1.6,
        "price_range": (200, 8000),
        "cost_margin": 0.40,
    },
    ProductCategory.SPORTS: {
        "base_demand": (8, 35),
        "trend": 0.0004,
        "seasonality_strength": 0.6,   # strong summer peak
        "holiday_sensitivity": 1.3,
        "price_range": (300, 5000),
        "cost_margin": 0.45,
    },
    ProductCategory.BEAUTY: {
        "base_demand": (25, 90),
        "trend": 0.0003,
        "seasonality_strength": 0.25,
        "holiday_sensitivity": 1.7,
        "price_range": (100, 2000),
        "cost_margin": 0.55,
    },
}


# ─── Product Generation ────────────────────────────────────────────────────────

def generate_products(n: int = N_PRODUCTS) -> list[dict]:
    """Generate realistic product catalog entries."""
    categories = list(ProductCategory)
    products = []

    product_names = {
        ProductCategory.ELECTRONICS: [
            "Wireless Earbuds Pro", "Smart Watch Series X", "Bluetooth Speaker Mini",
            "USB-C Hub 7-in-1", "Mechanical Keyboard RGB", "Gaming Mouse 12K DPI",
            "Webcam 4K Ultra", "Power Bank 20000mAh", "LED Desk Lamp Smart",
            "Laptop Stand Adjustable",
        ],
        ProductCategory.CLOTHING: [
            "Cotton Kurta Men's", "Silk Saree Premium", "Denim Jeans Slim Fit",
            "Athletic T-Shirt Dry-Fit", "Woolen Jacket Winter", "Casual Sneakers",
            "Office Formal Shirt", "Leggings High-Waist", "Kids School Uniform", "Rain Jacket",
        ],
        ProductCategory.FOOD: [
            "Basmati Rice 5kg", "Cold Pressed Coconut Oil", "Organic Honey 500g",
            "Mixed Dry Fruits 250g", "Green Tea Premium 100 bags", "Protein Powder Whey",
            "Dark Chocolate 70%", "Quinoa 1kg", "Almond Milk 1L", "Oats Rolled 1kg",
        ],
        ProductCategory.HOME: [
            "Air Purifier HEPA", "Water Purifier RO", "Non-Stick Cookware Set",
            "Bedsheet Cotton 400TC", "Vacuum Cleaner Robot", "Coffee Maker Drip",
            "Storage Bins Set 6", "Curtains Blackout", "Towel Set Bamboo", "Candles Scented Set",
        ],
        ProductCategory.SPORTS: [
            "Yoga Mat Premium 6mm", "Resistance Bands Set", "Dumbbell Adjustable 20kg",
            "Badminton Racket Pro", "Cricket Bat Kashmir Willow", "Running Shoes Cushion",
            "Cycling Helmet MTB", "Swim Goggles Anti-Fog", "Skipping Rope Speed", "Pull-Up Bar",
        ],
        ProductCategory.BEAUTY: [
            "Vitamin C Face Serum", "Sunscreen SPF 50 PA+++", "Hair Serum Repair",
            "Lipstick Matte Set", "Face Wash Salicylic", "Moisturizer Hyaluronic",
            "Kajal Waterproof", "Shampoo Argan Oil 400ml", "Body Lotion SPF 15", "Rose Water Toner",
        ],
    }

    for i in range(n):
        category = categories[i % len(categories)]
        profile = CATEGORY_PROFILES[category]
        cat_products = product_names[category]
        name = cat_products[i // len(categories) % len(cat_products)]

        price_min, price_max = profile["price_range"]
        selling_price = round(np.random.uniform(price_min, price_max), 2)
        unit_cost = round(selling_price * (1 - profile["cost_margin"]), 2)

        products.append({
            "sku": f"SKU-{category.value[:3].upper()}-{i+1:04d}",
            "name": f"{name} #{i+1}",
            "category": category,
            "unit_cost": unit_cost,
            "selling_price": selling_price,
            "lead_time_days": int(np.random.choice([3, 5, 7, 10, 14])),
            "holding_cost_pct": round(np.random.uniform(0.15, 0.30), 2),
            "ordering_cost": round(np.random.uniform(20, 100), 2),
        })

    return products


# ─── Sales Generation ─────────────────────────────────────────────────────────

def generate_demand_series(
    profile: dict,
    n_days: int,
    dates: list[date],
) -> np.ndarray:
    """
    Generate synthetic daily demand with:
      - Base demand (random, per product)
      - Linear trend
      - Weekly seasonality (weekends higher for most categories)
      - Annual seasonality (festivals, seasons)
      - Holiday spikes
      - Random promotions
      - Gaussian noise
    """
    base_min, base_max = profile["base_demand"]
    base = np.random.uniform(base_min, base_max)
    t = np.arange(n_days)

    # Trend component
    trend = base * profile["trend"] * t

    # Weekly seasonality (sin with 7-day period)
    weekly = base * 0.15 * np.sin(2 * np.pi * t / 7)

    # Annual seasonality (sin with 365-day period)
    annual_amp = base * profile["seasonality_strength"]
    annual = annual_amp * np.sin(2 * np.pi * t / 365 - np.pi / 2)  # peak in summer

    # Base demand signal
    demand = base + trend + weekly + annual

    # Holiday multipliers
    for i, d in enumerate(dates):
        key = (d.month, d.day)
        if key in HOLIDAYS:
            multiplier = 1 + (HOLIDAYS[key] - 1) * profile["holiday_sensitivity"] * 0.5
            demand[i] *= multiplier

    # Weekend boost
    for i, d in enumerate(dates):
        if d.weekday() >= 5:  # Saturday/Sunday
            demand[i] *= np.random.uniform(1.1, 1.4)

    # Random promotional events (5% of days)
    promo_mask = np.random.random(n_days) < 0.05
    demand[promo_mask] *= np.random.uniform(1.3, 2.0, size=promo_mask.sum())

    # Gaussian noise (10% of demand)
    noise = np.random.normal(0, base * 0.10, n_days)
    demand = demand + noise

    # Clip to non-negative integers
    return np.clip(np.round(demand), 0, None).astype(int)


def generate_sales(products: list, product_db_ids: list[int]) -> list[dict]:
    """Generate all sales records for all products."""
    dates = pd.date_range(START_DATE, END_DATE, freq="D").date.tolist()
    n_days = len(dates)
    sales = []

    for product, db_id in zip(products, product_db_ids):
        profile = CATEGORY_PROFILES[product["category"]]
        demand_series = generate_demand_series(profile, n_days, dates)

        for i, (d, qty) in enumerate(zip(dates, demand_series)):
            if qty == 0:
                continue

            key = (d.month, d.day)
            is_holiday = key in HOLIDAYS
            promo = bool(np.random.random() < 0.05)
            revenue = round(qty * product["selling_price"], 2)

            sales.append({
                "product_id": db_id,
                "date": d,
                "quantity_sold": int(qty),
                "revenue": revenue,
                "is_holiday": is_holiday,
                "promotion_active": promo,
            })

    return sales


def generate_initial_inventory(products: list, product_db_ids: list[int]) -> list[dict]:
    """Set a reasonable opening stock for each product."""
    inventory = []
    for product, db_id in zip(products, product_db_ids):
        profile = CATEGORY_PROFILES[product["category"]]
        base_min, base_max = profile["base_demand"]
        avg_daily = (base_min + base_max) / 2
        # Start with ~60 days of stock
        initial_stock = int(avg_daily * 60 * np.random.uniform(0.8, 1.2))

        inventory.append({
            "product_id": db_id,
            "current_stock": initial_stock,
            "reorder_point": None,    # calculated by optimization engine in Phase 3
            "safety_stock": None,
            "optimal_order_qty": None,
        })
    return inventory


# ─── Main ─────────────────────────────────────────────────────────────────────

def seed_database():
    """Run the full data generation pipeline and persist to database."""
    create_tables()

    with get_db_context() as db:
        # Check if already seeded
        existing = db.query(Product).count()
        if existing > 0:
            logger.info(f"Database already has {existing} products. Skipping seed.")
            return

        # 1. Products
        logger.info(f"Generating {N_PRODUCTS} products...")
        product_dicts = generate_products(N_PRODUCTS)
        product_objects = [Product(**p) for p in product_dicts]
        db.add_all(product_objects)
        db.flush()  # get DB-assigned IDs without committing
        product_db_ids = [p.id for p in product_objects]
        logger.info(f"  → {len(product_objects)} products created.")

        # 2. Sales
        logger.info("Generating sales data (2 years, 50 products)...")
        sale_dicts = generate_sales(product_dicts, product_db_ids)
        # Bulk insert in batches of 5000 for speed
        batch_size = 5000
        for i in range(0, len(sale_dicts), batch_size):
            batch = sale_dicts[i:i + batch_size]
            db.bulk_insert_mappings(Sale, batch)
            logger.info(f"  → Inserted sales batch {i // batch_size + 1} ({len(batch)} rows)")

        # 3. Inventory
        logger.info("Generating initial inventory records...")
        inv_dicts = generate_initial_inventory(product_dicts, product_db_ids)
        db.bulk_insert_mappings(Inventory, inv_dicts)
        logger.info(f"  → {len(inv_dicts)} inventory records created.")

    logger.info("✓ Database seeded successfully!")
    logger.info(f"  Products: {N_PRODUCTS}")
    logger.info(f"  Sales records: {len(sale_dicts)}")
    logger.info(f"  Date range: {START_DATE} → {END_DATE}")


if __name__ == "__main__":
    seed_database()
