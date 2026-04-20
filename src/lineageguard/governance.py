"""
Fetches governance signals (tier, owner, glossary terms, data contracts)
for OpenMetadata entities.
"""

from typing import List, Optional
from pydantic import BaseModel

from lineageguard.client import OpenMetadataClient
from lineageguard.lineage import DownstreamEntity, walk_downstream


class OwnerInfo(BaseModel):
    name: str                     # display name of team or user
    type: str                     # "team" or "user"
    team_name: Optional[str] = None  # if the owner is a user, which team they belong to (may be None)


class GovernanceSignals(BaseModel):
    fqn: str                      # pass-through from DownstreamEntity
    name: str
    entity_type: str
    depth: int                    # pass-through
    tier: Optional[str]           # "Tier1", "Tier2", "Tier3", ... or None
    owners: List[OwnerInfo]       # empty list if unowned
    glossary_terms: List[str]     # glossary term FQNs attached
    tags: List[str]               # non-Tier, non-Glossary tag FQNs
    has_contract_fallback: bool   # True if the "DataContracts.FinanceCoreMetrics" tag is present


def fetch_signals_for_entity(client: OpenMetadataClient, entity: DownstreamEntity) -> GovernanceSignals:
    """
    Fetches the full GovernanceSignals for a single downstream entity.
    Uses client.get_entity_by_fqn with fields=["tags","owners"] to retrieve
    the entity with its tags and owner references populated.
    """
    plural_type = f"{entity.entity_type}s"
    try:
        data = client.get_entity_by_fqn(
            entity_type=plural_type,
            fqn=entity.fqn,
            fields=["tags", "owners"]
        )
    except RuntimeError as err:
        print(f"[WARN] Failed to fetch signals for {entity.fqn}: {err}")
        return GovernanceSignals(
            fqn=entity.fqn,
            name=entity.name,
            entity_type=entity.entity_type,
            depth=entity.depth,
            tier=None,
            owners=[],
            glossary_terms=[],
            tags=[],
            has_contract_fallback=False
        )

    raw_tags = data.get("tags")
    if raw_tags is None:
        raw_tags = []

    raw_owners = data.get("owners")
    if raw_owners is None:
        raw_owners = []

    tier = None
    glossary_terms = []
    other_tags = []

    # 1. Process tags to find Tier, Glossary, and Classification tags
    for tag in raw_tags:
        tag_fqn = tag.get("tagFQN", "")
        source = tag.get("source", "")

        if tag_fqn.startswith("Tier."):
            if tier is None:
                # Extract the second part "Tier.Tier1" -> "Tier1"
                parts = tag_fqn.split(".")
                if len(parts) >= 2:
                    tier = parts[1]
                else:
                    tier = tag_fqn
        elif source == "Glossary":
            glossary_terms.append(tag_fqn)
        elif source == "Classification" and not tag_fqn.startswith("Tier."):
            other_tags.append(tag_fqn)

    # 2. Check for the Data Contract fallback tag
    has_contract_fallback = False
    if "DataContracts.FinanceCoreMetrics" in other_tags:
        has_contract_fallback = True

    # 3. Process owners to extract type, name, and resolve team if needed
    owners = []
    for owner_ref in raw_owners:
        owner_type = owner_ref.get("type", "")
        # Prefer displayName, fallback to name
        owner_name = owner_ref.get("displayName")
        if not owner_name:
            owner_name = owner_ref.get("name", "Unknown")

        team_name = None
        if owner_type == "team":
            team_name = owner_name
        elif owner_type == "user":
            user_fqn = owner_ref.get("fullyQualifiedName")
            if user_fqn:
                try:
                    user_data = client.get_entity_by_fqn("users", user_fqn, fields=["teams"])
                    user_teams = user_data.get("teams", [])
                    if len(user_teams) > 0:
                        first_team = user_teams[0]
                        team_name = first_team.get("displayName")
                        if not team_name:
                            team_name = first_team.get("name", "Unknown")
                except RuntimeError as user_err:
                    print(f"[WARN] Could not fetch team for user {user_fqn}: {user_err}")

        owners.append(OwnerInfo(name=owner_name, type=owner_type, team_name=team_name))

    return GovernanceSignals(
        fqn=entity.fqn,
        name=entity.name,
        entity_type=entity.entity_type,
        depth=entity.depth,
        tier=tier,
        owners=owners,
        glossary_terms=glossary_terms,
        tags=other_tags,
        has_contract_fallback=has_contract_fallback
    )


