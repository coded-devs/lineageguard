"""
Tests for deterministic severity ranking logic.
"""

from lineageguard.ranker import rank_signal, rank_signals
from lineageguard.governance import GovernanceSignals, OwnerInfo


def get_base_signal(name: str = "test_asset") -> GovernanceSignals:
    """Helper to create an empty baseline signal for testing."""
    return GovernanceSignals(
        fqn=f"test.db.schema.{name}",
        name=name,
        entity_type="table",
        depth=1,
        tier=None,
        owners=[],
        glossary_terms=[],
        tags=[],
        has_contract_fallback=False
    )


def test_critical_contract_fallback() -> None:
    signal = get_base_signal()
    signal.has_contract_fallback = True

    finding = rank_signal(signal)

    assert finding.severity == "CRITICAL"
    assert finding.contract_violated is True
    assert "Contract-protected asset" in finding.reason


def test_critical_tier1_with_owner_and_glossary() -> None:
    signal = get_base_signal()
    signal.tier = "Tier1"
    signal.owners = [OwnerInfo(name="Finance", type="team")]
    signal.glossary_terms = ["LineageGuardDemo.NetRevenue"]

    finding = rank_signal(signal)

    assert finding.severity == "CRITICAL"
    assert finding.contract_violated is True
    assert "Tier 1 asset owned by Finance" in finding.reason


def test_critical_tier1_with_owner_only() -> None:
    signal = get_base_signal()
    signal.tier = "Tier1"
    signal.owners = [OwnerInfo(name="Finance", type="team")]

    finding = rank_signal(signal)

    assert finding.severity == "CRITICAL"
    assert finding.contract_violated is False
    assert "Tier 1 asset owned by Finance" in finding.reason


def test_high_tier1_alone() -> None:
    signal = get_base_signal()
    signal.tier = "Tier1"

    finding = rank_signal(signal)

    assert finding.severity == "HIGH"
    assert finding.contract_violated is False
    assert "no additional governance — still business-critical" in finding.reason


def test_high_tier2_with_glossary() -> None:
    signal = get_base_signal()
    signal.tier = "Tier2"
    signal.glossary_terms = ["LineageGuardDemo.Customer"]

    finding = rank_signal(signal)

    assert finding.severity == "HIGH"
    assert "Tier 2 asset backing business concept Customer" in finding.reason


def test_high_owner_plus_glossary_no_tier() -> None:
    signal = get_base_signal()
    signal.owners = [OwnerInfo(name="Finance", type="team")]
    signal.glossary_terms = ["LineageGuardDemo.Revenue"]

    finding = rank_signal(signal)

    assert finding.severity == "HIGH"
    assert "Governed asset: Revenue, owned by Finance" in finding.reason


def test_warning_glossary_only() -> None:
    signal = get_base_signal()
    signal.glossary_terms = ["LineageGuardDemo.Customer"]

    finding = rank_signal(signal)

    assert finding.severity == "WARNING"
    assert "Business concept Customer attached — review with owner" in finding.reason


def test_warning_tier3_only() -> None:
    signal = get_base_signal()
    signal.tier = "Tier3"

    finding = rank_signal(signal)

    assert finding.severity == "WARNING"
    assert "Tier 3 asset — lower priority but worth flagging" in finding.reason


def test_info_no_signals() -> None:
    signal = get_base_signal()

    finding = rank_signal(signal)

    assert finding.severity == "INFO"
    assert "No semantic governance attached" in finding.reason


def test_canonical_demo_graph_ordering() -> None:
    # 1. dim_customers: Tier2, Customer glossary, no owner, no contract
    dim_customers = GovernanceSignals(
        fqn="stg.dim_customers", name="dim_customers", entity_type="table", depth=1,
        tier="Tier2", owners=[], glossary_terms=["Customer"], tags=[], has_contract_fallback=False
    )
    
    # 2. stg_stripe_charges: no signals at all
    stg_stripe_charges = GovernanceSignals(
        fqn="stg.stg_stripe_charges", name="stg_stripe_charges", entity_type="table", depth=1,
        tier=None, owners=[], glossary_terms=[], tags=[], has_contract_fallback=False
    )
    
    # 3. fct_orders: Tier1, Finance owner, Net Revenue glossary, Contract fallback YES
    fct_orders = GovernanceSignals(
        fqn="stg.fct_orders", name="fct_orders", entity_type="table", depth=2,
        tier="Tier1", owners=[OwnerInfo(name="Finance", type="team")], 
        glossary_terms=["NetRevenue"], tags=[], has_contract_fallback=True
    )
    
    # 4. executive_revenue_dashboard: Tier1, no governance otherwise
    executive_revenue_dashboard = GovernanceSignals(
        fqn="dash.executive_revenue_dashboard", name="executive_revenue_dashboard", entity_type="dashboard", depth=3,
        tier="Tier1", owners=[], glossary_terms=[], tags=[], has_contract_fallback=False
    )
    
    # 5. marketing_attribution_dashboard: Tier3, no governance otherwise
    marketing_attribution_dashboard = GovernanceSignals(
        fqn="dash.marketing_attribution_dashboard", name="marketing_attribution_dashboard", entity_type="dashboard", depth=3,
        tier="Tier3", owners=[], glossary_terms=[], tags=[], has_contract_fallback=False
    )
    
    signals = [
        dim_customers,
        stg_stripe_charges,
        fct_orders,
        executive_revenue_dashboard,
        marketing_attribution_dashboard
    ]
    
    result = rank_signals("source.raw_stripe_data", signals)
    
    assert result.summary == {"critical": 1, "high": 2, "warning": 1, "info": 1}
    assert result.findings[0].severity == "CRITICAL"
    assert result.findings[0].entity_name == "fct_orders"
    assert result.findings[-1].severity == "INFO"
    assert result.findings[-1].entity_name == "stg_stripe_charges"
