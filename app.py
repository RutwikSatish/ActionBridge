"""
ActionBridge
─────────────────────────────────────────────────────────────────
From Visibility Alert to SAP Transaction Draft in One Step.

Inspired by Jett McCandless, CEO of project44:
"AI that doesn't lead to action is just another dashboard."
Source: PR Newswire / project44 Decision Intelligence launch, June 12, 2025

Built by Rutwik Satish | MS Engineering Management, Northeastern
SAP S/4HANA | McKinsey Forward

NOTE: All shipment, order, inventory and carrier data is synthetically
generated (random seed). No real company or operational data is used.
SAP transactions generated are DRAFTS only — no live SAP connection exists.
"""

import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

from utils.data_generator import (
    generate_all, get_summary_stats, MANUAL_PROCESS_STEPS,
    DISRUPTION_TYPES, CARRIERS, CUSTOMERS,
)
from utils.decision_engine import (
    score_impact, rank_responses, get_best_decision, validate_decision_quality,
)
from utils.sap_validator import (
    generate_sap_transactions, get_time_savings_summary, validate_data_quality,
)
from utils.charts import (
    fig_disruption_timeline, fig_severity_donut,
    fig_order_impact_scatter, fig_penalty_by_customer,
    fig_response_comparison, fig_impact_radar,
    fig_process_comparison, fig_roi_annualised,
    fig_data_quality_bar, fig_carrier_reliability,
)

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ActionBridge",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #0A0E1A !important;
    color: #F9FAFB !important;
}
section[data-testid="stSidebar"] {
    background-color: #0A0E1A !important;
    border-right: 1px solid #1F2937 !important;
}
section[data-testid="stSidebar"] * { color: #F9FAFB !important; }

div[data-testid="metric-container"] {
    background: #111827; border: 1px solid #1F2937;
    border-radius: 10px; padding: 14px 18px !important;
}
div[data-testid="metric-container"] label { color: #6B7280 !important; font-size:11px !important; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #F9FAFB !important; font-family: 'Space Mono', monospace !important; font-size: 1.5rem !important;
}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] { font-size: 11px !important; }

button[data-baseweb="tab"] {
    background: transparent !important; color: #6B7280 !important;
    font-family: 'Space Mono', monospace !important; font-size: 11px !important;
    border-bottom: 2px solid transparent !important; letter-spacing: 0.5px;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #F59E0B !important; border-bottom: 2px solid #F59E0B !important;
}