def fetch_signals_for_many(client: OpenMetadataClient, entities: List[DownstreamEntity]) -> List[GovernanceSignals]:
    """
    Loops fetch_signals_for_entity over every downstream entity.
    Prints one [INFO] line per entity showing its fqn and severity-worthy
    signals (tier + glossary count + owner count). Returns the full list.
    Does NOT parallelize — simplicity over speed for demo purposes.
    """
    signals = []
    for entity in entities:
        sig = fetch_signals_for_entity(client, entity)
        signals.append(sig)

        tier_str = sig.tier if sig.tier else "None"
        glossary_count = len(sig.glossary_terms)
        owner_count = len(sig.owners)
        print(f"[INFO] Fetched {sig.fqn} | Tier: {tier_str} | Glossary: {glossary_count} | Owners: {owner_count}")

    return signals


if __name__ == "__main__":
    try:
        with OpenMetadataClient() as client:
            source_fqn = "Stripe.stripe_db.public.raw_stripe_data"
            print(f"[INFO] Finding downstream entities for {source_fqn}...")
            
            entities = walk_downstream(client, source_fqn, entity_type="table", max_depth=5)
            
            print(f"[INFO] Fetching governance signals for {len(entities)} entities...")
            signals = fetch_signals_for_many(client, entities)
            
            print()
            print(f"[OK] Fetched governance signals for {len(entities)} entities")
            print()
            
            # Print details table
            headers = ["Depth", "Entity", "Tier", "Owner", "Glossary", "Contract-fallback"]
            print(f"{headers[0]:<5} | {headers[1]:<37} | {headers[2]:<6} | {headers[3]:<11} | {headers[4]:<15} | {headers[5]}")
            print("-" * 5 + "-+-" + "-" * 37 + "-+-" + "-" * 6 + "-+-" + "-" * 11 + "-+-" + "-" * 15 + "-+-" + "-" * 17)
            
            for sig in signals:
                # Format Depth
                depth_str = str(sig.depth)
                
                # Format Entity Name (truncate to max 37 chars)
                entity_name = sig.name
                if len(entity_name) > 37:
                    entity_name = entity_name[:34] + "..."
                    
                # Format Tier
                tier_str = sig.tier if sig.tier else "—"
                
                # Format Owner
                owner_str = "—"
                if len(sig.owners) > 0:
                    owner_str = sig.owners[0].name
                if len(owner_str) > 11:
                    owner_str = owner_str[:8] + "..."
                    
                # Format Glossary
                glossary_str = "—"
                if len(sig.glossary_terms) > 0:
                    # Extract the last path segment: e.g. "LineageGuardDemo.NetRevenue" -> "NetRevenue"
                    first_term = sig.glossary_terms[0]
                    parts = first_term.split(".")
                    glossary_str = parts[-1] if len(parts) > 0 else first_term
                if len(glossary_str) > 15:
                    glossary_str = glossary_str[:12] + "..."
                    
                # Format Contract-fallback
                contract_str = "yes" if sig.has_contract_fallback else "no"
                
                print(f"{depth_str:<5} | {entity_name:<37} | {tier_str:<6} | {owner_str:<11} | {glossary_str:<15} | {contract_str}")
                
    except RuntimeError as err:
        print(err)
        exit(1)
