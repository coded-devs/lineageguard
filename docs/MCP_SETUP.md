# Claude Desktop MCP Setup

To integrate LineageGuard with Claude Desktop, you need to configure it as an MCP (Model Context Protocol) server.

## Installation

Add the following to your `claude_desktop_config.json` file. 

On Windows, this is typically located at:
`%APPDATA%\Claude\claude_desktop_config.json`

On macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`

The 'cwd' key is REQUIRED — it ensures .env is discoverable when Claude Desktop launches the server.

```json
{
  "mcpServers": {
    "lineageguard": {
      "command": "C:\\Users\\HP\\OneDrive\\Desktop\\startup\\Team\\Coded-devs\\Building\\lineageguard\\.venv\\Scripts\\python.exe",
      "args": ["-m", "lineageguard.mcp_server"],
      "cwd": "C:\\Users\\HP\\OneDrive\\Desktop\\startup\\Team\\Coded-devs\\Building\\lineageguard"
    }
  }
}
```

*Note: Replace `path/to/lineageguard` with the true absolute path to your LineageGuard repository. Replace `YOUR_PERSONAL_ACCESS_TOKEN` with your OpenMetadata PAT, generated within OpenMetadata settings.*

## Restarting Claude Desktop

After making the configuration changes and saving the file, completely quit and restart Claude Desktop. When it restarts, you should see two new tools available:
- `analyze_semantic_impact`
- `get_entity_governance`
