"""
Local MCP Server for Cricket Match Analyst & Fantasy Team Builder.
Communicates directly with CricketData.org API over Model Context Protocol (MCP) using stdio transport.
"""

import os
import re
import json
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from mcp.server.mcpserver import MCPServer

# Initialize MCP Server
server = MCPServer("CricketDataMCP")

CRICAPI_BASE_URL = "https://api.cricapi.com/v1"


def _cricapi_request(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute an authorized request to CricketData.org API.
    Does not expose or log the raw API key.
    """
    api_key = os.getenv("CRICKETDATA_API_KEY")
    if not api_key:
        return {
            "status": "failure",
            "reason": "CRICKETDATA_API_KEY is not configured in the environment."
        }

    request_params = params.copy() if params else {}
    request_params["apikey"] = api_key

    query_str = urllib.parse.urlencode(request_params)
    url = f"{CRICAPI_BASE_URL}/{endpoint}?{query_str}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CricketMatchAnalyst-MCP/1.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data
    except Exception as e:
        return {
            "status": "failure",
            "reason": f"CricketData API connection error: {str(e)}"
        }


# ==============================================================================
# 1. PLAYER STATS TOOL
# ==============================================================================
@server.tool()
def player_stats(player: str, format: str = "T20", season: Optional[str] = None, venue: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch comprehensive batting and bowling statistics for a cricket player from CricketData.org.

    Args:
        player: Name of the player (e.g. 'Virat Kohli', 'Jasprit Bumrah')
        format: Match format (e.g. 'T20', 'IPL', 'ODI', 'Test')
        season: Optional season filter
        venue: Optional stadium or ground filter
    """
    # Step 1: Search player ID
    search_res = _cricapi_request("players", {"search": player, "offset": 0})
    if search_res.get("status") != "success" or not search_res.get("data"):
        reason = search_res.get("reason", f"Player '{player}' not found on CricketData.org.")
        return {
            "player": player,
            "status": "unavailable",
            "message": f"Could not retrieve statistics: {reason}",
            "found": False
        }

    players_list = search_res.get("data", [])
    # Find closest matching player
    target_player = players_list[0]
    for p in players_list:
        if p.get("name", "").lower() == player.lower():
            target_player = p
            break

    player_id = target_player.get("id")

    # Step 2: Fetch detailed statistics
    info_res = _cricapi_request("players_info", {"id": player_id})
    if info_res.get("status") != "success" or not info_res.get("data"):
        reason = info_res.get("reason", "Player statistics data unavailable.")
        return {
            "player": target_player.get("name", player),
            "player_id": player_id,
            "status": "unavailable",
            "message": f"Could not retrieve statistics for {target_player.get('name')}: {reason}",
            "found": False
        }

    p_data = info_res.get("data", {})
    raw_stats = p_data.get("stats", [])

    # Map requested format to CricAPI format tags
    fmt_clean = format.strip().lower()
    fmt_map = {
        "t20": "t20",
        "t20i": "t20",
        "ipl": "ipl",
        "odi": "odi",
        "test": "test"
    }
    matchtype = fmt_map.get(fmt_clean, "t20")

    # Extract batting & bowling stats for the format
    batting_stats: Dict[str, Any] = {}
    bowling_stats: Dict[str, Any] = {}

    for s in raw_stats:
        if s.get("matchtype", "").strip().lower() == matchtype:
            stat_name = s.get("stat", "").strip().lower()
            val = s.get("value", "").strip()
            if s.get("fn") == "batting":
                batting_stats[stat_name] = val
            elif s.get("fn") == "bowling":
                bowling_stats[stat_name] = val

    # Fallback to IPL if T20 was empty or vice-versa
    if not batting_stats and not bowling_stats:
        alt_type = "ipl" if matchtype == "t20" else "t20"
        for s in raw_stats:
            if s.get("matchtype", "").strip().lower() == alt_type:
                stat_name = s.get("stat", "").strip().lower()
                val = s.get("value", "").strip()
                if s.get("fn") == "batting":
                    batting_stats[stat_name] = val
                elif s.get("fn") == "bowling":
                    bowling_stats[stat_name] = val
        if batting_stats or bowling_stats:
            matchtype = alt_type

    venue_season_note = None
    if venue or season:
        venue_season_note = "CricketData.org provides format-level career aggregates. Specific venue/season filters are not directly provided by the API."

    return {
        "status": "success",
        "found": True,
        "player": p_data.get("name", player),
        "player_id": player_id,
        "country": p_data.get("country"),
        "role": p_data.get("role"),
        "format": matchtype.upper(),
        "batting": {
            "matches": batting_stats.get("m", "-"),
            "innings": batting_stats.get("inn", "-"),
            "runs": batting_stats.get("runs", "-"),
            "average": batting_stats.get("avg", "-"),
            "strike_rate": batting_stats.get("sr", "-"),
            "highest_score": batting_stats.get("hs", "-"),
            "fifties": batting_stats.get("50", "-"),
            "hundreds": batting_stats.get("100", "-")
        },
        "bowling": {
            "matches": bowling_stats.get("m", "-"),
            "innings": bowling_stats.get("inn", "-"),
            "wickets": bowling_stats.get("wkts", "-"),
            "economy": bowling_stats.get("econ", "-"),
            "average": bowling_stats.get("avg", "-"),
            "strike_rate": bowling_stats.get("sr", "-"),
            "best_bowling": bowling_stats.get("bbi", "-")
        },
        "filter_note": venue_season_note,
        "source": "CricketData.org API via MCP"
    }


# ==============================================================================
# 2. HEAD TO HEAD TOOL
# ==============================================================================
@server.tool()
def head_to_head(entity: str, opponent: str, format: str = "T20", venue: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch historical head-to-head match records between two teams or player performance against a specific opponent from CricketData.org.

    Args:
        entity: First team or player name (e.g. 'CSK' or 'Virat Kohli')
        opponent: Opposing team or player name (e.g. 'MI' or 'Jasprit Bumrah')
        format: Match format (default: 'T20')
        venue: Match venue or stadium (optional)
    """
    matches_res = _cricapi_request("currentMatches", {"offset": 0})
    if matches_res.get("status") != "success":
        reason = matches_res.get("reason", "API unavailable")
        return {
            "entity": entity,
            "opponent": opponent,
            "status": "unavailable",
            "message": f"Head-to-head records currently unavailable from CricketData.org: {reason}",
            "found": False
        }

    matches = matches_res.get("data", [])
    relevant_matches = []
    e_low = entity.lower()
    o_low = opponent.lower()

    for m in matches:
        teams = [t.lower() for t in m.get("teams", [])]
        name = m.get("name", "").lower()
        if (e_low in name or any(e_low in t for t in teams)) and (o_low in name or any(o_low in t for t in teams)):
            relevant_matches.append({
                "name": m.get("name"),
                "status": m.get("status"),
                "venue": m.get("venue"),
                "date": m.get("date"),
                "score": m.get("score")
            })

    if relevant_matches:
        return {
            "status": "success",
            "found": True,
            "type": "Head to Head Match Records",
            "entity": entity,
            "opponent": opponent,
            "recent_matches": relevant_matches,
            "source": "CricketData.org API via MCP"
        }

    return {
        "entity": entity,
        "opponent": opponent,
        "status": "unavailable",
        "message": f"Direct historical head-to-head aggregation for '{entity}' vs '{opponent}' is not directly supported by the current CricketData.org API endpoints.",
        "found": False
    }


# ==============================================================================
# 3. VENUE STATS TOOL
# ==============================================================================
@server.tool()
def venue_stats(venue: str, format: str = "T20", season: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch venue pitch dynamics, average score, pace vs spin wicket split, and chasing/defending win rates from CricketData.org.

    Args:
        venue: Stadium or ground name (e.g. 'Chepauk', 'Wankhede Stadium')
        format: Match format (default: 'T20')
        season: Optional season filter
    """
    # CricketData.org does not offer synthetic pitch splits or historical pace/spin metrics
    return {
        "venue": venue,
        "status": "unavailable",
        "message": f"Historical pitch dynamics, pace/spin splits, and chasing percentages for '{venue}' are not directly provided by CricketData.org API. In accordance with zero-fabrication guardrails, these metrics are marked unavailable.",
        "found": False
    }


# ==============================================================================
# 4. MATCH INFORMATION TOOL
# ==============================================================================
@server.tool()
def match_info(team1: str, team2: str) -> Dict[str, Any]:
    """
    Retrieve real match information, schedule, squads, and playing status between two teams from CricketData.org.

    Args:
        team1: First team name (e.g. 'CSK', 'India', 'Australia')
        team2: Second team name (e.g. 'MI', 'South Africa', 'England')
    """
    matches_res = _cricapi_request("currentMatches", {"offset": 0})
    if matches_res.get("status") != "success":
        reason = matches_res.get("reason", "API unavailable")
        return {
            "team1": team1,
            "team2": team2,
            "status": "unavailable",
            "message": f"Could not retrieve match information: {reason}",
            "found": False
        }

    matches = matches_res.get("data", [])
    t1_low = team1.strip().lower()
    t2_low = team2.strip().lower()

    found_match = None
    for m in matches:
        teams = [t.lower() for t in m.get("teams", [])]
        name = m.get("name", "").lower()
        if (t1_low in name or any(t1_low in t for t in teams)) and (t2_low in name or any(t2_low in t for t in teams)):
            found_match = m
            break

    if not found_match:
        return {
            "team1": team1,
            "team2": team2,
            "status": "unavailable",
            "message": f"No active or recent match found between '{team1}' and '{team2}' on CricketData.org.",
            "found": False
        }

    match_id = found_match.get("id")

    # Fetch detailed squads if available
    squad_res = _cricapi_request("match_squad", {"id": match_id})
    squads_data = squad_res.get("data", []) if squad_res.get("status") == "success" else []

    return {
        "status": "success",
        "found": True,
        "match_id": match_id,
        "name": found_match.get("name"),
        "status_text": found_match.get("status"),
        "venue": found_match.get("venue"),
        "date": found_match.get("date"),
        "dateTimeGMT": found_match.get("dateTimeGMT"),
        "teams": found_match.get("teams"),
        "team_info": found_match.get("teamInfo"),
        "score": found_match.get("score"),
        "fantasy_enabled": found_match.get("fantasyEnabled", False),
        "has_squad": found_match.get("hasSquad", False),
        "squads": squads_data,
        "source": "CricketData.org API via MCP"
    }


# ==============================================================================
# 5. FANTASY CREDITS TOOL
# ==============================================================================
@server.tool()
def fantasy_credits(match_id: str) -> Dict[str, Any]:
    """
    Retrieve real player fantasy credits, roles, and fantasy points from CricketData.org Fantasy API for a given match ID.

    Args:
        match_id: Valid CricketData match ID
    """
    # Attempt to query fantasy / squad points endpoints
    res = _cricapi_request("match_points", {"id": match_id})
    if res.get("status") != "success":
        reason = res.get("reason", "Fantasy API unavailable")
        return {
            "match_id": match_id,
            "status": "unavailable",
            "message": f"Fantasy credit data is unavailable for the current CricketData plan ({reason}).",
            "found": False
        }

    data = res.get("data", {})
    totals = data.get("totals", [])

    if not totals:
        return {
            "match_id": match_id,
            "status": "unavailable",
            "message": "Fantasy credit data is unavailable for the current CricketData plan.",
            "found": False
        }

    return {
        "status": "success",
        "found": True,
        "match_id": match_id,
        "players": totals,
        "source": "CricketData.org Fantasy API via MCP"
    }


# ==============================================================================
# SERVER ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    server.run(transport="stdio")
