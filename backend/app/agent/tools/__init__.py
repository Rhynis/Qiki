"""Read-only LangChain tools wrapping existing Qiki services.

Every tool here is READ-only for the MVP (search_products, check_inventory,
lookup_safety_policy) — no mutations. Errors are returned as structured
results, never raised, so a tool-calling loop always gets a value to reason
about instead of an unhandled exception.
"""
