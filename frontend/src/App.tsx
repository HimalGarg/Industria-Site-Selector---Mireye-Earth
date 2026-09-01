import React, { useEffect, useState } from "react";
import {
  CartItem,
  EvaluationResult,
  fetchCartItems,
  fetchHealth,
  fetchAllEvaluations,
  deleteCartItem,
} from "./api";
import SiteDetailPage from "./pages/SiteDetailPage";
import ComparePage from "./pages/ComparePage";
import RecommendationsPage from "./pages/RecommendationsPage";

export default function App() {
  const [healthStatus, setHealthStatus] = useState<string>("connecting");
  const [sessionId, setSessionId] = useState<string>("default-session");
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [evaluationsMap, setEvaluationsMap] = useState<Record<string, EvaluationResult>>({});
  const [loadingCart, setLoadingCart] = useState<boolean>(true);
  const [selectedFilter, setSelectedFilter] = useState<"all" | "crexi" | "loopnet">("all");
  const [rawViewItemIds, setRawViewItemIds] = useState<Record<string, boolean>>({});

  // Client-Side Routing State: "pipeline" | "site" | "compare"
  const [route, setRoute] = useState<"pipeline" | "site" | "compare" | "recommendations">("pipeline");
  const [activeCartItemId, setActiveCartItemId] = useState<string | null>(null);

  // 1. Health check & Initial Data Fetch with Auto-refresh
  useEffect(() => {
    fetchHealth()
      .then((h) => setHealthStatus(`${h.service} v${h.version}`))
      .catch(() => setHealthStatus("Offline (Check Backend)"));

    loadCart(true);

    // Auto-poll cart items & evaluations every 4s to catch updates
    const interval = setInterval(() => {
      loadCart(false);
    }, 4000);

    return () => clearInterval(interval);
  }, [sessionId]);

  const loadCart = async (showSpinner = false) => {
    if (showSpinner) setLoadingCart(true);
    try {
      const items = await fetchCartItems();
      setCartItems(items);

      // Fetch all completed evaluations to map status per card
      const evals = await fetchAllEvaluations();
      const evalMap: Record<string, EvaluationResult> = {};
      evals.forEach((ev) => {
        if (!evalMap[ev.cart_item_id]) {
          evalMap[ev.cart_item_id] = ev;
        }
      });
      setEvaluationsMap(evalMap);
    } catch (err) {
      console.error(err);
    } finally {
      if (showSpinner) setLoadingCart(false);
    }
  };

  // Delete Cart Item Handler
  const handleDeleteItem = async (e: React.MouseEvent, cartItemId: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this property from your pipeline?")) return;

    try {
      await deleteCartItem(cartItemId);
      setCartItems((prev) => prev.filter((item) => item.cart_item_id !== cartItemId));
      setEvaluationsMap((prev) => {
        const next = { ...prev };
        delete next[cartItemId];
        return next;
      });
      if (activeCartItemId === cartItemId) {
        setRoute("pipeline");
        setActiveCartItemId(null);
      }
    } catch (err: any) {
      alert(`Error deleting listing: ${err.message}`);
    }
  };

  // Navigation Helper
  const navigateToSite = (cartItemId: string) => {
    setActiveCartItemId(cartItemId);
    setRoute("site");
  };

  const navigateToCompare = () => {
    setRoute("compare");
  };

  const navigateToRecommendations = () => {
    setRoute("recommendations");
  };

  const navigateToPipeline = () => {
    setRoute("pipeline");
    setActiveCartItemId(null);
  };

  // Filtered items for Pipeline view
  const filteredCartItems = cartItems.filter((item) => {
    // Hide radius recommendations from the main pipeline
    if ((item as any).is_radius_recommendation) return false;

    if (selectedFilter === "crexi") return item.source_url?.includes("crexi");
    if (selectedFilter === "loopnet") return item.source_url?.includes("loopnet");
    return true;
  });

  const pipelineItemsCount = cartItems.filter(i => !(i as any).is_radius_recommendation).length;

  return (
    <div className="flex h-screen overflow-hidden bg-[#0B0F17] text-[#DFE2EE] font-body">
      {/* ── Left Sidebar Navigation ────────────────────────────────────────── */}
      <aside className="hidden md:flex flex-col w-64 bg-[#0A0E16]/90 backdrop-blur-2xl border-r border-white/5 shadow-[20px_0_40px_rgba(0,0,0,0.4)] fixed inset-y-0 left-0 z-40">
        {/* Brand Header */}
        <div className="p-6 flex items-center gap-3 border-b border-white/5 cursor-pointer" onClick={navigateToPipeline}>
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
            onClick={navigateToPipeline}
            className={`w-full px-4 py-3 rounded flex items-center gap-3 text-sm font-medium transition-all ${
              route === "pipeline"
                ? "bg-[#0566D9]/20 text-[#4EDEA3] border-r-4 border-[#4EDEA3]"
                : "text-[#BBCABF] hover:bg-white/5"
            }`}
          >
            <span className="material-symbols-outlined text-[20px]">domain</span>
            <span>Property Pipeline</span>
            <span className="ml-auto bg-[#262A33] text-xs px-2 py-0.5 rounded text-[#4EDEA3] font-mono">{pipelineItemsCount}</span>
          </button>

          <button
            onClick={navigateToCompare}
            className={`w-full px-4 py-3 rounded flex items-center gap-3 text-sm font-medium transition-all ${
              route === "compare"
                ? "bg-[#0566D9]/20 text-[#4EDEA3] border-r-4 border-[#4EDEA3]"
                : "text-[#BBCABF] hover:bg-white/5"
            }`}
          >
            <span className="material-symbols-outlined text-[20px]">compare_arrows</span>
            <span>Compare Sites</span>
            <span className="ml-auto bg-[#262A33] text-xs px-2 py-0.5 rounded text-[#4EDEA3] font-mono">Matrix</span>
          </button>
          <button
            onClick={navigateToRecommendations}
            className={`w-full px-4 py-3 rounded flex items-center gap-3 text-sm font-medium transition-all ${
              route === "recommendations"
                ? "bg-[#0566D9]/20 text-[#4EDEA3] border-r-4 border-[#4EDEA3]"
                : "text-[#BBCABF] hover:bg-white/5"
            }`}
          >
            <span className="material-symbols-outlined text-[20px]">my_location</span>
            <span>Recommendations</span>
            <span className="ml-auto bg-[#262A33] text-xs px-2 py-0.5 rounded text-[#4EDEA3] font-mono">2km</span>
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
      <main className="flex-1 flex flex-col md:ml-64 relative w-full overflow-y-auto">
        {/* Top Mobile Header */}
        <header className="md:hidden flex items-center justify-between p-4 border-b border-white/5 glass-panel sticky top-0 z-30">
          <div className="flex items-center gap-2" onClick={navigateToPipeline}>
            <span className="material-symbols-outlined text-[#4EDEA3]">radar</span>
            <span className="font-display font-bold text-white text-lg">Site Ranker</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={navigateToCompare} className="text-xs px-2.5 py-1 bg-[#0566D9] text-white rounded">
              Compare
            </button>
            <span className="text-xs px-2 py-1 bg-[#10B981]/20 text-[#4EDEA3] rounded border border-[#10B981]/30">{pipelineItemsCount}</span>
          </div>
        </header>

        {/* ROUTE 1: Site Detail View (/site/:cartItemId) */}
        {route === "site" && activeCartItemId && (
          <SiteDetailPage
            cartItemId={activeCartItemId}
            sessionId={sessionId}
            onBack={navigateToPipeline}
          />
        )}

        {/* ROUTE 2: Compare Page (/compare) */}
        {route === "compare" && (
          <ComparePage
            sessionId={sessionId}
            onBack={navigateToPipeline}
          />
        )}

        
        {/* ROUTE 4: Recommendations Page (/recommendations) */}
        {route === "recommendations" && (
          <RecommendationsPage
            sessionId={sessionId}
            onBack={navigateToPipeline}
            onOpenSite={(id) => {
              setActiveCartItemId(id);
              setRoute("site");
            }}
          />
        )}

        {/* ROUTE 3: Bento Grid Pipeline View (/) */}
        {route === "pipeline" && (
          <div className="p-6 md:p-10 space-y-8">
            {/* Header Bar */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-xs font-mono text-[#4EDEA3] uppercase tracking-widest mb-1">
                  <span>Obsidian Intelligence System</span>
                  <span>•</span>
                  <span>v0.3.5 API</span>
                </div>
                <h1 className="font-display text-3xl md:text-4xl font-bold text-white tracking-tight">Property Pipeline</h1>
                <p className="text-[#BBCABF] text-sm mt-1">Multi-site commercial real estate listings captured via Chrome Extension.</p>
              </div>

              {/* Action & Filter Pills */}
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={navigateToCompare}
                  className="px-4 py-2 rounded-lg bg-[#0566D9] hover:bg-[#0566D9]/80 text-white font-medium text-xs flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(5,102,217,0.4)]"
                >
                  <span className="material-symbols-outlined text-base">compare_arrows</span>
                  <span>Compare Sites</span>
                </button>

                <div className="flex items-center gap-1 bg-[#181C24] p-1 rounded-lg border border-white/5">
                  <button
                    onClick={() => setSelectedFilter("all")}
                    className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                      selectedFilter === "all" ? "bg-[#0566D9] text-white" : "text-[#BBCABF] hover:text-white"
                    }`}
                  >
                    All ({pipelineItemsCount})
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
                  const showRaw = !!rawViewItemIds[item.cart_item_id];
                  const existingEval = evaluationsMap[item.cart_item_id];
                  const isEvaluated = existingEval && existingEval.status === "done";

                  return (
                    <div
                      key={item.cart_item_id}
                      onClick={() => navigateToSite(item.cart_item_id)}
                      className="glass-panel-interactive rounded-xl overflow-hidden flex flex-col group relative cursor-pointer"
                    >
                      {/* Source & Status Badges */}
                      <div className="absolute top-3 left-3 z-10 flex flex-wrap items-center gap-1.5 max-w-[calc(100%-60px)]">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider backdrop-blur-md border ${
                          isCrexi 
                            ? "bg-purple-900/70 text-purple-200 border-purple-500/50" 
                            : "bg-red-900/70 text-red-200 border-red-500/50"
                        }`}>
                          {isCrexi ? "Crexi" : "LoopNet"}
                        </span>

                        {isEvaluated && (
                          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-[#10B981]/25 text-[#4EDEA3] border border-[#10B981]/60 flex items-center gap-1 backdrop-blur-md shadow-[0_0_10px_rgba(78,222,163,0.3)]">
                            <span className="material-symbols-outlined text-[12px]">verified</span>
                            Score: {existingEval.overall_score}/100
                          </span>
                        )}
                      </div>

                      {/* Delete Icon Button (Top-Right) */}
                      <button
                        onClick={(e) => handleDeleteItem(e, item.cart_item_id)}
                        className="absolute top-3 right-3 z-10 p-1.5 rounded-full bg-[#0F131C]/80 text-[#BBCABF] hover:text-red-400 hover:bg-red-950/80 border border-white/10 backdrop-blur-md transition-all opacity-80 group-hover:opacity-100"
                        title="Delete Listing"
                      >
                        <span className="material-symbols-outlined text-base">delete</span>
                      </button>

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
                          <h3 className="font-display font-semibold text-lg text-white leading-snug line-clamp-1 group-hover:text-[#4EDEA3] transition-colors">
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
                              <div className="text-white font-medium truncate">
                                {structured?.financials?.asking_price_display ||
                                 (structured?.financials?.asking_price ? `$${structured.financials.asking_price.toLocaleString()}` : null) ||
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
                            onClick={(e) => {
                              e.stopPropagation();
                              setRawViewItemIds((prev) => ({ ...prev, [item.cart_item_id]: !showRaw }));
                            }}
                            className="text-[11px] text-[#BBCABF] hover:text-white transition-colors underline decoration-white/20"
                          >
                            {showRaw ? "Clean Facts" : "Raw Provenance"}
                          </button>

                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigateToSite(item.cart_item_id);
                            }}
                            className="px-3 py-1.5 rounded bg-[#0566D9] hover:bg-[#0566D9]/80 text-white font-medium text-xs flex items-center gap-1 transition-all shadow-[0_0_10px_rgba(5,102,217,0.3)]"
                          >
                            <span>Open Detail & Chat</span>
                            <span className="material-symbols-outlined text-sm">arrow_forward</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
