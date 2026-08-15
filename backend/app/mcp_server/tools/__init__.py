"""MCP-only tool factories.

These two tools (``find_nearest_store``, ``calculate_delivery_fee``) don't
have a LangChain equivalent in app/agent/tools/ yet — see the PR description
for #349 for why they were added here instead of there. Structurally they
follow the exact same ``build_*_tool() -> BaseTool`` pattern as
app/agent/tools/ so migrating them later (once the agent graph wants them
too) is a pure file move.
"""
