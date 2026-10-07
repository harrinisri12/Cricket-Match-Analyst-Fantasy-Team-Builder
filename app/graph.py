"""
LangGraph Orchestration for Cricket Match Analyst & Fantasy Team Builder.
Implements the multi-agent graph with routing, MCP stats, Tavily news, RAG rules, Team Builder, and Validator loop.
"""

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

from app.agents import (
    router_node,
    rules_node,
    stats_node,
    news_node,
    team_builder_node,
    validator_node,
    final_response_node
)

# ==============================================================================
# 1. SHARED STATE DEFINITION
# ==============================================================================
class CricketState(TypedDict, total=False):
    user_query: str
    intent: str
    messages: List[Dict[str, Any]]
    stats: Dict[str, Any]
    news: List[Dict[str, Any]]
    rules: str
    candidate_team: Dict[str, Any]
    validation_result: str  # "VALID" or "INVALID"
    validation_errors: List[str]
    iteration: int
    final_answer: str
    players: List[str]
    teams: List[str]
    venue: Optional[str]
    season: Optional[str]


# ==============================================================================
# 2. CONDITIONAL ROUTING LOGIC
# ==============================================================================
def route_initial(state: CricketState) -> str:
    """Route user query to the appropriate starting agent based on classified intent."""
    intent = state.get("intent", "ANALYSIS").upper()
    if intent == "RULES":
        return "rules"
    elif intent == "NEWS":
        return "news"
    elif intent == "TEAM_BUILDING":
        return "news"  # Team building begins by gathering live news & availability
    else:
        return "stats"


def route_after_news(state: CricketState) -> str:
    """Determine flow after News Agent."""
    intent = state.get("intent", "NEWS").upper()
    if intent == "TEAM_BUILDING":
        return "stats"  # Follow pipeline: NEWS -> STATS -> TEAM BUILDER
    return "final_response"


def route_after_stats(state: CricketState) -> str:
    """Determine flow after Stats Agent."""
    intent = state.get("intent", "ANALYSIS").upper()
    if intent == "TEAM_BUILDING":
        return "team_builder"
    return "final_response"


def route_validator(state: CricketState) -> str:
    """Validator loop: retries Team Builder up to 3 times if invalid."""
    val_result = state.get("validation_result", "INVALID")
    iteration = state.get("iteration", 1)

    if val_result in ["VALID", "DATA_UNAVAILABLE"] or iteration >= 3:
        return "final_response"
    else:
        return "team_builder"


# ==============================================================================
# 3. BUILD APPLICATION GRAPH
# ==============================================================================
def build_cricket_graph():
    workflow = StateGraph(CricketState)

    # Register Nodes
    workflow.add_node("router", router_node)
    workflow.add_node("rules", rules_node)
    workflow.add_node("stats", stats_node)
    workflow.add_node("news", news_node)
    workflow.add_node("team_builder", team_builder_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("final_response", final_response_node)

    # Initial Edge
    workflow.add_edge(START, "router")

    # Router conditional branching
    workflow.add_conditional_edges(
        "router",
        route_initial,
        {
            "rules": "rules",
            "stats": "stats",
            "news": "news"
        }
    )

    # Rules goes to final_response
    workflow.add_edge("rules", "final_response")

    # News branch
    workflow.add_conditional_edges(
        "news",
        route_after_news,
        {
            "stats": "stats",
            "final_response": "final_response"
        }
    )

    # Stats branch
    workflow.add_conditional_edges(
        "stats",
        route_after_stats,
        {
            "team_builder": "team_builder",
            "final_response": "final_response"
        }
    )

    # Team Builder -> Validator
    workflow.add_edge("team_builder", "validator")

    # Validator loop
    workflow.add_conditional_edges(
        "validator",
        route_validator,
        {
            "team_builder": "team_builder",
            "final_response": "final_response"
        }
    )

    # Final response -> END
    workflow.add_edge("final_response", END)

    return workflow.compile()


cricket_graph = build_cricket_graph()
