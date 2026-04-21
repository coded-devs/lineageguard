"""
MCP Server for LineageGuard.
"""
import sys

import json
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from lineageguard.client import OpenMetadataClient
from lineageguard.lineage import walk_downstream, DownstreamEntity
from lineageguard.governance import fetch_signals_for_many, fetch_signals_for_entity
from lineageguard.ranker import rank_signals
from lineageguard.formatter import to_json


server = Server("lineageguard")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="analyze_semantic_impact",
            description=(
                "Analyze the downstream semantic blast radius of a proposed "
                "schema change. Walks OpenMetadata lineage and classifies each downstream "
                "entity as CRITICAL / HIGH / WARNING / INFO based on deterministic "
                "governance signals (tier, owner, glossary, data contracts). Returns "
                "structured findings. This tool is deterministic \u2014 it does not use an LLM "
                "to reason. The LLM calling it should narrate the returned findings in "
                "human language but should NOT invent entities, severities, or signals "
                "not present in the response."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_fqn": {
                        "type": "string",
                        "description": "Fully qualified name of the entity being changed, e.g. 'Stripe.stripe_db.public.raw_stripe_data'"
                    },
                    "change_type": {
                        "type": "string",
                        "enum": ["drop_column", "rename_column", "drop_table"],
                        "description": "Type of schema change being simulated"
                    },
                    "change_details": {
                        "type": "object",
                        "description": "Change-specific parameters: {column_name} for drop_column, {old_name, new_name} for rename_column, empty for drop_table"
                    },
                    "traversal_depth": {
                        "type": "integer",
                        "default": 5,
                        "description": "How many lineage hops to traverse downstream"
                    }
                },
                "required": ["entity_fqn", "change_type"]
            }
        ),
        types.Tool(
            name="get_entity_governance",
            description=(
                "Fetch governance signals (tier, owner, glossary terms, "
                "contract status) for a single OpenMetadata entity by FQN. Use this to "
                "answer follow-up questions about specific entities that appeared in a "
                "previous analyze_semantic_impact response. Deterministic \u2014 no LLM "
                "reasoning involved."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_fqn": {
                        "type": "string",
                        "description": "Fully qualified name of the entity"
                    },
                    "entity_type": {
                        "type": "string",
                        "enum": ["table", "dashboard", "pipeline"],
                        "default": "table"
                    }
                },
                "required": ["entity_fqn"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    sys.stderr.write(f"[MCP] Tool called: {name}\n")
    try:
        if name == "analyze_semantic_impact":
            fqn = arguments["entity_fqn"]
            change_type = arguments["change_type"]
            change_details = arguments.get("change_details", {})
            depth = arguments.get("traversal_depth", 5)

            with OpenMetadataClient() as client:
                entities = walk_downstream(client, fqn, entity_type="table", max_depth=depth)
                signals = fetch_signals_for_many(client, entities)
                result = rank_signals(fqn, signals)
                js = to_json(result)
                js["change_spec"] = {
                    "table_fqn": fqn,
                    "change_type": change_type,
                    "change_details": change_details
                }
            
            sys.stderr.write(f"[MCP] Tool {name} completed successfully.\n")
            return [types.TextContent(type="text", text=json.dumps(js, indent=2))]

        elif name == "get_entity_governance":
            fqn = arguments["entity_fqn"]
            entity_type = arguments.get("entity_type", "table")
            
            with OpenMetadataClient() as client:
                ent_json = client.get_entity_by_fqn(entity_type, fqn)
                entity_id = ent_json["id"]
                downstream_entity = DownstreamEntity(
                    fqn=fqn,
                    name=ent_json.get("name", "unknown"),
                    entity_type=entity_type,
                    entity_id=entity_id,
                    depth=0
                )
                signal = fetch_signals_for_entity(client, downstream_entity)
            
            sys.stderr.write(f"[MCP] Tool {name} completed successfully.\n")
            return [types.TextContent(type="text", text=signal.model_dump_json(indent=2))]
            
        else:
            sys.stderr.write(f"[MCP ERROR] Unknown tool: {name}\n")
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    except RuntimeError as e:
        sys.stderr.write(f"[MCP ERROR] {str(e)}\n")
        return [types.TextContent(type="text", text=json.dumps({
            "error": str(e),
            "hint": "Is OpenMetadata running? Is .env set?"
        }, indent=2))]
    except Exception as e:
        sys.stderr.write(f"[MCP FATAL] {str(e)}\n")
        return [types.TextContent(type="text", text=json.dumps({
            "error": type(e).__name__ + ": " + str(e),
            "hint": "Internal engine error."
        }, indent=2))]


async def run() -> None:
    sys.stderr.write("[MCP] Starting LineageGuard MCP server (stdio)...\n")
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
