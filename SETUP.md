# Setup Instructions

## 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. MCP Inspector Setup

1. Copy the example config:
```bash
cp mcp_config.example.json mcp_config.json
```

2. Update `mcp_config.json` with your absolute path:
```json
{
  "mcpServers": {
    "kommunalpolitik-mcp": {
      "command": "/YOUR_ABSOLUTE_PATH/kommunalpolitik-mcp/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/YOUR_ABSOLUTE_PATH/kommunalpolitik-mcp"
    }
  }
}
```

3. Run MCP Inspector:
```bash
npx @modelcontextprotocol/inspector mcp_config.json
```

## 3. Test Server

```bash
source .venv/bin/activate
python test_server.py
```