.ab-card {
    background: #111827; border: 1px solid #1F2937;
    border-radius: 10px; padding: 18px 22px; margin-bottom: 14px;
}
.ab-card-alert {
    background: linear-gradient(135deg, #1a0a0a 0%, #111827 100%);
    border: 1px solid #EF444440; border-left: 3px solid #EF4444;
    border-radius: 0 10px 10px 0; padding: 16px 20px; margin-bottom: 12px;
}
.ab-card-success {
    background: linear-gradient(135deg, #061a12 0%, #111827 100%);
    border: 1px solid #10B98140; border-left: 3px solid #10B981;
    border-radius: 0 10px 10px 0; padding: 16px 20px; margin-bottom: 12px;
}
.ab-card-amber {
    background: linear-gradient(135deg, #1a110a 0%, #111827 100%);
    border: 1px solid #F59E0B40; border-left: 3px solid #F59E0B;
    border-radius: 0 10px 10px 0; padding: 16px 20px; margin-bottom: 12px;
}
.ab-mono { font-family: 'Space Mono', monospace; font-size: 11px; }
.ab-label {
    font-family: 'Space Mono', monospace; font-size: 10px;
    color: #F59E0B; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 10px;
}
.ab-hero {
    background: linear-gradient(135deg, #0A0E1A 0%, #0d1520 50%, #0A0E1A 100%);
    border: 1px solid #F59E0B22; border-radius: 14px;
    padding: 28px 32px; margin-bottom: 24px;
}
.ab-tag {
    display: inline-block; background: #F59E0B18; color: #F59E0B;
    border: 1px solid #F59E0B33; border-radius: 5px; padding: 2px 10px;
    font-size: 10px; font-family: 'Space Mono', monospace; margin-right: 6px;
}
.sap-block {
    background: #0d1520; border: 1px solid #1F2937; border-radius: 8px;
    padding: 14px 18px; margin-bottom: 10px; font-family: 'Space Mono', monospace;
    font-size: 11px;
}
div[data-testid="stSelectbox"] > div { background: #111827 !important; border-color: #1F2937 !important; }
div[data-testid="stSlider"] { padding: 4px 0; }
div[data-testid="stFileUploadDropzone"] {
    background: #111827 !important; border: 1px dashed #1F2937 !important; border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)


# ── Cache ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data(n_ships: int):
    carriers, inventory, shipments, orders = generate_all(n_ships)
    stats = get_summary_stats(shipments, orders)
    dq    = validate_data_quality(shipments, orders, inventory, carriers)
    return carriers, inventory, shipments, orders, stats, dq


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding:16px 0 20px 0;'>
        <div style='font-family: Space Mono, monospace; font-size:20px;
                    font-weight:700; color:#F59E0B; letter-spacing:-1px;'>
            ⚡ ActionBridge
        </div>
        <div style='font-size:9px; color:#6B7280; letter-spacing:3px;
                    text-transform:uppercase; margin-top:4px;'>
            VISIBILITY → DECISION → SAP DRAFTS
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<p class="ab-label">Simulation Config</p>', unsafe_allow_html=True)

    n_shipments = st.slider("Shipments to simulate", 80, 300, 150, 10)
    carriers, inventory, shipments, orders, stats, dq = load_data(n_shipments)

    st.markdown("---")
    st.markdown('<p class="ab-label">Disruption Simulator</p>', unsafe_allow_html=True)

    sel_shipment = st.selectbox(
        "Select disrupted shipment",
        shipments[shipments["is_delayed"]]["shipment_id"].tolist(),
        help="Pick any delayed shipment to run full decision analysis",
    )

    st.markdown("---")
    st.markdown('<p class="ab-label">AI Analyst (Groq)</p>', unsafe_allow_html=True)
    groq_key = st.secrets.get("GROQ_API_KEY", "")
    if groq_key:
        st.markdown('<div style="font-size:10px;color:#10B981;">✅ AI Analyst ready</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:10px;color:#6B7280;">Add GROQ_API_KEY to secrets</div>',
                    unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload your shipment CSV", type=["csv"],
                                 help="Columns: shipment_id, carrier, delay_hours, disruption_type, expected_delivery")

    st.markdown("---")
    st.markdown("""
    <div style='font-size:10px; color:#6B7280; text-align:center; line-height:1.7;'>
        Inspired by <b style='color:#F9FAFB;'>Jett McCandless</b><br>
        Founder &amp; CEO, project44<br>
        <i style='color:#F59E0B;'>"AI that doesn't lead to<br>
        action is just another<br>dashboard."</i>
        <br><small style='color:#4B5563;'>PR Newswire, June 12, 2025</small>
        <br><br>
        <b style='color:#F9FAFB;'>Rutwik Satish</b><br>
        MS Eng. Mgmt · Northeastern<br>
        <span style='color:#F59E0B;'>SAP S/4HANA · McKinsey Forward</span><br>
        <span style='color:#4B5563; font-size:9px;'>Synthetic data · SAP drafts only</span>
    </div>
    """, unsafe_allow_html=True)


# ── Load selected shipment data ───────────────────────────────────────────────
sel_ship_row   = shipments[shipments["shipment_id"] == sel_shipment].iloc[0]
sel_orders     = orders[orders["shipment_id"] == sel_shipment]
impact         = score_impact(sel_orders, sel_ship_row)
responses      = rank_responses(sel_ship_row, sel_orders, inventory, carriers, impact)
best_decision  = get_best_decision(responses)
decision_valid = validate_decision_quality(responses, impact)
transactions   = generate_sap_transactions(sel_ship_row, sel_orders, best_decision)
time_savings   = get_time_savings_summary(transactions)

if uploaded:
    try:
        df_up = pd.read_csv(uploaded)
        req   = {"shipment_id","carrier","delay_hours","disruption_type","expected_delivery"}
        if req.issubset(df_up.columns):
            st.sidebar.success(f"✅ {len(df_up)} rows loaded")
    except Exception as e:
        st.sidebar.error(f"Parse error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# HERO
# ══════════════════════════════════════════════════════════════════════════════
dq_color = "#10B981" if dq["overall_score"] >= 90 else "#F59E0B" if dq["overall_score"] >= 75 else "#EF4444"
st.markdown(f"""
<div class="ab-hero">
    <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
        <div>
            <div style='font-size:26px; font-weight:700; font-family: DM Sans, sans-serif;
                        letter-spacing:-0.5px; margin-bottom:6px;'>
                ⚡ Action<span style='color:#F59E0B;'>Bridge</span>
            </div>
            <div style='font-size:12px; color:#6B7280; margin-bottom:12px;'>
                Disruption Detection · Impact Analysis · Decision Engine · SAP Draft Generator
            </div>
            <div>
                <span class="ab-tag">project44 ↔ SAP</span>
                <span class="ab-tag">Decision Intelligence</span>
                <span class="ab-tag">Process Mining</span>
                <span class="ab-tag">SAP S/4HANA</span>
                <span class="ab-tag">Synthetic Data</span>
            </div>
        </div>
        <div style='text-align:right;'>
            <div style='font-family: Space Mono; font-size:10px; color:#6B7280;'>DATA QUALITY</div>
            <div style='font-size:28px; font-weight:700; color:{dq_color};
                        font-family: Space Mono;'>{dq["overall_score"]:.0f}%</div>
            <div style='font-size:9px; color:#6B7280;'>{dq["action_message"]}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

k1,k2,k3,k4,k5,k6 = st.columns(6)
with k1: st.metric("Shipments", f"{stats['total_shipments']:,}")
with k2: st.metric("Delayed", f"{stats['delayed_shipments']:,}",
                   f"{stats['delay_rate_pct']}% delay rate", delta_color="inverse")
with k3: st.metric("Orders at Risk", f"{stats['orders_at_risk']:,}",
                   f"{stats['tier_a_at_risk']} Tier-A", delta_color="inverse")
with k4: st.metric("Penalty Exposure", f"${stats['total_penalty_usd']/1e3:.0f}K",
                   delta_color="off")
with k5: st.metric("Critical Incidents", f"{stats['critical_shipments']:,}",
                   delta_color="off")
with k6: st.metric("Time Saved/Incident",
                   f"{stats['manual_process_mins'] - 3}m",
                   f"vs {stats['manual_process_mins']}m manual (illustrative)", delta_color="normal")

st.markdown("<br>", unsafe_allow_html=True)

