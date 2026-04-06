"""
ActionBridge — Decision Engine
Scores disruption impact, ranks response options,
and validates decision quality against rule-based baseline.
"""

import pandas as pd
import numpy as np
from utils.data_generator import RESPONSE_OPTIONS, DISRUPTION_TYPES, CUSTOMERS

# ── Impact Scoring ────────────────────────────────────────────────────────────

TIER_WEIGHT = {"A": 1.0, "B": 0.65, "C": 0.35}

def score_impact(orders_affected: pd.DataFrame, shipment_row: pd.Series) -> dict:
    """
    Composite impact score (0-100) for a disrupted shipment.
    Factors: order value, customer tier, delay severity, SLA breach, penalty exposure.
    """
    if orders_affected.empty:
        return {"score": 0, "grade": "Low", "components": {}}

    # Financial exposure
    total_value   = orders_affected["order_value"].sum()
    total_penalty = orders_affected["estimated_penalty"].sum()
    fin_score     = min(100, (total_penalty / max(total_value, 1)) * 200 +
                        np.log1p(total_value) * 3)

    # Customer tier weight
    tier_score = sum(
        TIER_WEIGHT.get(row["customer_tier"], 0.35) * row["order_value"]
        for _, row in orders_affected.iterrows()
    ) / max(total_value, 1) * 100

    # Delay severity
    delay_hrs = shipment_row.get("delay_hours", 0)
    delay_score = min(100, delay_hrs / 72 * 100)

    # SLA breach
    breach_orders = orders_affected[orders_affected["sla_breach_hours"] > 0]
    breach_score  = len(breach_orders) / len(orders_affected) * 100

    # Composite (weighted)
    composite = (
        fin_score   * 0.30 +
        tier_score  * 0.30 +
        delay_score * 0.25 +
        breach_score* 0.15
    )
    composite = min(100, max(0, composite))

    grade = ("Critical" if composite >= 75 else
             "High"     if composite >= 50 else
             "Medium"   if composite >= 25 else "Low")

    return {
        "score":      round(composite, 1),
        "grade":      grade,
        "components": {
            "Financial Exposure":  round(fin_score,    1),
            "Customer Priority":   round(tier_score,   1),
            "Delay Severity":      round(delay_score,  1),
            "SLA Breach Risk":     round(breach_score, 1),
        },
        "total_value_at_risk":   round(total_value, 2),
        "total_penalty_at_risk": round(total_penalty, 2),
        "orders_count":          len(orders_affected),
        "tier_a_count":          len(orders_affected[orders_affected["customer_tier"] == "A"]),
    }


# ── Response Option Ranking ──────────────────────────────────────────────────

