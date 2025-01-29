from typing import Any, Optional
import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from atproto import Client
from atproto.exceptions import (
    AtProtocolError,
    TokenExpiredError,
    AuthenticationError,
    RateLimitError,
    ServerError
)
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
from functools import wraps

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv('BLUESKY_APP_PASSWORD')
IDENTIFIER = os.getenv('BLUESKY_IDENTIFIER')
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

class BlueSkyError(Exception):
    """Base exception class for BlueSky-related errors."""
    pass

class ConfigurationError(BlueSkyError):
    """Raised when there's an issue with the configuration."""
    pass

class ConnectionError(BlueSkyError):
    """Raised when there's an issue with the connection."""
    pass

class ValidationError(BlueSkyError):
    """Raised when there's an issue with input validation."""
    pass

def validate_environment():
    """Validate required environment variables."""
    if not API_KEY or not IDENTIFIER:
        raise ConfigurationError(
            "Missing required environment variables: "
            "BLUESKY_APP_PASSWORD and BLUESKY_IDENTIFIER must be set"
        )

server = Server("bluesky_social")

class BlueSkyClient:
    def __init__(self):
        self.client = None
        self.last_auth = None
        self.auth_expiry = timedelta(hours=1)  # Token typically expires after 2 hours

    def _should_refresh_auth(self) -> bool:
        """Check if authentication should be refreshed."""
        if not self.last_auth:
            return True
        return datetime.now() - self.last_auth > self.auth_expiry

    async def ensure_client(self):
        """Ensure we have an authenticated client with retry logic."""
        try:
            if not self.client or self._should_refresh_auth():
                self.client = Client()
                for attempt in range(MAX_RETRIES):
                    try:
                        profile = await asyncio.to_thread(
                            self.client.login,
                            IDENTIFIER,
                            API_KEY
                        )
                        if not profile:
                            raise AuthenticationError("Failed to authenticate with BlueSky")
                        self.last_auth = datetime.now()
                        logger.info("Successfully authenticated with BlueSky")
                        break
                    except (AuthenticationError, ConnectionError) as e:
                        if attempt == MAX_RETRIES - 1:
                            raise
                        logger.warning(f"Authentication attempt {attempt + 1} failed: {str(e)}")
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))
        except Exception as e:
            logger.error(f"Error in ensure_client: {str(e)}")
            raise ConnectionError(f"Failed to establish connection: {str(e)}")

def handle_api_errors(func):
    """Decorator to handle API errors consistently."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except TokenExpiredError:
            logger.warning("Token expired, attempting to refresh...")
            if hasattr(args[0], 'ensure_client'):
                await args[0].ensure_client()
            return await func(*args, **kwargs)
        except RateLimitError as e:
            logger.warning(f"Rate limit exceeded: {str(e)}")
            return [types.TextContent(
                type="text",
                text="Rate limit exceeded. Please try again later."
            )]
        except AuthenticationError as e:
            logger.error(f"Authentication error: {str(e)}")
            return [types.TextContent(
                type="text",
                text="Authentication failed. Please check your credentials."
            )]
        except ServerError as e:
            logger.error(f"Server error: {str(e)}")
            return [types.TextContent(
                type="text",
                text="BlueSky server error. Please try again later."
            )]
        except AtProtocolError as e:
            logger.error(f"AT Protocol error: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"BlueSky API error: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return [types.TextContent(
                type="text",
                text="An unexpected error occurred. Please try again later."
            )]
    return wrapper

def validate_limit(limit: Optional[int], default: int = 50, max_limit: int = 100) -> int:
    """Validate and normalize limit parameter."""
    if limit is None:
        return default
    try:
        limit = int(limit)
        if limit < 1:
            return default
        return min(limit, max_limit)
    except (ValueError, TypeError):
        return default

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools for BlueSky API integration."""
    try:
        validate_environment()
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
    except ConfigurationError as e:
        logger.error(f"Configuration error in handle_list_tools: {str(e)}")
        return []

@server.call_tool()
@handle_api_errors
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests with improved error handling."""
    if not arguments:
        arguments = {}
    
    try:
        validate_environment()
    except ConfigurationError as e:
        return [types.TextContent(type="text", text=str(e))]

    bluesky = BlueSkyClient()
    await bluesky.ensure_client()
    
    try:
        if name == "bluesky_get_profile":
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.actor.get_profile,
                {'actor': IDENTIFIER}
            )

        elif name == "bluesky_get_posts":
            limit = validate_limit(arguments.get("limit"))
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.feed.get_author_feed,
                {'actor': IDENTIFIER, 'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_search_posts":
            query = arguments.get("query")
            if not query:
                raise ValidationError("Missing required argument: query")
            limit = validate_limit(arguments.get("limit"), default=25)
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.feed.search_posts,
                {'q': query, 'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_get_follows":
            limit = validate_limit(arguments.get("limit"))
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.graph.get_follows,
                {'actor': IDENTIFIER, 'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_get_followers":
            limit = validate_limit(arguments.get("limit"))
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.graph.get_followers,
                {'actor': IDENTIFIER, 'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_get_liked_posts":
            limit = validate_limit(arguments.get("limit"))
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.feed.get_likes,
                {'uri': IDENTIFIER, 'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_get_personal_feed":
            limit = validate_limit(arguments.get("limit"))
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.feed.get_timeline,
                {'limit': limit, 'cursor': cursor}
            )

        elif name == "bluesky_search_profiles":
            query = arguments.get("query")
            if not query:
                raise ValidationError("Missing required argument: query")
            limit = validate_limit(arguments.get("limit"), default=25)
            cursor = arguments.get("cursor")
            response = await asyncio.to_thread(
                bluesky.client.app.bsky.actor.search_actors,
                {'term': query, 'limit': limit, 'cursor': cursor}
            )

        else:
            raise ValidationError(f"Unknown tool: {name}")

        return [types.TextContent(type="text", text=json.dumps(response.model_dump(), indent=2))]

    except ValidationError as e:
        return [types.TextContent(type="text", text=str(e))]

async def main():
    """Main entry point with improved error handling."""
    try:
        validate_environment()
        
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
    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise SystemExit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise SystemExit(1)