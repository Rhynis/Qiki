# Future work — deferred features and when to revisit

This document records features that were **deliberately deferred**, not forgotten.
Each one is premature for the shop's current scale: it would add complexity,
operational cost, or model risk without a matching payoff today. For each item we
record **why it is deferred now**, the **concrete threshold that should trigger a
revisit**, and the **approach to take when that threshold is reached**.

Read this before proposing any of these features again. If a threshold below has
been crossed, the feature is worth reopening; if not, the current lightweight
alternative is the right choice.

## Current scale (baseline, as of 2026-07)

Thresholds below are relative to this baseline. Update it when re-reading.

| Signal | Value now |
| --- | --- |
| Real customer accounts | ~1 (mostly the owner + test accounts) |
| Orders | ~17 |
| Products | 22 active |
| Knowledge-base docs | 48 |
| Conversations / messages | ~350 / ~1.3k |
| Staff-reviewed chat transcripts | 0 (no review queue yet) |
| Roles | 3 — customer, staff, admin |
| Delivery zones | 2 — Bình Thạnh, Thủ Đức |
| A/B-test / experiment infra | none |
| Daily traffic | low (single shop, launch phase) |

The through-line: **almost everything advanced here needs either (a) a lot more
data, or (b) more organizational structure (teams, drivers, experiment infra)
than a single-shop launch has.** Ship the data-light alternative now; keep the
heavy version on this list.

---

## 1. Continuous LLM fine-tuning

**What:** periodically fine-tune the assistant (Qwen 2.5 7B, or the cloud model)
on the shop's own resolved conversations so it sounds more on-brand and needs
less prompt/context engineering.

**Why deferred:** high model risk for low current payoff. Fine-tuning on our own
raw logs invites:
- **Catastrophic forgetting** — the model loses general ability it wasn't
  retrained on.
- **Learning its own mistakes** — if we train on unfiltered assistant outputs, we
  amplify whatever it already gets wrong.
- **Overfitting** — on a few hundred conversations it memorizes phrasings instead
  of generalizing.
- **Safety regression** — the single most important property (100% emergency
  detection) is currently guaranteed by a deterministic gate *outside* the model.
  A fine-tune must never be allowed to weaken that.

We also have **0 staff-reviewed transcripts**: there is no clean training set yet.

