# Claude Desktop MCP Setup

To integrate LineageGuard with Claude Desktop, you need to configure it as an MCP (Model Context Protocol) server.

## Installation

Add the following to your `claude_desktop_config.json` file. 

On Windows, this is typically located at:
`%APPDATA%\Claude\claude_desktop_config.json`

On macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "lineageguard": {
      "command": "path/to/lineageguard/.venv/Scripts/python.exe",
      "args": [
        "-m",
        "lineageguard.mcp_server"
      ],
      "env": {
        "OPENMETADATA_URL": "http://localhost:8585/api/v1",
        "OPENMETADATA_TOKEN": "YOUR_PERSONAL_ACCESS_TOKEN"
      }
    }
  }
}
```

*Note: Replace `path/to/lineageguard` with the true absolute path to your LineageGuard repository. Replace `YOUR_PERSONAL_ACCESS_TOKEN` with your OpenMetadata PAT, generated within OpenMetadata settings.*

## Restarting Claude Desktop

After making the configuration changes and saving the file, completely quit and restart Claude Desktop. When it restarts, you should see two new tools available:
- `analyze_semantic_impact`
- `get_entity_governance`
