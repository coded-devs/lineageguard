"""
OpenMetadata REST API Client wrapper.
Provides authenticated, read-only access to OpenMetadata entities and lineage.
"""

import os
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

class OpenMetadataClient:
    def __init__(self):
        load_dotenv()
        url = os.getenv("OPENMETADATA_URL")
        token = os.getenv("OPENMETADATA_TOKEN")
        
        if not url or not token:
            raise RuntimeError(
                "[ERROR] Missing OPENMETADATA_URL or OPENMETADATA_TOKEN in .env. "
                "Did you create a .env file from .env.example with your PAT?"
            )
            
        self.url = url
        self.token = token
        
        self.client = httpx.Client(
            base_url=self.url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json"
            },
            timeout=10.0
        )
        
    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Makes a GET request to the given path relative to base_url."""
        try:
            resp = self.client.get(path, params=params)
        except httpx.TimeoutException:
            raise RuntimeError(
                f"[ERROR] OpenMetadataClient.get(): Timeout at {path}. "
                "OpenMetadata may be down; check `docker compose ps`."
            )
            
        if resp.status_code == 401:
            raise RuntimeError(
                f"[ERROR] OpenMetadataClient.get(): 401 Unauthorized at {resp.url}. "
                "Check OPENMETADATA_TOKEN in .env."
            )
        elif resp.status_code == 404:
            raise RuntimeError(
                f"[ERROR] OpenMetadataClient.get(): 404 Not Found at {resp.url}. "
                "Entity may not exist \u2014 did you run seed.py?"
            )
        elif resp.status_code not in (200, 201):
            body_snippet = resp.text[:200]
            raise RuntimeError(
                f"[ERROR] OpenMetadataClient.get() failed: {resp.request.method} {resp.url} "
                f"returned {resp.status_code}. \nBody: {body_snippet}"
            )
            
        return resp.json()
        
    def get_entity_by_fqn(self, entity_type: str, fqn: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convenience wrapper to fetch an entity by its Fully Qualified Name."""
        params = {"fields": ",".join(fields)} if fields else None
        return self.get(f"{entity_type}/name/{fqn}", params=params)
        
    def get_lineage(self, entity_type: str, entity_id: str, upstream_depth: int = 0, downstream_depth: int = 5) -> Dict[str, Any]:
        """Fetches upstream and downstream lineage graph for a given entity ID."""
        params = {
            "upstreamDepth": upstream_depth,
            "downstreamDepth": downstream_depth
        }
        return self.get(f"lineage/{entity_type}/{entity_id}", params=params)

    def close(self) -> None:
        """Closes the internal httpx client connection pool."""
        self.client.close()
        
    def __enter__(self):
        return self
        
    def __exit__(self, type, value, traceback):
        self.close()

if __name__ == "__main__":
    try:
        with OpenMetadataClient() as client:
            version_info = client.get("system/version")
            version_str = version_info.get("version", "Unknown")
            print(f"[OK] Connected to OpenMetadata version: {version_str}")
            
            fqn = "Snowflake.analytics_db.dbt_schema.fct_orders"
            fct_orders = client.get_entity_by_fqn("tables", fqn, fields=["tags", "owners"])
            
            tags = fct_orders.get("tags", [])
            owners = fct_orders.get("owners", [])
            
            tier_tag = "none"
            glossary_term = "none"
            
            for tag in tags:
                fqn_val = tag.get("tagFQN", "")
                if fqn_val.startswith("Tier."):
                    tier_tag = fqn_val
                elif tag.get("source") == "Glossary":
                    glossary_term = fqn_val
                    
            owner_name = owners[0].get("name") if owners else "unowned"
            
            print("[OK] Fetched fct_orders")
            print(f"  tier tag: {tier_tag}")
            print(f"  owner: {owner_name}")
            print(f"  glossary: {glossary_term}")
            
    except RuntimeError as err:
        print(err)
        exit(1)
