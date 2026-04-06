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
tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs([
    "🚨  Disruption Feed",
    "🔍  Impact Analyser",
    "🧠  Decision Engine",
    "⚙️  SAP Actions",
    "✅  Proof of Value",
    "🗂️  Data Quality",
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
