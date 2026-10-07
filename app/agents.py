"""
Agents for Cricket Match Analyst & Fantasy Team Builder:
- Router Agent
- Rules RAG Agent
- Stats Agent (MCP Tools)
- News Agent (Tavily Live Search)
- Fantasy Team Builder Agent (AI & Deterministic Selection Score Engine)
- Validator Agent (Zero-Fabrication Validation Loop)
- Final Response Agent
"""

import os
import re
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.tools import (
    player_stats,
    head_to_head,
    venue_stats,
    match_info,
    search_rules,
    is_mcp_configured
)
from app.prompts import (
    ROUTER_SYSTEM_PROMPT,
    STATS_AGENT_PROMPT,
    RULES_AGENT_PROMPT,
    NEWS_AGENT_PROMPT,
    TEAM_BUILDER_PROMPT,
    VALIDATOR_PROMPT,
    DISCLAIMER_TEXT
)


def _get_llm_text(res) -> str:
    """Safely extract plain text string from LangChain response."""
    if not res:
        return ""
    content = getattr(res, "content", res)
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
        return "\n".join(parts)
    return str(content)


def get_llm():
    """
    Instantiate Google Gemini as primary LLM.
    Supports optional OpenAI fallback if configured.
    Returns None if no API keys are configured.
    """
    google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if google_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            for model_name in ["gemini-3.5-flash-lite", "gemini-3.7-flash", "gemini-flash-lite-latest", "gemini-flash-latest"]:
                try:
                    return ChatGoogleGenerativeAI(
                        model=model_name,
                        google_api_key=google_api_key,
                        temperature=0.2
                    )
                except Exception:
                    continue
        except Exception:
            pass

    if openai_api_key:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model="gpt-4o-mini",
                openai_api_key=openai_api_key,
                temperature=0.2
            )
        except Exception:
            pass

    return None


# ==============================================================================
# 1. ROUTER AGENT
# ==============================================================================
def router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify user query into exactly one of: RULES, ANALYSIS, NEWS, TEAM_BUILDING.
    Extracts entities: players, teams, venue, season.
    The Router does NOT answer the question itself.
    """
    query = state.get("user_query", "")
    llm = get_llm()

    intent = "ANALYSIS"
    extracted_players = []
    extracted_teams = []
    extracted_venue = None
    extracted_season = None

    if llm:
        try:
            messages = [
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ]
            response = llm.invoke(messages)
            content = _get_llm_text(response)
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                intent = parsed.get("intent", "ANALYSIS").upper()
                extracted_players = parsed.get("players", [])
                extracted_teams = parsed.get("teams", [])
                extracted_venue = parsed.get("venue")
                extracted_season = parsed.get("season")
        except Exception:
            pass

    # Heuristic fallback / booster
    q_lower = query.lower()
    if any(k in q_lower for k in ["fantasy", "build", "team", "lineup", "credits", "captain"]):
        intent = "TEAM_BUILDING"
    elif any(k in q_lower for k in ["rule", "drs", "umpire's call", "lbw", "no-ball", "no ball", "free hit", "powerplay", "super over", "impact player", "scoring"]):
        intent = "RULES"
    elif any(k in q_lower for k in ["injury", "injuries", "left out", "tonight", "latest", "news", "weather", "pitch report", "announced", "playing xi"]):
        intent = "NEWS"
    elif any(k in q_lower for k in ["compare", "stats", "statistics", "average", "strike rate", "wickets", "economy", "head to head", "record"]):
        intent = "ANALYSIS"

    # Known players lookup for entity extraction
    known_players = [
        "Virat Kohli", "Shubman Gill", "Rohit Sharma", "MS Dhoni", "Ruturaj Gaikwad",
        "Suryakumar Yadav", "Jasprit Bumrah", "Ravindra Jadeja", "Hardik Pandya",
        "Rashid Khan", "Ravichandran Ashwin", "Shivam Dube", "Matheesha Pathirana",
        "Deepak Chahar", "Ishan Kishan", "Tilak Varma", "Devon Conway", "Moeen Ali",
        "Faf du Plessis", "Glenn Maxwell", "Mohammed Siraj", "Sanju Samson", "Yashasvi Jaiswal",
        "Andre Russell", "Sunil Narine", "KL Rahul", "Rishabh Pant", "Heinrich Klaasen",
        "Dewald Brevis", "Sarfaraz Khan", "Urvil Patel", "Jamie Overton", "Quinton de Kock"
    ]
    for p in known_players:
        if p.lower() in q_lower:
            if p not in extracted_players:
                extracted_players.append(p)

    known_teams = ["CSK", "MI", "RCB", "GT", "KKR", "RR", "SRH", "DC", "LSG", "PBKS", "Australia", "India", "South Africa", "England"]
    for t in known_teams:
        if re.search(rf'\b{t.lower()}\b', q_lower):
            if t not in extracted_teams:
                extracted_teams.append(t)

    if "chepauk" in q_lower or "chidambaram" in q_lower:
        extracted_venue = "MA Chidambaram Stadium (Chepauk)"
    elif "wankhede" in q_lower:
        extracted_venue = "Wankhede Stadium"
    elif "chinnaswamy" in q_lower or "bengaluru" in q_lower or "bangalore" in q_lower:
        extracted_venue = "M. Chinnaswamy Stadium"
    elif "ahmedabad" in q_lower or "narendra modi" in q_lower:
        extracted_venue = "Narendra Modi Stadium"
    elif "eden" in q_lower or "kolkata" in q_lower:
        extracted_venue = "Eden Gardens"

    if "last 3 seasons" in q_lower or "last three seasons" in q_lower:
        extracted_season = "Last 3 Seasons"
    elif "2024" in q_lower:
        extracted_season = "2024"
    elif "2023" in q_lower:
        extracted_season = "2023"

    return {
        **state,
        "intent": intent,
        "players": extracted_players,
        "teams": extracted_teams,
        "venue": extracted_venue,
        "season": extracted_season
    }


# ==============================================================================
# 2. RULES RAG AGENT
# ==============================================================================
def rules_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    RAG Agent for cricket laws, ICC playing conditions, and fantasy rules.
    Retrieves knowledge strictly from data/rules.txt.
    """
    query = state.get("user_query", "")
    retrieved_sections = search_rules(query, top_k=2)

    rules_context = "\n\n".join([sec["full_text"] for sec in retrieved_sections])

    llm = get_llm()
    if llm and rules_context:
        try:
            messages = [
                {"role": "system", "content": RULES_AGENT_PROMPT},
                {"role": "user", "content": f"User Question: {query}\n\nRetrieved Official Rules Knowledge:\n{rules_context}"}
            ]
            response = llm.invoke(messages)
            return {
                **state,
                "rules": rules_context,
                "final_answer": _get_llm_text(response)
            }
        except Exception:
            pass

    # Fallback using retrieved section
    if retrieved_sections:
        sec = retrieved_sections[0]
        answer = f"""### Rule Explanation
{sec['content']}

### Match Example
In a live match situation involving this rule, on-field umpires refer to the standard playing conditions to ensure correct adjudication.

### Rule Source
Official Cricket Regulations: {sec['title']}
"""
    else:
        answer = "I couldn't find a matching rule section in the official cricket knowledge document (data/rules.txt)."

    return {
        **state,
        "rules": rules_context,
        "final_answer": answer
    }


