"""
Output formatters for rendering AnalysisResult as JSON and Markdown.
"""

import json
import os
from datetime import datetime, timezone
from lineageguard.ranker import AnalysisResult


def to_json(result: AnalysisResult) -> dict:
    """
    Returns the analysis result as a plain Python dict suitable for
    json.dumps() or returning from an MCP tool.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    findings_list = []
    for f in result.findings:
        owner_dict = None
        if f.owner_name is not None:
            owner_dict = {
                "name": f.owner_name,
                "team": f.owner_team
            }
            
        finding_dict = {
            "severity": f.severity,
            "entity_fqn": f.entity_fqn,
            "entity_name": f.entity_name,
            "entity_type": f.entity_type,
            "depth": f.depth,
            "business_concept": f.business_concept,
            "tier": f.tier,
            "owner": owner_dict,
            "governance": {
                "contract_violated": f.contract_violated,
                "tier_classification": f.tier
            },
            "reason": f.reason
        }
        findings_list.append(finding_dict)
        
    return {
        "source_entity": result.source_fqn,
        "analysis_timestamp": timestamp,
        "findings": findings_list,
        "findings_summary": result.summary
    }


def to_markdown(result: AnalysisResult) -> str:
    """
    Returns a human-readable Markdown report.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    emoji_map = {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "WARNING": "🟡",
        "INFO": "🔵"
    }
    
    lines = []
    lines.append("# LineageGuard \u2014 Semantic Blast Radius Report")
    lines.append("")
    lines.append(f"**Source entity:** `{result.source_fqn}`")
    lines.append(f"**Analysis time:** {timestamp}")
    lines.append("")
    lines.append("## Summary")
    
    lines.append(f"- 🔴 CRITICAL: {result.summary.get('critical', 0)}")
    lines.append(f"- 🟠 HIGH: {result.summary.get('high', 0)}")
    lines.append(f"- 🟡 WARNING: {result.summary.get('warning', 0)}")
    lines.append(f"- 🔵 INFO: {result.summary.get('info', 0)}")
    lines.append("")
    
    lines.append("## Findings")
    lines.append("")
    
    for idx, f in enumerate(result.findings):
        emoji = emoji_map.get(f.severity, "🔵")
        lines.append(f"### {emoji} {f.severity} \u2014 {f.entity_name} (depth {f.depth})")
        
        if f.business_concept is not None:
            lines.append(f"**Business concept:** {f.business_concept}")
            
        if f.tier is not None:
            lines.append(f"**Tier:** {f.tier}")
            
        if f.owner_name is not None:
            lines.append(f"**Owner:** {f.owner_name}")
            
        cv_str = "yes" if f.contract_violated else "no"
        lines.append(f"**Contract violated:** {cv_str}")
        lines.append("")
        lines.append(f"> {f.reason}")
        
        # Add separator between findings, but not after the last one
        if idx < len(result.findings) - 1:
            lines.append("")
            lines.append("---")
            lines.append("")
            
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    from lineageguard.client import OpenMetadataClient
    from lineageguard.lineage import walk_downstream
    from lineageguard.governance import fetch_signals_for_many
    from lineageguard.ranker import rank_signals
    
    try:
        with OpenMetadataClient() as client:
            source_fqn = "Stripe.stripe_db.public.raw_stripe_data"
            
            entities = walk_downstream(client, source_fqn, entity_type="table", max_depth=5)
            # The API warns and limits depth, that's fine.
            signals = fetch_signals_for_many(client, entities)
            result = rank_signals(source_fqn, signals)
            
            json_dict = to_json(result)
            md_str = to_markdown(result)
            
            json_str = json.dumps(json_dict, indent=2)
            
            print("=== JSON ===")
            print(json_str)
            print("\n=== MARKDOWN ===")
            print(md_str)
            
            os.makedirs("examples", exist_ok=True)
            
            with open("examples/sample_output.json", "w", encoding="utf-8") as f:
                f.write(json_str)
                
            with open("examples/sample_output.md", "w", encoding="utf-8") as f:
                f.write(md_str)
                
            print("\n[OK] Outputs saved to examples/sample_output.json and examples/sample_output.md")
            
    except RuntimeError as err:
        print(err)
        exit(1)
