"""
ActionBridge
─────────────────────────────────────────────────────────────────
From Visibility Alert to SAP Action in One Step.

Inspired by Jett McCandless, CEO of project44:
"AI that doesn't lead to action is just another dashboard."

Built by Rutwik Satish | MS Engineering Management, Northeastern
Celonis Process Mining Certified | SAP S/4HANA | McKinsey Forward
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
            VISIBILITY → DECISION → SAP ACTION
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
        <i style='color:#F59E0B;'>"AI that doesn't lead to<br>
        action is just another<br>dashboard."</i>
        <br><br>
        <b style='color:#F9FAFB;'>Rutwik Satish</b><br>
        MS Eng. Mgmt · Northeastern<br>
        <span style='color:#F59E0B;'>Celonis Certified · SAP S/4HANA</span>
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

# Handle upload override
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
                Disruption Detection · Impact Analysis · Decision Engine · SAP Action Generator
            </div>
            <div>
                <span class="ab-tag">project44 ↔ SAP</span>
                <span class="ab-tag">Decision Intelligence</span>
                <span class="ab-tag">Celonis Process Mining</span>
                <span class="ab-tag">SAP S/4HANA</span>
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

# ── KPI strip ─────────────────────────────────────────────────────────────────
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
                   f"vs {stats['manual_process_mins']}m manual", delta_color="normal")

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8 = st.tabs([
    "🚨  Disruption Feed",
    "🔍  Impact Analyser",
    "🧠  Decision Engine",
    "⚙️  SAP Actions",
    "✅  Proof of Value",
    "🗂️  Data Quality",
    "📋  Data Preview",
    "ℹ️  About & Problem",
])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Disruption Feed
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<p class="ab-label">Live Disruption Feed</p>', unsafe_allow_html=True)

    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.plotly_chart(fig_disruption_timeline(shipments), use_container_width=True)
    with c2:
        st.plotly_chart(fig_severity_donut(shipments), use_container_width=True)

    st.markdown('<p class="ab-label">Active Exceptions — Requires Decision</p>', unsafe_allow_html=True)
    delayed_view = (
        shipments[shipments["is_delayed"]]
        [["shipment_id","carrier","disruption_type","delay_hours","severity",
          "expected_delivery","origin_warehouse"]]
        .sort_values("delay_hours", ascending=False)
        .head(15)
        .reset_index(drop=True)
    )
    delayed_view.columns = ["Shipment","Carrier","Disruption","Delay (hrs)","Severity",
                             "Expected Delivery","Origin WH"]
    st.dataframe(delayed_view, use_container_width=True, height=300)

    # Context card
    sev_color = {"Critical":"#EF4444","High":"#F59E0B","Medium":"#3B82F6","Low":"#10B981"}
    sev = sel_ship_row["severity"]
    sc  = sev_color.get(sev, "#6B7280")
    st.markdown(f"""
    <div class="ab-card-alert" style="border-left-color:{sc};">
        <div class="ab-label">Selected Incident: {sel_shipment}</div>
        <div style='display:flex; gap:24px; flex-wrap:wrap; font-size:12px;'>
            <div><span style='color:#6B7280;'>Carrier: </span>
                 <b>{sel_ship_row["carrier"]}</b></div>
            <div><span style='color:#6B7280;'>Disruption: </span>
                 <b>{sel_ship_row["disruption_type"]}</b></div>
            <div><span style='color:#6B7280;'>Delay: </span>
                 <b style='color:{sc};'>{sel_ship_row["delay_hours"]:.0f}h</b></div>
            <div><span style='color:#6B7280;'>Orders linked: </span>
                 <b>{len(sel_orders)}</b></div>
            <div><span style='color:#6B7280;'>Severity: </span>
                 <b style='color:{sc};'>{sev}</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Impact Analyser
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown(f'<p class="ab-label">Impact Analysis — {sel_shipment}</p>', unsafe_allow_html=True)

    grade_color = {"Critical":"#EF4444","High":"#F59E0B","Medium":"#3B82F6","Low":"#10B981"}
    gc = grade_color.get(impact["grade"],"#6B7280")

    i1,i2,i3,i4 = st.columns(4)
    with i1: st.metric("Impact Score", f"{impact['score']}/100",
                        impact["grade"], delta_color="off")
    with i2: st.metric("Orders Affected", str(impact.get("orders_count",0)))
    with i3: st.metric("Value at Risk", f"${impact.get('total_value_at_risk',0):,.0f}")
    with i4: st.metric("Penalty Exposure", f"${impact.get('total_penalty_at_risk',0):,.0f}",
                        delta_color="off")

    c1,c2 = st.columns([1.3,1])
    with c1:
        st.plotly_chart(fig_order_impact_scatter(orders), use_container_width=True)
    with c2:
        st.plotly_chart(fig_impact_radar(impact), use_container_width=True)

    st.plotly_chart(fig_penalty_by_customer(orders), use_container_width=True)

    st.markdown('<p class="ab-label">Affected Orders Detail</p>', unsafe_allow_html=True)
    if not sel_orders.empty:
        show_cols = ["order_id","customer","customer_tier","sku_desc","quantity",
                     "order_value","sla_breach_hours","estimated_penalty","order_status"]
        disp = sel_orders[show_cols].copy()
        disp["order_value"]       = disp["order_value"].apply(lambda x: f"${x:,.0f}")
        disp["estimated_penalty"] = disp["estimated_penalty"].apply(lambda x: f"${x:,.0f}")
        disp.columns = ["Order","Customer","Tier","SKU","Qty","Value",
                         "SLA Breach (hrs)","Penalty","Status"]
        st.dataframe(disp, hide_index=True, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Decision Engine
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown('<p class="ab-label">Decision Engine Output</p>', unsafe_allow_html=True)

    # Validation badge
    vs = decision_valid["validation_status"]
    vs_color = {"PASS":"#10B981","WARN":"#F59E0B","FAIL":"#EF4444"}[vs]
    vs_icon  = {"PASS":"✅","WARN":"⚠️","FAIL":"❌"}[vs]
    st.markdown(f"""
    <div style='background:{vs_color}18; border:1px solid {vs_color}44;
                border-radius:8px; padding:10px 16px; margin-bottom:16px;
                display:flex; align-items:center; gap:12px;'>
        <span style='font-size:16px;'>{vs_icon}</span>
        <div>
            <span style='color:{vs_color}; font-family:Space Mono; font-size:11px;
                          font-weight:700;'>DECISION VALIDATION: {vs}</span>
            <br>
            <span style='font-size:11px; color:#9CA3AF;'>
                Confidence: {decision_valid["confidence"]}% |
                Feasible options: {decision_valid["feasible_options"]} |
                {decision_valid["issues"][0]}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Best decision highlight
    bd = best_decision
    st.markdown(f"""
    <div class="ab-card-success">
        <div class="ab-label">⚡ Recommended Action</div>
        <div style='font-size:18px; font-weight:600; color:#F9FAFB; margin-bottom:8px;'>
            {bd.get("label","Manual Review Required")}
        </div>
        <div style='font-size:12px; color:#9CA3AF; line-height:1.7;'>
            {bd.get("rationale","")}
        </div>
        <div style='display:flex; gap:20px; margin-top:10px; font-size:12px;'>
            <div><span style='color:#6B7280;'>Net Benefit: </span>
                 <b style='color:#10B981;'>${bd.get("net_benefit",0):,.0f}</b></div>
            <div><span style='color:#6B7280;'>Hours Saved: </span>
                 <b style='color:#10B981;'>{bd.get("hours_saved",0):.0f}h</b></div>
            <div><span style='color:#6B7280;'>Success Rate: </span>
                 <b style='color:#10B981;'>{bd.get("success_rate",0)*100:.0f}%</b></div>
            <div><span style='color:#6B7280;'>Value Score: </span>
                 <b style='color:#F59E0B;'>{bd.get("value_score",0):.0f}/100</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.plotly_chart(fig_response_comparison(responses), use_container_width=True)

    # All options table
    st.markdown('<p class="ab-label">All Response Options Ranked</p>', unsafe_allow_html=True)
    if not responses.empty:
        disp_r = responses[["rank","response_label","added_cost_usd","hours_saved",
                              "penalty_avoided","net_benefit_usd","success_rate","feasible"]].copy()
        disp_r["added_cost_usd"]  = disp_r["added_cost_usd"].apply(lambda x: f"${x:,.0f}")
        disp_r["penalty_avoided"] = disp_r["penalty_avoided"].apply(lambda x: f"${x:,.0f}")
        disp_r["net_benefit_usd"] = disp_r["net_benefit_usd"].apply(lambda x: f"${x:,.0f}")
        disp_r["success_rate"]    = disp_r["success_rate"].apply(lambda x: f"{x*100:.0f}%")
        disp_r["feasible"]        = disp_r["feasible"].map({True:"✅ Feasible", False:"❌ Not Feasible"})
        disp_r.columns = ["#","Response","Added Cost","Hrs Saved","Penalty Avoided",
                           "Net Benefit","Success Rate","Feasibility"]
        st.dataframe(disp_r, hide_index=True, use_container_width=True)

    # AI Analyst
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p class="ab-label">🤖 AI Analyst Brief</p>', unsafe_allow_html=True)
    generate_ai = st.button("Generate AI Decision Brief", type="primary",
                             use_container_width=False)

    if generate_ai and groq_key and GROQ_AVAILABLE:
        prompt = f"""You are a senior logistics operations analyst specialising in SAP and carrier management.

A shipment disruption has been detected with these details:
- Shipment: {sel_shipment}
- Carrier: {sel_ship_row['carrier']}
- Disruption: {sel_ship_row['disruption_type']}
- Delay: {sel_ship_row['delay_hours']:.0f} hours
- Orders affected: {len(sel_orders)} orders across {sel_orders['customer'].nunique()} customers
- Penalty exposure: ${impact.get('total_penalty_at_risk',0):,.0f}
- Impact score: {impact['score']}/100 ({impact['grade']})

Decision engine recommends: {bd.get('label','Manual Review')}
Net benefit: ${bd.get('net_benefit',0):,.0f} | Hours saved: {bd.get('hours_saved',0):.0f}h
Validation confidence: {decision_valid['confidence']}%

Write a 3-paragraph operations analyst brief:
1. What exactly happened and why it matters (be specific with numbers)
2. Why the recommended action is the right call and what to watch for during execution
3. What process change would prevent this type of disruption in future

Be concise, direct, and operational. No bullet points. Prose only."""

        try:
            client_g = Groq(api_key=groq_key)
            st.markdown("""
            <div style='background:#0d1520; border:1px solid #F59E0B33;
                        border-left:3px solid #F59E0B; border-radius:0 10px 10px 0;
                        padding:18px 22px; margin-top:8px;'>
            <div class="ab-label">AI ANALYST BRIEF · GROQ</div>
            """, unsafe_allow_html=True)
            def stream():
                s = client_g.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"user","content":prompt}],
                    stream=True, max_tokens=600, temperature=0.3,
                )
                for chunk in s:
                    c = chunk.choices[0].delta.content
                    if c: yield c
            st.write_stream(stream())
            st.markdown("</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Groq error: {e}")
    elif generate_ai and not groq_key:
        st.warning("Add GROQ_API_KEY to Streamlit secrets to enable AI brief.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — SAP Actions
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.markdown(f'<p class="ab-label">SAP Transaction Drafts — {sel_shipment} ({len(transactions)} actions)</p>',
                unsafe_allow_html=True)

    ts = time_savings
    t1,t2,t3,t4 = st.columns(4)
    with t1: st.metric("Manual Process Time", f"{ts['manual_minutes']}m",
                        f"{len(MANUAL_PROCESS_STEPS)} steps", delta_color="off")
    with t2: st.metric("ActionBridge Time", f"{ts['auto_minutes']:.0f}m",
                        f"{ts['transactions']} transactions auto-generated", delta_color="off")
    with t3: st.metric("Time Saved", f"{ts['saved_minutes']:.0f}m",
                        f"{ts['reduction_pct']:.0f}% reduction", delta_color="normal")
    with t4: st.metric("Transactions Ready", str(ts["transactions"]),
                        "Ready to push to SAP", delta_color="off")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p class="ab-label">Generated SAP Transactions</p>', unsafe_allow_html=True)

    priority_color = {"HIGH":"#EF4444", "URGENT":"#EF4444", "MEDIUM":"#F59E0B", "LOW":"#6B7280"}

    for txn in transactions:
        pc    = priority_color.get(txn.get("priority","LOW"), "#6B7280")
        t_code = txn["t_code"]
        cat   = txn.get("category","")
        cat_color = {"Sales Order":"#3B82F6","Procurement":"#F59E0B",
                     "Warehouse Management":"#8B5CF6","Transportation":"#10B981",
                     "Communication":"#6B7280"}.get(cat,"#6B7280")

        fields_html = "".join([
            f"<tr><td style='color:#6B7280;padding:2px 12px 2px 0;font-size:11px;'>{k}</td>"
            f"<td style='color:#F9FAFB;font-size:11px;'>{v}</td></tr>"
            for k,v in txn["fields"].items()
        ])

        st.markdown(f"""
        <div class="sap-block">
            <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;'>
                <div>
                    <span style='background:{cat_color}22; color:{cat_color}; border:1px solid {cat_color}44;
                                 border-radius:4px; padding:2px 8px; font-size:10px;'>{t_code}</span>
                    <span style='color:#F9FAFB; font-size:13px; font-weight:600; margin-left:10px;'>
                        {txn["title"]}</span>
                </div>
                <div style='text-align:right;'>
                    <span style='background:{pc}22; color:{pc}; border:1px solid {pc}44;
                                 border-radius:4px; padding:2px 8px; font-size:10px;'>
                        {txn.get("priority","MEDIUM")}</span>
                </div>
            </div>
            <table style='width:100%; border-collapse:collapse;'>
                {fields_html}
            </table>
            <div style='display:flex; gap:20px; margin-top:10px; font-size:10px;'>
                <span style='color:#10B981;'>⚡ Auto: {txn.get("estimated_time","< 30s")}</span>
                <span style='color:#EF4444;'>⏱ Manual: {txn.get("vs_manual","20+ min")}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Download
    txn_rows = []
    for txn in transactions:
        for k,v in txn["fields"].items():
            txn_rows.append({"t_code":txn["t_code"],"title":txn["title"],
                             "field":k,"value":v})
    txn_df = pd.DataFrame(txn_rows)
    st.download_button("⬇️  Download SAP Transaction Drafts (CSV)",
                       txn_df.to_csv(index=False).encode(),
                       f"actionbridge_{sel_shipment}_transactions.csv",
                       "text/csv", use_container_width=False)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — Proof of Value
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    st.markdown('<p class="ab-label">Proof: The Problem Is Being Solved</p>', unsafe_allow_html=True)

    # The claim
    st.markdown("""
    <div class="ab-card-amber">
        <div class="ab-label">The Problem (Jett McCandless, CEO project44)</div>
        <div style='font-size:14px; color:#F9FAFB; line-height:1.7;'>
            <i>"AI that doesn't lead to action is just another dashboard."</i>
            <br><br>
            Before ActionBridge: a project44 alert fires → analyst spends
            <b style='color:#EF4444;'>230 minutes across 10 manual steps</b>
            to get from alert to SAP action. 4–5 people involved. Decisions made on
            incomplete data. Customers waiting.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Process comparison
    st.plotly_chart(fig_process_comparison(MANUAL_PROCESS_STEPS, ts["auto_minutes"]),
                    use_container_width=True)

    # Manual steps breakdown
    st.markdown('<p class="ab-label">Manual Process Steps (Before ActionBridge)</p>',
                unsafe_allow_html=True)
    step_rows = [{"Step": s[0], "What Happens": s[1], "Time (min)": s[2],
                  "Automated?": "❌ Manual"} for s in MANUAL_PROCESS_STEPS]
    step_rows.append({"Step":"TOTAL","What Happens":"","Time (min)":sum(s[2] for s in MANUAL_PROCESS_STEPS),
                      "Automated?":"✅ ActionBridge: 3 min"})
    st.dataframe(pd.DataFrame(step_rows), hide_index=True, use_container_width=True)

    # Annualised ROI
    avg_penalty = (orders[orders["is_at_risk"]]["estimated_penalty"].mean()
                   if not orders[orders["is_at_risk"]].empty else 2000)
    st.plotly_chart(fig_roi_annualised(stats, avg_penalty), use_container_width=True)

    # Summary proof card
    annual_manual_cost = (stats["incidents_per_month"] * 12 *
                          (stats["manual_process_mins"]/60) * 85)
    annual_auto_cost   = (stats["incidents_per_month"] * 12 *
                          (stats["actionbridge_mins"]/60) * 85)
    annual_penalty_saved = stats["total_penalty_usd"] * 0.65 * 2

    st.markdown(f"""
    <div class="ab-card-success">
        <div class="ab-label">Annual Business Case Summary</div>
        <div style='display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:16px;'>
            <div>
                <div style='font-size:10px; color:#6B7280;'>Manual Process Cost/yr</div>
                <div style='font-size:18px; color:#EF4444; font-family:Space Mono;'>
                    ${annual_manual_cost:,.0f}</div>
            </div>
            <div>
                <div style='font-size:10px; color:#6B7280;'>ActionBridge Cost/yr</div>
                <div style='font-size:18px; color:#10B981; font-family:Space Mono;'>
                    ${annual_auto_cost:,.0f}</div>
            </div>
            <div>
                <div style='font-size:10px; color:#6B7280;'>Penalty Avoided/yr</div>
                <div style='font-size:18px; color:#F59E0B; font-family:Space Mono;'>
                    ${annual_penalty_saved:,.0f}</div>
            </div>
            <div>
                <div style='font-size:10px; color:#6B7280;'>Net Annual Saving</div>
                <div style='font-size:18px; color:#10B981; font-family:Space Mono;'>
                    ${annual_manual_cost - annual_auto_cost + annual_penalty_saved:,.0f}</div>
            </div>
        </div>
        <div style='font-size:11px; color:#6B7280; margin-top:12px;'>
            Based on {stats["incidents_per_month"]} incidents/month · $85/hr blended rate ·
            65% penalty recovery rate
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 — Data Quality
# ─────────────────────────────────────────────────────────────────────────────
with tab6:
    st.markdown('<p class="ab-label">Data Quality — Decision Readiness Validation</p>',
                unsafe_allow_html=True)

    grade_color = {"A":"#10B981","B":"#F59E0B","C":"#EF4444","D":"#EF4444"}
    gc2 = grade_color.get(dq["grade"],"#6B7280")

    q1,q2,q3,q4 = st.columns(4)
    with q1: st.metric("Overall Score", f"{dq['overall_score']}%")
    with q2: st.metric("Grade", dq["grade"])
    with q3: st.metric("Total Records", f"{dq['total_records']:,}")
    with q4: st.metric("Datasets Checked", str(len(dq["datasets"])))

    st.markdown(f"""
    <div class="ab-card{'_success' if dq['overall_score']>=90 else '_amber' if dq['overall_score']>=75 else '_alert'}">
        <div class="ab-label">Decision Readiness</div>
        <div style='font-size:14px; color:#F9FAFB;'>{dq["action_message"]}</div>
        <div style='font-size:11px; color:#6B7280; margin-top:6px;'>
            Grade {dq["grade"]} — Overall data quality score: {dq["overall_score"]}%
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(fig_data_quality_bar(dq), use_container_width=True)
    with c2:
        st.plotly_chart(fig_carrier_reliability(carriers), use_container_width=True)

    # Per-dataset checks
    st.markdown('<p class="ab-label">Validation Checks by Dataset</p>', unsafe_allow_html=True)
    for ds_name, ds_data in dq["datasets"].items():
        grade = ds_data["grade"]
        gc3   = grade_color.get(grade, "#6B7280")
        with st.expander(f"{ds_name} — Score: {ds_data['score']}% (Grade {grade}) "
                         f"· {ds_data['row_count']:,} records", expanded=False):
            check_rows = [{"Check": c["check"], "Status": c["status"],
                           "Completeness": f"{c['completeness']}%",
                           "Result": "✅ PASS" if c["passed"] else "❌ FAIL"}
                          for c in ds_data["checks"]]
            st.dataframe(pd.DataFrame(check_rows), hide_index=True, use_container_width=True)

    # Download quality report
    all_checks = []
    for ds, ds_d in dq["datasets"].items():
        for c in ds_d["checks"]:
            all_checks.append({"dataset":ds, "check":c["check"],
                               "passed":c["passed"],"completeness":c["completeness"]})
    st.download_button("⬇️  Download Quality Report (CSV)",
                       pd.DataFrame(all_checks).to_csv(index=False).encode(),
                       "actionbridge_data_quality.csv","text/csv")

    # Attribution
    st.markdown("""<br>""", unsafe_allow_html=True)
    st.markdown("""
    <div style='background:#111827; border:1px solid #1F2937; border-radius:10px;
                padding:18px 22px; text-align:center;'>
        <div style='font-size:11px; color:#6B7280; line-height:1.8;'>
            Built to prove the thesis of
            <b style='color:#F59E0B;'>Jett McCandless, CEO project44</b>:
            "AI that doesn't lead to action is just another dashboard."
            <br>
            ActionBridge closes the gap between visibility alert and SAP action —
            turning 230 minutes of manual work into 3 minutes of automated decision-making.
            <br><br>
            <b style='color:#F9FAFB;'>Rutwik Satish</b> ·
            MS Engineering Management, Northeastern University ·
            <span style='color:#F59E0B;'>Celonis Process Mining Certified</span> ·
            SAP S/4HANA · McKinsey Forward · May 2026
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 7 — Data Preview
# ─────────────────────────────────────────────────────────────────────────────
with tab7:
    st.markdown('<p class="ab-label">Data Preview — All Datasets</p>', unsafe_allow_html=True)

    st.markdown("""
    <div class="ab-card-amber">
        <div class="ab-label">What You're Looking At</div>
        <div style='font-size:12px; color:#F9FAFB; line-height:1.8;'>
            ActionBridge works with <b>4 interconnected datasets</b> — Shipments (project44 events),
            Orders (SAP sales orders), Inventory (SAP MM stock levels), and Carriers (reliability profiles).
            Together these datasets power every decision the engine makes.
            Download any dataset to explore it in Excel or import it into Celonis.
        </div>
    </div>
    """, unsafe_allow_html=True)

    dataset_choice = st.selectbox(
        "Select dataset to preview",
        ["Shipments (project44 events)", "Orders (SAP SO)", "Inventory (SAP MM)", "Carriers"],
    )

    if "Shipments" in dataset_choice:
        df_show   = shipments.copy()
        col_info  = {
            "shipment_id":       "Unique shipment identifier (maps to project44 tracking ID)",
            "carrier":           "Carrier name — links to Carriers dataset for reliability profile",
            "origin_warehouse":  "Source warehouse (SAP plant / storage location)",
            "destination_state": "Delivery state",
            "ship_date":         "Date goods left origin warehouse",
            "expected_delivery": "Original ETA from carrier",
            "actual_delivery":   "Actual / projected delivery including delay",
            "delay_hours":       "Hours of delay detected (0 = on-time)",
            "disruption_type":   "Root cause category of delay (from project44 exception event)",
            "is_delayed":        "Boolean flag — True if delay_hours > 0",
            "severity":          "Severity grade: Critical ≥48h, High ≥24h, Medium ≥12h",
            "freight_cost_usd":  "Base freight cost before any expedite premium",
        }
        ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1.2, 1.2])
        with ctrl1:
            sev_filter = st.multiselect("Filter severity",
                options=sorted(df_show["severity"].unique()),
                default=sorted(df_show["severity"].unique()))
        with ctrl2:
            carrier_filter = st.multiselect("Filter carrier",
                options=sorted(df_show["carrier"].unique()),
                default=sorted(df_show["carrier"].unique()))
        with ctrl3:
            rows_n = st.selectbox("Rows", [25, 50, 100, 200, "All"], index=1)
        df_show = df_show[
            df_show["severity"].isin(sev_filter) &
            df_show["carrier"].isin(carrier_filter)
        ]

    elif "Orders" in dataset_choice:
        df_show  = orders.copy()
        col_info = {
            "order_id":             "SAP Sales Order number (SO-XXXXX)",
            "shipment_id":          "FK → Shipments. Links order to its carrying shipment",
            "customer":             "Customer name",
            "customer_tier":        "A = strategic / penalty-heavy, B = standard, C = basic SLA",
            "sla_days":             "Contractual delivery SLA in days",
            "penalty_per_day":      "Daily penalty rate ($) for SLA breach",
            "sku":                  "SAP material number",
            "sku_desc":             "Material description",
            "quantity":             "Order quantity in units",
            "order_value":          "Total order value ($)",
            "required_delivery":    "Customer's required delivery date",
            "is_at_risk":           "True if linked shipment is delayed",
            "sla_breach_hours":     "Hours by which SLA is breached (0 = within SLA)",
            "estimated_penalty":    "Estimated financial penalty for this order",
        }
        ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 1])
        with ctrl1:
            tier_filter = st.multiselect("Customer Tier",
                options=["A","B","C"], default=["A","B","C"])
        with ctrl2:
            status_filter = st.multiselect("Status",
                options=sorted(df_show["order_status"].unique()),
                default=sorted(df_show["order_status"].unique()))
        with ctrl3:
            rows_n = st.selectbox("Rows", [25, 50, 100, 200, "All"], index=1)
        df_show = df_show[
            df_show["customer_tier"].isin(tier_filter) &
            df_show["order_status"].isin(status_filter)
        ]

    elif "Inventory" in dataset_choice:
        df_show  = inventory.copy()
        col_info = {
            "sku":           "SAP material number",
            "description":   "Material description",
            "category":      "Product category (Mechanical, Electronics, etc.)",
            "warehouse":     "SAP warehouse / storage location",
            "current_stock": "Current on-hand quantity",
            "safety_stock":  "SAP safety stock level (replenishment trigger)",
            "reorder_point": "Reorder point (MRP trigger)",
            "unit_cost":     "Standard cost per unit ($)",
            "lead_time_days":"Replenishment lead time from supplier (days)",
            "status":        "OK = above safety stock | Low = between safety/reorder | Critical = below safety",
        }
        ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 1])
        with ctrl1:
            wh_filter = st.multiselect("Warehouse",
                options=sorted(df_show["warehouse"].unique()),
                default=sorted(df_show["warehouse"].unique()))
        with ctrl2:
            status_filter2 = st.multiselect("Stock Status",
                options=["OK","Low","Critical"], default=["OK","Low","Critical"])
        with ctrl3:
            rows_n = st.selectbox("Rows", [25, 50, 100, 200, "All"], index=1)
        df_show = df_show[
            df_show["warehouse"].isin(wh_filter) &
            df_show["status"].isin(status_filter2)
        ]

    else:  # Carriers
        df_show  = carriers.copy()
        col_info = {
            "carrier_name":       "Carrier name",
            "reliability_score":  "Historical on-time delivery rate (0–1). Used in decision scoring.",
            "avg_delay_hrs":      "Average delay when late (hours). Used to estimate recovery time.",
            "capacity":           "Capacity tier (high/medium/low). Used for alt-carrier feasibility.",
            "cost_index":         "Relative cost multiplier vs base rate (1.0 = market rate)",
            "network_coverage":   "Geographic network coverage score (0–1)",
            "on_time_2025":       "2025 YTD on-time performance (%)",
        }
        rows_n = st.selectbox("Rows", [9, "All"], index=1)
        df_show = df_show.copy()

    # Show table
    rows_n_int = len(df_show) if rows_n == "All" else int(rows_n)
    st.markdown(
        f'<p style="font-size:11px; color:#6B7280; margin-bottom:6px;">' +
        f'Showing {min(rows_n_int, len(df_show)):,} of {len(df_show):,} rows</p>',
        unsafe_allow_html=True,
    )
    st.dataframe(df_show.head(rows_n_int).reset_index(drop=True),
                 use_container_width=True, height=360)

    # Column glossary
    st.markdown('<p class="ab-label" style="margin-top:16px;">Column Glossary</p>',
                unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    for i, (col, desc) in enumerate(col_info.items()):
        with (g1 if i % 2 == 0 else g2):
            st.markdown(f"""
            <div style='background:#0d1520; border:1px solid #1F2937; border-radius:7px;
                        padding:9px 13px; margin-bottom:7px;'>
                <div style='font-family:Space Mono; font-size:10px;
                            color:#F59E0B; margin-bottom:2px;'>{col}</div>
                <div style='font-size:11px; color:#9CA3AF;'>{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    # Downloads
    st.markdown('<p class="ab-label" style="margin-top:16px;">Download</p>',
                unsafe_allow_html=True)
    d1, d2, d3, d4, _ = st.columns([1,1,1,1,2])
    datasets_map = {
        "shipments": shipments, "orders": orders,
        "inventory": inventory, "carriers": carriers,
    }
    for col_btn, (name, df_dl) in zip([d1,d2,d3,d4], datasets_map.items()):
        with col_btn:
            st.download_button(
                f"⬇️ {name.title()}",
                df_dl.to_csv(index=False).encode(),
                f"actionbridge_{name}.csv", "text/csv",
                use_container_width=True,
            )

    st.markdown("""
    <div style='font-size:10px; color:#6B7280; margin-top:8px; line-height:1.6;'>
        💡 Download Shipments as CSV and upload to
        <b style='color:#F9FAFB;'>Celonis Academic</b> — the columns map directly
        to Celonis event log format (Case ID = shipment_id, Activity = disruption_type,
        Timestamp = ship_date / expected_delivery).
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 8 — About & Problem Statement
# ─────────────────────────────────────────────────────────────────────────────
with tab8:
    # ── The Problem ───────────────────────────────────────────────────────────
    st.markdown('<p class="ab-label">The Problem This App Solves</p>', unsafe_allow_html=True)

    st.markdown("""
    <div class="ab-card-alert">
        <div class="ab-label">🔴 Executive Statement — The Exact Problem</div>
        <div style='font-size:20px; font-style:italic; color:#F9FAFB;
                    line-height:1.5; margin-bottom:10px;'>
            "AI that doesn't lead to action is just another dashboard."
        </div>
        <div style='font-size:12px; color:#9CA3AF;'>
            — <b style='color:#F9FAFB;'>Jett McCandless</b>, Founder & CEO, project44<br>
            Source: FreightWaves / project44 Decision Intelligence launch, August 2025
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="ab-card">
        <div class="ab-label">The Situation Before ActionBridge</div>
        <div style='font-size:13px; color:#F9FAFB; line-height:1.8;'>
            project44 connects 250,000+ carriers and can see every shipment delay in real time.
            When a disruption alert fires, a logistics analyst can <b>see</b> the problem instantly.
            <br><br>
            But turning that visibility into <b>action</b> still requires:
        </div>
        <div style='display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:12px;'>
    """, unsafe_allow_html=True)

    from utils.data_generator import MANUAL_PROCESS_STEPS
    for i, (step, desc, mins) in enumerate(MANUAL_PROCESS_STEPS):
        color = "#EF4444" if mins > 30 else "#F59E0B" if mins > 15 else "#6B7280"
        st.markdown(f"""
        <div style='background:#0d1520; border:1px solid #1F2937; border-radius:7px;
                    padding:9px 13px; margin-bottom:6px;'>
            <div style='display:flex; justify-content:space-between;'>
                <span style='font-size:11px; color:#F9FAFB; font-weight:500;'>
                    {i+1}. {step}</span>
                <span style='font-family:Space Mono; font-size:11px; color:{color};
                              font-weight:700;'>{mins}m</span>
            </div>
            <div style='font-size:10px; color:#6B7280; margin-top:2px;'>{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    total_manual = sum(s[2] for s in MANUAL_PROCESS_STEPS)
    st.markdown(f"""
    </div>
    <div style='background:#EF444415; border:1px solid #EF444430; border-radius:7px;
                padding:10px 14px; margin-top:10px; font-family:Space Mono; font-size:12px;'>
        🔴 Total: <b style='color:#EF4444;'>{total_manual} minutes</b> per incident ·
        4–5 people involved · Decisions made on incomplete, unvalidated data
    </div>
    </div>
    """, unsafe_allow_html=True)

    # ── How It Works ──────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p class="ab-label">How ActionBridge Solves It</p>', unsafe_allow_html=True)

    steps = [
        ("1", "🚨", "Disruption Detected",
         "project44 fires an exception alert — delayed shipment identified with carrier, origin, delay hours, and disruption type.",
         "#EF4444"),
        ("2", "📊", "Impact Assessed Automatically",
         "ActionBridge queries the linked SAP sales orders, calculates penalty exposure per customer, scores impact by tier (A/B/C), delay severity, and financial risk.",
         "#F59E0B"),
        ("3", "🧠", "Response Options Ranked",
         "The decision engine scores 5 response options (expedite, alt carrier, alt warehouse, reroute, notify) by net benefit = (penalty avoided × success rate) / added cost. Feasibility is validated against live inventory and carrier data.",
         "#3B82F6"),
        ("4", "✅", "Decision Validated",
         "Before outputting a recommendation, ActionBridge runs a validation layer: checks data completeness, confirms feasibility, and compares engine output against a rule-based baseline. Confidence score calculated.",
         "#8B5CF6"),
        ("5", "⚙️", "SAP Transactions Generated",
         "Based on the chosen response, ActionBridge auto-generates draft SAP transactions: VA02 (delivery date change), ME22N (expedite PO), LT01 (transfer order), VT02N (carrier change), and customer notification emails.",
         "#10B981"),
        ("6", "💰", "ROI Quantified",
         "Every decision is tied to a dollar outcome: penalty avoided, freight premium cost, net benefit. 12-month projection calculated from historical incident frequency.",
         "#10B981"),
    ]

    for s_num, icon, title, desc, color in steps:
        st.markdown(f"""
        <div style='background:#111827; border:1px solid #1F2937;
                    border-left:3px solid {color};
                    border-radius:0 10px 10px 0; padding:14px 18px; margin-bottom:10px;
                    display:flex; gap:16px;'>
            <div style='font-size:24px; min-width:32px;'>{icon}</div>
            <div>
                <div style='font-size:13px; font-weight:600; color:#F9FAFB; margin-bottom:4px;'>
                    Step {s_num}: {title}</div>
                <div style='font-size:12px; color:#9CA3AF; line-height:1.6;'>{desc}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── What It Proves ────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p class="ab-label">What This Project Demonstrates</p>', unsafe_allow_html=True)

    skills = [
        ("SAP S/4HANA Domain Knowledge",
         "Transaction codes, movement types, and data structures are real — VA02, ME22N, LT01, VT02N, reason codes ZW01/ZP01 etc. The decision engine knows which SAP action maps to which disruption type.",
         "#F59E0B"),
        ("Celonis Process Mining Methodology",
         "The shipment event log is structured as a Celonis-compatible XES format (Case ID, Activity, Timestamp). The 'manual process steps' analysis mirrors a Celonis process discovery output.",
         "#F59E0B"),
        ("Business Analysis & Requirements Design",
         "The decision engine was designed from a BA perspective — starting with the business problem (penalty exposure, SLA breach), defining KPIs (net benefit, hours saved), and validating against a baseline before recommending.",
         "#3B82F6"),
        ("Data Validation Framework",
         "4-dataset quality checks, FK integrity validation, confidence scoring, and decision validation against rule-based baseline — the kind of data governance work that separates consultants from coders.",
         "#3B82F6"),
        ("McKinsey Problem-Solving Structure",
         "Situation (alert detected) → Complication (230-min manual process) → Resolution (3-min automated decision with quantified ROI). Every screen answers a business question, not a technical one.",
         "#8B5CF6"),
        ("AI Integration (Groq / Llama 3.3 70B)",
         "The AI Analyst Brief uses the structured decision output as context — not raw data. The prompt is designed like a consulting brief, not a chatbot query.",
         "#8B5CF6"),
    ]

    s1, s2 = st.columns(2)
    for i, (title, desc, color) in enumerate(skills):
        with (s1 if i % 2 == 0 else s2):
            st.markdown(f"""
            <div style='background:#111827; border:1px solid #1F2937; border-radius:9px;
                        padding:14px 16px; margin-bottom:10px;'>
                <div style='font-size:11px; font-weight:600; color:{color};
                            margin-bottom:6px;'>{title}</div>
                <div style='font-size:11px; color:#9CA3AF; line-height:1.6;'>{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Target Companies & CTA ────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p class="ab-label">Companies to Approach With This</p>', unsafe_allow_html=True)

    companies = [
        ("project44", "Chicago, IL", "Founder/CEO: Jett McCandless",
         "Built this project directly from his public quote. Hiring Implementation Consultants and Supply Chain Solutions Analysts.",
         "#F59E0B"),
        ("GEP Worldwide", "Clark, NJ", "VP: Wayne Clark",
         "SAP-integrated procurement consulting. Actively hiring new grad analysts. Strong H-1B sponsor.",
         "#3B82F6"),
        ("Blue Yonder", "Dallas, TX", "CEO: Duncan Angove",
         "Supply chain AI platform — SADA Loop mirrors ActionBridge's See/Analyze/Decide/Act structure.",
         "#8B5CF6"),
        ("Celonis", "New York, NY", "Co-CEO: Alex Rinke",
         "Process mining platform this app's methodology is based on. Hiring Customer Success and Implementation roles.",
         "#10B981"),
    ]

    co1, co2 = st.columns(2)
    for i, (company, location, contact, desc, color) in enumerate(companies):
        with (co1 if i % 2 == 0 else co2):
            st.markdown(f"""
            <div style='background:#111827; border:1px solid {color}33;
                        border-top:2px solid {color}; border-radius:9px;
                        padding:14px 16px; margin-bottom:10px;'>
                <div style='font-size:14px; font-weight:700; color:#F9FAFB;'>{company}</div>
                <div style='font-size:10px; color:{color}; font-family:Space Mono;
                            margin:3px 0;'>{location} · {contact}</div>
                <div style='font-size:11px; color:#9CA3AF; line-height:1.5; margin-top:6px;'>{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    # Final attribution
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style='background:#111827; border:1px solid #1F2937; border-radius:10px;
                padding:20px 24px; text-align:center;'>
        <div style='font-size:11px; color:#6B7280; line-height:1.9;'>
            <b style='color:#F59E0B;'>ActionBridge</b> was built to solve the exact problem
            Jett McCandless (CEO, project44) publicly described in August 2025:<br>
            <i style='color:#F9FAFB;'>
            "AI that doesn't lead to action is just another dashboard."</i>
            <br><br>
            Built by <b style='color:#F9FAFB;'>Rutwik Satish</b> ·
            MS Engineering Management, Northeastern University (May 2026) ·
            <span style='color:#F59E0B;'>Celonis Process Mining Certified</span> ·
            SAP S/4HANA · McKinsey Forward
        </div>
    </div>
    """, unsafe_allow_html=True)