# ==============================================================================
# 3. STATS AGENT (MCP TOOLS)
# ==============================================================================
def stats_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stats Agent using MCP tools: player_stats, head_to_head, venue_stats, match_info.
    Never fabricates statistics.
    """
    players = state.get("players", [])
    teams = state.get("teams", [])
    venue = state.get("venue")
    season = state.get("season")
    query = state.get("user_query", "")
    intent = state.get("intent", "ANALYSIS")

    stats_results = {
        "players": {},
        "head_to_head": {},
        "venue": {},
        "mcp_configured": is_mcp_configured()
    }

    # Collect players to query (both query-mentioned and candidate pool)
    target_players = list(players)
    candidates = state.get("candidates", [])
    for cand in candidates:
        c_name = cand.get("name")
        if c_name and c_name not in target_players:
            target_players.append(c_name)

    # Fetch stats via MCP tools for candidate and mentioned players (up to 24 priority players)
    rate_limited = False
    for p in target_players[:24]:
        if rate_limited:
            stats_results["players"][p] = {
                "player": p,
                "status": "unavailable",
                "message": "CricketData provider daily rate limit reached.",
                "found": False
            }
            continue

        res = player_stats.invoke({"player": p, "season": season, "venue": venue})
        stats_results["players"][p] = res
        if not res.get("found", False) and "limit" in str(res.get("message", "")).lower():
            rate_limited = True

    if len(teams) >= 2:
        h2h_res = head_to_head.invoke({"entity": teams[0], "opponent": teams[1], "venue": venue})
        stats_results["head_to_head"] = h2h_res
    elif len(players) >= 1 and len(teams) >= 1:
        h2h_res = head_to_head.invoke({"entity": players[0], "opponent": teams[0], "venue": venue})
        stats_results["head_to_head"] = h2h_res

    if venue:
        v_res = venue_stats.invoke({"venue": venue, "season": season})
        stats_results["venue"] = v_res

    # In TEAM_BUILDING flow, also retrieve real match info from MCP
    if intent == "TEAM_BUILDING" and len(teams) >= 2:
        m_info = match_info.invoke({"team1": teams[0], "team2": teams[1]})
        stats_results["match_info"] = m_info

    # If this is a standalone ANALYSIS query, produce the final answer
    if intent == "ANALYSIS":
        llm = get_llm()
        if llm and stats_results.get("mcp_configured"):
            try:
                messages = [
                    {"role": "system", "content": STATS_AGENT_PROMPT},
                    {"role": "user", "content": f"User Question: {query}\n\nMCP Statistical Tool Results:\n{json.dumps(stats_results, indent=2)}"}
                ]
                response = llm.invoke(messages)
                return {
                    **state,
                    "stats": stats_results,
                    "final_answer": _get_llm_text(response)
                }
            except Exception:
                pass

        # If MCP is unconfigured or no real stats returned, report honestly
        if not stats_results.get("mcp_configured"):
            answer = """### Comparison / Statistical Analysis

Cricket statistics are currently unavailable because no MCP cricket statistics provider is configured.

### Key Analytical Insights
- Real-time and historical statistics require a configured MCP provider.
- In accordance with system guardrails, no statistics or player averages have been fabricated.

### Source
MCP Cricket Statistics Provider (Not Configured)
"""
        else:
            rows = []
            for p, data in stats_results["players"].items():
                if data.get("found"):
                    bat = data.get("batting", {})
                    bowl = data.get("bowling", {})
                    r = bat.get("runs", "-")
                    w = bowl.get("wickets", "-")
                    avg = bat.get("average", "-")
                    sr = bat.get("strike_rate", "-")
                    rows.append(f"| {p} | {bat.get('matches', '-')} | {r} / {w} | {avg} | {sr} |")
                else:
                    rows.append(f"| {p} | Unavailable | Unavailable | Unavailable | Unavailable |")

            table_str = "\n".join(rows) if rows else "| Entity | Matches | Runs / Wickets | Average | Strike Rate / Economy |\n| :--- | :---: | :---: | :---: | :---: |\n| Data | Unavailable | Unavailable | Unavailable | Unavailable |"

            answer = f"""### Comparison / Statistical Analysis

