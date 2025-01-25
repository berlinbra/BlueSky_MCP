from typing import Any
import asyncio
import httpx
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
import os
import json

BLUESKY_BASE = "https://bsky.social/xrpc/"
API_KEY = os.getenv('BLUESKY_APP_PASSWORD')  # Changed to match TypeScript implementation
IDENTIFIER = os.getenv('BLUESKY_IDENTIFIER')

if not API_KEY or not IDENTIFIER:
    raise ValueError("BLUESKY_APP_PASSWORD and BLUESKY_IDENTIFIER must be set")

server = Server("bluesky_social")

class BlueSkySession:
    def __init__(self):
        self.jwt = None
        self.did = None
        self.refresh_jwt = None
        self.session = None
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def ensure_auth(self, client: httpx.AsyncClient) -> None:
        """Ensure we have a valid authentication token"""
        if not self.jwt:
            try:
                response = await client.post(
                    f"{BLUESKY_BASE}com.atproto.server.createSession",
                    headers=self.headers,
                    json={
                        "identifier": IDENTIFIER,
                        "password": API_KEY
                    }
                )
                
                if response.status_code == 400:
                    error_data = response.json()
                    error_message = error_data.get('message', 'Unknown authentication error')
                    print(f"Authentication error: {error_message}")
                    raise ValueError(f"Authentication failed: {error_message}")
                
                response.raise_for_status()
                auth_data = response.json()
                
                self.jwt = auth_data.get('accessJwt')
                self.refresh_jwt = auth_data.get('refreshJwt')
                self.did = auth_data.get('did')
                
                if not self.jwt or not self.did:
                    raise ValueError("Invalid authentication response")
                
                self.headers["Authorization"] = f"Bearer {self.jwt}"
                
            except Exception as e:
                print(f"Authentication error: {str(e)}")
                raise

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools for BlueSky API integration."""
    return [
        types.Tool(
            name="bluesky_get_profile",
            description="Get a user's profile information",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="bluesky_get_posts",
            description="Get recent posts from a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of posts to return (default 50, max 100)",
                        "default": 50,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor for next page of results",
                    },
                },
            },
        ),
        types.Tool(
            name="bluesky_search_posts",
            description="Search for posts on Bluesky",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of posts to return (default 25, max 100)",
                        "default": 25,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor for next page of results",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="bluesky_get_follows",
            description="Get a list of accounts the user follows",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of follows to return (default 50, max 100)",
                        "default": 50,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor for next page of results",
                    },
                },
            },
        ),
        types.Tool(
            name="bluesky_get_followers",
            description="Get a list of accounts following the user",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of followers to return (default 50, max 100)",
                        "default": 50,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor for next page of results",
                    },
                },
            },
        ),
        types.Tool(
            name="bluesky_get_liked_posts",
            description="Get a list of posts liked by the user",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of liked posts to return (default 50, max 100)",
                        "default": 50,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor for next page of results",
                    },
                },
            },
        ),
        types.Tool(
            name="bluesky_get_personal_feed",
            description="Get your personalized Bluesky feed",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of feed items to return (default 50, max 100)",
                        "default": 50,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor for next page of results",
                    },
                },
            },
        ),
        types.Tool(
            name="bluesky_search_profiles",
            description="Search for Bluesky profiles",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 25, max 100)",
                        "default": 25,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "Pagination cursor for next page of results",
                    },
                },
                "required": ["query"],
            },
        ),
    ]

async def make_bluesky_request(session: BlueSkySession, client: httpx.AsyncClient, endpoint: str, params: dict = None, method: str = "GET", json_data: dict = None) -> dict[str, Any] | str:
    """Make an authenticated request to the BlueSky API with proper error handling."""
    try:
        await session.ensure_auth(client)
        
        if method == "GET":
            response = await client.get(
                f"{BLUESKY_BASE}{endpoint}",
                headers=session.headers,
                params=params,
                timeout=30.0
            )
        else:  # POST
            response = await client.post(
                f"{BLUESKY_BASE}{endpoint}",
                headers=session.headers,
                json=json_data,
                timeout=30.0
            )
            
        if response.status_code == 429:
            return "Rate limit exceeded. Please try again later."
        elif response.status_code == 401:
            session.jwt = None
            return "Authentication failed. Please try again."
            
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        return f"Error: {str(e)}"

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    if not arguments:
        arguments = {}  # Empty dict for tools that don't require arguments
    
    session = BlueSkySession()
    
    async with httpx.AsyncClient() as client:
        try:
            if name == "bluesky_get_profile":
                response = await make_bluesky_request(
                    session, client,
                    "app.bsky.actor.getProfile",
                    {"actor": IDENTIFIER}
                )

            elif name == "bluesky_get_posts":
                limit = arguments.get("limit", 50)
                cursor = arguments.get("cursor")
                response = await make_bluesky_request(
                    session, client,
                    "app.bsky.feed.getAuthorFeed",
                    {"actor": IDENTIFIER, "limit": limit, "cursor": cursor}
                )

            elif name == "bluesky_search_posts":
                query = arguments.get("query")
                if not query:
                    return [types.TextContent(type="text", text="Missing required argument: query")]
                limit = arguments.get("limit", 25)
                cursor = arguments.get("cursor")
                response = await make_bluesky_request(
                    session, client,
                    "app.bsky.feed.searchPosts",
                    {"q": query, "limit": limit, "cursor": cursor}
                )

            elif name == "bluesky_get_follows":
                limit = arguments.get("limit", 50)
                cursor = arguments.get("cursor")
                response = await make_bluesky_request(
                    session, client,
                    "app.bsky.graph.getFollows",
                    {"actor": IDENTIFIER, "limit": limit, "cursor": cursor}
                )

            elif name == "bluesky_get_followers":
                limit = arguments.get("limit", 50)
                cursor = arguments.get("cursor")
                response = await make_bluesky_request(
                    session, client,
                    "app.bsky.graph.getFollowers",
                    {"actor": IDENTIFIER, "limit": limit, "cursor": cursor}
                )

            elif name == "bluesky_get_liked_posts":
                limit = arguments.get("limit", 50)
                cursor = arguments.get("cursor")
                response = await make_bluesky_request(
                    session, client,
                    "app.bsky.feed.getActorLikes",
                    {"actor": IDENTIFIER, "limit": limit, "cursor": cursor}
                )

            elif name == "bluesky_get_personal_feed":
                limit = arguments.get("limit", 50)
                cursor = arguments.get("cursor")
                response = await make_bluesky_request(
                    session, client,
                    "app.bsky.feed.getTimeline",
                    {"limit": limit, "cursor": cursor}
                )

            elif name == "bluesky_search_profiles":
                query = arguments.get("query")
                if not query:
                    return [types.TextContent(type="text", text="Missing required argument: query")]
                limit = arguments.get("limit", 25)
                cursor = arguments.get("cursor")
                response = await make_bluesky_request(
                    session, client,
                    "app.bsky.actor.searchActors",
                    {"q": query, "limit": limit, "cursor": cursor}
                )

            else:
                return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

            if isinstance(response, str):
                return [types.TextContent(type="text", text=response)]
            
            return [types.TextContent(type="text", text=json.dumps(response, indent=2))]

        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="bluesky_social",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())