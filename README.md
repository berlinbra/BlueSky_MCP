# BlueSky MCP Server

A Model Context Protocol (MCP) server that provides access to [BlueSky](https://bsky.app) social network data through its official API. This server implements a standardized interface for retrieving user profiles and social graph information.

<a href="https://glama.ai/mcp/servers/bxvvsqt34k"><img width="380" height="200" src="https://glama.ai/mcp/servers/bxvvsqt34k/badge" alt="BlueSky Server MCP server" /></a>

## Features

- Fetch detailed user profile information
- Retrieve user following lists with pagination
- Built-in authentication handling and session management
- Comprehensive error handling

## Installation



#### Claude Desktop

- On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
- On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

<details>
<summary>Development/Unpublished Servers Configuration</summary>

```json
    "mcpServers": {
        "bluesky-mcp": {
            "command": "uv",
            "args": [
            "--directory",
            "C:\\Users\\{INSERT_USER}\\YOUR\\PATH\\TO\\bluesky-mcp\\bluesky-mcp",
            "run",
            "src/bluesky_mcp/bluesky-mcp"
            ],
            "env": {
                "BLUESKY_IDENTIFIER": "your.handle.bsky.social",
                "BLUESKY_APP_PASSWORD": "your-app-password"
            }
        }
    }
```
</details>

### Running Locally

#### Install Libraries
```
uv pip install -e .
```

### Running 
After connecting Claude client with the MCP tool via json file and installing the packages, Claude should see the server's mcp tools:

You can run the sever yourself via:
In bluesky_mcp repo: 
```
uv run src/bluesky_mcp/server.py
```

*if you want to run the server inspector along with the server: 
```
npx @modelcontextprotocol/inspector uv --directory C:\\Users\\{INSERT_USER}\\YOUR\\PATH\\TO\\bluesky-mcp run src/bluesky_mcp/server.py
```

## Available Tools

The server implements two tools:
- `get-profile`: Get detailed profile information for a BlueSky user
- `get-follows`: Get a list of accounts that a specified user follows

### get-profile

Retrieves detailed profile information for a given BlueSky user.

**Input Schema:**
```json
{
    "handle": {
        "type": "string",
        "description": "The user's handle (e.g., 'alice.bsky.social')"
    }
}
```

**Example Response:**
```
Profile information for alice.bsky.social:

Handle: alice.bsky.social
Display Name: Alice
Description: Just a BlueSky user sharing thoughts
Followers: 1234
Following: 567
Posts: 789
```

### get-follows

Retrieves a list of accounts that a specified user follows, with support for pagination.

**Input Schema:**
```json
{
    "actor": {
        "type": "string",
        "description": "The user's handle (e.g., 'alice.bsky.social')"
    },
    "limit": {
        "type": "integer",
        "description": "Maximum number of results to return",
        "default": 50,
        "minimum": 1,
        "maximum": 100
    },
    "cursor": {
        "type": "string",
        "description": "Pagination cursor",
        "optional": true
    }
}
```

**Example Response:**
```
Follows for alice.bsky.social:

Follows:
Handle: bob.bsky.social
Display Name: Bob
---
Handle: carol.bsky.social
Display Name: Carol
---
Handle: dave.bsky.social
Display Name: Dave
---

More results available. Use cursor: bafygeia...
```

## Error Handling

The server includes comprehensive error handling for various scenarios:

- Authentication failures
- Rate limiting
- Network connectivity issues
- Invalid parameters
- Timeout handling
- Malformed responses

Error messages are returned in a clear, human-readable format.

## Prerequisites

- Python 3.12 or higher
- httpx
- mcp

## Authentication

To use this MCP server, you need to:
1. Create a BlueSky account if you don't have one
2. Generate an App Password in your BlueSky account settings
3. Set the following environment variables:
   - `BLUESKY_IDENTIFIER`: Your BlueSky handle (e.g., "username.bsky.social")
   - `BLUESKY_APP_PASSWORD`: Your generated App Password

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License
This MCP server is licensed under the MIT License. 
This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.