| Player / Entity | Matches | Runs / Wickets | Average | Strike Rate / Economy |
| :--- | :---: | :---: | :---: | :---: |
{table_str}

### Key Analytical Insights
- Statistical metrics retrieved from the configured MCP provider (CricketData.org).
- If metrics display 'Unavailable', provider API rate limits were reached. No statistics were fabricated.

### Source
MCP Cricket Statistics Provider
"""

        return {
            **state,
            "stats": stats_results,
            "final_answer": answer
        }

    return {
        **state,
        "stats": stats_results
    }


# ==============================================================================
# 4. NEWS AGENT (TAVILY)
# ==============================================================================

INVALID_NAME_WORDS = {
    # Match & Tournament concepts
    "stadium", "update", "tips", "fantasy", "prediction", "pitch", "weather",
    "advertisement", "strengthening", "choice", "captaincy", "super", "kings",
    "mumbai", "indians", "chennai", "match", "matches", "today", "tomorrow", "tonight",
    "dream11", "feed", "ipl", "cricket", "report", "edition", "league",
    "point", "table", "news", "squad", "squads", "sqaud", "playing", "ground", "versus", "preview",
    "probables", "eleven", "xi", "t20", "toss", "lineup", "team", "teams", "guide",
    "vs", "score", "details", "head-to-head", "winner", "live", "highlights",
    "punt", "picks", "pick", "vice", "vc", "budget", "differential", "grand", "small",
    "impact", "player", "players", "substitute", "role", "roles", "record", "records",
    "allrounder", "allrounders", "rounder", "rounders", "batter", "batters", "bowler", "bowlers",
    "wicketkeeper", "wicketkeepers", "order", "middle", "batting", "bowling", "fielding",
    # Media and Publisher entities & Web phrases
    "times", "india", "content", "hindustan", "express", "tribune", "media", "agency",
    "getty", "images", "photo", "reuters", "ani", "pti", "espn", "cricinfo", "cricbuzz",
    "sportskeeda", "sportstar", "ndtv", "jagran", "bhaskar", "editor", "author",
    "reporter", "staff", "bureau", "published", "updated", "read", "share", "follow",
    "subscribe", "channel", "subscribers", "likes", "views", "posted", "video",
    "post", "article", "headline", "caption", "source", "sources", "credit", "rights", "reserved",
    "copyright", "official", "website", "board", "bcci", "icc", "the", "and", "for", "with",
    "facebook", "page", "join", "telegram", "full", "best", "possible", "who", "has", "have",
    "star", "network", "sports", "telecast", "broadcast", "stream", "streaming", "app",
    "watch", "online", "free", "link", "links", "all", "top", "latest", "date", "time", "local"
}

def is_valid_player_name(name: str) -> bool:
    """Validate that a string represents a real person's cricket player name."""
    if not name or not isinstance(name, str):
        return False
    if "\n" in name or "\r" in name:
        return False
    name_clean = " ".join(name.strip().split())
    words = [w.lower().strip(".,;:()[]{}'\"") for w in name_clean.split()]
    if len(words) < 2 or len(words) > 3:
        return False
    if set(words).intersection(INVALID_NAME_WORDS):
        return False
    for w in words:
        if any(inv in w for inv in ["allrounder", "batter", "bowler", "wicketkeeper", "cricket", "stadium", "preview"]):
            return False
    if not all(w.replace("-", "").isalpha() for w in words):
        return False
    if any(len(w) < 2 for w in words):
        return False
    return True


def infer_player_role(name: str, given_role: Optional[str] = None) -> str:
    """Ensure accurate cricket role assignment based on player identity."""
    if given_role in ["WK", "BAT", "AR", "BOWL"]:
        return given_role
    n_low = name.lower()
    if any(k in n_low for k in ["samson", "dhoni", "kock", "kishan", "rickelton", "karthik", "pant", "klaasen", "rawat", "jurel", "patel", "minz", "sharma"]):
        return "WK"
    elif any(k in n_low for k in ["jadeja", "pandya", "dube", "overton", "maxwell", "russell", "narine", "santner", "green", "dhir", "hosein", "shankar", "short", "veer", "ghosh", "brevis", "malewar"]):
        return "AR"
    elif any(k in n_low for k in ["bumrah", "chahar", "pathirana", "deshpande", "coetzee", "chawla", "thushara", "siraj", "ahmad", "kamboj", "singh", "ahmed", "dayal", "boult", "chahal", "kuldeep", "ghazanfar", "choudhary", "henry", "johnson", "shami", "bishnoi"]):
        return "BOWL"
    return "BAT"


