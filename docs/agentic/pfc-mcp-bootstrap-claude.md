# pfc-mcp Bootstrap (Claude Code)

Use this profile when the client uses `.mcp.json` style MCP config.

For Codex, use `docs/agentic/pfc-mcp-bootstrap-codex.md` instead.

## Step 1 (Claude Code) - Configure MCP

[AGENT]

Default target: user-level MCP config (global, available across all working directories).
Preferred mechanism: `claude mcp add --scope user pfc-mcp -- uvx pfc-mcp` (idempotent; handles merge; no need to locate the config file).
Fall back to workspace `.mcp.json` only if the user-scope config is unavailable or write-blocked.

Add/merge this MCP entry:

```json
{
  "mcpServers": {
    "pfc-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["pfc-mcp"]
    }
  }
}
```

If `uvx` is unavailable, fallback to:

```json
{
  "mcpServers": {
    "pfc-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["tool", "run", "pfc-mcp"]
    }
  }
}
```

## Continue with common bootstrap

After Step 1, continue from Step 2 in:

- `docs/agentic/pfc-mcp-bootstrap.md`
