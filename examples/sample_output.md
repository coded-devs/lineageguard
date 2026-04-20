# LineageGuard — Semantic Blast Radius Report

**Source entity:** `Stripe.stripe_db.public.raw_stripe_data`
**Analysis time:** 2026-04-20T05:09:37Z

## Summary
- 🔴 CRITICAL: 1
- 🟠 HIGH: 2
- 🟡 WARNING: 1
- 🔵 INFO: 1

## Findings

### 🔴 CRITICAL — fct_orders (depth 2)
**Business concept:** NetRevenue
**Tier:** Tier1
**Owner:** Finance
**Contract violated:** yes

> Contract-protected asset: Data Contract 'FinanceCoreMetrics' on fct_orders.

---

### 🟠 HIGH — dim_customers (depth 1)
**Business concept:** Customer
**Tier:** Tier2
**Contract violated:** no

> Tier 2 asset backing business concept Customer.

---

### 🟠 HIGH — executive_revenue_dashboard (depth 3)
**Tier:** Tier1
**Contract violated:** no

> Tier 1 asset with no additional governance — still business-critical.

---

### 🟡 WARNING — marketing_attribution_dashboard (depth 3)
**Tier:** Tier3
**Contract violated:** no

> Tier 3 asset — lower priority but worth flagging.

---

### 🔵 INFO — stg_stripe_charges (depth 1)
**Contract violated:** no

> No semantic governance attached.