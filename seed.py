import os
import json
import httpx
from typing import Dict, Any, List
from dotenv import load_dotenv

def get_client() -> httpx.Client:
    """Initialize and return an httpx Client configured for OpenMetadata."""
    url = os.getenv("OPENMETADATA_URL")
    token = os.getenv("OPENMETADATA_TOKEN")
    
    if not url or not token:
        print("[ERROR] Missing OPENMETADATA_URL or OPENMETADATA_TOKEN in .env")
        exit(1)
        
    return httpx.Client(
        base_url=url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        timeout=10.0
    )

def put_entity(client: httpx.Client, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Idempotently create or update an entity in OpenMetadata using PUT."""
    resp = client.put(endpoint, json=payload)
    if resp.status_code not in (200, 201):
        print(f"[ERROR] Failed to create entity at {endpoint}")
        print(f"Payload: {json.dumps(payload)}")
        print(f"Response: {resp.status_code} - {resp.text}")
        exit(1)
    return resp.json()

def seed_team(client: httpx.Client) -> Dict[str, Any]:
    """Create the Finance Team for ownership."""
    print("[INFO] Creating Finance Team...")
    return put_entity(client, "/teams", {
        "name": "finance_team",
        "displayName": "Finance",
        "description": "Core Finance Data Team",
        "teamType": "Group"
    })

def seed_glossary_and_terms(client: httpx.Client, finance_team: Dict[str, Any]) -> Dict[str, Any]:
    """Create the LineageGuard Demo Glossary and its terms."""
    print("[INFO] Creating Glossary...")
    glossary = put_entity(client, "/glossaries", {
        "name": "LineageGuardDemo",
        "displayName": "LineageGuard Demo",
        "description": "Glossary for LineageGuard demo scenario"
    })
    
    print("[INFO] Creating 'Net Revenue' term...")
    term_revenue = put_entity(client, "/glossaryTerms", {
        "name": "NetRevenue",
        "displayName": "Net Revenue",
        "description": "Total revenue after all deductions",
        "glossary": glossary["fullyQualifiedName"],
        "owners": [{"id": finance_team["id"], "type": "team"}]
    })
    
    print("[INFO] Creating 'Customer' term...")
    term_customer = put_entity(client, "/glossaryTerms", {
        "name": "Customer",
        "displayName": "Customer",
        "description": "A paying user of our services",
        "glossary": glossary["fullyQualifiedName"]
    })
    
    return {"NetRevenue": term_revenue, "Customer": term_customer}

def seed_services(client: httpx.Client) -> Dict[str, Any]:
    """Create the database and dashboard services."""
    print("[INFO] Creating Services...")
    stripe_svc = put_entity(client, "/services/databaseServices", {
        "name": "Stripe",
        "serviceType": "Postgres",
        "connection": {
            "config": {
                "type": "Postgres",
                "username": "dummy",
                "hostPort": "localhost:5432",
                "database": "stripe_api"
            }
        }
    })
    
    snowflake_svc = put_entity(client, "/services/databaseServices", {
        "name": "Snowflake",
        "serviceType": "Snowflake",
        "connection": {
            "config": {
                "type": "Snowflake",
                "username": "dummy",
                "account": "dummy",
                "warehouse": "dummy",
                "database": "analytics"
            }
        }
    })
    
    metabase_svc = put_entity(client, "/services/dashboardServices", {
        "name": "Metabase",
        "serviceType": "Metabase",
        "connection": {
            "config": {
                "type": "Metabase",
                "hostPort": "http://localhost:3000",
                "username": "dummy"
            }
        }
    })
    
    return {"Stripe": stripe_svc, "Snowflake": snowflake_svc, "Metabase": metabase_svc}

def seed_databases_schemas(client: httpx.Client, svcs: Dict[str, Any]) -> Dict[str, Any]:
    """Create databases and schemas under the services."""
    print("[INFO] Creating Databases and Schemas...")
    
    stripe_db = put_entity(client, "/databases", {
        "name": "stripe_db",
        "service": svcs["Stripe"]["fullyQualifiedName"]
    })
    stripe_schema = put_entity(client, "/databaseSchemas", {
        "name": "public",
        "database": stripe_db["fullyQualifiedName"]
    })
    
    snowflake_db = put_entity(client, "/databases", {
        "name": "analytics_db",
        "service": svcs["Snowflake"]["fullyQualifiedName"]
    })
    snowflake_schema = put_entity(client, "/databaseSchemas", {
        "name": "dbt_schema",
        "database": snowflake_db["fullyQualifiedName"]
    })
    
    return {"StripeSchema": stripe_schema, "SnowflakeSchema": snowflake_schema}

def seed_fallback_tag(client: httpx.Client) -> Dict[str, Any]:
    """Create a classification and tag to serve as a Data Contract fallback."""
    print("[INFO] Creating Data Contracts classification & fallback tag...")
    classification = put_entity(client, "/classifications", {
        "name": "DataContracts",
        "description": "Data contracts covering expectations and SLAs"
    })
    
    contract_tag = put_entity(client, "/tags", {
        "name": "FinanceCoreMetrics",
        "description": "Finance Core Metrics Data Contract Fallback",
        "classification": classification["fullyQualifiedName"]
    })
    
    return contract_tag

def attempt_data_contract(client: httpx.Client, table: Dict[str, Any], fallback_tag: Dict[str, Any]) -> None:
    """Attempt to create a Data Contract via API; fallback to tags if unsupported."""
    print(f"[INFO] Attempting to create Data Contract for {table['name']}...")
    payload = {
        "name": "FinanceCoreMetrics",
        "entityReference": {"id": table["id"], "type": "table"}
    }
    resp = client.post("/dataContracts", json=payload)
    if resp.status_code in (404, 400):
        print(f"[WARN] Data Contract API unavailable or invalid ({resp.status_code}). Using tag fallback.")
        # Apply the fallback tag (DataContracts.FinanceCoreMetrics) via PUT on the table
        # We need to fetch the existing tags to avoid overwriting them
        current_tags = table.get("tags", [])
        new_tag = {
            "tagFQN": fallback_tag["fullyQualifiedName"],
            "labelType": "Manual",
            "source": "Classification",
            "state": "Confirmed"
        }
        # Add only if not present
        if not any(t.get("tagFQN") == fallback_tag["fullyQualifiedName"] for t in current_tags):
            current_tags.append(new_tag)
            
        update_payload = {
            "name": table["name"],
            "databaseSchema": table["databaseSchema"]["fullyQualifiedName"],
            "tags": current_tags,
            "columns": table.get("columns", [])
        }
        if "owners" in table:
            update_payload["owners"] = table["owners"]
            
        put_entity(client, "/tables", update_payload)
    elif resp.status_code not in (200, 201):
        print(f"[ERROR] Data Contract creation failed with unexpected error: {resp.status_code} - {resp.text}")
    else:
        print("[INFO] Data Contract created successfully.")

def seed_tables(client: httpx.Client, schemas: Dict[str, Any], team: Dict[str, Any], terms: Dict[str, Any]) -> Dict[str, Any]:
    """Create tables with accurate tags, owners, and properly formatted columns."""
    print("[INFO] Creating Tables...")
    
    # 1. raw_stripe_data (no tier)
    raw_stripe = put_entity(client, "/tables", {
        "name": "raw_stripe_data",
        "databaseSchema": schemas["StripeSchema"]["fullyQualifiedName"],
        "columns": [
            {"name": "charge_id", "dataType": "VARCHAR", "dataLength": 64},
            {"name": "revenue_cents", "dataType": "INT"},
            {"name": "customer_id", "dataType": "VARCHAR", "dataLength": 36},
            {"name": "created_at", "dataType": "TIMESTAMP"}
        ]
    })
    
    # 2. stg_stripe_charges
    stg_stripe = put_entity(client, "/tables", {
        "name": "stg_stripe_charges",
        "databaseSchema": schemas["SnowflakeSchema"]["fullyQualifiedName"],
        "columns": [
            {"name": "charge_id", "dataType": "VARCHAR", "dataLength": 64},
            {"name": "revenue_cents", "dataType": "INT"},
            {"name": "customer_id", "dataType": "VARCHAR", "dataLength": 36},
            {"name": "charge_date", "dataType": "DATE"}
        ]
    })
    
    # 3. fct_orders (Tier 1, Finance owner, Net Revenue term)
    fct_orders = put_entity(client, "/tables", {
        "name": "fct_orders",
        "databaseSchema": schemas["SnowflakeSchema"]["fullyQualifiedName"],
        "owners": [{"id": team["id"], "type": "team"}],
        "tags": [
            {"tagFQN": "Tier.Tier1", "labelType": "Manual", "source": "Classification", "state": "Confirmed"},
            {"tagFQN": terms["NetRevenue"]["fullyQualifiedName"], "labelType": "Manual", "source": "Glossary", "state": "Confirmed"}
        ],
        "columns": [
            {"name": "order_id", "dataType": "VARCHAR", "dataLength": 64},
            {"name": "revenue_cents", "dataType": "INT"},
            {"name": "customer_id", "dataType": "VARCHAR", "dataLength": 36},
            {"name": "order_date", "dataType": "DATE"}
        ]
    })
    
    # 4. dim_customers (Tier 2, Customer term)
    dim_customers = put_entity(client, "/tables", {
        "name": "dim_customers",
        "databaseSchema": schemas["SnowflakeSchema"]["fullyQualifiedName"],
        "tags": [
            {"tagFQN": "Tier.Tier2", "labelType": "Manual", "source": "Classification", "state": "Confirmed"},
            {"tagFQN": terms["Customer"]["fullyQualifiedName"], "labelType": "Manual", "source": "Glossary", "state": "Confirmed"}
        ],
        "columns": [
            {"name": "customer_id", "dataType": "VARCHAR", "dataLength": 36},
            {"name": "name", "dataType": "VARCHAR", "dataLength": 255},
            {"name": "email", "dataType": "VARCHAR", "dataLength": 320},
            {"name": "created_at", "dataType": "TIMESTAMP"}
        ]
    })
    
    return {
        "raw_stripe_data": raw_stripe,
        "stg_stripe_charges": stg_stripe,
        "fct_orders": fct_orders,
        "dim_customers": dim_customers
    }

def seed_dashboards(client: httpx.Client, svcs: Dict[str, Any]) -> Dict[str, Any]:
    """Create executive and marketing dashboards with specific tiers."""
    print("[INFO] Creating Dashboards...")
    
    exec_dash = put_entity(client, "/dashboards", {
        "name": "executive_revenue_dashboard",
        "displayName": "Executive Revenue Dashboard",
        "service": svcs["Metabase"]["fullyQualifiedName"],
        "tags": [
            {"tagFQN": "Tier.Tier1", "labelType": "Manual", "source": "Classification", "state": "Confirmed"}
        ]
    })
    
    marketing_dash = put_entity(client, "/dashboards", {
        "name": "marketing_attribution_dashboard",
        "displayName": "Marketing Attribution Dashboard",
        "service": svcs["Metabase"]["fullyQualifiedName"],
        "tags": [
            {"tagFQN": "Tier.Tier3", "labelType": "Manual", "source": "Classification", "state": "Confirmed"}
        ]
    })
    
    return {"executive_dash": exec_dash, "marketing_dash": marketing_dash}

def seed_lineage(client: httpx.Client, tables: Dict[str, Any], dashboards: Dict[str, Any]):
    """Draw the exact 5 directed lineage edges required."""
    print("[INFO] Drawing Lineage Edges...")
    
    def put_lineage_edge(from_node: Dict[str, Any], from_type: str, to_node: Dict[str, Any], to_type: str):
        print(f"[INFO] Lineage Edge: {from_node['name']} -> {to_node['name']}")
        payload = {
            "edge": {
                "fromEntity": {"id": from_node["id"], "type": from_type},
                "toEntity": {"id": to_node["id"], "type": to_type}
            }
        }
        resp = client.put("/lineage", json=payload)
        if resp.status_code not in (200, 201):
            print(f"[ERROR] Failed to draw lineage from {from_node['name']} to {to_node['name']}")
            print(resp.text)
    
    # 1. raw_stripe_data -> stg_stripe_charges
    put_lineage_edge(tables["raw_stripe_data"], "table", tables["stg_stripe_charges"], "table")
    # 2. stg_stripe_charges -> fct_orders
    put_lineage_edge(tables["stg_stripe_charges"], "table", tables["fct_orders"], "table")
    # 3. fct_orders -> Executive Revenue Dashboard
    put_lineage_edge(tables["fct_orders"], "table", dashboards["executive_dash"], "dashboard")
    # 4. fct_orders -> marketing_attribution_dashboard
    put_lineage_edge(tables["fct_orders"], "table", dashboards["marketing_dash"], "dashboard")
    # 5. raw_stripe_data -> dim_customers
    put_lineage_edge(tables["raw_stripe_data"], "table", tables["dim_customers"], "table")

def main():
    print("[INFO] Starting LineageGuard Demo Seeder...")
    load_dotenv()
    
    with get_client() as client:
        # Phase 1: Organizational & Governance Entities
        team = seed_team(client)
        terms = seed_glossary_and_terms(client, team)
        
        # Phase 2: Technical Service Hierarchy
        svcs = seed_services(client)
        schemas = seed_databases_schemas(client, svcs)
        
        # Phase 3: Data Assets (Tables and Dashboards)
        tables = seed_tables(client, schemas, team, terms)
        dashboards = seed_dashboards(client, svcs)
        
        # Phase 4: Data Contract check
        fallback_tag = seed_fallback_tag(client)
        attempt_data_contract(client, tables["fct_orders"], fallback_tag)
        
        # Phase 5: Build Lineage Graph
        seed_lineage(client, tables, dashboards)
        
    print("[INFO] Seed completed successfully!")

if __name__ == "__main__":
    main()
