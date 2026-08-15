"""MCP server exposing Qiki's read-only tools over Streamable HTTP.

See docs/mcp.md and app.mcp_server.server.create_mcp_server(). Mounted into
the existing FastAPI app (app/main.py) behind the MCP_ENABLED setting; a
disabled flag imports nothing from this package, so it has zero cost when off.
"""