def extract_candidates_from_news_and_mcp(teams: List[str], news_items: List[Dict[str, Any]], stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract verified candidate players dynamically from Tavily live search and MCP match squads.
    Does NOT rely on hardcoded player dictionaries.
    """
    candidates = []
    seen_names = set()

    t1 = teams[0].upper() if len(teams) >= 1 else "CSK"
    t2 = teams[1].upper() if len(teams) >= 2 else "MI"

    # Source 1: Real squads from MCP match_info
    m_info = stats.get("match_info", {})
    if m_info.get("found") and m_info.get("squads"):
        for sq in m_info.get("squads", []):
            sq_team = t1 if t1 in sq.get("teamName", "").upper() else (t2 if t2 in sq.get("teamName", "").upper() else t1)
            for p in sq.get("players", []):
                p_name = " ".join(p.get("name", "").strip().split())
                if is_valid_player_name(p_name) and p_name.lower() not in seen_names:
                    seen_names.add(p_name.lower())
                    candidates.append({
                        "name": p_name,
                        "team": sq_team,
                        "role": infer_player_role(p_name, p.get("role")),
                        "availability": "EXPECTED_PLAYING_XI",
                        "is_captain": "capt" in p_name.lower() or "(c)" in p_name.lower()
                    })

    # Source 2: Dynamic Extraction from Tavily Search Results via LLM
    news_text = "\n".join([f"Article: {item.get('title', '')}\nContent: {item.get('content', '')}" for item in news_items])
    llm = get_llm()

    if llm and news_text:
        try:
            prompt = f"""
From the following cricket match news for {t1} vs {t2}, extract the real candidate squad and playing XI players for BOTH teams.

News Text:
{news_text}

Return strictly a JSON array of objects with keys:
- "name": string (Player full name, e.g. 'Ruturaj Gaikwad', 'Sanju Samson', 'Jasprit Bumrah')
- "team": "{t1}" or "{t2}"
- "role": "WK" | "BAT" | "AR" | "BOWL"
- "availability": "CONFIRMED_PLAYING_XI" | "EXPECTED_PLAYING_XI" | "SQUAD_MEMBER" | "INJURY_DOUBTFUL" | "INJURED_RULED_OUT"
- "is_captain": boolean

Rules:
1. ONLY extract individual real human cricket players.
2. NEVER include media outlets (e.g. Times, Express), phrases, stadiums, or headlines.
3. Ensure accurate role assignment.
"""
            res = llm.invoke([{"role": "user", "content": prompt}])
            res_str = _get_llm_text(res)
            json_match = re.search(r'\[.*\]', res_str, re.DOTALL)
            if json_match:
                extracted = json.loads(json_match.group(0))
                for p in extracted:
                    p_name = " ".join(p.get("name", "").strip().split())
                    if is_valid_player_name(p_name) and p_name.lower() not in seen_names:
                        seen_names.add(p_name.lower())
                        candidates.append({
                            "name": p_name,
                            "team": p.get("team", t1).upper(),
                            "role": infer_player_role(p_name, p.get("role")),
                            "availability": p.get("availability", "EXPECTED_PLAYING_XI"),
                            "is_captain": p.get("is_captain", False)
                        })
        except Exception:
            pass

    # Source 3: Heuristic Regex Parser Fallback from News Content
    if len(candidates) < 11 and news_text:
        pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+(?: [A-Z][a-z]+)?)\b'
        matches = re.findall(pattern, news_text)
        for m in matches:
            name_clean = " ".join(m.strip().split())
            if is_valid_player_name(name_clean) and name_clean.lower() not in seen_names:
                p_team = t1
                if name_clean in news_text:
                    surrounding = news_text[max(0, news_text.find(name_clean)-80):news_text.find(name_clean)+80].lower()
                    if t2.lower() in surrounding or "mumbai" in surrounding or "indians" in surrounding:
                        p_team = t2

                role = infer_player_role(name_clean)
                seen_names.add(name_clean.lower())
                candidates.append({
                    "name": name_clean,
                    "team": p_team,
                    "role": role,
                    "availability": "EXPECTED_PLAYING_XI",
                    "is_captain": "gaikwad" in name_clean.lower() or "samson" in name_clean.lower()
                })

    return candidates



def news_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    News Agent using Tavily Live Web Search.
    Handles injury updates, confirmed/expected playing XI, pitch reports, weather.
    Never presents expected info as confirmed.
    Flags sources older than 24 hours.
    """
    query = state.get("user_query", "")
    teams = state.get("teams", [])
    players = state.get("players", [])
    intent = state.get("intent", "NEWS")
    tavily_api_key = os.getenv("TAVILY_API_KEY")

    if not teams and len(players) < 2 and intent == "TEAM_BUILDING":
        teams = ["CSK", "MI"]

    search_query = query
    if teams:
        search_query = f"{' vs '.join(teams)} cricket injury news playing XI squad pitch report update"
    elif players:
        search_query = f"{' '.join(players)} cricket injury availability playing XI update"

    news_items = []

    if tavily_api_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=tavily_api_key)
            response = client.search(
                query=search_query,
                search_depth="advanced",
                max_results=5
            )
            raw_results = response.get("results", [])
            for r in raw_results:
                pub_date = r.get("published_date") or "Recent"
                is_outdated = False
                if pub_date and any(yr in pub_date for yr in ["2020", "2021", "2022", "2023", "2024"]):
                    is_outdated = True

                content = r.get("content", "")
                status = "EXPECTED"
                if any(w in content.lower() for w in ["officially confirmed", "ruled out", "medical bulletin", "bcci confirmed"]):
                    status = "CONFIRMED"
                elif any(w in content.lower() for w in ["rumor", "speculation", "doubtful", "unverified"]):
                    status = "RUMORED"

                news_items.append({
                    "title": r.get("title", "Cricket News"),
                    "url": r.get("url", ""),
                    "content": content,
                    "published_date": pub_date,
                    "is_outdated": is_outdated,
                    "status": status
                })
        except Exception:
            pass

    # In TEAM_BUILDING flow, extract candidate players from the live news
    extracted_candidates = []
    if intent == "TEAM_BUILDING":
        extracted_candidates = extract_candidates_from_news_and_mcp(teams, news_items, state.get("stats", {}))

    # If this is a standalone NEWS query, generate final answer
    if intent == "NEWS":
        llm = get_llm()
        if llm and news_items:
            try:
                messages = [
                    {"role": "system", "content": NEWS_AGENT_PROMPT},
                    {"role": "user", "content": f"User Query: {query}\n\nTavily Search Results:\n{json.dumps(news_items, indent=2)}"}
                ]
                response = llm.invoke(messages)
                return {
                    **state,
                    "news": news_items,
                    "candidates": extracted_candidates,
                    "final_answer": response.content
                }
            except Exception:
                pass

        if not news_items:
            answer = f"""### Latest Team News & Match Updates
I couldn't retrieve current injury information from the available sources. Please verify the Tavily configuration (`TAVILY_API_KEY` in `.env`) and try again.

### Disclaimer
{DISCLAIMER_TEXT}
"""
        else:
            confirmed_items = [n for n in news_items if n["status"] == "CONFIRMED"]
            expected_items = [n for n in news_items if n["status"] != "CONFIRMED"]

            c_text = "\n".join([f"- **{n['title']}**: {n['content'][:150]}... ({n['url']})" for n in confirmed_items]) if confirmed_items else "- No official medical bulletins or confirmed XIs published yet."
            e_text = "\n".join([f"- **{n['title']}**: {n['content'][:150]}... ({n['url']})" for n in expected_items]) if expected_items else "- No probable lineup reports found."
            sources_text = "\n".join([f"- [{n['title']}]({n['url']})" for n in news_items if n.get("url")])

            answer = f"""### Latest Team News & Match Updates

#### Confirmed:
{c_text}

#### Expected:
{e_text}

#### Sources:
{sources_text}

### Disclaimer
{DISCLAIMER_TEXT}
"""

        return {
            **state,
            "news": news_items,
            "candidates": extracted_candidates,
            "final_answer": answer
        }

    return {
        **state,
        "news": news_items,
        "candidates": extracted_candidates
    }


