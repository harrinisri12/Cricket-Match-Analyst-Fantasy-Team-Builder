"""
MCP Client Tools for Cricket Match Analyst & Fantasy Team Builder.
Communicates with the local MCP Server (mcp_server/server.py) over Model Context Protocol (MCP) using stdio transport.
Does NOT directly query CricketData.org from this file.
"""

import os
import sys
import json
import asyncio
import concurrent.futures
from typing import Optional, Dict, Any, List
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

# Base path for rules knowledge document
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RULES_TXT = os.path.join(DATA_DIR, "rules.txt")
SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server", "server.py")


def is_mcp_configured() -> bool:
    """Check if MCP server script exists and CRICKETDATA_API_KEY is configured."""
    return os.path.exists(SERVER_SCRIPT) and bool(os.getenv("CRICKETDATA_API_KEY"))


async def _async_call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute tool call over MCP stdio protocol."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    cmd = os.getenv("MCP_CRICKET_SERVER_COMMAND")
    if cmd:
        parts = cmd.split()
        exec_cmd = parts[0]
        exec_args = parts[1:]
    else:
        exec_cmd = sys.executable
        exec_args = [SERVER_SCRIPT]

    server_params = StdioServerParameters(
        command=exec_cmd,
        args=exec_args,
        env=os.environ.copy()
    )

    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                
                # Check for structured or content output
                if hasattr(result, "structured_content") and result.structured_content:
                    if isinstance(result.structured_content, dict) and "result" in result.structured_content:
                        return result.structured_content["result"]
                    return result.structured_content

                if result.content:
                    first_text = result.content[0].text
                    try:
                        return json.loads(first_text)
                    except Exception:
                        return {"result": first_text, "status": "success", "found": True}

                return {
                    "status": "unavailable",
                    "message": "MCP Server returned empty response.",
                    "found": False
                }
    except Exception as e:
        return {
            "status": "unavailable",
            "message": f"MCP connection error: {str(e)}",
            "found": False
        }


def _call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous wrapper for MCP stdio client tool calls."""
    if not is_mcp_configured():
        return {
            "status": "unavailable",
            "message": "Cricket statistics are currently unavailable because no MCP cricket statistics provider is configured.",
            "found": False,
            "mcp_configured": False
        }

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, _async_call_mcp_tool(tool_name, arguments)).result()
    else:
        return asyncio.run(_async_call_mcp_tool(tool_name, arguments))


# ==============================================================================
# 1. MCP CRICKET STATISTICAL TOOLS (LangChain Tool Wrappers)
# ==============================================================================

@tool
def player_stats(player: str, format: str = "T20", season: Optional[str] = None, venue: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch comprehensive batting and bowling statistics for a cricket player from CricketData.org via MCP.

    Args:
        player: Name of the player (e.g. 'Virat Kohli', 'Jasprit Bumrah')
        format: Match format (default: 'T20')
        season: Specific season or time frame (optional)
        venue: Match venue or stadium (optional)
    """
    args = {"player": player, "format": format}
    if season:
        args["season"] = season
    if venue:
        args["venue"] = venue

    return _call_mcp_tool("player_stats", args)


@tool
def head_to_head(entity: str, opponent: str, format: str = "T20", venue: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch historical head-to-head match records between two teams or player performance against a specific opponent via MCP.

    Args:
        entity: First team or player name (e.g. 'CSK' or 'Virat Kohli')
        opponent: Opposing team or player name (e.g. 'MI' or 'Jasprit Bumrah')
        format: Match format (default: 'T20')
        venue: Match venue or stadium (optional)
    """
    args = {"entity": entity, "opponent": opponent, "format": format}
    if venue:
        args["venue"] = venue

    return _call_mcp_tool("head_to_head", args)


@tool
def venue_stats(venue: str, format: str = "T20", season: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch venue pitch conditions, average first innings score, pace vs spin wicket split, and chasing/defending win rates via MCP.

    Args:
        venue: Stadium or ground name (e.g. 'Chepauk', 'Wankhede Stadium')
        format: Match format (default: 'T20')
        season: Optional season filter
    """
    args = {"venue": venue, "format": format}
    if season:
        args["season"] = season

    return _call_mcp_tool("venue_stats", args)


@tool
def match_info(team1: str, team2: str) -> Dict[str, Any]:
    """
    Retrieve real match information, schedule, squads, and playing status between two teams from CricketData.org via MCP.

    Args:
        team1: First team name (e.g. 'CSK', 'India')
        team2: Second team name (e.g. 'MI', 'Australia')
    """
    args = {"team1": team1, "team2": team2}
    return _call_mcp_tool("match_info", args)


@tool
def fantasy_credits(match_id: str) -> Dict[str, Any]:
    """
    Retrieve real player fantasy credits, roles, and fantasy points from CricketData.org Fantasy API via MCP for a given match ID.

    Args:
        match_id: Valid CricketData match ID
    """
    args = {"match_id": match_id}
    return _call_mcp_tool("fantasy_credits", args)


CRICKET_TOOLS = [player_stats, head_to_head, venue_stats, match_info, fantasy_credits]


# ==============================================================================
# 2. RAG KNOWLEDGE BASE RETRIEVAL (data/rules.txt)
# ==============================================================================

def load_rules_sections() -> List[Dict[str, str]]:
    """Parse data/rules.txt into structured sections."""
    if not os.path.exists(RULES_TXT):
        return []
    with open(RULES_TXT, mode="r", encoding="utf-8") as f:
        content = f.read()

    sections = []
    raw_sections = content.split("=== SECTION: ")
    for sec in raw_sections:
        if not sec.strip():
            continue
        parts = sec.split(" ===", 1)
        if len(parts) == 2:
            title = parts[0].strip()
            body = parts[1].strip()
            sections.append({
                "title": title,
                "content": body,
                "full_text": f"Section: {title}\n{body}"
            })
    return sections


def search_rules(query: str, top_k: int = 2) -> List[Dict[str, str]]:
    """
    Retrieve top matching rule sections from data/rules.txt using keyword and title relevance scoring.
    """
    import re
    sections = load_rules_sections()
    if not sections:
        return []

    q_words = set(re.findall(r'\w+', query.lower()))
    scored_sections = []

    for sec in sections:
        sec_text = (sec["title"] + " " + sec["content"]).lower()
        sec_words = set(re.findall(r'\w+', sec_text))

        overlap = len(q_words.intersection(sec_words))
        title_words = set(re.findall(r'\w+', sec["title"].lower()))
        title_overlap = len(q_words.intersection(title_words))
        score = overlap + (title_overlap * 3)

        if "drs" in q_words and "drs" in sec_text:
            score += 5
        if "umpire" in q_words and "umpire" in sec_text:
            score += 5
        if "lbw" in q_words and "lbw" in sec_text:
            score += 5
        if "free hit" in query.lower() and "free hit" in sec_text:
            score += 5
        if "no-ball" in query.lower() or "no ball" in query.lower():
            if "no ball" in sec_text:
                score += 5
        if "wide" in q_words and "wide" in sec_text:
            score += 5
        if "powerplay" in q_words and "powerplay" in sec_text:
            score += 5
        if "super over" in query.lower() and "super over" in sec_text:
            score += 5
        if "impact player" in query.lower() and "impact player" in sec_text:
            score += 5
        if "role" in q_words or "keeper" in q_words or "bowler" in q_words or "batsman" in q_words:
            if "role" in sec_text:
                score += 4
        if "fantasy" in q_words or "credits" in q_words or "points" in q_words:
            if "fantasy" in sec_text:
                score += 6

        scored_sections.append((score, sec))

    scored_sections.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_sections[:top_k]]
