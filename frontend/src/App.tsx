import React, { useEffect, useState } from "react";
import {
  CartItem,
  EvaluationResult,
  fetchCartItems,
  fetchHealth,
  startEvaluation,
  pollEvaluation,
  fetchEvaluationsForCartItem,
} from "./api";

export default function App() {
  const [healthStatus, setHealthStatus] = useState<string>("connecting");
  const [sessionId, setSessionId] = useState<string>("");
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [loadingCart, setLoadingCart] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<"pipeline" | "evaluations">("pipeline");
  const [selectedFilter, setSelectedFilter] = useState<"all" | "crexi" | "loopnet">("all");
  
  // Evaluation Drawer State
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [activeItem, setActiveItem] = useState<CartItem | null>(null);
  const [activeEval, setActiveEval] = useState<EvaluationResult | null>(null);
  const [evaluatingIds, setEvaluatingIds] = useState<Record<string, string>>({}); // cart_item_id -> evaluation_id
  const [rawViewItemIds, setRawViewItemIds] = useState<Record<string, boolean>>({});

  // 1. Health check & Initial Data Fetch with Auto-refresh
  useEffect(() => {
    fetchHealth()
      .then((h) => setHealthStatus(`${h.service} v${h.version}`))
      .catch(() => setHealthStatus("Offline (Check Backend)"));

    loadCart(true);

    // Auto-poll cart items every 4s to catch new captures from Chrome Extension
    const interval = setInterval(() => {
      loadCart(false);
    }, 4000);

    return () => clearInterval(interval);
  }, [sessionId]);

  const loadCart = async (showSpinner = false) => {
    if (showSpinner) setLoadingCart(true);
    try {
      const items = await fetchCartItems(sessionId);
      setCartItems(items);
    } catch (err) {
      console.error(err);
    } finally {
      if (showSpinner) setLoadingCart(false);
    }
  };

  // 2. Trigger Site Evaluation
  const handleStartEvaluation = async (item: CartItem) => {
    setActiveItem(item);
    setDrawerOpen(true);
    
    // Check if we already have an evaluation
    try {
      const existing = await fetchEvaluationsForCartItem(item.cart_item_id);
      if (existing.length > 0 && existing[0].status === "done") {
        setActiveEval(existing[0]);
        return;
      }
    } catch (e) {
      console.error(e);
    }

    // Start fresh evaluation
    try {
      setActiveEval({ evaluation_id: "starting", cart_item_id: item.cart_item_id, status: "processing" });
      const job = await startEvaluation(item.cart_item_id);
      setEvaluatingIds((prev) => ({ ...prev, [item.cart_item_id]: job.evaluation_id }));

      // Poll until done
      pollUntilComplete(job.evaluation_id, item);
    } catch (err: any) {
      alert(`Error starting evaluation: ${err.message}`);
      setActiveEval({
        evaluation_id: "error",
        cart_item_id: item.cart_item_id,
        status: "error",
        error: err.message,
      });
    }
  };

  // Poll helper
  const pollUntilComplete = (evalId: string, item: CartItem) => {
    const interval = setInterval(async () => {
      try {
        const res = await pollEvaluation(evalId);
        if (res.status === "done" || res.status === "error") {
          clearInterval(interval);
          setActiveEval(res);
          setEvaluatingIds((prev) => {
            const next = { ...prev };
            delete next[item.cart_item_id];
            return next;
          });
        } else {
          setActiveEval(res);
        }
      } catch (err) {
        clearInterval(interval);
      }
    }, 2500);
  };

  const handleOpenDrawer = async (item: CartItem) => {
    setActiveItem(item);
    setDrawerOpen(true);
    setActiveEval(null);
    try {
      const existing = await fetchEvaluationsForCartItem(item.cart_item_id);
      if (existing.length > 0) {
        setActiveEval(existing[0]);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Filtered items
  const filteredCartItems = cartItems.filter((item) => {
    if (selectedFilter === "crexi") return item.source_url?.includes("crexi");
    if (selectedFilter === "loopnet") return item.source_url?.includes("loopnet");
    return true;
  });

  return (
    <div className="flex h-screen overflow-hidden bg-[#0B0F17] text-[#DFE2EE] font-body">
      {/* ── Left Sidebar Navigation ────────────────────────────────────────── */}
      <aside className="hidden md:flex flex-col w-64 bg-[#0A0E16]/90 backdrop-blur-2xl border-r border-white/5 shadow-[20px_0_40px_rgba(0,0,0,0.4)] fixed inset-y-0 left-0 z-40">
        {/* Brand Header */}
        <div className="p-6 flex items-center gap-3 border-b border-white/5">
          <div className="w-8 h-8 rounded-full bg-[#10B981]/20 border border-[#10B981]/40 flex items-center justify-center text-[#4EDEA3] shadow-[0_0_15px_rgba(78,222,163,0.3)]">
            <span className="material-symbols-outlined text-[20px]">radar</span>
          </div>
          <div>
            <h1 className="font-display font-bold text-lg text-white leading-tight tracking-tight">Site Ranker</h1>
            <p className="text-[11px] text-[#BBCABF] font-mono uppercase tracking-wider">Obsidian Intelligence</p>
          </div>
        </div>

        {/* Status Indicator */}
        <div className="px-6 py-3 border-b border-white/5 bg-[#181C24]/50 flex items-center justify-between text-xs">
          <span className="text-[#BBCABF] flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${healthStatus.includes("Offline") ? "bg-red-500" : "bg-[#4EDEA3] animate-pulse"}`}></span>
            Backend Engine
          </span>
          <span className="font-mono text-[#4EDEA3] text-[11px]">{healthStatus.includes("v") ? healthStatus.split("v")[1] : "Online"}</span>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <button
            onClick={() => setActiveTab("pipeline")}
            className={`w-full px-4 py-3 rounded flex items-center gap-3 text-sm font-medium transition-all ${
              activeTab === "pipeline"
                ? "bg-[#0566D9]/20 text-[#4EDEA3] border-r-4 border-[#4EDEA3]"
                : "text-[#BBCABF] hover:bg-white/5"
            }`}
          >
            <span className="material-symbols-outlined text-[20px]">domain</span>
            <span>Property Pipeline</span>
            <span className="ml-auto bg-[#262A33] text-xs px-2 py-0.5 rounded text-[#4EDEA3] font-mono">{cartItems.length}</span>
          </button>
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-white/5 bg-[#0F131C]">
          <div className="text-[11px] text-[#BBCABF] space-y-1">
            <div className="flex justify-between">
              <span>Session:</span>
              <span className="font-mono text-white truncate max-w-[120px]">{sessionId || "Default"}</span>
            </div>
            <div className="flex justify-between">
              <span>5-Agent AI:</span>
              <span className="text-[#4EDEA3]">GPT-4o Ready</span>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main Content Area ──────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col md:ml-64 relative w-full overflow-hidden">
        {/* Top Mobile Header */}
        <header className="md:hidden flex items-center justify-between p-4 border-b border-white/5 glass-panel sticky top-0 z-30">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[#4EDEA3]">radar</span>
            <span className="font-display font-bold text-white text-lg">Site Ranker</span>
          </div>
          <span className="text-xs px-2 py-1 bg-[#10B981]/20 text-[#4EDEA3] rounded border border-[#10B981]/30">{cartItems.length} Items</span>
        </header>

        {/* Scrollable Canvas */}
        <div className="flex-1 overflow-y-auto p-6 md:p-10 space-y-8">
          {/* Header Bar */}
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-xs font-mono text-[#4EDEA3] uppercase tracking-widest mb-1">
                <span>Obsidian Intelligence System</span>
                <span>•</span>
                <span>v0.3.3 API</span>
              </div>
              <h1 className="font-display text-3xl md:text-4xl font-bold text-white tracking-tight">Property Pipeline</h1>
              <p className="text-[#BBCABF] text-sm mt-1">Multi-site commercial real estate listings captured via Chrome Extension.</p>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-2 bg-[#181C24] p-1 rounded-lg border border-white/5">
              <button
                onClick={() => setSelectedFilter("all")}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                  selectedFilter === "all" ? "bg-[#0566D9] text-white" : "text-[#BBCABF] hover:text-white"
                }`}
              >
                All ({cartItems.length})
              </button>
              <button
                onClick={() => setSelectedFilter("crexi")}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                  selectedFilter === "crexi" ? "bg-purple-600 text-white" : "text-[#BBCABF] hover:text-white"
                }`}
              >
                Crexi
              </button>
              <button
                onClick={() => setSelectedFilter("loopnet")}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                  selectedFilter === "loopnet" ? "bg-red-600 text-white" : "text-[#BBCABF] hover:text-white"
                }`}
              >
                LoopNet
              </button>
            </div>
          </div>

          {/* Loading State */}
          {loadingCart && (
            <div className="flex flex-col items-center justify-center py-20 text-[#BBCABF] space-y-3">
              <div className="w-8 h-8 border-2 border-[#4EDEA3] border-t-transparent rounded-full animate-spin"></div>
              <p className="text-sm">Loading captured property portfolio...</p>
            </div>
          )}

          {/* Empty State */}
          {!loadingCart && filteredCartItems.length === 0 && (
            <div className="glass-panel rounded-xl p-12 text-center max-w-xl mx-auto space-y-4">
              <div className="w-12 h-12 rounded-full bg-[#262A33] text-[#BBCABF] flex items-center justify-center mx-auto">
                <span className="material-symbols-outlined text-2xl">domain_disabled</span>
              </div>
              <h3 className="font-display font-semibold text-lg text-white">No Captured Listings Found</h3>
              <p className="text-sm text-[#BBCABF]">
                Use the <span className="text-[#4EDEA3] font-medium">Site Ranker Chrome Extension</span> on Crexi or LoopNet listing detail pages to capture properties into your pipeline!
              </p>
            </div>
          )}

          {/* Bento Property Cards Grid */}
          {!loadingCart && filteredCartItems.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
              {filteredCartItems.map((item) => {
                const structured = item.llm_structured || {};
                const isCrexi = item.source_url?.includes("crexi");
                const isEvaluating = !!evaluatingIds[item.cart_item_id];
                const showRaw = !!rawViewItemIds[item.cart_item_id];

                return (
                  <div
                    key={item.cart_item_id}
                    className="glass-panel-interactive rounded-xl overflow-hidden flex flex-col group relative"
                  >
                    {/* Source & Status Badges */}
                    <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
                      <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider backdrop-blur-md border ${
                        isCrexi 
                          ? "bg-purple-900/60 text-purple-200 border-purple-500/40" 
                          : "bg-red-900/60 text-red-200 border-red-500/40"
                      }`}>
                        {isCrexi ? "Crexi" : "LoopNet"}
                      </span>

                      {isEvaluating && (
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-[#10B981]/20 text-[#4EDEA3] border border-[#10B981]/40 animate-pulse flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#4EDEA3] animate-ping"></span>
                          5-Agent AI Running...
                        </span>
                      )}
                    </div>

                    {/* Image Header */}
                    <div
                      className="w-full h-44 bg-cover bg-center relative border-b border-white/5 bg-[#181C24]"
                      style={{
                        backgroundImage: item.image_url
                          ? `url('${item.image_url}')`
                          : "linear-gradient(to bottom, #1C2028, #0F131C)",
                      }}
                    >
                      <div className="absolute inset-0 bg-gradient-to-t from-[#151C28] via-transparent to-transparent opacity-90"></div>
                      {!item.image_url && (
                        <div className="absolute inset-0 flex items-center justify-center text-white/10">
                          <span className="material-symbols-outlined text-6xl">apartment</span>
                        </div>
                      )}
                    </div>

                    {/* Card Body */}
                    <div className="p-5 flex-1 flex flex-col space-y-4">
                      {/* Title & Location */}
                      <div>
                        <h3 className="font-display font-semibold text-lg text-white leading-snug line-clamp-1">
                          {item.listing_title || item.address}
                        </h3>
                        <p className="text-xs text-[#BBCABF] mt-0.5 flex items-center gap-1 truncate">
                          <span className="material-symbols-outlined text-sm text-[#4EDEA3]">location_on</span>
                          {item.address}
                        </p>
                      </div>

                      {/* Financial Metrics Grid */}
                      {!showRaw ? (
                        <div className="grid grid-cols-3 gap-2 py-2.5 px-3 bg-[#0D121C] rounded-lg border border-white/5 text-xs font-mono">
                          <div>
                            <div className="text-[10px] text-[#BBCABF] uppercase tracking-wider mb-0.5">Price</div>
                            <div className="text-white font-medium truncate" title={
                              structured?.financials?.asking_price_display ||
                              (structured?.financials?.asking_price ? `$${structured.financials.asking_price.toLocaleString()}` : null) ||
                              item.details?.["price"] || item.details?.["Asking Price"] || "N/A"
                            }>
                              {structured?.financials?.asking_price_display ||
                               (structured?.financials?.asking_price ? `$${structured.financials.asking_price.toLocaleString()}` : null) ||
                               (structured?.asking_price ? `$${structured.asking_price.toLocaleString()}` : null) ||
                               item.details?.["price"] || item.details?.["Asking Price"] || "N/A"}
                            </div>
                          </div>
                          <div>
                            <div className="text-[10px] text-[#BBCABF] uppercase tracking-wider mb-0.5">Cap Rate</div>
                            <div className="text-[#4EDEA3] font-medium truncate">
                              {structured?.financials?.cap_rate_percent !== undefined && structured?.financials?.cap_rate_percent !== null
                                ? `${structured.financials.cap_rate_percent}%`
                                : (structured?.cap_rate_pct ? `${structured.cap_rate_pct}%` : (item.details?.["Cap Rate"] || "N/A"))}
                            </div>
                          </div>
                          <div>
                            <div className="text-[10px] text-[#BBCABF] uppercase tracking-wider mb-0.5">NOI</div>
                            <div className="text-white font-medium truncate">
                              {structured?.financials?.noi_annual
                                ? `$${structured.financials.noi_annual.toLocaleString()}`
                                : (structured?.noi_annual ? `$${structured.noi_annual.toLocaleString()}` : (item.details?.["NOI"] || "N/A"))}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="max-h-28 overflow-y-auto p-2 bg-[#0A0E16] rounded border border-white/5 font-mono text-[10px] text-[#BBCABF] space-y-1">
                          {Object.entries(item.details || {}).map(([k, v]) => (
                            <div key={k} className="flex justify-between">
                              <span className="text-white/60 truncate max-w-[120px]">{k}:</span>
                              <span className="text-white truncate max-w-[140px]">{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* View Toggle & Actions */}
                      <div className="pt-2 border-t border-white/5 flex items-center justify-between gap-2 mt-auto">
                        <button
                          onClick={() => setRawViewItemIds((prev) => ({ ...prev, [item.cart_item_id]: !showRaw }))}
                          className="text-[11px] text-[#BBCABF] hover:text-white transition-colors underline decoration-white/20"
                        >
                          {showRaw ? "Show Clean Facts" : "Show Raw Provenance"}
                        </button>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleOpenDrawer(item)}
                            className="p-2 rounded bg-white/5 text-[#BBCABF] hover:text-white hover:bg-white/10 transition-colors"
                            title="View Saved Reports"
                          >
                            <span className="material-symbols-outlined text-sm">visibility</span>
                          </button>

                          <button
                            onClick={() => handleStartEvaluation(item)}
                            disabled={isEvaluating}
                            className="px-3 py-2 rounded bg-[#0566D9] hover:bg-[#0566D9]/80 text-white font-medium text-xs flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(5,102,217,0.4)] disabled:opacity-50"
                          >
                            <span className="material-symbols-outlined text-sm">psychology</span>
                            <span>{isEvaluating ? "Evaluating..." : "Evaluate Site"}</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      {/* ── Slide-Over 5-Agent Council Evaluation Drawer ───────────────────── */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop Overlay */}
          <div className="drawer-overlay fixed inset-0" onClick={() => setDrawerOpen(false)}></div>

          {/* Drawer Container */}
          <div className="relative w-full md:w-[540px] bg-[#151C28] border-l border-white/10 shadow-[ -20px_0_40px_rgba(0,0,0,0.6) ] flex flex-col h-full z-50 overflow-hidden">
            {/* Header */}
            <div className="p-6 border-b border-white/5 flex justify-between items-start bg-[#1C2028]">
              <div>
                <div className="flex items-center gap-2 text-xs font-mono text-[#4EDEA3] uppercase tracking-wider mb-1">
                  <span className="material-symbols-outlined text-sm">psychology</span>
                  <span>5-Agent Council Evaluation Report</span>
                </div>
                <h2 className="font-display text-xl font-bold text-white line-clamp-1">{activeItem?.listing_title || activeItem?.address}</h2>
                <p className="text-xs text-[#BBCABF] truncate max-w-[400px] mt-0.5">{activeItem?.address}</p>
              </div>

              <button
                onClick={() => setDrawerOpen(false)}
                className="p-1.5 rounded-full text-[#BBCABF] hover:text-white hover:bg-white/5 transition-colors"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            </div>

            {/* Scrollable Content Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Evaluating State */}
              {(!activeEval || activeEval.status === "processing") && (
                <div className="p-8 glass-panel rounded-xl text-center space-y-4">
                  <div className="w-12 h-12 border-4 border-[#4EDEA3] border-t-transparent rounded-full animate-spin mx-auto"></div>
                  <h3 className="font-display font-semibold text-lg text-white">Running 5-Agent Council Audit</h3>
                  <p className="text-xs text-[#BBCABF] max-w-sm mx-auto">
                    Energy, Water, Surface, Transportation, and Risk agents are concurrently fetching Mireye GIS data and analyzing location intelligence...
                  </p>
                </div>
              )}

              {/* Error State */}
              {activeEval?.status === "error" && (
                <div className="p-6 bg-red-950/40 border border-red-500/30 rounded-xl space-y-2 text-red-200">
                  <h3 className="font-semibold text-sm flex items-center gap-2 text-red-400">
                    <span className="material-symbols-outlined">error</span>
                    Evaluation Failed
                  </h3>
                  <p className="text-xs font-mono">{activeEval.error}</p>
                </div>
              )}

              {/* Completed Evaluation View */}
              {activeEval?.status === "done" && (
                <>
                  {/* Executive Score & Verdict Banner */}
                  <div className="p-6 rounded-xl bg-gradient-to-br from-[#10B981]/15 to-transparent border border-[#10B981]/30 flex items-center gap-6">
                    {/* Score Dial */}
                    <div className="relative w-24 h-24 flex items-center justify-center shrink-0">
                      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                        <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(78, 222, 163, 0.1)" strokeWidth="8" />
                        <circle
                          cx="50"
                          cy="50"
                          r="42"
                          fill="none"
                          stroke="#4EDEA3"
                          strokeWidth="8"
                          strokeDasharray="263.8"
                          strokeDashoffset={263.8 - (263.8 * (activeEval.overall_score || 0)) / 100}
                          strokeLinecap="round"
                          className="transition-all duration-1000 ease-out"
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="font-display font-bold text-3xl text-[#4EDEA3]">{activeEval.overall_score || 0}</span>
                        <span className="text-[9px] uppercase tracking-wider text-[#BBCABF]">/ 100</span>
                      </div>
                    </div>

                    {/* Verdict Message */}
                    <div className="space-y-1">
                      <div className="text-[10px] text-[#BBCABF] uppercase tracking-widest font-mono">Executive Board Verdict</div>
                      <h3 className="font-display text-xl font-bold text-[#4EDEA3]">{activeEval.recommendation}</h3>
                      <p className="text-xs text-[#BBCABF] leading-relaxed">
                        Synthesized aggregate score based on physical GIS facts and listing claims.
                      </p>
                    </div>
                  </div>

                  {/* Flagged Conflicts Alert Card */}
                  {activeEval.conflicts_flagged && activeEval.conflicts_flagged.length > 0 && (
                    <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-500/30 text-amber-200 space-y-2">
                      <div className="flex items-center gap-2 font-semibold text-xs text-amber-400">
                        <span className="material-symbols-outlined text-base">warning</span>
                        <span>Council Disagreements & Listing Contradictions ({activeEval.conflicts_flagged.length})</span>
                      </div>
                      <ul className="space-y-1.5 pl-6 list-disc text-xs text-amber-200/90 font-mono">
                        {activeEval.conflicts_flagged.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* 5 Agent Discipline Cards */}
                  <div className="space-y-4">
                    <h3 className="font-display font-semibold text-sm text-white flex items-center gap-2">
                      <span className="material-symbols-outlined text-[#4EDEA3]">group_work</span>
                      <span>Discipline Agent Breakdown (5 Council Members)</span>
                    </h3>

                    {activeEval.agent_results?.map((agent) => (
                      <div key={agent.agent_name} className="glass-panel p-4 rounded-xl space-y-3">
                        <div className="flex items-center justify-between border-b border-white/5 pb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-display font-semibold text-sm text-white">{agent.agent_name}</span>
                            <span className="text-[10px] px-2 py-0.5 rounded bg-white/5 text-[#BBCABF] uppercase font-mono">
                              {agent.data_availability} data
                            </span>
                          </div>
                          <span className="font-mono font-bold text-sm text-[#4EDEA3]">{agent.score} / 100</span>
                        </div>

                        <p className="text-xs text-[#DFE2EE] leading-relaxed">{agent.summary}</p>
                        <p className="text-xs text-[#BBCABF] italic bg-[#0A0E16] p-2.5 rounded border border-white/5">
                          "{agent.memo}"
                        </p>

                        {/* Citations Tag Cloud */}
                        {agent.citations && agent.citations.length > 0 && (
                          <div className="space-y-1 pt-1">
                            <div className="text-[10px] text-[#BBCABF] font-mono uppercase tracking-wider">Citations ({agent.citations.length})</div>
                            <div className="flex flex-wrap gap-1.5">
                              {agent.citations.map((c, idx) => (
                                <span
                                  key={idx}
                                  className={`text-[10px] px-2 py-0.5 rounded font-mono border ${
                                    c.source === "mireye"
                                      ? "bg-[#0566D9]/15 text-blue-300 border-blue-500/30"
                                      : "bg-purple-950/40 text-purple-300 border-purple-500/30"
                                  }`}
                                >
                                  {c.field}: {String(c.value)}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
