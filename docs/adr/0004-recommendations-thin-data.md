# ADR-0004: Content + popularity + rules recommendations, over a thin-data catalog

## Status

Accepted

## Context

Qiki's portfolio plan calls for a recommendation/ranking capability (the "P5
RecSys" milestone) — a `recommend_products` agent tool, a storefront "Gợi ý
cho bạn" row, and an offline eval harness with the metrics a recsys role
actually asks about (recall@k, NDCG@k, MAP, coverage).

**The honest constraint that shapes every decision below:** production has
roughly **one real customer** and a handful of self-test orders placed while
building and QA-ing the storefront. That is not a dataset — it is noise. Any
model that "learns" from it (collaborative filtering, a learned embedding
retriever, even a simple item-item co-occurrence table built from real
orders) would really be memorizing a dozen test transactions and presenting
that as personalization. A reviewer or interviewer who asks "what data did
this learn from?" deserves a true answer, not a dressed-up one.

The value this feature can honestly deliver today is different: prove the
**schema, the ranking framework, the cold-start path, and the agent/serving
integration** are real and correct, on a system that will keep working
once (if) real interaction volume exists — not fabricate present-day
personalization accuracy.

## Decision

Build `RecommendationService` as **content-based similarity + a real
popularity prior + explicit, hand-written complementary rules** — no
collaborative filtering, no learned embeddings, no personalization by
customer identity. Concretely (see `backend/app/services/recommendation_service.py`
for the exact weights):

- **Content similarity** to the viewed product — same brand, same category,
  adjacent gas cylinder size, similar price band. This is the primary,
  highest-confidence signal: it doesn't need behavioral data at all, it's
  derivable straight from `products` rows already in the DB.
- **Popularity** — `OrderService.get_best_sellers`, i.e. actual order
  history, however sparse. Used as a *prior* (a tiebreaker / cold-start
  fallback), not fit to it the way a learned ranker would be. Honest about
  being near-empty today: with zero real orders, every popularity
  contribution is 0.0 and the service says so explicitly (see
  `REASON_POPULAR_FALLBACK` — never claims a fabricated "best-seller").
- **Explicit complementary rules** — a merchandiser's judgment encoded
  directly: a gas cylinder suggests water as an add-on; a water order
  suggests the *other* water brand (cross-sell/diversify, not more of the
  same). These are the highest-weighted signal on purpose — they encode real
  domain knowledge (gas and water are genuinely complementary in this
  business) that no amount of thin interaction data would reliably surface.
- **Cold start** (no viewed product — a new/anonymous visitor) degrades
  cleanly to the popularity prior alone, or an honest "nothing to rank on
  yet" fallback reason when there's no order history at all.

Every candidate's score is the sum of whichever signals matched; the
single highest-weighted one becomes the customer-facing Vietnamese `reason`
string — always something a human could verify against the catalog (never
"customers like you also liked…", which would be a lie at this data volume).

### Why not collaborative filtering / a learned ranker

The standard argument for CF (or a two-tower embedding retriever) is that it
finds non-obvious patterns human-written rules miss. That argument needs
real interaction volume to hold — with ~1 real user, CF would either produce
degenerate output (nothing to collaborate on) or overfit to noise and present
it with false confidence. Content + rules degrades gracefully to *something
defensible* at zero interaction data and only gets better (not fundamentally
different in kind) as real signal accumulates — see the migration path below.

### The eval harness is honestly a simulation, not a benchmark

`bench/recsys_eval.py` generates a **seeded, deterministic simulated**
interaction log over the real catalog, then reports recall@k/NDCG@k/MAP/
coverage against it. Read that as a **self-consistency check** — "does the
ranker's output line up with the same kind of structure the simulator
encodes" — not an accuracy claim about real user behavior, because the
simulator's bias is deliberately built from the *same* signal categories
(same brand, gas→water, adjacent size) the ranker itself scores on. A
ranker that failed this check would have an actual bug; passing it is
evidence of correctness, not of real-world predictive power. The one place
real data enters the eval is the cold-start slice, scored against the
*actual* best-sellers list — and reported as "N/A" instead of a fabricated
number on any database with no real order history.

## What real interaction logging would change (the stretch)

Out of scope for this PR, called out honestly rather than silently omitted:

- **Event logging**: capture real product views / add-to-cart / purchases
  per session (even anonymous, cookie-keyed) — Qiki doesn't log this today.
- **A real co-occurrence or item-item CF table**, once there's enough volume
  that it wouldn't just be memorizing test orders — this slots in as an
  *additional* signal in `_signal_contributions`, same scoring framework,
  no rearchitecture needed.
- **A/B measurement**: click-through / add-to-cart rate on recommended slots
  vs. a control, to validate the ranker actually helps rather than just
  looking plausible offline.
- **A learned re-ranker** (even a small logistic-regression blend of the
  existing signals, before jumping to embeddings) once there's enough
  labeled interaction data to fit one without overfitting.

None of this requires touching the pricing (#239), safety, checkout, or
agent-graph-structure invariants this PR is careful not to touch — it's
additive to `RecommendationService`'s signal set.
