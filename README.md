# Cricket Match Analyst & Fantasy Team Builder

An Agentic AI cricket analysis and fantasy team builder built with **Python**, **LangGraph**, **LangChain**, **MCP (Model Context Protocol)**, **Tavily**, **RAG**, and **Google Gemini**.

> **Note on Data Architecture:**  
> **This project does not maintain a local cricket statistics database.**  
> Historical statistics, live news, and static cricket laws are strictly partitioned across dedicated external and local retrieval channels:
> - **MCP** → Cricket statistics & historical metrics
> - **Tavily** → Latest/current cricket news, injury reports, and pitch conditions
> - **RAG** → Cricket rules and playing conditions knowledge base (`data/rules.txt`)

---

## 🏗 Architecture & Workflow

The system is orchestrated using **LangGraph** following a stateful multi-agent graph:

```text
                         USER
                           │
                           ▼
                        ROUTER
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
          RULES         ANALYSIS       TEAM BUILDING
            │              │              │
            ▼              ▼              ▼
           RAG            MCP           NEWS
                           │              │
                           │            Tavily
                           │              │
                           └──────┬───────┘
                                  ▼
                            TEAM BUILDER
                                  │
                                  ▼
                              VALIDATOR
                                  │
                         ┌────────┴────────┐
                         │                 │
                       Valid            Invalid
                         │                 │
                         ▼                 ▼
                       OUTPUT       TEAM BUILDER
                                      (max 3 loops)
```

### LangGraph Workflow Execution

1. **Router**: Classifies user query into `RULES`, `ANALYSIS`, `NEWS`, or `TEAM_BUILDING`.
2. **Rules (RAG)**: Retrieves official laws from `data/rules.txt` and generates a step-by-step explanation with realistic match examples.
3. **Analysis (MCP)**: Queries statistical tools (`player_stats`, `head_to_head`, `venue_stats`) via external MCP provider and formats statistical comparison tables.
4. **News (Tavily)**: Searches live web intelligence for injury reports, official squad announcements, confirmed vs probable XIs, and pitch reports.
5. **Team Builder**: Synthesizes live news and stats into a balanced 11-player fantasy lineup respecting budget (100 credits), role bounds, team limits, and player availability.
6. **Validator Loop**: Programmatically validates candidate lineups against all 6 fantasy constraints. If invalid, routes back to Team Builder (up to 3 iterations).

---

## 📁 Project Structure

```text
cricket-match-analyst/
│
├── app/
│   ├── main.py          # Interactive CLI interface
│   ├── graph.py         # LangGraph workflow, state, and routing
│   ├── agents.py        # Router, Rules RAG, Stats MCP, News Tavily, Team Builder, Validator
│   ├── tools.py         # MCP cricket statistics tools & RAG rules retriever
│   └── prompts.py       # Agent prompts, guardrails, and templates
│
├── data/
│   └── rules.txt        # Cricket laws, playing conditions, and fantasy scoring rules
│
├── requirements.txt     # Minimal, locked dependencies
├── .env                 # API keys (create from .env.example)
├── .env.example         # Environment variable template
├── .gitignore           # Git ignore file
└── README.md            # Documentation
```

---

## 🔌 Data Sources & Roles

| Source | Component | Responsibility |
| :--- | :--- | :--- |
| **MCP** | Stats Agent (`app/tools.py`) | Historical player career metrics, head-to-head records, venue dynamics via external statistics provider. |
| **Tavily** | News Agent (`app/agents.py`) | Real-time match day news, injury bulletins, confirmed/expected playing XI, weather, and pitch conditions. |
| **RAG** | Rules Agent (`data/rules.txt`) | Authoritative knowledge on ICC/MCC laws, DRS umpire's call, LBW, powerplay, super overs, and fantasy scoring rules. |

---

## 🛡 Guardrails & Compliance

- **No Fabricated Statistics**: If MCP data source is unavailable, the system states: *"I couldn't retrieve that statistic from the configured cricket data source."* and never fabricates numbers.
- **News Freshness**: Articles older than 24 hours are explicitly flagged with `⚠ Older than 24 hours`.
- **Status Distinction**: Lineups and injuries are strictly classified as `CONFIRMED`, `EXPECTED`, or `RUMORED`.
- **Honest Predictions**: Outputs use realistic analytical language (`likely`, `possible`) and never claim certainty.
- **Responsible AI**: Fantasy analysis is strictly for informational simulation; no real-money gambling is supported or encouraged.

---

## ⚙️ Installation & Setup

### 1. Clone & Set Up Virtual Environment

```bash
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On Linux/macOS:
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create `.env` by copying `.env.example`:

```bash
cp .env.example .env
```

Add your API keys to `.env`:

```ini
# Google Gemini (Primary LLM)
GOOGLE_API_KEY=your_gemini_api_key_here

# Tavily (Live Web Search for News Agent)
TAVILY_API_KEY=your_tavily_api_key_here

# Optional: MCP Cricket Statistics Server (when an external MCP server is running)
# MCP_CRICKET_SERVER_URL=
```

---

## 🚀 How to Run

### Interactive CLI

```bash
python -m app.main
```

### Example Questions to Try

```text
Enter your cricket question:
> How does DRS umpire's call work?
```

```text
Enter your cricket question:
> Compare Virat Kohli and Shubman Gill at Chepauk in the last 3 seasons.
```

```text
Enter your cricket question:
> Give me the latest injury updates for CSK vs MI.
```

```text
Enter your cricket question:
> Build a fantasy XI for CSK vs MI within 100 credits.
```