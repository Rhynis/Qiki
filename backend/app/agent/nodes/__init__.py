"""One module per LangGraph node. Each node is a plain async function of
``(state) -> dict`` so it is trivially unit-testable without constructing the
whole compiled graph.
"""
