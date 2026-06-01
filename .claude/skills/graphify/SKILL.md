---
name: graphify-windows
description: any input (code, docs, papers, images) → knowledge graph → clustered communities → HTML + JSON + audit report
trigger: /graphify
---

# /graphify

> **Note**: Full skill content installed at `~/.claude/skills/graphify/SKILL.md` (user level).
> This repo-level file is maintained as a project reference.

## Usage

```
/graphify .                             # full pipeline on current directory
/graphify . --update                    # incremental re-extract
graphify query "your question"          # BFS traversal of graph.json
graphify path "A" "B"                   # shortest path between nodes
graphify explain "X"                    # explain a node and its neighbors
graphify hook status                    # check git hooks
```

The graph auto-rebuilds on every git commit (post-commit hook).
MCP server config is in `.mcp.json` and `.cursor/mcp.json`.
