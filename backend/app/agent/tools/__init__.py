"""LangChain tools wrapping existing Qiki services, plus their authorization
matrix.

``build_tools()`` in ``agent/graph.py`` wires up the read-only tools
(search_products, check_inventory, lookup_safety_policy, recommend_products)
— no mutations reach production yet. Errors are returned as structured
results, never raised, so a tool-calling loop always gets a value to reason
about instead of an unhandled exception.

``registry.py`` (issue #348) declares each tool's authorization policy
(read/write, requires_auth, requires_confirm), enforced by
``agent/nodes/tool_executor.py`` before any tool is invoked. The
``_mock_*_example.py`` modules are test-only fixtures proving the write/
confirm and owner-scoping guardrails work — see their docstrings — and are
never wired into ``build_tools()``.
"""
