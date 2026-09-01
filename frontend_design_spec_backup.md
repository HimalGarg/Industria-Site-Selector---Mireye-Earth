# AgentCouncil: Frontend Design Specification

This document outlines the required UI components, data flows, and layout structures for the frontend implementation of the Agentic Council architecture. It is based on the finalized design requirements.

## 1. Input Interface (Site Selection)

**Component: Interactive Map & Form**
- **Map:** Display an interactive map where users can drop up to 5 pins.
- **Auto-fill:** Dropping a pin should automatically extract and lock in the `lat` and `lng` values for that site.
- **Popup/Sidebar Form:** For each dropped pin, provide a form to capture:
  - **Label (String):** e.g., "Austin Gigafactory" (Required)
  - **Cost (Number):** Total cost of the land in USD (Optional)
  - **Area (Number):** Size of the land in acres (Optional)
  
*Note: Cost and Area are passed to the backend so the Lead Synthesizer can evaluate "value-for-money" (Cost per Acre).*

## 2. Configuration Interface

**Component: Agent Weighting (Independent Sliders)**
- Render a 0-100% slider for each of the core agents:
  1. Energy & Power
  2. Water & Sewer
  3. Surface & Environment
  4. Transportation
  5. Risk & Compliance
- **UX Rule:** These sliders should operate independently. The frontend should collect the raw slider values (e.g., 80, 50, 100) and pass them as a dictionary to the backend. The backend will handle the mathematical normalization so they sum to 1.0.

**Component: Workforce Toggle (Day-in-the-Life)**
- Provide a checkbox: `[ ] Include Workforce Analysis`
- **Conditional UI:** When checked, display a multiline text area allowing the user to describe the worker profile (e.g., "Shifts are 6am to 6pm, needs urban access...").
- **UX Rule:** If checked, a 6th slider for "Workforce & Livability" must appear in the Agent Weighting section.

## 3. Output Presentation (Dashboard Layout)

The backend returns a rich JSON payload. The results should be presented in a top-down hierarchy.

### A. The Executive Summary
- **Placement:** Top of the page (Hero section).
- **Content:** Render the `synthesis` string from the backend response. This is the GPT-4o comparative analysis.
- **Citations:** Include the `synthesis_citations` as clickable footnotes or tooltips.

### B. Comparative Scoreboard
- **Placement:** Directly below the Executive Summary.
- **Format:** A table or leaderboard.
- **Columns:** Rank, Site Label, Weighted Score (0-100), Cost per Acre (if available), and Sparklines/Badges for the top positive/negative agent verdicts.

### C. Deep Dive (Modals/Drawers)
- **Interaction:** When a user clicks on a specific site row in the scoreboard, open a side-drawer or modal.
- **Content:** 
  - Display the array of `agent_reports`.
  - For each agent, show its individual `score`, a bolded `verdict`, and the detailed `memo`.
  - **Data Gaps:** If an agent report contains items in its `data_gaps` array, display a warning icon (e.g., ⚠️ "API data missing for X, agent fell back to LLM estimation").
  - **Citations:** Provide links using the `source_url` from the agent's citation list so users can verify the raw data.

---

### Integration Notes for Frontend Devs

The backend exposes a single execution function/endpoint that expects a payload matching this structure:

```json
{
  "sites": [
    {
      "lat": 30.199699,
      "lng": -97.496411,
      "label": "Cedar Creek TX",
      "cost_usd": 5000000,
      "area_acres": 50
    }
  ],
  "worker_profile": "Needs a 30 min commute max by car.",
  "weights": {
    "energy_power": 100,
    "water_sewer": 50,
    "surface_environment": 80,
    "transportation": 90,
    "risk_compliance": 100,
    "workforce_livability": 70
  }
}
```