**Revisit when:**
- There are on the order of **~1,000+ staff-reviewed, high-quality
  conversations** (see Conversation mining, issue #278, as the feeder), AND
- a **data review queue** exists so only staff-approved exchanges become training
  data (never raw/auto logs), AND
- prompt-engineering has clearly plateaued (we keep hitting quality limits that
  context/prompt changes can't fix).

**Approach when revisiting (two mandatory guardrails):**
1. **Curation gate (before training):** a review queue where staff explicitly
   approve each example. Only approved, corrected exchanges enter the dataset.
   Never train on unfiltered production logs.
2. **Eval gate (after training):** run the existing eval suites
   (`scripts/run_evaluation.py`, 232 cases) against the candidate model.
   **Safety-emergency detection must stay 100%**; intent/RAG metrics must not
   regress. A model that fails the gate is never deployed.
- Keep the deterministic safety gate in front of the model **regardless** — the
  fine-tune improves tone/helpfulness, it does not own safety.
- **Free-GPU path for experiments:** QLoRA/LoRA with
  [Unsloth](https://github.com/unslothai/unsloth) on a free Colab or Kaggle T4.
  This is for experimentation only; a validated adapter can then be promoted.
- Start with LoRA adapters (cheap, reversible) rather than full fine-tunes.

**Related:** #278 (conversation mining) produces the reviewed dataset this needs.

---

## 2. Personalized recommender (collaborative filtering)

**What:** ML-driven "recommended for you" / "customers also bought" personalization.

**Why deferred:** collaborative filtering needs a **dense user × item interaction
matrix**. With ~1 real user and ~17 orders across 22 products, there is no signal
to learn from — this is the classic **cold-start** problem, and no algorithm fixes
missing data.

**Revisit when:** there are **hundreds to low-thousands of customers with repeat
purchase history** (enough overlapping purchases that "people who bought X also
bought Y" is statistically meaningful).

**Approach when revisiting:** start with simple item-item co-occurrence
(association rules) before any matrix-factorization / neural approach; measure
uplift against the non-personalized baseline below before investing further.

**Ship instead now (data-light, high value):**
- **Re-order** — one-tap repeat of a past order. Gas/water are consumables people
  reorder on a cycle; this needs *zero* ML and serves the top real use case.
- **Best-sellers** — "most ordered" list from a simple SQL aggregation. Good
  enough guidance for new visitors without personalization.

**Related:** #280 (Re-order + best-sellers) is the deliberate stand-in for this.

---

## 3. Causal inference / experimentation (A/B testing)

**What:** measure whether an intervention **causes** a business outcome, rather
than just correlating with it. Example: does the monthly gas-price-change email
(#274) or a coupon (#275) actually *cause* more orders, or would those customers
have ordered anyway (seasonality, payday, Tết)? Answering "caused" requires a
control group, not just a before/after line chart.

**Why deferred:** two hard blockers today —
- **No experiment infrastructure** — no way to randomly assign users to
  treatment/control, no flagging/bucketing, no metrics pipeline.
- **Not enough traffic** — with low daily volume, an A/B test can't reach
  statistical significance in a reasonable time; the confidence interval stays too
  wide to conclude anything.

**Revisit when:**
- Daily order/traffic volume is high enough that a 2-week experiment can detect a
  realistic effect size at ~95% confidence (rule of thumb: hundreds of
  conversions per arm), AND
- basic experiment infra exists (deterministic user bucketing + per-arm metric
  capture — the coupon/email features above are natural first surfaces).

**Approach when revisiting:** begin with one clean A/B on an existing campaign
(email or coupon): randomize eligible users into treatment/control, hold
everything else constant, compare conversion between arms, report the effect with
a confidence interval — not just a raw delta. Only add heavier causal methods
(diff-in-diff, uplift modeling) once simple A/B is running reliably.

---

## 4. Department-based conversation routing

**What:** route incoming chats to different teams/queues by intent (e.g. sales vs
support vs billing), each with its own staff group and SLAs.

**Why deferred:** routing to departments presupposes **multiple departments**.
Today there is effectively one small staff group; the existing
status/flag/escalation workflow (active → escalated → resolved/closed, plus
`flagged_for_review`) already covers the real need.

**Revisit when:** the shop grows to **multiple distinct staff teams/departments**
that genuinely need separate queues and ownership.

**Approach when revisiting:** reuse the existing intent classifier to tag
conversations, then map intent → team queue; add per-team assignment and a
routing table. The classifier and status machinery are already in place, so this
is mostly an assignment/queue layer, not new ML.

---

## 5. Realtime GPS delivery tracking

**What:** live "where is my driver" map for customers, updated continuously.

**Why deferred:** realtime tracking needs a **driver-side app streaming GPS
continuously** plus a realtime channel to the customer — a substantial build, and
we don't yet have drivers reporting location at all. For 2 nearby zones, a status
update ("out for delivery") already covers most of the value.

**Revisit when:** the driver role is adopted in practice (#277) **and** customers
actually ask for live tracking, **and** delivery volume/area is large enough that
"out for delivery" is no longer specific enough.

**Approach when revisiting:** build on the driver role — start with periodic
last-known-location updates (driver app posts coordinates every N seconds while on
a delivery) before anything resembling continuous streaming; expose an ETA/coarse
location to the customer rather than a raw live dot at first.

**Related:** #277 (driver role) is the prerequisite and can store an optional
last-known location as a stepping stone.

---

## 6. Route optimization for drivers

**What:** compute an optimal multi-stop delivery route (traveling-salesman style)
across a driver's pending deliveries.

**Why deferred:** with 2 zones and low daily delivery counts, a human orders stops
better than the tooling cost of a routing engine. Optimization only pays off past
a certain stop count.

**Revisit when:** a single driver regularly handles **many stops per run**
(roughly 8+), such that manual ordering is visibly suboptimal.

**Approach when revisiting:** use a mapping/routing API (distance matrix +
route optimization) rather than rolling our own solver; feed it the deliveries
table (#271) grouped per driver per day.

**Related:** #271 (multi-delivery / deliveries table), #277 (driver role).

---

## 7. Native mobile app

**What:** a native iOS/Android app in the app stores.

**Why deferred:** high build + maintenance + store-review cost for a single shop.
Most of the value (installable, home-screen icon, offline shell, push
notifications) is reachable far more cheaply.

**Revisit when:** there is clear demand for something a PWA genuinely cannot do
(deep native integrations, or app-store presence is a business requirement).

**Approach when revisiting:** ship a **PWA first** — add a web app manifest +
service worker to the existing Next.js app so it is installable to the home
screen and works offline for the shell. Reassess a native app only if the PWA
hits a hard limit.

> **PWA (Progressive Web App):** a normal website that, via a manifest and a
> service worker, can be "installed" to the phone home screen, launch full-screen
> without browser chrome, cache its shell for offline use, and (with permission)
> receive push notifications — most of the "app feel" without an app store.

---

## How to use this list

- When someone proposes one of these, check its **Revisit when** against the
  current baseline. If the threshold isn't met, point them to the data-light
  alternative already shipped or listed here.
- When a threshold **is** crossed, open an issue that references this section and
  follow the **Approach** notes.
- Keep the **Current scale** table above up to date; it is what makes these
  thresholds meaningful.
