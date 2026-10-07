"""
CLI Interface for Cricket Match Analyst & Fantasy Team Builder.
Run via: python -m app.main
"""

import sys
import os
from dotenv import load_dotenv

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from app.graph import cricket_graph


def execute_query(user_query: str) -> dict:
    """Execute a cricket question through the LangGraph pipeline and return the final state dictionary."""
    initial_state = {
        "user_query": user_query,
        "iteration": 0
    }
    final_state = {}
    for output in cricket_graph.stream(initial_state):
        for key, value in output.items():
            final_state.update(value)
    return final_state


def run_query(user_query: str) -> None:
    """Execute a cricket question through the LangGraph pipeline with step markers."""
    print("\n" + "-" * 50)
    print(f"Question: {user_query}")
    print("-" * 50)

    initial_state = {
        "user_query": user_query,
        "iteration": 0
    }

    final_state = {}

    try:
        for output in cricket_graph.stream(initial_state):
            for key, value in output.items():
                final_state.update(value)
                if key == "router":
                    print("[Router] Classifying query...")
                elif key == "rules":
                    print("[Rules RAG] Retrieving cricket laws & conditions...")
                elif key == "stats":
                    print("[Stats Agent] Fetching statistics via MCP...")
                elif key == "news":
                    print("[News Agent] Searching latest news & updates via Tavily...")
                elif key == "team_builder":
                    print("[Team Builder] Assembling fantasy lineup...")
                elif key == "validator":
                    print("[Validator] Checking fantasy constraints...")
    except Exception as e:
        print(f"\n[Error] Pipeline execution encountered an issue: {e}")
        return

    print("\n" + "=" * 50)
    answer = final_state.get("final_answer", "No response generated.")
    print(answer)
    print("=" * 50 + "\n")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--serve":
            from app.server import run_server
            port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8000
            run_server(port=port)
            return
        query = " ".join(sys.argv[1:])
        run_query(query)
        return

    print("===============================================")
    print("     CRICKET MATCH ANALYST & FANTASY BUILDER   ")
    print("===============================================")
    print("Enter your cricket questions below. Type 'exit' or 'quit' to close.\n")

    while True:
        try:
            user_input = input("Enter your cricket question:\n> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Exiting Cricket Match Analyst. Goodbye!")
                break
            run_query(user_input)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye!")
            break


if __name__ == "__main__":
    main()
