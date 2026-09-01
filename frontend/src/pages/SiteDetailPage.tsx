import React, { useEffect, useState } from "react";
import {
  CartItem,
  EvaluationResult,
  ChatMessage,
  ListingMemory,
  AgentResult,
  ComplianceReport,
  fetchCartItems,
  fetchEvaluationsForCartItem,
  startEvaluation,
  pollEvaluation,
  fetchChatHistory,
  sendChatMessage,
  fetchListingMemory,
  fetchComplianceReport,
} from "../api";

import RadiusRecommendations from "../components/RadiusRecommendations";

interface SiteDetailPageProps {
  cartItemId: string;
  sessionId: string;
  onBack: () => void;
}

export default function SiteDetailPage({ cartItemId, sessionId, onBack }: SiteDetailPageProps) {
  const [item, setItem] = useState<CartItem | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [compliance, setCompliance] = useState<ComplianceReport | null>(null);
  const [loadingItem, setLoadingItem] = useState<boolean>(true);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [loadingCompliance, setLoadingCompliance] = useState<boolean>(false);
  const [showRawFacts, setShowRawFacts] = useState<boolean>(false);

  // Tab State for Council Audit Reports: "summary" | "energy" | "water" | "surface" | "transport" | "risk" | "compliance"
  const [activeAuditTab, setActiveAuditTab] = useState<string>("summary");

  // Chat & Memory State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState<string>("");
  const [sendingChat, setSendingChat] = useState<boolean>(false);
  const [memories, setMemories] = useState<ListingMemory[]>([]);
  const [loadingMemory, setLoadingMemory] = useState<boolean>(false);

  // Load Item, Evaluation, Chat History, and Memory Facts on mount
  useEffect(() => {
    loadPageData();
  }, [cartItemId]);

  const loadPageData = async () => {
    setLoadingItem(true);
    try {
      // 1. Fetch Cart Item
      const items = await fetchCartItems();
      const found = items.find((i) => i.cart_item_id === cartItemId);
      if (found) {
        setItem(found);
      }

      // 2. Fetch Evaluation Report
      const evals = await fetchEvaluationsForCartItem(cartItemId);
      if (evals.length > 0) {
        setEvaluation(evals[0]);
      } else {
        setEvaluation(null);
      }

      // 3. Fetch Chat History & Listing Memory
      loadChatAndMemory();
      
      // 4. Fetch Compliance Report
      loadCompliance();
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingItem(false);
    }
  };

  const loadCompliance = async () => {
    setLoadingCompliance(true);
    try {
      const rep = await fetchComplianceReport(cartItemId);
      setCompliance(rep);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingCompliance(false);
    }
  };

  const loadChatAndMemory = async () => {
    setLoadingMemory(true);
    try {
      const [chats, mems] = await Promise.all([
        fetchChatHistory(cartItemId),
        fetchListingMemory(cartItemId),
      ]);
      setChatMessages(chats);
      setMemories(mems);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingMemory(false);
    }
  };

  // Start / Regenerate 5-Agent Evaluation
  const handleStartEvaluation = async () => {
    setEvaluating(true);
    try {
      setEvaluation({ evaluation_id: "starting", cart_item_id: cartItemId, status: "processing" });
      const job = await startEvaluation(cartItemId);

      // Poll until done
      const interval = setInterval(async () => {
        try {
          const res = await pollEvaluation(job.evaluation_id);
          if (res.status === "done" || res.status === "error") {
            clearInterval(interval);
            setEvaluation(res);
            setEvaluating(false);
          } else {
            setEvaluation(res);
          }
        } catch (err) {
          clearInterval(interval);
          setEvaluating(false);
        }
      }, 2500);
    } catch (err: any) {
      alert(`Error starting evaluation: ${err.message}`);
      setEvaluating(false);
    }
  };

  // Send Chat Message
  const handleSendChat = async (textToSend?: string) => {
    const query = (textToSend || chatInput).trim();
    if (!query || sendingChat) return;

    const activeSessionId = item?.session_id || (sessionId && sessionId.trim() ? sessionId.trim() : "default-session");

    setSendingChat(true);
    if (!textToSend) setChatInput("");

    // Optimistically add user message
    const tempUserMsg: ChatMessage = {
      message_id: `temp-${Date.now()}`,
      cart_item_id: cartItemId,
      session_id: activeSessionId,
      role: "user",
      content: query,
      created_at: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await sendChatMessage(cartItemId, activeSessionId, query);
      setChatMessages((prev) => [...prev.filter((m) => !m.message_id.startsWith("temp-")), tempUserMsg, res]);

      // Refresh memory panel immediately + delayed (since backend memory extraction runs in a background thread)
      const refreshMemories = async () => {
        try {
          const updatedMemories = await fetchListingMemory(cartItemId);
          setMemories(updatedMemories);
        } catch (e) {
          console.error(e);
        }
      };

      refreshMemories();
      setTimeout(refreshMemories, 1500);
      setTimeout(refreshMemories, 3500);
    } catch (err: any) {
      alert(`Chat error: ${err.message}`);
    } finally {
      setSendingChat(false);
    }
  };

  // Helper to find agent by discipline tab key
  const getAgentForTab = (tabKey: string): AgentResult | undefined => {
    if (!evaluation?.agent_results) return undefined;
    return evaluation.agent_results.find((ag) =>
      ag.agent_name.toLowerCase().includes(tabKey.toLowerCase())
    );
  };

  if (loadingItem) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-[#BBCABF] space-y-3">
        <div className="w-8 h-8 border-2 border-[#4EDEA3] border-t-transparent rounded-full animate-spin"></div>
        <p className="text-sm font-mono">Loading property intelligence context...</p>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="p-8 text-center space-y-4 max-w-md mx-auto">
        <h2 className="text-xl font-bold text-white">Listing Not Found</h2>
        <p className="text-sm text-[#BBCABF]">The requested property could not be loaded from your cart.</p>
        <button onClick={onBack} className="px-4 py-2 bg-[#0566D9] text-white text-xs font-semibold rounded">
          Back to Pipeline
        </button>
      </div>
    );
  }

  const structured = item.llm_structured || {};
  const isCrexi = item.source_url?.includes("crexi");

  return (
    <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto w-full">
      {/* ── Top Header Navigation & Action Bar ────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-4">
        <div>
          <button
            onClick={onBack}
            className="flex items-center gap-1 text-xs font-mono text-[#4EDEA3] hover:underline mb-2"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span>
            <span>Back to Pipeline</span>
          </button>

          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
              isCrexi ? "bg-purple-900/60 text-purple-200 border-purple-500/40" : "bg-red-900/60 text-red-200 border-red-500/40"
            }`}>
              {isCrexi ? "Crexi" : "LoopNet"}
            </span>

            {item.source_url && (
              <a
                href={item.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-[#BBCABF] hover:text-white flex items-center gap-1 underline decoration-white/20"
              >
                <span>Original Listing</span>
                <span className="material-symbols-outlined text-xs">open_in_new</span>
              </a>
            )}
          </div>

          <h1 className="font-display text-2xl md:text-3xl font-bold text-white leading-snug">
            {item.listing_title || item.address}
          </h1>
          <p className="text-sm text-[#BBCABF] mt-1 flex items-center gap-1">
            <span className="material-symbols-outlined text-base text-[#4EDEA3]">location_on</span>
            {item.address}
          </p>
        </div>

        {/* Score & Evaluation Action */}
        <div className="flex items-center gap-4 bg-[#151C28] p-4 rounded-xl border border-white/5 shrink-0">
          {evaluation?.status === "done" && (
            <>
              <div className="text-center">
                <div className="font-display font-bold text-3xl text-[#4EDEA3]">{evaluation.overall_score || 0}</div>
                <div className="text-[10px] text-[#BBCABF] font-mono uppercase">Council Score</div>
              </div>
              <div className="h-10 w-[1px] bg-white/10"></div>
              <div>
                <div className="text-xs font-bold text-white">{evaluation.recommendation}</div>
                <button
                  onClick={handleStartEvaluation}
                  disabled={evaluating}
                  className="mt-1 text-[11px] text-[#4EDEA3] hover:underline flex items-center gap-1"
                >
                  <span className="material-symbols-outlined text-xs">refresh</span>
                  <span>Regenerate Audit</span>
                </button>
              </div>
            </>
          )}

          {(!evaluation || evaluation.status !== "done") && (
            <button
              onClick={handleStartEvaluation}
              disabled={evaluating}
              className="px-4 py-2.5 bg-[#0566D9] hover:bg-[#0566D9]/80 text-white font-medium text-xs rounded-lg flex items-center gap-2 shadow-[0_0_15px_rgba(5,102,217,0.4)] disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-base">psychology</span>
              <span>{evaluating ? "Running 5-Agent Audit..." : "Run 5-Agent Audit"}</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Property Hero Image Banner ─────────────────────────────────── */}
      <div
        className="w-full h-56 md:h-64 rounded-2xl bg-cover bg-center relative border border-white/10 overflow-hidden bg-[#181C24] shadow-[0_10px_30px_rgba(0,0,0,0.5)]"
        style={{
          backgroundImage: item.image_url
            ? `url('${item.image_url}')`
            : "linear-gradient(to bottom, #1C2028, #0F131C)",
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-t from-[#0B0F17] via-transparent to-transparent opacity-80"></div>
        {!item.image_url && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-white/20 space-y-2">
            <span className="material-symbols-outlined text-6xl">apartment</span>
            <span className="text-xs font-mono">No Property Image Captured</span>
          </div>
        )}
      </div>

      {/* ── Radius Recommendations ─────────────────────────────────────────── */}
      <RadiusRecommendations parentCartItemId={cartItemId} />

      {/* ── 3-Region Layout Grid ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* CENTER COLUMN (Tabbed Council Audit Reports) - 7 cols on desktop */}
        <div className="lg:col-span-7 space-y-6">
          {/* Evaluating Spinner State */}
          {evaluation?.status === "processing" && (
            <div className="p-8 glass-panel rounded-xl text-center space-y-4">
              <div className="w-10 h-10 border-3 border-[#4EDEA3] border-t-transparent rounded-full animate-spin mx-auto"></div>
              <h3 className="font-display font-semibold text-lg text-white">Running 5-Agent Council Evaluation</h3>
              <p className="text-xs text-[#BBCABF] max-w-md mx-auto">
                Energy, Water, Surface, Transportation, and Risk agents are concurrently analyzing Mireye GIS location datasets...
              </p>
            </div>
          )}

          {/* Unevaluated Prompt */}
          {!evaluation && (
            <div className="glass-panel p-8 rounded-xl text-center space-y-3">
              <span className="material-symbols-outlined text-4xl text-[#BBCABF]">psychology_alt</span>
              <h3 className="font-display font-semibold text-lg text-white">No Evaluation Report Yet</h3>
              <p className="text-xs text-[#BBCABF] max-w-md mx-auto">
                Run the 5-Agent Council Audit to fetch Mireye GIS facts and generate discipline breakdown scores.
              </p>
              <button
                onClick={handleStartEvaluation}
                className="px-4 py-2 bg-[#0566D9] text-white font-medium text-xs rounded shadow-[0_0_12px_rgba(5,102,217,0.4)]"
              >
                Run Audit Now
              </button>
            </div>
          )}

          {/* TABBED COUNCIL AUDIT REPORTS (Saves Space & Sleek Interface) */}
          {evaluation?.status === "done" && (
            <div className="space-y-4">
              {/* Tab Selector Bar */}
              <div className="flex items-center gap-1.5 p-1 bg-[#151C28] rounded-xl border border-white/5 overflow-x-auto">
                <button
                  onClick={() => setActiveAuditTab("summary")}
                  className={`px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shrink-0 ${
                    activeAuditTab === "summary"
                      ? "bg-[#0566D9] text-white shadow-[0_0_12px_rgba(5,102,217,0.4)]"
                      : "text-[#BBCABF] hover:text-white hover:bg-white/5"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">dashboard</span>
                  <span>Total Report</span>
                </button>

                <button
                  onClick={() => setActiveAuditTab("energy")}
                  className={`px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shrink-0 ${
                    activeAuditTab === "energy"
                      ? "bg-amber-600 text-white shadow-[0_0_12px_rgba(217,119,6,0.4)]"
                      : "text-[#BBCABF] hover:text-white hover:bg-white/5"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">bolt</span>
                  <span>Energy</span>
                </button>

                <button
                  onClick={() => setActiveAuditTab("water")}
                  className={`px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shrink-0 ${
                    activeAuditTab === "water"
                      ? "bg-blue-600 text-white shadow-[0_0_12px_rgba(37,99,235,0.4)]"
                      : "text-[#BBCABF] hover:text-white hover:bg-white/5"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">water_drop</span>
                  <span>Water</span>
                </button>

                <button
                  onClick={() => setActiveAuditTab("surface")}
                  className={`px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shrink-0 ${
                    activeAuditTab === "surface"
                      ? "bg-emerald-600 text-white shadow-[0_0_12px_rgba(16,185,129,0.4)]"
                      : "text-[#BBCABF] hover:text-white hover:bg-white/5"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">terrain</span>
                  <span>Surface</span>
                </button>

                <button
                  onClick={() => setActiveAuditTab("transport")}
                  className={`px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shrink-0 ${
                    activeAuditTab === "transport"
                      ? "bg-indigo-600 text-white shadow-[0_0_12px_rgba(79,70,229,0.4)]"
                      : "text-[#BBCABF] hover:text-white hover:bg-white/5"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">local_shipping</span>
                  <span>Transport</span>
                </button>

                <button
                  onClick={() => setActiveAuditTab("risk")}
                  className={`px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shrink-0 ${
                    activeAuditTab === "risk"
                      ? "bg-rose-600 text-white shadow-[0_0_12px_rgba(225,29,72,0.4)]"
                      : "text-[#BBCABF] hover:text-white hover:bg-white/5"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">warning</span>
                  <span>Risk</span>
                </button>

                <button
                  onClick={() => setActiveAuditTab("compliance")}
                  className={`px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shrink-0 ${
                    activeAuditTab === "compliance"
                      ? "bg-fuchsia-600 text-white shadow-[0_0_12px_rgba(192,38,211,0.4)]"
                      : "text-[#BBCABF] hover:text-white hover:bg-white/5"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">gavel</span>
                  <span>Compliance</span>
                </button>
              </div>

              {/* TAB 1: TOTAL REPORT / EXECUTIVE SUMMARY */}
              {activeAuditTab === "summary" && (
                <div className="space-y-4 animate-fadeIn">
                  {/* Executive Overall Score Card */}
                  <div className="p-6 rounded-xl bg-gradient-to-br from-[#10B981]/15 to-transparent border border-[#10B981]/30 flex flex-col md:flex-row items-center gap-6">
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
                          strokeDashoffset={263.8 - (263.8 * (evaluation.overall_score || 0)) / 100}
                          strokeLinecap="round"
                          className="transition-all duration-1000 ease-out"
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="font-display font-bold text-3xl text-[#4EDEA3]">{evaluation.overall_score || 0}</span>
                        <span className="text-[9px] uppercase tracking-wider text-[#BBCABF]">/ 100</span>
                      </div>
                    </div>

                    <div className="space-y-1 text-center md:text-left">
                      <div className="text-[10px] text-[#BBCABF] uppercase tracking-widest font-mono">Total Executive Verdict</div>
                      <h3 className="font-display text-2xl font-bold text-[#4EDEA3]">{evaluation.recommendation}</h3>
                      <p className="text-xs text-[#BBCABF] leading-relaxed">
                        Synthesized 5-agent council aggregate score evaluating physical GIS location facts against listing metrics.
                      </p>
                    </div>
                  </div>

                  {/* Discipline Quick Score Grid */}
                  <div className="grid grid-cols-5 gap-2 p-3 bg-[#0D121C] rounded-xl border border-white/5 text-center font-mono text-xs">
                    {evaluation.agent_results?.map((ag) => (
                      <div
                        key={ag.agent_name}
                        onClick={() => {
                          const name = ag.agent_name.toLowerCase();
                          if (name.includes("energy")) setActiveAuditTab("energy");
                          else if (name.includes("water")) setActiveAuditTab("water");
                          else if (name.includes("surface")) setActiveAuditTab("surface");
                          else if (name.includes("transport")) setActiveAuditTab("transport");
                          else if (name.includes("risk")) setActiveAuditTab("risk");
                        }}
                        className="p-2 rounded bg-white/5 hover:bg-white/10 cursor-pointer transition-colors space-y-1"
                      >
                        <div className="text-[10px] text-[#BBCABF] truncate uppercase">{ag.agent_name.split(" ")[0]}</div>
                        <div className="font-bold text-[#4EDEA3]">{ag.score}</div>
                      </div>
                    ))}
                  </div>

                  {/* Flagged Conflicts Alert */}
                  {evaluation.conflicts_flagged && evaluation.conflicts_flagged.length > 0 && (
                    <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-500/30 text-amber-200 space-y-2">
                      <div className="flex items-center gap-2 font-semibold text-xs text-amber-400">
                        <span className="material-symbols-outlined text-base">warning</span>
                        <span>Council Disagreements & Contradictions ({evaluation.conflicts_flagged.length})</span>
                      </div>
                      <ul className="space-y-1.5 pl-6 list-disc text-xs text-amber-200/90 font-mono">
                        {evaluation.conflicts_flagged.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* General Site Specifications Card */}
                  <div className="glass-panel p-5 rounded-xl space-y-3">
                    <div className="flex items-center gap-2 border-b border-white/5 pb-2.5">
                      <span className="material-symbols-outlined text-sm text-[#4EDEA3]">info</span>
                      <h3 className="font-display font-semibold text-xs text-white uppercase tracking-wider font-mono">General Site Specifications</h3>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
                      <div className="p-2.5 bg-[#0D121C] rounded border border-white/5">
                        <div className="text-[10px] text-[#BBCABF] uppercase">Property Type</div>
                        <div className="text-white font-medium truncate mt-0.5">
                          {structured?.property?.property_type || item.details?.["Property Type"] || item.details?.["property_type"] || "Commercial"}
                        </div>
                      </div>

                      <div className="p-2.5 bg-[#0D121C] rounded border border-white/5">
                        <div className="text-[10px] text-[#BBCABF] uppercase">Building Size</div>
                        <div className="text-white font-medium truncate mt-0.5">
                          {structured?.property?.building_sqft
                            ? `${structured.property.building_sqft.toLocaleString()} SqFt`
                            : (item.details?.["Building Size"] || item.details?.["sqft"] || "N/A")}
                        </div>
                      </div>

                      <div className="p-2.5 bg-[#0D121C] rounded border border-white/5">
                        <div className="text-[10px] text-[#BBCABF] uppercase">Year Built / Class</div>
                        <div className="text-white font-medium truncate mt-0.5">
                          {structured?.property?.year_built || item.details?.["Year Built"] || "N/A"}
                          {structured?.property?.building_class ? ` (Class ${structured.property.building_class})` : ""}
                        </div>
                      </div>

                      <div className="p-2.5 bg-[#0D121C] rounded border border-white/5">
                        <div className="text-[10px] text-[#BBCABF] uppercase">Asking Price / Rent</div>
                        <div className="text-[#4EDEA3] font-medium truncate mt-0.5">
                          {structured?.financials?.asking_price_display ||
                           (structured?.financials?.asking_price ? `$${structured.financials.asking_price.toLocaleString()}` : null) ||
                           item.details?.["price"] || item.details?.["Asking Price"] || "N/A"}
                        </div>
                      </div>
                    </div>

                    {/* Description / Highlights Summary */}
                    {(structured?.narrative?.description || item.details?.["Description"] || item.details?.["highlights"]) && (
                      <div className="pt-2">
                        <div className="text-[10px] text-[#BBCABF] font-mono uppercase tracking-wider mb-1">Listing Overview & Highlights</div>
                        <p className="text-xs text-[#DFE2EE] leading-relaxed bg-[#0D121C] p-3 rounded-lg border border-white/5 max-h-32 overflow-y-auto">
                          {structured?.narrative?.description || item.details?.["Description"] || item.details?.["highlights"] || "No additional description provided."}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB: COMPLIANCE AGENT REPORT */}
              {activeAuditTab === "compliance" && (
                <div className="space-y-4 animate-fadeIn">
                  {loadingCompliance ? (
                    <div className="p-8 glass-panel rounded-xl text-center space-y-4">
                      <div className="w-10 h-10 border-3 border-[#4EDEA3] border-t-transparent rounded-full animate-spin mx-auto"></div>
                      <h3 className="font-display font-semibold text-lg text-white">Running Regulatory Due-Diligence</h3>
                      <p className="text-xs text-[#BBCABF] max-w-md mx-auto">
                        Querying EPA ECHO and Local Government Open Data portals...
                      </p>
                    </div>
                  ) : !compliance ? (
                    <div className="p-8 glass-panel rounded-xl text-center space-y-4">
                       <h3 className="font-display font-semibold text-lg text-white">No Compliance Data Found</h3>
                       <p className="text-xs text-[#BBCABF] max-w-md mx-auto">The agent could not generate a compliance report.</p>
                    </div>
                  ) : (
                    <>
                      <div className="p-6 rounded-xl bg-gradient-to-br from-fuchsia-900/20 to-transparent border border-fuchsia-500/30 flex flex-col md:flex-row items-center gap-6">
                        <div className="relative w-24 h-24 flex items-center justify-center shrink-0">
                          <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="font-display font-bold text-3xl text-fuchsia-400">{compliance.overall.score}</span>
                            <span className="text-[9px] uppercase tracking-wider text-[#BBCABF]">Score</span>
                          </div>
                        </div>

                        <div className="space-y-1 text-center md:text-left">
                          <div className="text-[10px] text-[#BBCABF] uppercase tracking-widest font-mono">Regulatory Due Diligence</div>
                          <h3 className="font-display text-2xl font-bold flex items-center gap-2">
                            {compliance.overall.risk === "POTENTIAL_RISK" && <span className="text-rose-400">🔴 Potential Risk</span>}
                            {compliance.overall.risk === "VIOLATION_FOUND" && <span className="text-red-500">❌ Violation Found</span>}
                            {compliance.overall.risk === "CLEAR" && <span className="text-[#4EDEA3]">🟢 Clear</span>}
                            {compliance.overall.risk === "LOW" && <span className="text-[#4EDEA3]">🟢 Low Risk</span>}
                            {compliance.overall.risk === "MEDIUM" && <span className="text-amber-400">🟡 Medium Risk</span>}
                            {compliance.overall.risk === "HIGH" && <span className="text-rose-400">🔴 High Risk</span>}
                            {compliance.overall.risk === "REQUIRES_MANUAL_REVIEW" && <span className="text-amber-400">🟡 Manual Review Required</span>}
                          </h3>
                          <p className="text-xs text-[#BBCABF] leading-relaxed">
                            {compliance.overall.summary}
                          </p>
                          <div className="text-[10px] text-fuchsia-300 mt-2">
                            Data Confidence: {compliance.overall.confidence}%
                          </div>
                        </div>
                      </div>

                      <div className="glass-panel p-6 rounded-xl space-y-4">
                         <h3 className="font-display font-semibold text-lg text-white border-b border-white/5 pb-2">Category Breakdown (Municipal Data)</h3>
                         {["environmental", "building", "zoning", "fire", "occupancy"].map((cat) => {
                           const catData = (compliance as any)[cat];
                           if (!catData) return null;

                           const normalFindings = catData.findings ? catData.findings.filter((f: any) => f.source_type !== "llm_agent" && f.source !== "LLM") : [];

                           if (normalFindings.length === 0 && catData.findings && catData.findings.length > 0) return null;

                           return (

                             <div key={cat} className="mb-4">
                               <div className="flex justify-between items-center bg-[#0D121C] p-3 rounded-t-lg border border-white/5">
                                 <span className="font-mono text-xs uppercase font-bold text-white">{cat}</span>
                                 <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-white/5 text-[#BBCABF]">
                                   {catData.status} {catData.score !== null ? `(${catData.score})` : ""}
                                 </span>
                               </div>
                               <div className="bg-[#0A0E16] p-3 rounded-b-lg border-x border-b border-white/5 space-y-2 max-h-64 overflow-y-auto">
                                 {normalFindings.length > 0 ? (
                                   normalFindings.map((f: any, i: number) => (
                                     <div key={i} className="text-xs text-[#DFE2EE] border-b border-white/5 pb-2 last:border-0 last:pb-0">
                                       <span className="font-bold mr-1">{f.status === "POTENTIAL_RISK" ? "⚠️" : f.status === "CLEAR" ? "✅" : "ℹ️"}</span>
                                       {f.finding}
                                       <div className="text-[10px] text-[#BBCABF] mt-1 ml-5">Source: {f.source}</div>
                                     </div>
                                   ))
                                 ) : (
                                   <div className="text-xs text-[#BBCABF] italic">No specific findings.</div>
                                 )}
                               </div>
                             </div>
                           );
                         })}
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* TABS 2-6: INDIVIDUAL DISCIPLINE AGENT REPORTS */}
              {activeAuditTab !== "summary" && activeAuditTab !== "compliance" && (
                <div className="glass-panel p-6 rounded-xl space-y-4 animate-fadeIn">
                  {(() => {
                    const agent = getAgentForTab(activeAuditTab);
                    if (!agent) {
                      return (
                        <div className="text-center py-6 text-xs text-[#BBCABF]">
                          No report details found for {activeAuditTab} discipline.
                        </div>
                      );
                    }

                    return (
                      <>
                        <div className="flex items-center justify-between border-b border-white/5 pb-3">
                          <div>
                            <h3 className="font-display font-bold text-lg text-white flex items-center gap-2">
                              <span>{agent.agent_name} Report</span>
                              <span className="text-[10px] px-2.5 py-0.5 rounded bg-white/5 text-[#BBCABF] uppercase font-mono font-normal">
                                {agent.data_availability} data
                              </span>
                            </h3>
                          </div>
                          <div className="text-right">
                            <div className="font-mono font-bold text-2xl text-[#4EDEA3]">{agent.score} / 100</div>
                            <div className="text-[10px] text-[#BBCABF] font-mono uppercase">Discipline Score</div>
                          </div>
                        </div>

                        <div className="space-y-3">
                          <div>
                            <div className="text-[10px] text-[#BBCABF] font-mono uppercase tracking-wider mb-1">Executive Summary</div>
                            <p className="text-xs text-[#DFE2EE] leading-relaxed bg-[#0D121C] p-3 rounded-lg border border-white/5">
                              {agent.summary}
                            </p>
                          </div>

                          <div>
                            <div className="text-[10px] text-[#BBCABF] font-mono uppercase tracking-wider mb-1">Board Memo</div>
                            <p className="text-xs text-[#BBCABF] italic bg-[#0A0E16] p-3 rounded-lg border border-white/5">
                              "{agent.memo}"
                            </p>
                          </div>

                          {/* Citations */}
                          {agent.citations && agent.citations.length > 0 && (
                            <div className="pt-2 space-y-1.5">
                              <div className="text-[10px] text-[#BBCABF] font-mono uppercase tracking-wider">Citations ({agent.citations.length})</div>
                              <div className="flex flex-wrap gap-1.5">
                                {agent.citations.map((c, idx) => (
                                  <span
                                    key={idx}
                                    className={`text-[10px] px-2.5 py-1 rounded font-mono border ${
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
                      </>
                    );
                  })()}
                </div>
              )}
            </div>
          )}
        </div>

        {/* RIGHT RAIL (Stacked: Listing Facts -> Listing Memory -> Chat Panel) - 5 cols on desktop */}
        <div className="lg:col-span-5 space-y-6">
          {/* 1. Listing Facts Toggle Card */}
          <div className="glass-panel p-5 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-semibold text-xs text-white uppercase tracking-wider font-mono">Listing Facts</h3>
              <button
                onClick={() => setShowRawFacts(!showRawFacts)}
                className="text-[11px] text-[#4EDEA3] hover:underline"
              >
                {showRawFacts ? "Clean Facts" : "Raw Provenance"}
              </button>
            </div>

            {!showRawFacts ? (
              <div className="grid grid-cols-2 gap-2 p-3 bg-[#0D121C] rounded border border-white/5 text-xs font-mono">
                <div>
                  <div className="text-[10px] text-[#BBCABF] uppercase">Price</div>
                  <div className="text-white font-medium truncate">
                    {structured?.financials?.asking_price_display || item.details?.["price"] || "N/A"}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-[#BBCABF] uppercase">Cap Rate</div>
                  <div className="text-[#4EDEA3] font-medium truncate">
                    {structured?.financials?.cap_rate_percent !== undefined
                      ? `${structured.financials.cap_rate_percent}%`
                      : (item.details?.["Cap Rate"] || "N/A")}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-[#BBCABF] uppercase">Building SqFt</div>
                  <div className="text-white font-medium truncate">
                    {structured?.property?.building_sqft
                      ? `${structured.property.building_sqft.toLocaleString()} SqFt`
                      : (item.details?.["Building Size"] || "N/A")}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-[#BBCABF] uppercase">Class</div>
                  <div className="text-white font-medium truncate">
                    {structured?.property?.building_class || "N/A"}
                  </div>
                </div>
              </div>
            ) : (
              <div className="max-h-36 overflow-y-auto p-2 bg-[#0A0E16] rounded border border-white/5 font-mono text-[10px] text-[#BBCABF] space-y-1">
                {Object.entries(item.details || {}).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-white/60 truncate max-w-[120px]">{k}:</span>
                    <span className="text-white truncate max-w-[150px]">{String(v)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 2. Listing Memory / Notes Panel */}
          <div className="glass-panel p-5 rounded-xl space-y-3">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-sm text-[#4EDEA3]">description</span>
              <h3 className="font-display font-semibold text-xs text-white uppercase tracking-wider font-mono">Listing Notes & Memory</h3>
            </div>

            {loadingMemory && memories.length === 0 ? (
              <div className="text-xs text-[#BBCABF] font-mono italic">Loading memory facts...</div>
            ) : memories.length === 0 ? (
              <div className="text-xs text-[#BBCABF] italic bg-[#0D121C] p-3 rounded border border-white/5">
                Notes and preferences from your conversation will appear here automatically.
              </div>
            ) : (
              <ul className="space-y-1.5 p-3 bg-[#0D121C] rounded border border-white/5 text-xs text-[#DFE2EE] font-mono list-disc pl-5">
                {memories.map((m) => (
                  <li key={m.memory_id}>{m.fact}</li>
                ))}
              </ul>
            )}
          </div>

          {/* 3. Site Chat Panel */}
          <div className="glass-panel p-5 rounded-xl flex flex-col h-[520px] relative">
            <div className="flex items-center gap-2 border-b border-white/5 pb-3">
              <span className="material-symbols-outlined text-sm text-[#4EDEA3]">chat</span>
              <h3 className="font-display font-semibold text-xs text-white uppercase tracking-wider font-mono">Site Intelligence Chat</h3>
            </div>

            {/* Starter Suggestion Chips */}
            {chatMessages.length === 0 && (
              <div className="py-3 border-b border-white/5 space-y-1.5">
                <div className="text-[10px] text-[#BBCABF] uppercase font-mono">Suggested Questions:</div>
                <div className="flex flex-wrap gap-1.5">
                  <button
                    onClick={() => handleSendChat("What's the flood risk here?")}
                    className="text-[11px] px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 text-[#4EDEA3] border border-white/10 transition-colors"
                  >
                    What's the flood risk here?
                  </button>
                  <button
                    onClick={() => handleSendChat("How's the power infrastructure?")}
                    className="text-[11px] px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 text-blue-300 border border-white/10 transition-colors"
                  >
                    How's the power infrastructure?
                  </button>
                  <button
                    onClick={() => handleSendChat("Are there cell towers nearby?")}
                    className="text-[11px] px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 text-purple-300 border border-white/10 transition-colors"
                  >
                    Are there cell towers nearby?
                  </button>
                </div>
              </div>
            )}

            {/* Message Thread */}
            <div className="flex-1 overflow-y-auto py-3 space-y-3 pr-1">
              {chatMessages.map((msg) => {
                const isUser = msg.role === "user";
                return (
                  <div key={msg.message_id} className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
                    <div
                      className={`max-w-[85%] p-3 rounded-xl text-xs ${
                        isUser
                          ? "bg-[#0566D9] text-white rounded-br-none"
                          : "bg-[#0D121C] border border-white/5 text-[#DFE2EE] rounded-bl-none"
                      }`}
                    >
                      <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                      {/* Citations Badges */}
                      {!isUser && msg.citations && msg.citations.length > 0 && (
                        <div className="mt-2.5 pt-2 border-t border-white/10 flex flex-wrap gap-1">
                          {msg.citations.map((c, i) => (
                            <span
                              key={i}
                              className={`text-[9px] px-1.5 py-0.5 rounded font-mono border ${
                                c.source === "mireye"
                                  ? "bg-blue-950/60 text-blue-300 border-blue-500/40"
                                  : c.source === "listing"
                                  ? "bg-purple-950/60 text-purple-300 border-purple-500/40"
                                  : "bg-emerald-950/60 text-emerald-300 border-emerald-500/40"
                              }`}
                            >
                              [{c.source}] {c.field || c.fact}: {String(c.value || "")}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Input & Send Button */}
            <div className="pt-3 border-t border-white/5 flex gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendChat()}
                placeholder="Ask about flood, power, zoning, cell towers..."
                disabled={sendingChat}
                className="flex-1 bg-[#0D121C] border border-white/10 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[#4EDEA3]"
              />
              <button
                onClick={() => handleSendChat()}
                disabled={sendingChat || !chatInput.trim()}
                className="px-4 py-2 bg-[#4EDEA3] hover:bg-[#4EDEA3]/80 text-[#0B0F17] font-bold text-xs rounded-lg transition-all disabled:opacity-50 flex items-center justify-center"
              >
                {sendingChat ? (
                  <div className="w-4 h-4 border-2 border-[#0B0F17] border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <span className="material-symbols-outlined text-base">send</span>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
