"""
ActionBridge — SAP Transaction Generator + Data Validator
Generates SAP-formatted transaction drafts and validates data quality.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.data_generator import MANUAL_PROCESS_STEPS


# ══════════════════════════════════════════════════════════════════════════════
# SAP TRANSACTION GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_sap_transactions(shipment_row: pd.Series,
                               orders_affected: pd.DataFrame,
                               best_decision: dict) -> list:
    """
    Generate formatted SAP transaction drafts based on chosen response.
    Returns list of transaction dicts ready to display.
    """
    transactions = []
    decision_key = best_decision.get("key", "notify")
    now_str      = datetime.now().strftime("%Y-%m-%d %H:%M")
    delay_hrs    = float(shipment_row.get("delay_hours", 0))
    new_delivery = (
        pd.to_datetime(shipment_row["expected_delivery"]) + timedelta(hours=delay_hrs)
        if delay_hrs > 0 else pd.to_datetime(shipment_row["expected_delivery"])
    )

    # ── Always generate: Delivery Date Change (VA02) ──────────────────────
    for _, order in orders_affected.iterrows():
        transactions.append({
            "t_code":      "VA02",
            "title":       "Change Sales Order — Delivery Date",
            "category":    "Sales Order",
            "priority":    "HIGH" if order["customer_tier"] == "A" else "MEDIUM",
            "fields": {
                "Order Number":         order["order_id"],
                "Customer":             order["customer"],
                "Old Delivery Date":    str(order["required_delivery"])[:10],
                "New Delivery Date":    new_delivery.strftime("%Y-%m-%d"),
                "Delay Reason Code":    _get_delay_reason(shipment_row.get("disruption_type", "")),
                "Changed By":           "ACTIONBRIDGE_AUTO",
                "Change Timestamp":     now_str,
                "Confirmation Flag":    "Set",
            },
            "estimated_time": "< 30 seconds",
            "vs_manual":      "18 min manual entry",
        })

    # ── Expedite: Create Purchase Order Expedite (ME22N) ─────────────────
    if decision_key == "expedite":
        transactions.append({
            "t_code":   "ME22N",
            "title":    "Expedite Purchase Order",
            "category": "Procurement",
            "priority": "URGENT",
            "fields": {
                "Shipment ID":       shipment_row["shipment_id"],
                "Carrier":           shipment_row["carrier"],
                "Expedite Flag":     "RUSH",
                "Priority Level":    "1 — Critical",
                "Cost Override":     f"+85% freight premium approved",
                "Auth Code":         "AUTO-ABRIDGE-001",
                "Requested By":      now_str,
                "ETA After Expedite":
                    (new_delivery - timedelta(hours=float(delay_hrs) * 0.6)).strftime("%Y-%m-%d"),
            },
            "estimated_time": "< 45 seconds",
            "vs_manual":      "35 min calls + approval chain",
        })

    # ── Alt Warehouse: Transfer Order (LT01) ──────────────────────────────
    if decision_key == "alt_warehouse" and best_decision.get("alt_warehouse"):
        alt_wh = best_decision["alt_warehouse"]
        for _, order in orders_affected.head(3).iterrows():
            transactions.append({
                "t_code":   "LT01",
                "title":    "Create Transfer Order — Alt Warehouse",
                "category": "Warehouse Management",
                "priority": "HIGH",
                "fields": {
                    "Source Warehouse":   alt_wh,
                    "Destination":        order["customer"],
                    "SKU":                order["sku"],
                    "Quantity":           str(order["quantity"]),
                    "Movement Type":      "641 — Transfer to Customer",
                    "Delivery Priority":  "01 — Rush",
                    "Requested Date":     datetime.now().strftime("%Y-%m-%d"),
                    "Auto-Confirmed":     "Yes — Stock verified",
                },
                "estimated_time": "< 60 seconds",
                "vs_manual":      "15 min inventory check + entry",
            })

    # ── Alt Carrier: Carrier Assignment Change ─────────────────────────────
    if decision_key == "alt_carrier" and best_decision.get("alt_carrier"):
        transactions.append({
            "t_code":   "VT02N",
            "title":    "Change Carrier Assignment",
            "category": "Transportation",
            "priority": "HIGH",
            "fields": {
                "Shipment ID":     shipment_row["shipment_id"],
                "Current Carrier": shipment_row["carrier"],
                "New Carrier":     best_decision["alt_carrier"],
                "Reason":         "Carrier exception — automated reroute",
                "New ETA":        (new_delivery - timedelta(hours=float(delay_hrs) * 0.7)).strftime("%Y-%m-%d"),
                "Cost Delta":     "+40% freight — auto-approved < $5000",
                "Auth":           "ACTIONBRIDGE_AUTO",
            },
            "estimated_time": "< 45 seconds",
            "vs_manual":      "35 min carrier coordination",
        })

    # ── Always: Customer Notification (custom) ────────────────────────────
    unique_customers = orders_affected["customer"].unique()[:3]
    for cust in unique_customers:
        cust_orders = orders_affected[orders_affected["customer"] == cust]
        transactions.append({
            "t_code":   "EMAIL",
            "title":    f"Customer Notification — {cust}",
            "category": "Communication",
            "priority": "HIGH" if orders_affected[
                orders_affected["customer"] == cust]["customer_tier"].iloc[0] == "A" else "MEDIUM",
            "fields": {
                "To":           f"procurement@{cust.lower().replace(' ', '')[:15]}.com",
                "Subject":      f"Shipment {shipment_row['shipment_id']} — Delivery Update",
                "Order Count":  str(len(cust_orders)),
                "Original ETA": str(shipment_row["expected_delivery"])[:10],
                "Revised ETA":  new_delivery.strftime("%Y-%m-%d"),
                "Reason":       shipment_row.get("disruption_type", "Operational delay"),
                "Action Taken": best_decision.get("label", "Under review"),
                "Auto-Sent":    "Yes — Template AB-DELAY-001",
            },
            "estimated_time": "< 15 seconds",
            "vs_manual":      "15 min drafting + approval",
        })

    return transactions


def _get_delay_reason(disruption_type: str) -> str:
    mapping = {
        "Weather Event":          "ZW01 — Weather",
        "Port Congestion":        "ZP01 — Port Delay",
        "Carrier Mechanical":     "ZC01 — Carrier Issue",
        "Customs Hold":           "ZD01 — Customs",
        "Traffic/Infrastructure": "ZT01 — Traffic",
        "Carrier Capacity":       "ZC02 — Capacity",
        "Documentation Error":    "ZD02 — Documentation",
        "Warehouse Processing":   "ZW02 — Warehouse",
    }
    return mapping.get(disruption_type, "ZO01 — Other")


def get_time_savings_summary(transactions: list) -> dict:
    manual_total  = sum(s[2] for s in MANUAL_PROCESS_STEPS)
    auto_time_min = len(transactions) * 0.5  # ~30 sec per transaction
    return {
        "manual_minutes":  manual_total,
        "auto_minutes":    round(auto_time_min, 1),
        "saved_minutes":   round(manual_total - auto_time_min, 1),
        "reduction_pct":   round((1 - auto_time_min / manual_total) * 100, 1),
        "transactions":    len(transactions),
    }


# ══════════════════════════════════════════════════════════════════════════════
# DATA VALIDATOR
# ══════════════════════════════════════════════════════════════════════════════

def validate_data_quality(shipments_df: pd.DataFrame,
                           orders_df: pd.DataFrame,
                           inventory_df: pd.DataFrame,
                           carriers_df: pd.DataFrame) -> dict:
    """
    Run comprehensive data quality checks across all four datasets.
    Returns per-dataset scores and overall health grade.
    """
    results = {}

    # ── Shipments ────────────────────────────────────────────────────────
    s_checks = []
    s_checks.append(_check("No null shipment_id",
                            shipments_df["shipment_id"].notnull().all(),
                            shipments_df["shipment_id"].notnull().mean()))
    s_checks.append(_check("No null carrier",
                            shipments_df["carrier"].notnull().all(),
                            shipments_df["carrier"].notnull().mean()))
    s_checks.append(_check("Delay hours ≥ 0",
                            (shipments_df["delay_hours"] >= 0).all(),
                            (shipments_df["delay_hours"] >= 0).mean()))
    s_checks.append(_check("Expected delivery > ship date",
                            (pd.to_datetime(shipments_df["expected_delivery"]) >=
                             pd.to_datetime(shipments_df["ship_date"])).all(),
                            (pd.to_datetime(shipments_df["expected_delivery"]) >=
                             pd.to_datetime(shipments_df["ship_date"])).mean()))
    s_checks.append(_check("Severity label populated",
                            shipments_df["severity"].notnull().all(),
                            shipments_df["severity"].notnull().mean()))
    results["Shipments"] = _aggregate(s_checks, len(shipments_df))

    # ── Orders ───────────────────────────────────────────────────────────
    o_checks = []
    o_checks.append(_check("No null order_id",
                            orders_df["order_id"].notnull().all(),
                            orders_df["order_id"].notnull().mean()))
    o_checks.append(_check("Order value > 0",
                            (orders_df["order_value"] > 0).all(),
                            (orders_df["order_value"] > 0).mean()))
    o_checks.append(_check("Shipment FK valid",
                            orders_df["shipment_id"].isin(shipments_df["shipment_id"]).all(),
                            orders_df["shipment_id"].isin(shipments_df["shipment_id"]).mean()))
    o_checks.append(_check("Customer tier populated",
                            orders_df["customer_tier"].isin(["A","B","C"]).all(),
                            orders_df["customer_tier"].isin(["A","B","C"]).mean()))
    o_checks.append(_check("Penalty ≥ 0",
                            (orders_df["estimated_penalty"] >= 0).all(),
                            (orders_df["estimated_penalty"] >= 0).mean()))
    results["Orders"] = _aggregate(o_checks, len(orders_df))

    # ── Inventory ────────────────────────────────────────────────────────
    i_checks = []
    i_checks.append(_check("No null SKU",
                            inventory_df["sku"].notnull().all(),
                            inventory_df["sku"].notnull().mean()))
    i_checks.append(_check("Current stock ≥ 0",
                            (inventory_df["current_stock"] >= 0).all(),
                            (inventory_df["current_stock"] >= 0).mean()))
    i_checks.append(_check("Safety stock > 0",
                            (inventory_df["safety_stock"] > 0).all(),
                            (inventory_df["safety_stock"] > 0).mean()))
    i_checks.append(_check("Status label correct",
                            inventory_df["status"].isin(["OK","Low","Critical"]).all(),
                            inventory_df["status"].isin(["OK","Low","Critical"]).mean()))
    results["Inventory"] = _aggregate(i_checks, len(inventory_df))

    # ── Carriers ─────────────────────────────────────────────────────────
    c_checks = []
    c_checks.append(_check("Reliability 0–1",
                            carriers_df["reliability_score"].between(0, 1).all(),
                            carriers_df["reliability_score"].between(0, 1).mean()))
    c_checks.append(_check("No null carrier name",
                            carriers_df["carrier_name"].notnull().all(),
                            carriers_df["carrier_name"].notnull().mean()))
    results["Carriers"] = _aggregate(c_checks, len(carriers_df))

    # ── Overall ──────────────────────────────────────────────────────────
    all_scores  = [v["score"] for v in results.values()]
    overall     = round(np.mean(all_scores), 1)
    grade       = ("A" if overall >= 95 else "B" if overall >= 85
                   else "C" if overall >= 70 else "D")
    action_msg  = ("Data is decision-ready" if overall >= 90
                   else "Minor data gaps — decisions may have lower confidence"
                   if overall >= 75 else "Significant data issues — review before acting")

    return {
        "datasets":       results,
        "overall_score":  overall,
        "grade":          grade,
        "action_message": action_msg,
        "total_records":  len(shipments_df) + len(orders_df) + len(inventory_df) + len(carriers_df),
    }


def _check(name: str, passed: bool, completeness: float) -> dict:
    return {
        "check":        name,
        "passed":       bool(passed),
        "completeness": round(float(completeness) * 100, 1),
        "status":       "✅" if passed else "❌",
    }


def _aggregate(checks: list, row_count: int) -> dict:
    passed = sum(1 for c in checks if c["passed"])
    score  = round(passed / len(checks) * 100, 1) if checks else 0
    return {
        "checks":    checks,
        "passed":    passed,
        "total":     len(checks),
        "score":     score,
        "row_count": row_count,
        "grade":     "A" if score >= 95 else "B" if score >= 80 else "C" if score >= 60 else "D",
    }
