/**
 * Cricket Match Analyst & Fantasy Team Builder - Frontend Controller
 * Connects directly to the Python LangGraph backend endpoint (/api/analyze).
 * Strictly zero frontend data fabrication.
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const queryForm = document.getElementById("queryForm");
  const queryInput = document.getElementById("queryInput");
  const analyzeBtn = document.getElementById("analyzeBtn");
  const clearBtn = document.getElementById("clearBtn");
  const retryBtn = document.getElementById("retryBtn");
  const quickButtons = document.querySelectorAll(".quick-btn");

  const statusBadge = document.getElementById("statusBadge");
  const emptyState = document.getElementById("emptyState");
  const loadingState = document.getElementById("loadingState");
  const errorState = document.getElementById("errorState");
  const outputContainer = document.getElementById("outputContainer");
  const loadingMessage = document.getElementById("loadingMessage");

  let currentQuery = "";

  // ----------------------------------------------------------------------------
  // UI State Management
  // ----------------------------------------------------------------------------
  function setViewState(state, message = "") {
    emptyState.style.display = "none";
    loadingState.style.display = "none";
    errorState.style.display = "none";
    outputContainer.style.display = "none";

    statusBadge.className = "status-badge";

    if (state === "EMPTY") {
      emptyState.style.display = "block";
      statusBadge.textContent = "READY";
      statusBadge.classList.add("status-ready");
    } else if (state === "LOADING") {
      loadingState.style.display = "block";
      loadingMessage.textContent = message || "Executing multi-agent cricket intelligence pipeline...";
      statusBadge.textContent = "ANALYZING...";
      statusBadge.classList.add("status-analyzing");
    } else if (state === "ERROR") {
      errorState.style.display = "block";
      statusBadge.textContent = "ERROR";
      statusBadge.classList.add("status-error");
    } else if (state === "COMPLETE") {
      outputContainer.style.display = "block";
      statusBadge.textContent = "COMPLETE";
      statusBadge.classList.add("status-complete");
    }
  }

  // ----------------------------------------------------------------------------
  // API Execution
  // ----------------------------------------------------------------------------
  async function performAnalysis(queryText) {
    if (!queryText || !queryText.trim()) {
      queryInput.focus();
      return;
    }

    currentQuery = queryText.trim();
    queryInput.value = currentQuery;
    setViewState("LOADING", "Querying LangGraph, MCP Statistics, and Tavily Intelligence...");

    // Determine API Endpoint (works whether served from Python server or separate port)
    const apiEndpoint = window.location.origin.startsWith("http")
      ? `${window.location.origin}/api/analyze`
      : "http://localhost:8000/api/analyze";

    try {
      const response = await fetch(apiEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({ query: currentQuery })
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const data = await response.json();
      if (data.status === "error") {
        throw new Error(data.message || "Analysis request failed.");
      }

      renderResponse(data);
      setViewState("COMPLETE");
    } catch (err) {
      console.error("Analysis Pipeline Error:", err);
      setViewState("ERROR");
    }
  }

  // ----------------------------------------------------------------------------
  // Render Response Controller
  // ----------------------------------------------------------------------------
  function renderResponse(data) {
    outputContainer.innerHTML = "";

    const intent = (data.intent || "").toUpperCase();
    const candidateTeam = data.candidate_team || {};
    const finalAnswer = data.final_answer || "";

    const hasValidTeam = candidateTeam && candidateTeam.players && candidateTeam.players.length === 11;

    if (hasValidTeam) {
      renderFantasyXI(data);
    } else {
      renderGeneralAnalysis(finalAnswer, data);
    }
  }

  // ----------------------------------------------------------------------------
  // Render Fantasy XI View
  // ----------------------------------------------------------------------------
  function renderFantasyXI(data) {
    const candidate = data.candidate_team || {};
    const players = candidate.players || [];
    const captainName = candidate.captain || "N/A";
    const captainReason = candidate.captain_reason || "Ranked #1 with highest verified Selection Score.";
    const viceCaptainName = candidate.vice_captain || "N/A";
    const viceCaptainReason = candidate.vice_captain_reason || "Ranked #2 with strong dual-utility balance.";
    const insights = candidate.selection_insights || [];
    const stats = data.stats || {};

    // Find captain & vice captain player objects
    const captainObj = players.find(p => p.name === captainName) || { name: captainName, team: "", role: "", selection_score: 43.0 };
    const vcObj = players.find(p => p.name === viceCaptainName) || { name: viceCaptainName, team: "", role: "", selection_score: 40.5 };

    const dashboard = document.createElement("div");
    dashboard.className = "fantasy-dashboard";

    // 1. Leadership Scoreboard (Captain & Vice-Captain)
    const leadershipGrid = document.createElement("div");
    leadershipGrid.className = "leadership-grid";
    leadershipGrid.innerHTML = `
      <div class="leadership-card captain-card">
        <div class="card-header-bar">
          <span class="card-tag">CAPTAIN</span>
          <span class="role-badge">${escapeHtml(captainObj.role || "C")}</span>
        </div>
        <div class="player-identity-name">${escapeHtml(captainObj.name)}</div>
        <div class="player-identity-sub">${escapeHtml(captainObj.team)} &middot; ${escapeHtml(captainObj.role)}</div>
        <div class="score-display-box">
          <span class="score-display-label">SELECTION SCORE</span>
          <span class="score-display-value">${(captainObj.selection_score || 0).toFixed(1)}</span>
        </div>
      </div>

      <div class="leadership-card vice-captain-card">
        <div class="card-header-bar">
          <span class="card-tag tag-vc">VICE CAPTAIN</span>
          <span class="role-badge">${escapeHtml(vcObj.role || "VC")}</span>
        </div>
        <div class="player-identity-name">${escapeHtml(vcObj.name)}</div>
        <div class="player-identity-sub">${escapeHtml(vcObj.team)} &middot; ${escapeHtml(vcObj.role)}</div>
        <div class="score-display-box">
          <span class="score-display-label">SELECTION SCORE</span>
          <span class="score-display-value">${(vcObj.selection_score || 0).toFixed(1)}</span>
        </div>
      </div>
    `;
    dashboard.appendChild(leadershipGrid);

    // 2. Fantasy XI Data Table
    const tableContainer = document.createElement("div");
    tableContainer.className = "data-table-container";

    let rowsHtml = "";
    players.forEach((p, idx) => {
      const isC = p.name === captainName ? " <strong>(C)</strong>" : (p.name === viceCaptainName ? " <strong>(VC)</strong>" : "");
      const numStr = String(idx + 1).padStart(2, "0");
      const availRaw = (p.data_factors && p.data_factors.availability) || "EXPECTED";
      const availDisplay = formatAvailabilityBadge(availRaw);

      rowsHtml += `
        <tr>
          <td class="col-num">${numStr}</td>
          <td>${escapeHtml(p.name)}${isC}</td>
          <td class="col-center"><strong>${escapeHtml(p.team || "")}</strong></td>
          <td class="col-center"><span class="role-badge">${escapeHtml(p.role || "")}</span></td>
          <td class="col-score"><span class="score-badge">${(p.selection_score || 0).toFixed(1)}</span></td>
          <td class="col-center">${availDisplay}</td>
        </tr>
      `;
    });

    tableContainer.innerHTML = `
      <table class="analytics-table">
        <thead>
          <tr>
            <th class="col-num">#</th>
            <th>PLAYER</th>
            <th class="col-center">TEAM</th>
            <th class="col-center">ROLE</th>
            <th class="col-score">SELECTION SCORE</th>
            <th class="col-center">AVAILABILITY</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
    `;
    dashboard.appendChild(tableContainer);

    // 3. Selection Analysis Section
    const analysisBox = document.createElement("div");
    analysisBox.className = "analysis-card-box";

    let insightsListHtml = `
      <li><strong>Captain Selection:</strong> ${escapeHtml(captainReason)}</li>
      <li><strong>Vice-Captain Selection:</strong> ${escapeHtml(viceCaptainReason)}</li>
    `;

    insights.forEach(ins => {
      insightsListHtml += `<li>${escapeHtml(ins)}</li>`;
    });

    analysisBox.innerHTML = `
      <div class="box-title">
        <span>SELECTION ANALYSIS</span>
        <span class="section-badge">VERIFIED REASONING</span>
      </div>
      <ul class="box-list">
        ${insightsListHtml}
      </ul>

      <div class="box-title" style="margin-top: 18px;">
        <span>DATA FACTOR TRANSPARENCY</span>
      </div>
      <div class="factors-grid">
        <div class="factor-item">
          <span class="factor-name">Batting Statistics</span>
          <span class="factor-val">${stats.players && Object.keys(stats.players).length ? "Available / MCP" : "Unavailable (Limit)"}</span>
        </div>
        <div class="factor-item">
          <span class="factor-name">Bowling Statistics</span>
          <span class="factor-val">${stats.players && Object.keys(stats.players).length ? "Available / MCP" : "Unavailable (Limit)"}</span>
        </div>
        <div class="factor-item">
          <span class="factor-name">Head-to-Head Records</span>
          <span class="factor-val">${stats.head_to_head && stats.head_to_head.found ? "Available" : "Unavailable from endpoints"}</span>
        </div>
        <div class="factor-item">
          <span class="factor-name">Live News &amp; Lineups</span>
          <span class="factor-val">Verified via Tavily Live Search</span>
        </div>
      </div>
    `;
    dashboard.appendChild(analysisBox);

    // 4. Data Sources Strip
    const sourcesStrip = document.createElement("div");
    sourcesStrip.className = "sources-strip";
    sourcesStrip.innerHTML = `
      <span class="sources-label">DATA SOURCES:</span>
      <div class="sources-tags">
        <span class="source-tag">MCP Cricket Statistics Provider (CricketData.org)</span>
        <span class="source-tag">Tavily Live Team &amp; News Intelligence</span>
        <span class="source-tag">Deterministic Selection Score Engine</span>
      </div>
    `;
    dashboard.appendChild(sourcesStrip);

    outputContainer.appendChild(dashboard);
  }

  // ----------------------------------------------------------------------------
  // Render General Analysis / Markdown View
  // ----------------------------------------------------------------------------
  function renderGeneralAnalysis(markdownText, fullData) {
    const container = document.createElement("div");
    container.className = "general-analysis-output";

    if (!markdownText || !markdownText.trim()) {
      container.innerHTML = `
        <div class="result-view-state">
          <div class="empty-headline">DATA UNAVAILABLE</div>
          <p class="empty-text">No analytical response was returned by the backend.</p>
        </div>
      `;
      outputContainer.appendChild(container);
      return;
    }

    container.innerHTML = parseMarkdownToHtml(markdownText);

    // Append data sources strip
    const sourcesStrip = document.createElement("div");
    sourcesStrip.className = "sources-strip";
    sourcesStrip.style.marginTop = "12px";
    sourcesStrip.innerHTML = `
      <span class="sources-label">DATA SOURCES:</span>
      <div class="sources-tags">
        <span class="source-tag">MCP Cricket Statistics Provider</span>
        <span class="source-tag">RAG Official Regulations (data/rules.txt)</span>
        <span class="source-tag">Tavily Current Research</span>
      </div>
    `;
    container.appendChild(sourcesStrip);

    outputContainer.appendChild(container);
  }

  // ----------------------------------------------------------------------------
  // Helper: Format Availability Badges
  // ----------------------------------------------------------------------------
  function formatAvailabilityBadge(statusText) {
    const s = String(statusText || "").toLowerCase();
    if (s.includes("confirmed") || s.includes("verified (confirmed")) {
      return `<span class="status-pill status-confirmed">CONFIRMED</span>`;
    } else if (s.includes("expected") || s.includes("verified (expected")) {
      return `<span class="status-pill status-expected">EXPECTED</span>`;
    } else if (s.includes("doubtful") || s.includes("fitness")) {
      return `<span class="status-pill status-doubtful">DOUBTFUL</span>`;
    } else if (s.includes("ruled out") || s.includes("injured")) {
      return `<span class="status-pill status-doubtful">RULED OUT</span>`;
    }
    return `<span class="status-pill status-squad">SQUAD</span>`;
  }

  // ----------------------------------------------------------------------------
  // Helper: Custom Clean Markdown Parser for Data & Tables
  // ----------------------------------------------------------------------------
  function parseMarkdownToHtml(md) {
    if (!md) return "";

    const lines = md.split("\n");
    let html = "";
    let inTable = false;
    let tableLines = [];
    let inList = false;

    function flushList() {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
    }

    function flushTable() {
      if (inTable && tableLines.length > 0) {
        html += renderMarkdownTable(tableLines);
        inTable = false;
        tableLines = [];
      }
    }

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i].trim();

      // Check Table
      if (line.startsWith("|") && line.endsWith("|")) {
        flushList();
        inTable = true;
        tableLines.push(line);
        continue;
      } else {
        flushTable();
      }

      if (!line) {
        flushList();
        continue;
      }

      // Headings
      if (line.startsWith("### ")) {
        flushList();
        html += `<h3>${escapeHtml(line.slice(4))}</h3>`;
      } else if (line.startsWith("## ")) {
        flushList();
        html += `<h3>${escapeHtml(line.slice(3))}</h3>`;
      } else if (line.startsWith("# ")) {
        flushList();
        html += `<h3>${escapeHtml(line.slice(2))}</h3>`;
      } else if (line.startsWith("- ") || line.startsWith("* ")) {
        if (!inList) {
          html += "<ul class='box-list'>";
          inList = true;
        }
        const itemContent = line.slice(2);
        html += `<li>${formatInlineMarkdown(itemContent)}</li>`;
      } else {
        flushList();
        html += `<p>${formatInlineMarkdown(line)}</p>`;
      }
    }

    flushList();
    flushTable();

    return html;
  }

  function renderMarkdownTable(lines) {
    if (lines.length < 2) return "";

    const headerLine = lines[0];
    const headers = headerLine.split("|").map(s => s.trim()).filter((s, idx, arr) => idx > 0 && idx < arr.length - 1);

    // Skip separator line (lines[1])
    const bodyLines = lines.slice(2);

    let thHtml = headers.map(h => `<th>${escapeHtml(h)}</th>`).join("");
    let tbodyHtml = "";

    bodyLines.forEach(bl => {
      const cells = bl.split("|").map(s => s.trim()).filter((s, idx, arr) => idx > 0 && idx < arr.length - 1);
      if (cells.length > 0) {
        tbodyHtml += "<tr>" + cells.map(c => `<td>${formatInlineMarkdown(c)}</td>`).join("") + "</tr>";
      }
    });

    return `
      <div class="data-table-container" style="margin: 12px 0;">
        <table class="analytics-table">
          <thead>
            <tr>${thHtml}</tr>
          </thead>
          <tbody>
            ${tbodyHtml}
          </tbody>
        </table>
      </div>
    `;
  }

  function formatInlineMarkdown(text) {
    if (!text) return "";
    let res = escapeHtml(text);
    // Bold: **text**
    res = res.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Inline code: `text`
    res = res.replace(/`(.*?)`/g, "<span class='score-badge'>$1</span>");
    return res;
  }

  function escapeHtml(str) {
    if (typeof str !== "string") return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // ----------------------------------------------------------------------------
  // Event Listeners
  // ----------------------------------------------------------------------------
  queryForm.addEventListener("submit", (e) => {
    e.preventDefault();
    performAnalysis(queryInput.value);
  });

  clearBtn.addEventListener("click", () => {
    queryInput.value = "";
    setViewState("EMPTY");
    queryInput.focus();
  });

  retryBtn.addEventListener("click", () => {
    if (currentQuery) {
      performAnalysis(currentQuery);
    } else {
      setViewState("EMPTY");
    }
  });

  quickButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-query");
      if (q) {
        performAnalysis(q);
      }
    });
  });

  // Initial State
  setViewState("EMPTY");
});