def rank_responses(shipment_row: pd.Series,
                   orders_affected: pd.DataFrame,
                   inventory_df: pd.DataFrame,
                   carriers_df: pd.DataFrame,
                   impact: dict) -> pd.DataFrame:
    """
    Rank all feasible response options by value score:
      value = (penalty_avoided * success_rate) / added_cost
    """
    delay_hrs         = float(shipment_row.get("delay_hours", 0))
    freight_cost      = float(shipment_row.get("freight_cost_usd", 1000))
    disruption_type   = shipment_row.get("disruption_type", "Weather Event")
    origin_wh         = shipment_row.get("origin_warehouse", "Chicago-IL")
    carrier           = shipment_row.get("carrier", "XPO Logistics")
    total_penalty     = impact.get("total_penalty_at_risk", 0)

    # Feasibility checks
    alt_whs = _check_alt_warehouse(orders_affected, inventory_df, origin_wh)
    alt_carriers = _get_alt_carriers(carrier, carriers_df)
    feasible_responses = _get_feasible_responses(disruption_type)

    rows = []
    for resp_key, resp_props in RESPONSE_OPTIONS.items():
        if resp_key not in feasible_responses:
            continue

        added_cost      = freight_cost * (resp_props["cost_mult"] - 1.0)
        hrs_saved       = delay_hrs * resp_props["time_save_pct"]
        penalty_avoided = total_penalty * resp_props["time_save_pct"] * resp_props["success_rate"]
        net_benefit     = penalty_avoided - added_cost

        # Feasibility flag
        feasible  = True
        feas_note = ""
        if resp_key == "alt_warehouse" and not alt_whs:
            feasible  = False
            feas_note = "No alt warehouse has sufficient stock"
        if resp_key == "alt_carrier" and not alt_carriers:
            feasible  = False
            feas_note = "No high-reliability alt carrier available"

        # Value score
        value_score = (net_benefit / max(added_cost + 1, 1)) * resp_props["success_rate"] * 100
        value_score = max(0, min(100, value_score))

        rows.append({
            "response_key":    resp_key,
            "response_label":  resp_props["label"],
            "added_cost_usd":  round(added_cost, 2),
            "hours_saved":     round(hrs_saved, 1),
            "penalty_avoided": round(penalty_avoided, 2),
            "net_benefit_usd": round(net_benefit, 2),
            "success_rate":    resp_props["success_rate"],
            "value_score":     round(value_score, 1),
            "feasible":        feasible,
            "feasibility_note":feas_note,
            "alt_warehouse":   alt_whs[0] if alt_whs else None,
            "alt_carrier":     alt_carriers[0] if alt_carriers else None,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values(["feasible", "net_benefit_usd"], ascending=[False, False])
    df["rank"] = range(1, len(df) + 1)
    return df.reset_index(drop=True)


def _check_alt_warehouse(orders_affected, inventory_df, origin_wh):
    """Return list of warehouses with sufficient stock for the orders."""
    if orders_affected.empty or inventory_df.empty:
        return []
    alt_whs = []
    needed_skus = orders_affected["sku"].unique()
    for wh in inventory_df["warehouse"].unique():
        if wh == origin_wh:
            continue
        wh_inv = inventory_df[inventory_df["warehouse"] == wh]
        has_all = all(
            len(wh_inv[(wh_inv["sku"] == sku) & (wh_inv["current_stock"] > wh_inv["safety_stock"])]) > 0
            for sku in needed_skus
        )
        if has_all:
            alt_whs.append(wh)
    return alt_whs


def _get_alt_carriers(current_carrier, carriers_df):
    """Return carriers with higher reliability than current."""
    if carriers_df.empty:
        return []
    current_rel = carriers_df[carriers_df["carrier_name"] == current_carrier]["reliability_score"]
    if current_rel.empty:
        return []
    threshold = float(current_rel.iloc[0])
    alts = carriers_df[
        (carriers_df["carrier_name"] != current_carrier) &
        (carriers_df["reliability_score"] >= threshold)
    ]["carrier_name"].tolist()
    return alts


def _get_feasible_responses(disruption_type):
    """Return applicable responses for a disruption type."""
    d_info = DISRUPTION_TYPES.get(disruption_type, {})
    base   = d_info.get("resolution", ["notify"])
    # Always add notify as fallback
    return list(set(base + ["notify"]))


# ── Best Decision Selector ───────────────────────────────────────────────────

def get_best_decision(responses_df: pd.DataFrame) -> dict:
    if responses_df.empty:
        return {"label": "Manual Review Required", "rationale": "Insufficient data"}
    feasible = responses_df[responses_df["feasible"]]
    if feasible.empty:
        return {"label": "Customer Notification Only", "rationale": "No automated options feasible"}
    best = feasible.iloc[0]
    return {
        "key":            best["response_key"],
        "label":          best["response_label"],
        "net_benefit":    best["net_benefit_usd"],
        "hours_saved":    best["hours_saved"],
        "success_rate":   best["success_rate"],
        "value_score":    best["value_score"],
        "alt_warehouse":  best.get("alt_warehouse"),
        "alt_carrier":    best.get("alt_carrier"),
        "rationale":      _build_rationale(best),
    }


def _build_rationale(row: pd.Series) -> str:
    parts = [
        f"Highest net benefit: ${row['net_benefit_usd']:,.0f}.",
        f"Saves {row['hours_saved']:.0f}h of delay at {row['success_rate']*100:.0f}% confidence.",
    ]
    if row.get("alt_warehouse"):
        parts.append(f"Stock confirmed at {row['alt_warehouse']}.")
    if row.get("alt_carrier"):
        parts.append(f"Alt carrier {row['alt_carrier']} available with higher reliability.")
    return " ".join(parts)


# ── Decision Validation ──────────────────────────────────────────────────────

def validate_decision_quality(responses_df: pd.DataFrame,
                               impact: dict) -> dict:
    """
    Validate the decision engine output against:
    1. Rule-based baseline (simple cost-minimisation)
    2. Data completeness
    3. Confidence score
    """
    if responses_df.empty:
        return {"confidence": 0, "validation_status": "FAIL", "issues": ["No response options generated"]}

    issues = []
    score  = 100

    # Check feasibility coverage
    feasible_count = responses_df["feasible"].sum()
    if feasible_count == 0:
        issues.append("No feasible responses identified — defaulting to notification only")
        score -= 30

    # Check data completeness
    null_fields = responses_df[["added_cost_usd", "penalty_avoided", "success_rate"]].isnull().sum().sum()
    if null_fields > 0:
        issues.append(f"{null_fields} missing values in response scoring")
        score -= 20

    # Check impact score reliability
    if impact.get("score", 0) == 0:
        issues.append("Impact score is zero — check order linkage to shipment")
        score -= 25

    # Validate rule-based agreement
    if feasible_count >= 2:
        rule_best   = responses_df[responses_df["feasible"]].sort_values("net_benefit_usd", ascending=False).iloc[0]
        engine_best = responses_df[responses_df["feasible"]].sort_values("value_score", ascending=False).iloc[0]
        if rule_best["response_key"] != engine_best["response_key"]:
            issues.append("Engine recommendation diverges from cost-only baseline — review weighting")
            score -= 10

    confidence = max(0, min(100, score))
    status     = "PASS" if confidence >= 70 else ("WARN" if confidence >= 50 else "FAIL")

    return {
        "confidence":        confidence,
        "validation_status": status,
        "issues":            issues if issues else ["All validation checks passed"],
        "feasible_options":  int(feasible_count),
        "baseline_agreement":feasible_count >= 2,
    }
