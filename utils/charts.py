"""ActionBridge — Charts (Plotly)"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# ── Palette: Operations Command Center ──────────────────────────────────────
BG      = "#0A0E1A"
CARD    = "#111827"
BORDER  = "#1F2937"
AMBER   = "#F59E0B"
RED     = "#EF4444"
GREEN   = "#10B981"
BLUE    = "#3B82F6"
PURPLE  = "#8B5CF6"
TEXT    = "#F9FAFB"
MUTED   = "#6B7280"
FONT    = "Space Mono, monospace"

BASE = dict(
    paper_bgcolor=BG, plot_bgcolor=CARD,
    font=dict(color=TEXT, family=FONT),
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER),
)

def _L(**kw):
    b = {k: (dict(v) if isinstance(v, dict) else v) for k, v in BASE.items()}
    for k, v in kw.items():
        if k in b and isinstance(b[k], dict) and isinstance(v, dict):
            b[k] = {**b[k], **v}
        else:
            b[k] = v
    return b


# ── 1. Disruption Feed ───────────────────────────────────────────────────────
def fig_disruption_timeline(shipments_df: pd.DataFrame) -> go.Figure:
    delayed = shipments_df[shipments_df["is_delayed"]].copy()
    delayed["ship_week"] = pd.to_datetime(delayed["ship_date"]).dt.isocalendar().week
    weekly   = delayed.groupby(["ship_week","severity"]).size().reset_index(name="count")
    color_map = {"Critical": RED, "High": AMBER, "Medium": BLUE, "Low": GREEN}

    fig = go.Figure()
    for sev, col in color_map.items():
        sub = weekly[weekly["severity"] == sev]
        if sub.empty: continue
        fig.add_trace(go.Bar(
            x=sub["ship_week"], y=sub["count"],
            name=sev, marker_color=col,
            hovertemplate=f"Week %{{x}}<br>{sev}: %{{y}} incidents<extra></extra>",
        ))
    fig.update_layout(**_L(
        title=dict(text="Disruption Incidents by Week & Severity", font=dict(size=13)),
        barmode="stack",
        xaxis=dict(title="Week", gridcolor=BORDER, color=MUTED),
        yaxis=dict(title="Incidents", gridcolor=BORDER, color=MUTED),
        height=280, legend=dict(orientation="h", y=1.1),
    ))
    return fig


def fig_severity_donut(shipments_df: pd.DataFrame) -> go.Figure:
    counts = shipments_df["severity"].value_counts()
    colors = [RED if s=="Critical" else AMBER if s=="High"
              else BLUE if s=="Medium" else GREEN if s=="Low" else MUTED
              for s in counts.index]
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values,
        hole=0.60, marker=dict(colors=colors, line=dict(color=BG, width=2)),
        textinfo="label+percent", textfont=dict(size=10),
        hovertemplate="<b>%{label}</b><br>%{value} shipments<extra></extra>",
    ))
    fig.update_layout(**_L(
        title=dict(text="Severity Distribution", font=dict(size=13)),
        showlegend=False, height=260,
    ))
    return fig


# ── 2. Impact Analysis ───────────────────────────────────────────────────────
def fig_order_impact_scatter(orders_df: pd.DataFrame) -> go.Figure:
    at_risk = orders_df[orders_df["is_at_risk"]].copy()
    tier_col = {
        "A": RED, "B": AMBER, "C": BLUE,
    }
    colors = [tier_col.get(t, MUTED) for t in at_risk["customer_tier"]]

    fig = go.Figure(go.Scatter(
        x=at_risk["delay_hours_exposure"],
        y=at_risk["order_value"],
        mode="markers",
        marker=dict(
            size=at_risk["estimated_penalty"].clip(upper=50000) / 2500 + 6,
            color=colors, opacity=0.75, line=dict(color=BG, width=1),
        ),
        text=at_risk["customer"],
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Delay: %{x:.0f}h<br>"
            "Order: $%{y:,.0f}<br>"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(**_L(
        title=dict(text="Orders at Risk (bubble = penalty; color = tier)", font=dict(size=13)),
        xaxis=dict(title="Delay Exposure (hrs)", gridcolor=BORDER, color=MUTED),
        yaxis=dict(title="Order Value ($)", gridcolor=BORDER, color=MUTED, tickformat="$,.0f"),
        height=320,
    ))
    return fig


def fig_penalty_by_customer(orders_df: pd.DataFrame) -> go.Figure:
    at_risk = orders_df[orders_df["is_at_risk"]]
    grp = at_risk.groupby("customer").agg(
        total_penalty=("estimated_penalty","sum"),
        tier=("customer_tier","first"),
    ).sort_values("total_penalty", ascending=True).tail(10).reset_index()

    tier_col = {"A": RED, "B": AMBER, "C": BLUE}
    colors   = [tier_col.get(t, MUTED) for t in grp["tier"]]

    fig = go.Figure(go.Bar(
        y=grp["customer"], x=grp["total_penalty"],
        orientation="h", marker_color=colors,
        text=[f"${v:,.0f}" for v in grp["total_penalty"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Penalty: $%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_L(
        title=dict(text="Top 10 Penalty Exposure by Customer", font=dict(size=13)),
        xaxis=dict(title="Estimated Penalty ($)", gridcolor=BORDER, tickformat="$,.0f", color=MUTED),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", color=TEXT),
        height=320,
    ))
    return fig


# ── 3. Decision Engine ───────────────────────────────────────────────────────
def fig_response_comparison(responses_df: pd.DataFrame) -> go.Figure:
    if responses_df.empty:
        return go.Figure()
    feasible = responses_df[responses_df["feasible"]].head(5)
    colors   = [GREEN if i == 0 else AMBER if i == 1 else BLUE
                for i in range(len(feasible))]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Net Benefit ($)",
        x=feasible["response_label"],
        y=feasible["net_benefit_usd"],
        marker_color=colors,
        text=[f"${v:,.0f}" for v in feasible["net_benefit_usd"]],
        textposition="outside",
        yaxis="y", offsetgroup=1,
        hovertemplate="<b>%{x}</b><br>Net: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        name="Hours Saved",
        x=feasible["response_label"],
        y=feasible["hours_saved"],
        mode="markers+lines",
        marker=dict(size=12, color=PURPLE),
        line=dict(color=PURPLE, dash="dot"),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>Hours saved: %{y:.0f}h<extra></extra>",
    ))
    fig.update_layout(**_L(
        title=dict(text="Response Options — Net Benefit vs Hours Saved", font=dict(size=13)),
        xaxis=dict(color=TEXT, tickangle=-20),
        yaxis=dict(title="Net Benefit ($)", gridcolor=BORDER, tickformat="$,.0f", color=MUTED),
        yaxis2=dict(title="Hours Saved", overlaying="y", side="right", color=PURPLE,
                    showgrid=False),
        height=320, barmode="group",
        legend=dict(orientation="h", y=1.1),
    ))
    return fig


def fig_impact_radar(impact: dict) -> go.Figure:
    components = impact.get("components", {})
    if not components:
        return go.Figure()
    cats   = list(components.keys())
    values = list(components.values())
    values_closed = values + [values[0]]
    cats_closed   = cats   + [cats[0]]

    fig = go.Figure(go.Scatterpolar(
        r=values_closed, theta=cats_closed,
        fill="toself",
        fillcolor=f"rgba(239,68,68,0.15)",
        line=dict(color=RED, width=2),
        marker=dict(size=8, color=RED),
        hovertemplate="%{theta}: %{r:.1f}<extra></extra>",
    ))
    fig.update_layout(**_L(
        title=dict(text="Impact Score Components", font=dict(size=13)),
        polar=dict(
            bgcolor=CARD,
            radialaxis=dict(visible=True, range=[0,100], color=MUTED,
                            gridcolor=BORDER, tickfont=dict(size=8)),
            angularaxis=dict(color=TEXT, gridcolor=BORDER),
        ),
        showlegend=False, height=300,
    ))
    return fig


# ── 4. Process Comparison (Proof) ────────────────────────────────────────────
def fig_process_comparison(manual_steps: list, auto_time_min: float) -> go.Figure:
    manual_labels = [s[0] for s in manual_steps]
    manual_times  = [s[2] for s in manual_steps]
    manual_cumsum = list(pd.Series(manual_times).cumsum())

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Manual Process",
        x=manual_labels,
        y=manual_times,
        marker_color=[RED if t > 30 else AMBER if t > 15 else MUTED for t in manual_times],
        text=[f"{t}m" for t in manual_times],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{y} minutes<extra></extra>",
    ))
    total_manual = sum(manual_times)
    fig.add_hline(
        y=auto_time_min, line_color=GREEN, line_dash="dash", line_width=2,
        annotation_text=f"⚡ ActionBridge: {auto_time_min:.0f}m total",
        annotation_font_color=GREEN, annotation_font_size=11,
        annotation_position="top right",
    )
    fig.update_layout(**_L(
        title=dict(text=f"Manual ({total_manual}m) vs ActionBridge ({auto_time_min:.0f}m) — Process Comparison",
                   font=dict(size=13)),
        xaxis=dict(color=TEXT, tickangle=-30),
        yaxis=dict(title="Minutes", gridcolor=BORDER, color=MUTED),
        height=340, showlegend=False,
    ))
    return fig


def fig_roi_annualised(stats: dict, avg_penalty_per_incident: float) -> go.Figure:
    incidents_mo = stats.get("incidents_per_month", 10)
    manual_hrs   = stats.get("manual_process_mins", 230) / 60
    auto_hrs     = stats.get("actionbridge_mins", 3) / 60
    hourly_rate  = 85

    months = list(range(1, 13))
    manual_cost  = [m * incidents_mo * manual_hrs * hourly_rate for m in months]
    auto_cost    = [m * incidents_mo * auto_hrs   * hourly_rate for m in months]
    penalty_saved= [m * incidents_mo * avg_penalty_per_incident * 0.65 for m in months]
    net_savings  = [p - (mc - ac) for p, mc, ac in zip(penalty_saved, manual_cost, auto_cost)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=months, y=manual_cost, name="Manual Process Cost",
        line=dict(color=RED, width=2),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.08)",
        hovertemplate="Month %{x}<br>Manual: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=auto_cost, name="ActionBridge Cost",
        line=dict(color=GREEN, width=2),
        fill="tozeroy", fillcolor="rgba(16,185,129,0.08)",
        hovertemplate="Month %{x}<br>Auto: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=net_savings, name="Cumulative Net Savings",
        line=dict(color=AMBER, width=2, dash="dot"),
        hovertemplate="Month %{x}<br>Saved: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_L(
        title=dict(text="12-Month Annualised Savings Projection", font=dict(size=13)),
        xaxis=dict(title="Month", gridcolor=BORDER, color=MUTED),
        yaxis=dict(title="Cumulative Cost ($)", gridcolor=BORDER, tickformat="$,.0f", color=MUTED),
        height=320, legend=dict(orientation="h", y=1.1),
    ))
    return fig


# ── 5. Data Quality ──────────────────────────────────────────────────────────
def fig_data_quality_bar(dq_results: dict) -> go.Figure:
    datasets = list(dq_results["datasets"].keys())
    scores   = [dq_results["datasets"][d]["score"] for d in datasets]
    colors   = [GREEN if s >= 90 else AMBER if s >= 75 else RED for s in scores]

    fig = go.Figure(go.Bar(
        x=datasets, y=scores,
        marker_color=colors,
        text=[f"{s:.0f}%" for s in scores],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Score: %{y:.0f}%<extra></extra>",
    ))
    fig.add_hline(y=90, line_color=GREEN, line_dash="dot",
                  annotation_text="Decision-Ready Threshold (90%)",
                  annotation_font_color=GREEN, annotation_font_size=10)
    fig.update_layout(**_L(
        title=dict(text="Data Quality Score by Dataset", font=dict(size=13)),
        xaxis=dict(color=TEXT),
        yaxis=dict(title="Quality Score (%)", range=[0,110], gridcolor=BORDER, color=MUTED),
        height=280, showlegend=False,
    ))
    return fig


def fig_carrier_reliability(carriers_df: pd.DataFrame) -> go.Figure:
    df = carriers_df.sort_values("reliability_score", ascending=True)
    colors = [GREEN if r >= 0.92 else AMBER if r >= 0.88 else RED
              for r in df["reliability_score"]]

    fig = go.Figure(go.Bar(
        y=df["carrier_name"],
        x=df["reliability_score"] * 100,
        orientation="h",
        marker_color=colors,
        text=[f"{r*100:.1f}%" for r in df["reliability_score"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Reliability: %{x:.1f}%<extra></extra>",
    ))
    fig.add_vline(x=90, line_color=GREEN, line_dash="dot",
                  annotation_text="90% threshold",
                  annotation_font_color=GREEN, annotation_font_size=10)
    fig.update_layout(**_L(
        title=dict(text="Carrier Reliability Scores", font=dict(size=13)),
        xaxis=dict(title="%", range=[75, 105], gridcolor=BORDER, color=MUTED),
        yaxis=dict(color=TEXT, gridcolor="rgba(0,0,0,0)"),
        height=320, showlegend=False,
    ))
    return fig
