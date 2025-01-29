from typing import Any
import asyncio
import json
import os
from atproto import Client
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

API_KEY = os.getenv('BLUESKY_APP_PASSWORD')
IDENTIFIER = os.getenv('BLUESKY_IDENTIFIER')

# if not API_KEY or not IDENTIFIER:
#     raise ValueError("BLUESKY_APP_PASSWORD and BLUESKY_IDENTIFIER must be set")

server = Server("bluesky_social")

class BlueSkyClient:
    def __init__(self):
        self.client = None

    async def ensure_client(self):
        """Ensure we have an authenticated client"""
        if not self.client:
            self.client = Client()
            profile = await asyncio.to_thread(
                self.client.login, 
                IDENTIFIER, 
                API_KEY
            )
            if not profile:
                raise ValueError("Failed to authenticate with BlueSky")

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

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    if not arguments:
        arguments = {}
    
    bluesky = BlueSkyClient()
    await bluesky.ensure_client()
    
    try:
        if name == "bluesky_get_profile":
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.actor.get_profile,
                {'actor': IDENTIFIER}
            )

        elif name == "bluesky_get_posts":
            limit = arguments.get("limit", 50)
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.feed.get_author_feed,
                {'actor': IDENTIFIER, 'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_search_posts":
            query = arguments.get("query")
            if not query:
                return [types.TextContent(type="text", text="Missing required argument: query")]
            limit = arguments.get("limit", 25)
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.feed.search_posts,
                {'q': query, 'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_get_follows":
            limit = arguments.get("limit", 50)
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.graph.get_follows,
                {'actor': IDENTIFIER, 'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_get_followers":
            limit = arguments.get("limit", 50)
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.graph.get_followers,
                {'actor': IDENTIFIER, 'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_get_liked_posts":
            limit = arguments.get("limit", 50)
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.feed.get_likes,
                {'uri': IDENTIFIER, 'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_get_personal_feed":
            limit = arguments.get("limit", 50)
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.feed.get_timeline,
                {'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_search_profiles":
            query = arguments.get("query")
            if not query:
                return [types.TextContent(type="text", text="Missing required argument: query")]
            limit = arguments.get("limit", 25)
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.actor.search_actors,
                {'term': query, 'limit': limit, 'cursor': cursor}
            )

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        return [types.TextContent(type="text", text=json.dumps(response.model_dump(), indent=2))]

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