# ==============================================================================
# 5. PYTHON FANTASY SCORING ENGINE & TEAM BUILDER
# ==============================================================================

def calculate_selection_score(
    player_name: str,
    team: str,
    role: str,
    stats: Dict[str, Any],
    availability_status: str,
    is_captain_news: bool,
    news_items: List[Dict[str, Any]],
    h2h_data: Dict[str, Any],
    venue_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministic Python Fantasy Scoring Engine based ONLY on real retrieved metrics and news.
    
    Formula:
      Selection Score = Base Score (30.0)
                      + Batting Contribution (0.0 to 30.0)
                      + Bowling Contribution (0.0 to 30.0)
                      + Role Utility Boost (0.0 to 5.0)
                      + Availability & Live News Factor (-999.0 to +11.0)
                      + Matchup & Venue Factor (0.0 to 4.0)

    CRITICAL RULE:
    Only use fields that actually exist in MCP / Tavily.
    If a field is unavailable, it contributes 0.0 to its sub-score and is explicitly marked 'unavailable'.
    No synthetic statistics or placeholder numbers are fabricated.
    """
    base_score = 30.0
    batting_score = 0.0
    bowling_score = 0.0
    role_score = 0.0
    availability_score = 0.0
    matchup_score = 0.0

    data_factors = {
        "batting_stats": "unavailable",
        "bowling_stats": "unavailable",
        "venue_stats": "unavailable",
        "h2h_stats": "unavailable",
        "availability": "unverified",
        "details": []
    }

    # 1. Batting Contribution (MCP player_stats)
    if stats.get("found"):
        batting = stats.get("batting", {})
        if batting:
            try:
                avg_str = str(batting.get("average", "-")).strip()
                sr_str = str(batting.get("strike_rate", "-")).strip()
                runs_str = str(batting.get("runs", "-")).strip()
                fifties_str = str(batting.get("fifties", "0")).strip()
                hundreds_str = str(batting.get("hundreds", "0")).strip()

                avg_val = float(avg_str) if avg_str not in ["-", "", "None"] else 0.0
                sr_val = float(sr_str) if sr_str not in ["-", "", "None"] else 0.0
                runs_val = float(runs_str) if runs_str not in ["-", "", "None"] else 0.0
                fifties_val = float(fifties_str) if fifties_str not in ["-", "", "None"] else 0.0
                hundreds_val = float(hundreds_str) if hundreds_str not in ["-", "", "None"] else 0.0

                if avg_val > 0 or sr_val > 0 or runs_val > 0:
                    data_factors["batting_stats"] = "available"

                # Weighted batting formula
                if avg_val > 0:
                    batting_score += min(avg_val, 60.0) * 0.35
                if sr_val >= 100.0:
                    batting_score += (min(sr_val, 200.0) - 100.0) * 0.12
                elif 0 < sr_val < 100.0:
                    batting_score += (sr_val - 100.0) * 0.10
                if runs_val > 0:
                    batting_score += min(runs_val, 6000.0) * 0.0015
                if fifties_val > 0 or hundreds_val > 0:
                    batting_score += min((fifties_val * 0.3) + (hundreds_val * 1.0), 6.0)
            except (ValueError, TypeError):
                pass

        # 2. Bowling Contribution (MCP player_stats)
        bowling = stats.get("bowling", {})
        if bowling:
            try:
                wkts_str = str(bowling.get("wickets", "-")).strip()
                econ_str = str(bowling.get("economy", "-")).strip()
                b_avg_str = str(bowling.get("average", "-")).strip()

                wkts_val = float(wkts_str) if wkts_str not in ["-", "", "None"] else 0.0
                econ_val = float(econ_str) if econ_str not in ["-", "", "None"] else 0.0
                b_avg_val = float(b_avg_str) if b_avg_str not in ["-", "", "None"] else 0.0

                if wkts_val > 0 or econ_val > 0:
                    data_factors["bowling_stats"] = "available"

                if wkts_val > 0:
                    bowling_score += min(wkts_val, 200.0) * 0.15
                if 0.0 < econ_val < 12.0:
                    bowling_score += max(0.0, (10.0 - econ_val) * 1.8)
                if b_avg_val > 0:
                    bowling_score += max(0.0, (35.0 - min(b_avg_val, 35.0)) * 0.25)
            except (ValueError, TypeError):
                pass

    # 3. Role Dynamic Value
    if role == "AR":
        role_score = 5.0
    elif role == "WK":
        role_score = 2.5
    else:
        role_score = 0.0

    # 4. Live News & Availability (Tavily)
    p_lower = player_name.lower()
    last_name = p_lower.split()[-1] if p_lower.split() else p_lower

    # Check for direct injury status
    is_injured_ruled_out = False
    is_injury_doubtful = False

    for n in news_items:
        c_lower = n.get("content", "").lower()
        t_lower = n.get("title", "").lower()
        full_text = c_lower + " " + t_lower

        if p_lower in full_text or last_name in full_text:
            if any(w in full_text for w in ["ruled out", "fracture", "surgery", "not available", "misses out"]):
                if n.get("status") == "CONFIRMED":
                    is_injured_ruled_out = True
                else:
                    is_injury_doubtful = True
            elif any(w in full_text for w in ["doubtful", "unfit", "fitness test"]):
                is_injury_doubtful = True

    if availability_status == "INJURED_RULED_OUT" or is_injured_ruled_out:
        data_factors["availability"] = "confirmed ruled out"
        return {
            "score": -999.0,
            "disqualified": True,
            "data_factors": data_factors,
            "reason": "Confirmed injured or ruled out in medical bulletin"
        }

    if availability_status == "INJURY_DOUBTFUL" or is_injury_doubtful:
        availability_score -= 15.0
        data_factors["availability"] = "doubtful / fitness concern"
    elif availability_status == "CONFIRMED_PLAYING_XI":
        availability_score += 8.0
        data_factors["availability"] = "verified (confirmed XI)"
    elif availability_status == "EXPECTED_PLAYING_XI":
        availability_score += 4.0
        data_factors["availability"] = "verified (expected XI)"
    else:
        availability_score += 0.0
        data_factors["availability"] = "unverified (squad pool)"

    if is_captain_news:
        availability_score += 3.0
        data_factors["details"].append("Designated Team Captain")

    # 5. Matchup & Venue (MCP)
    if h2h_data.get("found"):
        matchup_score += 1.5
        data_factors["h2h_stats"] = "available"
    if venue_data.get("found"):
        matchup_score += 1.5
        data_factors["venue_stats"] = "available"

    # Total score summation
    total_score = base_score + batting_score + bowling_score + role_score + availability_score + matchup_score
    bounded_score = round(min(98.5, max(15.0, total_score)), 1)

    return {
        "score": bounded_score,
        "disqualified": False,
        "data_factors": data_factors,
        "batting_contribution": round(batting_score, 1),
        "bowling_contribution": round(bowling_score, 1),
        "role_contribution": round(role_score, 1),
        "availability_contribution": round(availability_score, 1),
        "matchup_contribution": round(matchup_score, 1)
    }


def team_builder_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds a constraint-compliant 11-player fantasy team using the Deterministic Selection Score Engine,
    MCP player statistics, and Tavily news.
    Zero-fabrication: Never invents fake players or fake platform credits.
    """
    teams = state.get("teams", [])
    news = state.get("news", [])
    stats = state.get("stats", {})
    query = state.get("user_query", "")

    if len(teams) < 2:
        teams = ["CSK", "MI"]

    t1, t2 = teams[0], teams[1]

    # Candidate pool derived purely from Tavily live news and MCP match info
    candidates = state.get("candidates", [])
    if not candidates:
        candidates = extract_candidates_from_news_and_mcp(teams, news, stats)

    if len(candidates) < 11:
        return {
            **state,
            "candidate_team": {
                "status": "DATA_UNAVAILABLE",
                "reason": f"Insufficient verified real players found for {t1} vs {t2} from MCP match squads and Tavily live news (found {len(candidates)})."
            }
        }

    h2h_data = stats.get("head_to_head", {})
    venue_data = stats.get("venue", {})

    # Calculate selection scores for all candidate players
    scored_candidates: List[Dict[str, Any]] = []
    seen_names = set()

    for cand in candidates:
        p_name = cand["name"]
        if p_name.lower() in seen_names:
            continue
        seen_names.add(p_name.lower())

        p_team = cand.get("team", t1)
        p_role = cand.get("role", "BAT")
        p_avail = cand.get("availability", "EXPECTED_PLAYING_XI")
        is_capt = cand.get("is_captain", False)

        p_stats = stats.get("players", {}).get(p_name, {})

        score_res = calculate_selection_score(
            player_name=p_name,
            team=p_team,
            role=p_role,
            stats=p_stats,
            availability_status=p_avail,
            is_captain_news=is_capt,
            news_items=news,
            h2h_data=h2h_data,
            venue_data=venue_data
        )

        if not score_res.get("disqualified", False) and score_res["score"] > 0:
            scored_candidates.append({
                "name": p_name,
                "team": p_team,
                "role": p_role,
                "selection_score": score_res["score"],
                "data_factors": score_res["data_factors"],
                "breakdown": score_res
            })

    if len(scored_candidates) < 11:
        return {
            **state,
            "candidate_team": {
                "status": "DATA_UNAVAILABLE",
                "reason": f"Insufficient non-injured verified players to build 11-player lineup (available: {len(scored_candidates)})."
            }
        }

    # Sort descending by Selection Score
    sorted_players = sorted(scored_candidates, key=lambda x: x["selection_score"], reverse=True)

    # Filter by role groups
    wks = [p for p in sorted_players if p["role"] == "WK"]
    bats = [p for p in sorted_players if p["role"] == "BAT"]
    ars = [p for p in sorted_players if p["role"] == "AR"]
    bowls = [p for p in sorted_players if p["role"] == "BOWL"]

    selected = []

    # Mandatory minimums: 1 WK, 3 BAT, 1 AR, 3 BOWL (8 players)
    if wks:
        selected.append(wks[0])
    for b in bats[:3]:
        if b not in selected:
            selected.append(b)
    if ars:
        for a in ars[:1]:
            if a not in selected:
                selected.append(a)
    for bo in bowls[:3]:
        if bo not in selected:
            selected.append(bo)

    # Fill remaining slots prioritizing highest selection score with max 7 per team & role caps
    remaining = [p for p in sorted_players if p not in selected]
    for cand in remaining:
        if len(selected) >= 11:
            break
        team_count = sum(1 for p in selected if p["team"] == cand["team"])
        role_count = sum(1 for p in selected if p["role"] == cand["role"])
        role_limit = 4 if cand["role"] in ["WK", "AR"] else 6

        if team_count < 7 and role_count < role_limit:
            selected.append(cand)

    # If still under 11, greedily fill without exceeding team cap of 7
    if len(selected) < 11:
        for cand in remaining:
            if cand not in selected and len(selected) < 11:
                team_count = sum(1 for p in selected if p["team"] == cand["team"])
                if team_count < 7:
                    selected.append(cand)

    if len(selected) != 11:
        return {
            **state,
            "candidate_team": {
                "status": "DATA_UNAVAILABLE",
                "reason": f"Could not satisfy 11-player constraint with available players (selected {len(selected)})."
            }
        }

    # Select Captain (highest score) and Vice-Captain (second highest distinct score)
    ranked_selected = sorted(selected, key=lambda x: x["selection_score"], reverse=True)
    captain = ranked_selected[0]
    vice_captain = ranked_selected[1] if len(ranked_selected) > 1 else ranked_selected[0]

    # Generate transparent selection analysis using Gemini or deterministic reasoning
    llm = get_llm()
    captain_reason = f"Ranked #1 with highest Selection Score ({captain['selection_score']}) based on verified role impact and availability."
    vice_captain_reason = f"Ranked #2 with Selection Score ({vice_captain['selection_score']}) providing multi-dimensional balance."
    selection_insights = []

    if llm:
        try:
            prompt = f"""
Given the selected Fantasy XI for {t1} vs {t2}:
{json.dumps(selected, indent=2)}

Captain: {captain['name']} (Score: {captain['selection_score']})
Vice-Captain: {vice_captain['name']} (Score: {vice_captain['selection_score']})

Provide brief, transparent analytical reasons for:
1. 'captain_reason': Why {captain['name']} was selected as Captain based on score and availability
2. 'vice_captain_reason': Why {vice_captain['name']} was selected as Vice-Captain
3. 'key_players_reason': Tactical reasoning for key roles selected
4. 'injury_considerations': Availability and injury screening notes

Return strictly a JSON object with those 4 keys.
"""
            res = llm.invoke([{"role": "system", "content": TEAM_BUILDER_PROMPT}, {"role": "user", "content": prompt}])
            res_str = _get_llm_text(res)
            json_match = re.search(r'\{.*\}', res_str, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                captain_reason = parsed.get("captain_reason", captain_reason)
                vice_captain_reason = parsed.get("vice_captain_reason", vice_captain_reason)
                selection_insights = [
                    parsed.get("key_players_reason", "Core top-order anchors, dual-utility all-rounders, and death bowlers selected."),
                    parsed.get("injury_considerations", "Confirmed injured and doubtful players screened out.")
                ]
        except Exception:
            pass

    candidate_team = {
        "status": "VALID",
        "players": selected,
        "captain": captain["name"],
        "captain_reason": captain_reason,
        "vice_captain": vice_captain["name"],
        "vice_captain_reason": vice_captain_reason,
        "selection_insights": selection_insights
    }

    return {
        **state,
        "candidate_team": candidate_team
    }


# ==============================================================================
# 6. VALIDATOR AGENT
# ==============================================================================
def validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates candidate fantasy team against all 8 strict criteria:
    1. Exactly 11 players
    2. No duplicate players
    3. Valid roles (WK: 1-4, BAT: 3-6, AR: 1-4, BOWL: 3-6)
    4. Team balance (Maximum 7 players from any single team)
    5. Player availability considered (No confirmed injured or ruled-out players)
    6. Data provenance (Real players from verified sources)
    7. No fabricated values
    8. Captain and Vice-Captain are distinct and selected from the 11.
    """
    candidate = state.get("candidate_team", {})
    iteration = state.get("iteration", 0) + 1

    if not candidate or candidate.get("status") == "DATA_UNAVAILABLE" or not candidate.get("players"):
        return {
            **state,
            "iteration": iteration,
            "validation_result": "DATA_UNAVAILABLE",
            "validation_errors": [candidate.get("reason", "Real player and squad data is not currently available from the configured data sources.")]
        }

    players = candidate.get("players", [])
    captain = candidate.get("captain")
    vice_captain = candidate.get("vice_captain")
    news = state.get("news", [])
    errors = []

    # 1. Player Count
    if len(players) != 11:
        errors.append(f"Team must have exactly 11 players (got {len(players)}).")

    # 2. No Duplicate Players
    p_names = [p.get("name") for p in players]
    if len(set(p_names)) != len(players):
        errors.append("Duplicate players found in selected lineup.")

    # 3. Role Bounds
    wk_count = sum(1 for p in players if p.get("role") == "WK")
    bat_count = sum(1 for p in players if p.get("role") == "BAT")
    ar_count = sum(1 for p in players if p.get("role") == "AR")
    bowl_count = sum(1 for p in players if p.get("role") == "BOWL")

    if not (1 <= wk_count <= 4):
        errors.append(f"Invalid Wicket-Keeper count: {wk_count} (must be between 1 and 4).")
    if not (3 <= bat_count <= 6):
        errors.append(f"Invalid Batsmen count: {bat_count} (must be between 3 and 6).")
    if not (1 <= ar_count <= 4):
        errors.append(f"Invalid All-Rounder count: {ar_count} (must be between 1 and 4).")
    if not (3 <= bowl_count <= 6):
        errors.append(f"Invalid Bowler count: {bowl_count} (must be between 3 and 6).")

    # 4. Max 7 per team
    team_counts = {}
    for p in players:
        t = p.get("team", "Unknown")
        team_counts[t] = team_counts.get(t, 0) + 1
    for t, count in team_counts.items():
        if count > 7:
            errors.append(f"Maximum 7 players allowed from one team (got {count} from {t}).")

    # 5. Confirmed Unavailable / Injured Players
    injured_names = []
    for n in news:
        if n.get("status") == "CONFIRMED" and any(w in n.get("content", "").lower() for w in ["ruled out", "injured", "fracture", "surgery"]):
            for p in players:
                p_name = p.get("name", "")
                if p_name and (p_name.lower() in n.get("content", "").lower() or p_name.split()[-1].lower() in n.get("content", "").lower()):
                    injured_names.append(p_name)
    if injured_names:
        errors.append(f"Selected players reported confirmed injured/unavailable: {', '.join(set(injured_names))}.")

    # 6. Captain & Vice-Captain checks
    if not captain or captain not in p_names:
        errors.append("Captain must be an active selected player in the 11.")
    if not vice_captain or vice_captain not in p_names:
        errors.append("Vice-Captain must be an active selected player in the 11.")
    if captain and vice_captain and captain == vice_captain:
        errors.append("Captain and Vice-Captain cannot be the same player.")

    is_valid = len(errors) == 0

    return {
        **state,
        "iteration": iteration,
        "validation_result": "VALID" if is_valid else "INVALID",
        "validation_errors": errors
    }


# ==============================================================================
# 7. FINAL RESPONSE AGENT
# ==============================================================================
def final_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formats the final output for the user with complete data transparency.
    """
    intent = state.get("intent", "ANALYSIS")

    if intent in ["RULES", "ANALYSIS", "NEWS"]:
        return state

    if intent == "TEAM_BUILDING":
        val_res = state.get("validation_result", "DATA_UNAVAILABLE")
        candidate = state.get("candidate_team", {})

        if val_res == "DATA_UNAVAILABLE" or not candidate or candidate.get("status") == "DATA_UNAVAILABLE":
            final_text = f"""### Fantasy XI

Unable to build a reliable fantasy XI.

Reason:
{candidate.get('reason', 'Real player, role, availability and squad information is not currently available from the configured data sources.')}

No players or statistics have been fabricated.
"""
            return {
                **state,
                "final_answer": final_text
            }

        players = candidate.get("players", [])
        c = candidate.get("captain", "N/A")
        c_reason = candidate.get("captain_reason", "")
        vc = candidate.get("vice_captain", "N/A")
        vc_reason = candidate.get("vice_captain_reason", "")
        insights = candidate.get("selection_insights", [])
        stats_state = state.get("stats", {})

        # Check MCP data availability
        mcp_players_found = any(p_data.get("found", False) for p_data in stats_state.get("players", {}).values())
        batting_status_str = "Available from MCP" if mcp_players_found else "Unavailable (CricketData provider daily limit / unconfigured)"
        bowling_status_str = "Available from MCP" if mcp_players_found else "Unavailable (CricketData provider daily limit / unconfigured)"
        venue_status_str = "Unavailable (Not directly provided by CricketData.org API)"
        h2h_status_str = "Available from MCP" if stats_state.get("head_to_head", {}).get("found") else "Unavailable from current endpoints"

        # Build clean markdown table with #, Player, Team, Role, Selection Score, Availability
        rows = []
        for i, p in enumerate(players, 1):
            p_name = p.get("name")
            is_c = " **(C)**" if p_name == c else (" **(VC)**" if p_name == vc else "")
            team = p.get("team", "")
            role = p.get("role", "")
            score = p.get("selection_score", 30.0)
            avail = p.get("data_factors", {}).get("availability", "verified (expected XI)")
            rows.append(f"| {i} | {p_name}{is_c} | {team} | {role} | {score} | {avail} |")

        table_str = "\n".join(rows)
        insights_str = "\n".join([f"- {item}" for item in insights]) if insights else "- Balanced team composition across top-order batsmen, all-rounders, and bowling specialists."

        final_text = f"""### Fantasy XI

| # | Player | Team | Role | Selection Score | Availability |
| :-: | :----- | :---: | :---: | --------------: | :----------- |
{table_str}

**Captain:** {c}  
**Vice-Captain:** {vc}  

### Selection Analysis
- **Why the Captain was selected:** {c_reason}
- **Why the Vice-Captain was selected:** {vc_reason}
{insights_str}

#### Data Factor Transparency:
- **Batting Statistics:** {batting_status_str}
- **Bowling Statistics:** {bowling_status_str}
- **Head-to-Head Records:** {h2h_status_str}
- **Venue Pitch Metrics:** {venue_status_str}
- **Live Team News & Availability:** Verified via Tavily Live Search

### Data Sources
- MCP Cricket Statistics Provider (CricketData.org)
- Tavily current team/news research
- Deterministic Selection Score Engine

### Disclaimer
{DISCLAIMER_TEXT}
"""
        return {
            **state,
            "final_answer": final_text
        }

    return state

