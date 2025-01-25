from typing import Any
import asyncio
import httpx
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
import os

BLUESKY_BASE = "https://bsky.social/xrpc/"
API_KEY = os.getenv('BLUESKY_APP_PASSWORD')
IDENTIFIER = os.getenv('BLUESKY_IDENTIFIER')

if not API_KEY or not IDENTIFIER:
    raise ValueError("Missing BLUESKY_APP_PASSWORD or BLUESKY_IDENTIFIER environment variables")

server = Server("bluesky_social")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools for BlueSky API integration.
    Each tool specifies its arguments using JSON Schema validation.
    """
    return [
        types.Tool(
            name="get-profile",
            description="Get detailed profile information for a BlueSky user",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {
                        "type": "string",
                        "description": "The user's handle (e.g., 'alice.bsky.social')",
                    },
                },
                "required": ["handle"],
            },
        ),
        types.Tool(
            name="get-follows",
            description="Get a list of accounts that a BlueSky user follows",
            inputSchema={
                "type": "object",
                "properties": {
                    "actor": {
                        "type": "string",
                        "description": "The user's handle (e.g., 'alice.bsky.social')",
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
                    }
                },
                "required": ["actor"],
            },
        ),
    ]

class BlueSkySession:
    def __init__(self):
        self.session = None
        self.jwt = None
        self.refresh_jwt = None

    async def ensure_auth(self, client: httpx.AsyncClient) -> None:
        """Ensure we have a valid authentication token"""
        if not self.jwt:
            response = await client.post(
                f"{BLUESKY_BASE}com.atproto.server.createSession",
                json={
                    "identifier": IDENTIFIER,
                    "password": API_KEY
                }
            )
            response.raise_for_status()
            auth_data = response.json()
            self.jwt = auth_data['accessJwt']
            self.refresh_jwt = auth_data['refreshJwt']

async def make_bluesky_request(client: httpx.AsyncClient, endpoint: str, params: dict = None, session: BlueSkySession = None) -> dict[str, Any] | str:
    """Make an authenticated request to the BlueSky API with proper error handling."""
    if session:
        await session.ensure_auth(client)
        client.headers["Authorization"] = f"Bearer {session.jwt}"

    try:
        response = await client.get(
            f"{BLUESKY_BASE}{endpoint}",
            params=params,
            timeout=30.0
        )
        
        if response.status_code == 429:
            return "Rate limit exceeded. Please try again later."
        elif response.status_code == 401:
            return "Authentication failed. Please check your credentials."
        
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        return "Request timed out after 30 seconds."
    except httpx.ConnectError:
        return "Failed to connect to BlueSky API. Please check your internet connection."
    except httpx.HTTPStatusError as e:
        return f"HTTP error occurred: {str(e)} - Response: {e.response.text}"
    except Exception as e:
        return f"Unexpected error occurred: {str(e)}"

def format_profile(profile_data: dict) -> str:
    """Format profile data into a concise string."""
    try:
        return (
            f"Handle: {profile_data.get('handle', 'N/A')}\\n"
            f"Display Name: {profile_data.get('displayName', 'N/A')}\\n"
            f"Description: {profile_data.get('description', 'N/A')}\\n"
            f"Followers: {profile_data.get('followersCount', 0)}\\n"
            f"Following: {profile_data.get('followsCount', 0)}\\n"
            f"Posts: {profile_data.get('postsCount', 0)}\\n"
            "---"
        )
    except Exception as e:
        return f"Error formatting profile data: {str(e)}"

def format_follows(follows_data: dict) -> str:
    """Format follows data into a concise string."""
    try:
        follows = follows_data.get("follows", [])
        if not follows:
            return "No follows data available"
            
        formatted = ["Follows:"]
        for follow in follows:
            formatted.append(
                f"Handle: {follow.get('handle', 'N/A')}\\n"
                f"Display Name: {follow.get('displayName', 'N/A')}\\n"
                f"---"
            )
        
        cursor = follows_data.get("cursor")
        if cursor:
            formatted.append(f"\\nMore results available. Use cursor: {cursor}")
            
        return "\\n".join(formatted)
    except Exception as e:
        return f"Error formatting follows data: {str(e)}"

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests.
    Tools can fetch BlueSky data and notify clients of changes.
    """
    if not arguments:
        return [types.TextContent(type="text", text="Missing arguments for the request")]
    
    session = BlueSkySession()
    
    if name == "get-profile":
        handle = arguments.get("handle")
        if not handle:
            return [types.TextContent(type="text", text="Missing handle parameter")]

        async with httpx.AsyncClient() as client:
            profile_data = await make_bluesky_request(
                client,
                "app.bsky.actor.getProfile",
                {"actor": handle},
                session
            )

            if isinstance(profile_data, str):
                return [types.TextContent(type="text", text=f"Error: {profile_data}")]

            formatted_profile = format_profile(profile_data)
            profile_text = f"Profile information for {handle}:\\n\\n{formatted_profile}"

            return [types.TextContent(type="text", text=profile_text)]

    elif name == "get-follows":
        actor = arguments.get("actor")
        if not actor:
            return [types.TextContent(type="text", text="Missing actor parameter")]

        limit = arguments.get("limit", 50)
        cursor = arguments.get("cursor")
        
        params = {
            "actor": actor,
            "limit": limit
        }
        if cursor:
            params["cursor"] = cursor

        async with httpx.AsyncClient() as client:
            follows_data = await make_bluesky_request(
                client,
                "app.bsky.graph.getFollows",
                params,
                session
            )

            if isinstance(follows_data, str):
                return [types.TextContent(type="text", text=f"Error: {follows_data}")]

            formatted_follows = format_follows(follows_data)
            follows_text = f"Follows for {actor}:\\n\\n{formatted_follows}"

            return [types.TextContent(type="text", text=follows_text)]
    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="bluesky_social",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())