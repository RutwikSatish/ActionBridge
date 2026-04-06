"""
ActionBridge — Synthetic Data Generator
Generates realistic logistics operational data:
  - Shipments (with delays and exceptions)
  - SAP Sales Orders (linked to shipments)
  - Inventory (multi-warehouse)
  - Carriers (performance profiles)
  - Disruption events
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

random.seed(42)
np.random.seed(42)

# ── Constants ────────────────────────────────────────────────────────────────

CARRIERS = {
    "FedEx Freight":       {"reliability": 0.94, "avg_delay_hrs": 4,  "capacity": "high",   "cost_idx": 1.2},
    "UPS Supply Chain":    {"reliability": 0.93, "avg_delay_hrs": 5,  "capacity": "high",   "cost_idx": 1.15},
    "XPO Logistics":       {"reliability": 0.89, "avg_delay_hrs": 8,  "capacity": "high",   "cost_idx": 1.0},
    "J.B. Hunt":           {"reliability": 0.91, "avg_delay_hrs": 6,  "capacity": "medium", "cost_idx": 0.95},
    "Old Dominion":        {"reliability": 0.95, "avg_delay_hrs": 3,  "capacity": "medium", "cost_idx": 1.1},
    "Estes Express":       {"reliability": 0.87, "avg_delay_hrs": 10, "capacity": "medium", "cost_idx": 0.9},
    "Saia Inc.":           {"reliability": 0.88, "avg_delay_hrs": 9,  "capacity": "medium", "cost_idx": 0.88},
    "Southeastern Freight":{"reliability": 0.90, "avg_delay_hrs": 7,  "capacity": "low",    "cost_idx": 0.85},
    "Averitt Express":     {"reliability": 0.86, "avg_delay_hrs": 11, "capacity": "low",    "cost_idx": 0.82},
}

WAREHOUSES = ["Chicago-IL", "Dallas-TX", "Atlanta-GA", "Newark-NJ", "Los-Angeles-CA"]

CUSTOMERS = {
    "Walmart Stores Inc.":      {"tier": "A", "sla_days": 2, "penalty_per_day": 8500},
    "Amazon Fulfillment Corp":  {"tier": "A", "sla_days": 1, "penalty_per_day": 12000},
    "Target Corporation":       {"tier": "A", "sla_days": 2, "penalty_per_day": 7500},
    "Costco Wholesale":         {"tier": "A", "sla_days": 3, "penalty_per_day": 6000},
    "Home Depot USA":           {"tier": "B", "sla_days": 3, "penalty_per_day": 3500},
    "Lowes Companies":          {"tier": "B", "sla_days": 3, "penalty_per_day": 3200},
    "Best Buy Co Inc":          {"tier": "B", "sla_days": 4, "penalty_per_day": 2800},
    "Kroger Co":                {"tier": "B", "sla_days": 3, "penalty_per_day": 3000},
    "AutoZone Inc":             {"tier": "C", "sla_days": 5, "penalty_per_day": 1200},
    "Advance Auto Parts":       {"tier": "C", "sla_days": 5, "penalty_per_day": 1100},
    "Dollar General Corp":      {"tier": "C", "sla_days": 7, "penalty_per_day": 800},
    "Family Dollar Stores":     {"tier": "C", "sla_days": 7, "penalty_per_day": 750},
}

SKUS = [
    {"sku": "SKU-A001", "desc": "Industrial Bearing 6204",   "unit_cost": 45.0,  "category": "Mechanical"},
    {"sku": "SKU-A002", "desc": "Hydraulic Seal Kit 3/4\"",  "unit_cost": 22.5,  "category": "Mechanical"},
    {"sku": "SKU-B001", "desc": "Control Module CM-500",     "unit_cost": 320.0, "category": "Electronics"},
    {"sku": "SKU-B002", "desc": "Sensor Assembly SA-200",    "unit_cost": 185.0, "category": "Electronics"},
    {"sku": "SKU-C001", "desc": "Steel Bracket Type-IV",     "unit_cost": 12.0,  "category": "Structural"},
    {"sku": "SKU-C002", "desc": "Aluminum Frame L-Profile",  "unit_cost": 28.0,  "category": "Structural"},
    {"sku": "SKU-D001", "desc": "Safety Valve SV-750",       "unit_cost": 95.0,  "category": "Safety"},
    {"sku": "SKU-D002", "desc": "Pressure Regulator PR-100", "unit_cost": 67.0,  "category": "Safety"},
    {"sku": "SKU-E001", "desc": "Cable Assembly 14AWG-25ft", "unit_cost": 18.0,  "category": "Electrical"},
    {"sku": "SKU-E002", "desc": "Junction Box IP65",         "unit_cost": 42.0,  "category": "Electrical"},
]

DISRUPTION_TYPES = {
    "Weather Event":           {"base_delay_hrs": 24, "std": 12, "resolution": ["reroute", "wait", "notify"],     "freq": 0.18},
    "Port Congestion":         {"base_delay_hrs": 36, "std": 18, "resolution": ["expedite", "alt_warehouse"],    "freq": 0.15},
    "Carrier Mechanical":      {"base_delay_hrs": 18, "std": 8,  "resolution": ["alt_carrier", "expedite"],      "freq": 0.12},
    "Customs Hold":            {"base_delay_hrs": 48, "std": 24, "resolution": ["documentation", "expedite"],    "freq": 0.10},
    "Traffic/Infrastructure":  {"base_delay_hrs": 12, "std": 6,  "resolution": ["reroute", "notify"],            "freq": 0.20},
    "Carrier Capacity":        {"base_delay_hrs": 30, "std": 15, "resolution": ["alt_carrier", "alt_warehouse"], "freq": 0.13},
    "Documentation Error":     {"base_delay_hrs": 20, "std": 10, "resolution": ["documentation", "expedite"],    "freq": 0.07},
    "Warehouse Processing":    {"base_delay_hrs": 16, "std": 8,  "resolution": ["expedite", "alt_warehouse"],    "freq": 0.05},
}

RESPONSE_OPTIONS = {
    "expedite":       {"label": "Expedite Same Carrier",     "cost_mult": 1.85, "time_save_pct": 0.60, "success_rate": 0.82},
    "alt_carrier":    {"label": "Switch to Alternate Carrier","cost_mult": 1.40, "time_save_pct": 0.70, "success_rate": 0.88},
    "alt_warehouse":  {"label": "Ship from Alternate WH",    "cost_mult": 1.25, "time_save_pct": 0.55, "success_rate": 0.91},
    "reroute":        {"label": "Reroute via Alt Lane",       "cost_mult": 1.15, "time_save_pct": 0.45, "success_rate": 0.85},
    "notify":         {"label": "Customer Notification + ETA","cost_mult": 1.00, "time_save_pct": 0.00, "success_rate": 1.00},
    "documentation":  {"label": "Emergency Documentation",   "cost_mult": 1.10, "time_save_pct": 0.40, "success_rate": 0.78},
}

MANUAL_PROCESS_STEPS = [
    ("Alert Detection",          "Analyst notices alert in project44 dashboard",          25),
    ("SAP Order Lookup",         "Manually search SAP for affected sales orders",          18),
    ("Inventory Check",          "Check stock levels in each warehouse in SAP",            15),
    ("Customer Impact Review",   "Review customer SLA and penalty clauses manually",       20),
    ("Option Research",          "Research carrier alternatives via phone/email",          35),
    ("Cost Calculation",         "Manually calculate cost of each option in Excel",        25),
    ("Manager Approval",         "Email manager for approval on response",                 45),
    ("SAP Transaction Entry",    "Manually enter delivery date change in SAP VA02",        20),
    ("Customer Notification",    "Draft and send customer notification email",             15),
    ("Documentation Update",     "Update shipment log and incident record",                12),
]  # (step, description, minutes)


# ── Generators ───────────────────────────────────────────────────────────────

def generate_carriers_df() -> pd.DataFrame:
    rows = []
    for name, props in CARRIERS.items():
        rows.append({
            "carrier_name": name,
            "reliability_score": props["reliability"],
            "avg_delay_hrs": props["avg_delay_hrs"],
            "capacity": props["capacity"],
            "cost_index": props["cost_idx"],
            "network_coverage": random.uniform(0.70, 0.98),
            "on_time_2025": round(props["reliability"] * 100 + np.random.normal(0, 1), 1),
        })
    return pd.DataFrame(rows)


def generate_inventory_df() -> pd.DataFrame:
    rows = []
    for sku_info in SKUS:
        for wh in WAREHOUSES:
            current = random.randint(0, 500)
            safety  = random.randint(20, 80)
            rows.append({
                "sku":           sku_info["sku"],
                "description":   sku_info["desc"],
                "category":      sku_info["category"],
                "warehouse":     wh,
                "current_stock": current,
                "safety_stock":  safety,
                "reorder_point": safety + random.randint(10, 40),
                "unit_cost":     sku_info["unit_cost"],
                "lead_time_days":random.randint(2, 14),
                "status":        "Critical" if current < safety
                                  else ("Low" if current < safety * 1.5 else "OK"),
            })
    return pd.DataFrame(rows)


def generate_shipments_df(n: int = 150) -> pd.DataFrame:
    carrier_names = list(CARRIERS.keys())
    disruption_names = list(DISRUPTION_TYPES.keys())
    disruption_probs = [DISRUPTION_TYPES[d]["freq"] for d in disruption_names]

    rows = []
    base_date = datetime(2026, 1, 1)

    for i in range(n):
        carrier = random.choice(carrier_names)
        c_props  = CARRIERS[carrier]
        origin   = random.choice(WAREHOUSES)
        dest_state = random.choice(["New York", "Texas", "California", "Florida",
                                    "Ohio", "Michigan", "Georgia", "Illinois"])

        ship_date    = base_date + timedelta(days=random.randint(0, 85))
        transit_days = random.randint(2, 7)
        exp_delivery = ship_date + timedelta(days=transit_days)

        # Determine if delayed
        is_delayed  = random.random() > c_props["reliability"]
        disruption  = None
        delay_hrs   = 0
        if is_delayed:
            disruption = random.choices(disruption_names, weights=disruption_probs)[0]
            d_props    = DISRUPTION_TYPES[disruption]
            delay_hrs  = max(0, int(np.random.normal(d_props["base_delay_hrs"], d_props["std"])))

        act_delivery = exp_delivery + timedelta(hours=delay_hrs)
        severity     = ("Critical" if delay_hrs >= 48 else
                        "High"     if delay_hrs >= 24 else
                        "Medium"   if delay_hrs >= 12 else
                        "Low"      if delay_hrs >  0  else "On Time")

        rows.append({
            "shipment_id":       f"SHP-{i+1:04d}",
            "carrier":           carrier,
            "origin_warehouse":  origin,
            "destination_state": dest_state,
            "ship_date":         ship_date,
            "expected_delivery": exp_delivery,
            "actual_delivery":   act_delivery,
            "delay_hours":       delay_hrs,
            "disruption_type":   disruption if is_delayed else None,
            "is_delayed":        is_delayed,
            "severity":          severity,
            "tracking_status":   ("Exception" if is_delayed else
                                  random.choice(["In Transit", "Out for Delivery", "Delivered"])),
            "freight_cost_usd":  round(random.uniform(450, 4500) * c_props["cost_idx"], 2),
        })

    return pd.DataFrame(rows)


def generate_orders_df(shipments_df: pd.DataFrame) -> pd.DataFrame:
    customer_names = list(CUSTOMERS.keys())
    sku_ids        = [s["sku"] for s in SKUS]
    rows = []
    order_counter = 1

    for _, shipment in shipments_df.iterrows():
        n_orders = random.randint(1, 4)
        for _ in range(n_orders):
            customer   = random.choice(customer_names)
            c_props    = CUSTOMERS[customer]
            sku        = random.choice(sku_ids)
            sku_info   = next(s for s in SKUS if s["sku"] == sku)
            qty        = random.randint(10, 500)
            unit_price = sku_info["unit_cost"] * random.uniform(1.3, 1.8)
            order_val  = round(qty * unit_price, 2)

            req_delivery = shipment["expected_delivery"] - timedelta(days=random.randint(0, 1))
            # Penalty starts accruing after 50% of SLA window is exceeded by the delay
            sla_hrs      = c_props["sla_days"] * 24
            delay_impact = max(0, shipment["delay_hours"] - sla_hrs * 0.5)
            penalty      = round((delay_impact / 24) * c_props["penalty_per_day"], 2)

            rows.append({
                "order_id":             f"SO-{order_counter:05d}",
                "shipment_id":          shipment["shipment_id"],
                "customer":             customer,
                "customer_tier":        c_props["tier"],
                "sla_days":             c_props["sla_days"],
                "penalty_per_day":      c_props["penalty_per_day"],
                "sku":                  sku,
                "sku_desc":             sku_info["desc"],
                "quantity":             qty,
                "unit_price":           round(unit_price, 2),
                "order_value":          order_val,
                "required_delivery":    req_delivery,
                "is_at_risk":           shipment["is_delayed"],
                "delay_hours_exposure": shipment["delay_hours"],
                "sla_breach_hours":     max(0, shipment["delay_hours"] - c_props["sla_days"] * 24),
                "estimated_penalty":    penalty,
                "order_status":         "At Risk" if shipment["is_delayed"] else "On Track",
                "origin_warehouse":     shipment["origin_warehouse"],
            })
            order_counter += 1

    return pd.DataFrame(rows)


def generate_all(n_shipments: int = 150):
    carriers  = generate_carriers_df()
    inventory = generate_inventory_df()
    shipments = generate_shipments_df(n_shipments)
    orders    = generate_orders_df(shipments)
    return carriers, inventory, shipments, orders


def get_summary_stats(shipments: pd.DataFrame, orders: pd.DataFrame) -> dict:
    delayed    = shipments[shipments["is_delayed"]]
    at_risk_o  = orders[orders["is_at_risk"]]
    manual_min = sum(s[2] for s in MANUAL_PROCESS_STEPS)

    return {
        "total_shipments":      len(shipments),
        "delayed_shipments":    len(delayed),
        "delay_rate_pct":       round(len(delayed) / len(shipments) * 100, 1),
        "total_orders":         len(orders),
        "orders_at_risk":       len(at_risk_o),
        "total_penalty_usd":    round(at_risk_o["estimated_penalty"].sum()),
        "total_order_value_at_risk": round(at_risk_o["order_value"].sum()),
        "critical_shipments":   len(shipments[shipments["severity"] == "Critical"]),
        "tier_a_at_risk":       len(at_risk_o[at_risk_o["customer_tier"] == "A"]),
        "manual_process_mins":  manual_min,
        "actionbridge_mins":    3,
        "incidents_per_month":  round(len(delayed) / 3),
    }
