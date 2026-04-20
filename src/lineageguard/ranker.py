"""
Deterministic severity logic for ranking the impact of schema changes on downstream entities.
"""

from typing import List, Dict, Optional
from pydantic import BaseModel

from lineageguard.governance import GovernanceSignals, OwnerInfo
from lineageguard.lineage import walk_downstream
from lineageguard.client import OpenMetadataClient

class Finding(BaseModel):
    severity: str
    entity_fqn: str
    entity_name: str
    entity_type: str
    depth: int
    business_concept: Optional[str] = None
    tier: Optional[str] = None
    owner_name: Optional[str] = None
    owner_team: Optional[str] = None
    contract_violated: bool
    reason: str


class AnalysisResult(BaseModel):
    source_fqn: str
    findings: List[Finding]
    summary: Dict[str, int]


def rank_signal(signal: GovernanceSignals) -> Finding:
    """
    Classifies a single GovernanceSignals into a Finding with severity
    and a human-readable reason.
    Deterministic. No LLM calls. No network calls.
    """
    # 1. Base property extraction
    business_concept = None
    if len(signal.glossary_terms) > 0:
        business_concept = signal.glossary_terms[0].split(".")[-1]
        
    owner_name = None
    owner_team = None
    if len(signal.owners) > 0:
        first_owner = signal.owners[0]
        owner_name = first_owner.name
        if first_owner.type == "user":
            owner_team = first_owner.team_name
        else:
            owner_team = first_owner.name
            
    # 2. Determine severity and reason
    severity = ""
    reason = ""
    
    # RULE 1 — CRITICAL
    if signal.has_contract_fallback:
        severity = "CRITICAL"
        reason = f"Contract-protected asset: Data Contract 'FinanceCoreMetrics' on {signal.name}."
    elif signal.tier == "Tier1" and len(signal.owners) > 0:
        severity = "CRITICAL"
        reason = f"Tier 1 asset owned by {owner_name}: changes require owner approval."
    elif signal.tier == "Tier1" and len(signal.glossary_terms) > 0:
        severity = "CRITICAL"
        reason = f"Tier 1 asset backing business concept {business_concept}."
        
    # RULE 2 — HIGH
    elif signal.tier == "Tier1":
        severity = "HIGH"
        reason = "Tier 1 asset with no additional governance \u2014 still business-critical."
    elif signal.tier == "Tier2" and len(signal.glossary_terms) > 0:
        severity = "HIGH"
        reason = f"Tier 2 asset backing business concept {business_concept}."
    elif len(signal.owners) > 0 and len(signal.glossary_terms) > 0:
        severity = "HIGH"
        reason = f"Governed asset: {business_concept}, owned by {owner_name}."
        
    # RULE 3 — WARNING
    elif len(signal.glossary_terms) > 0:
        severity = "WARNING"
        reason = f"Business concept {business_concept} attached \u2014 review with owner."
    elif signal.tier in ("Tier2", "Tier3", "Tier4", "Tier5"):
        severity = "WARNING"
        n = signal.tier.replace("Tier", "")
        reason = f"Tier {n} asset \u2014 lower priority but worth flagging."
        
    # RULE 4 — INFO
    else:
        severity = "INFO"
        reason = "No semantic governance attached."

    # 3. Determine contract violated field
    contract_violated = False
    if signal.has_contract_fallback:
        contract_violated = True
    elif severity == "CRITICAL" and signal.tier == "Tier1" and len(signal.owners) > 0 and len(signal.glossary_terms) > 0:
        contract_violated = True
        
    return Finding(
        severity=severity,
        entity_fqn=signal.fqn,
        entity_name=signal.name,
        entity_type=signal.entity_type,
        depth=signal.depth,
        business_concept=business_concept,
        tier=signal.tier,
        owner_name=owner_name,
        owner_team=owner_team,
        contract_violated=contract_violated,
        reason=reason
    )


def rank_signals(source_fqn: str, signals: List[GovernanceSignals]) -> AnalysisResult:
    """
    Classifies every signal, sorts findings by severity then depth then fqn,
    and builds the summary count.
    """
    findings = []
    summary = {"critical": 0, "high": 0, "warning": 0, "info": 0}
    
    for sig in signals:
        finding = rank_signal(sig)
        findings.append(finding)
        summary[finding.severity.lower()] += 1
        
    severity_rank = {"CRITICAL": 0, "HIGH": 1, "WARNING": 2, "INFO": 3}
    
    findings.sort(key=lambda f: (severity_rank[f.severity], f.depth, f.entity_fqn))
    
    return AnalysisResult(
        source_fqn=source_fqn,
        findings=findings,
        summary=summary
    )


if __name__ == "__main__":
    # Import locally to avoid circular dependency problems on module run
    from lineageguard.governance import fetch_signals_for_many
    
    try:
        with OpenMetadataClient() as client:
            source_fqn = "Stripe.stripe_db.public.raw_stripe_data"
            entities = walk_downstream(client, source_fqn, entity_type="table", max_depth=5)
            signals = fetch_signals_for_many(client, entities)
            
            result = rank_signals(source_fqn, signals)
            
            crit = result.summary['critical']
            high = result.summary['high']
            warn = result.summary['warning']
            info = result.summary['info']
            total = len(result.findings)
            
            print(f"[OK] {total} findings: {crit} CRITICAL, {high} HIGH, {warn} WARNING, {info} INFO")
            print()
            
            headers = ["Severity", "Depth", "Entity", "Tier", "Reason"]
            print(f"{headers[0]:<9} | {headers[1]:<5} | {headers[2]:<27} | {headers[3]:<6} | {headers[4]}")
            print("-" * 9 + "-+-" + "-" * 5 + "-+-" + "-" * 27 + "-+-" + "-" * 6 + "-+-" + "-" * 42)
            
            for f in result.findings:
                severity_str = f.severity
                depth_str = str(f.depth)
                
                entity_name = f.entity_name
                if len(entity_name) > 27:
                    entity_name = entity_name[:24] + "..."
                    
                tier_str = f.tier if f.tier else "\u2014"
                
                reason_str = f.reason
                if len(reason_str) > 42:
                    reason_str = reason_str[:39] + "..."
                    
                print(f"{severity_str:<9} | {depth_str:<5} | {entity_name:<27} | {tier_str:<6} | {reason_str}")

    except RuntimeError as err:
        print(err)
        exit(1)
