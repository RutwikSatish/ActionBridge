# ⚡ ActionBridge
### From Visibility Alert to SAP Action in One Step

> *"AI that doesn't lead to action is just another dashboard."*
> — **Jett McCandless, Founder & CEO, project44**

---

## The Problem It Solves

project44 detects a shipment delay in real time.
Then what? A logistics analyst spends **230 minutes across 10 manual steps**
to get from alert → SAP delivery date change → customer notification.
4–5 people involved. Decisions made on incomplete, un-validated data.

**ActionBridge closes that gap: 230 minutes → 3 minutes.**

---

## What It Does

| Tab | Function |
|-----|----------|
| 🚨 Disruption Feed | Live exception alerts ranked by severity |
| 🔍 Impact Analyser | Which SAP orders are affected, penalty exposure, customer tier priority |
| 🧠 Decision Engine | Ranked response options (expedite / alt carrier / alt warehouse / reroute) with net benefit, success rate, feasibility validation |
| ⚙️ SAP Actions | Auto-generated SAP transaction drafts (VA02, ME22N, LT01, VT02N, Email) |
| ✅ Proof of Value | Before/after process comparison, 12-month ROI projection |
| 🗂️ Data Quality | 4-dataset validation framework, decision confidence scoring |

---

## Run Locally

```bash
cd actionbridge
pip install -r requirements.txt
streamlit run app.py
```

---

## Tech Stack
- Python · Pandas · NumPy · Plotly · Streamlit
- Groq (Llama 3.3 70B) for AI analyst brief
- SAP S/4HANA domain knowledge (VA02, ME22N, LT01, VT02N)
- Celonis Process Mining methodology (event log analysis)
- Decision engine: composite scoring with feasibility validation

---

## LinkedIn Post

```
project44 CEO Jett McCandless said:
"AI that doesn't lead to action is just another dashboard."

So I mapped exactly what happens after a shipment alert fires.
230 minutes. 10 manual steps. 4-5 people.

Then I built ActionBridge to do it in 3 minutes.

→ Impact analyser: which SAP orders are at risk
→ Decision engine: ranked responses with net benefit ($)
→ SAP drafts: VA02, ME22N, LT01 auto-generated
→ Data quality: 4-dataset validation before any decision

[Streamlit link]

@project44 #LogisticsTech #SupplyChain #AIOperations #SAP
```

---

## By
**Rutwik Satish** | MS Engineering Management, Northeastern (May 2026)
Celonis Process Mining Certified · SAP S/4HANA · McKinsey Forward
