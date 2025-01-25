import requests
import os
from typing import Optional, Dict, Any

class BlueSkyAPI:
    def __init__(self):
        self.base_url = "https://bsky.social/xrpc/"
        self.session = None
    
    def _ensure_session(self):
        """Ensure we have an authenticated session"""
        if not self.session:
            # Initialize session with credentials
            self.session = requests.Session()
            # You'll want to set these as environment variables
            identifier = os.getenv("BLUESKY_IDENTIFIER")
            password = os.getenv("BLUESKY_APP_PASSWORD")
            
            if not identifier or not password:
                raise ValueError("BLUESKY_IDENTIFIER and BLUESKY_APP_PASSWORD must be set")
            
            # Authenticate
            auth_response = self.session.post(
                f"{self.base_url}com.atproto.server.createSession",
                json={"identifier": identifier, "password": password}
            )
            auth_response.raise_for_status()
            
            # Set authentication header
            auth_data = auth_response.json()
            self.session.headers.update({
                "Authorization": f"Bearer {auth_data['accessJwt']}"
            })

    def get_profile(self, handle: str) -> Dict[str, Any]:
        """Get a user's profile information"""
        self._ensure_session()
        
        response = self.session.get(
            f"{self.base_url}app.bsky.actor.getProfile",
            params={"actor": handle}
        )
        response.raise_for_status()
        return response.json()

    def get_follows(self, actor: str, limit: int = 50, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Get a list of accounts that a user follows"""
        self._ensure_session()
        
        params = {
            "actor": actor,
            "limit": limit
        }
        if cursor:
            params["cursor"] = cursor
            
        response = self.session.get(
            f"{self.base_url}app.bsky.graph.getFollows",
            params=params
        )
        response.raise_for_status()
        return response.json()

# Initialize the API client
api = BlueSkyAPI()

def get_bluesky_profile(handle: str) -> Dict[str, Any]:
    """Handler for get_bluesky_profile function"""
    return api.get_profile(handle)

def get_bluesky_follows(actor: str, limit: int = 50, cursor: Optional[str] = None) -> Dict[str, Any]:
    """Handler for get_bluesky_follows function"""
    return api.get_follows(actor, limit, cursor)
