import React, { useEffect, useState } from "react";
import { CartItem, ComparisonResponse, fetchCartItems, compareSites } from "../api";

interface ComparePageProps {
  sessionId: string;
  onBack: () => void;
}

export default function ComparePage({ sessionId, onBack }: ComparePageProps) {
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loadingCart, setLoadingCart] = useState<boolean>(true);

  // Comparison Results State
  const [comparing, setComparing] = useState<boolean>(false);
  const [comparisonResult, setComparisonResult] = useState<ComparisonResponse | null>(null);

  useEffect(() => {
    loadCart();
  }, [sessionId]);

  const loadCart = async () => {
    setLoadingCart(true);
    try {
      const items = await fetchCartItems();
      setCartItems(items);
      // Auto-select first 2 or 3 items if available
      if (items.length >= 2) {
        setSelectedIds(items.slice(0, Math.min(3, items.length)).map((i) => i.cart_item_id));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingCart(false);
    }
  };

  const toggleSelect = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds((prev) => prev.filter((i) => i !== id));
    } else {
      if (selectedIds.length >= 4) {
        alert("Maximum 4 sites can be selected for side-by-side comparison.");
        return;
      }
      setSelectedIds((prev) => [...prev, id]);
    }
  };

  const handleRunComparison = async () => {
    if (selectedIds.length < 2 || selectedIds.length > 4) return;
    setComparing(true);
    try {
      const res = await compareSites(selectedIds);
      setComparisonResult(res);
    } catch (err: any) {
      alert(`Comparison error: ${err.message}`);
    } finally {
      setComparing(false);
    }
  };

  const isValidCount = selectedIds.length >= 2 && selectedIds.length <= 4;

  return (
    <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto w-full">
      {/* ── Top Header Navigation ────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-6">
        <div>
          <button
            onClick={onBack}
            className="flex items-center gap-1 text-xs font-mono text-[#4EDEA3] hover:underline mb-2"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span>
            <span>Back to Pipeline</span>
          </button>
          <div className="flex items-center gap-2 text-xs font-mono text-[#4EDEA3] uppercase tracking-widest mb-1">
            <span>Obsidian Intelligence</span>
            <span>•</span>
            <span>Multi-Site Matrix</span>
          </div>
          <h1 className="font-display text-3xl font-bold text-white">Compare Sites</h1>
          <p className="text-sm text-[#BBCABF] mt-1">Side-by-side location intelligence comparison & synthesized trade-offs.</p>
        </div>

        {/* Action Button */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-[#BBCABF]">
            Selected: <span className="text-[#4EDEA3] font-bold">{selectedIds.length}</span> / 4
          </span>
          <button
            onClick={handleRunComparison}
            disabled={!isValidCount || comparing}
            className="px-5 py-2.5 bg-[#0566D9] hover:bg-[#0566D9]/80 text-white font-medium text-xs rounded-lg transition-all shadow-[0_0_15px_rgba(5,102,217,0.4)] disabled:opacity-50 flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-base">compare_arrows</span>
            <span>{comparing ? "Comparing..." : "Synthesize Comparison"}</span>
          </button>
        </div>
      </div>

      {/* ── Part A: Site Picker ──────────────────────────────────────────── */}
      <div className="glass-panel p-5 rounded-xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-display font-semibold text-sm text-white flex items-center gap-2">
            <span className="material-symbols-outlined text-[#4EDEA3]">checklist</span>
            <span>Select 2 to 4 Properties from Pipeline</span>
          </h3>

          {!isValidCount && (
            <span className="text-xs text-amber-400 font-mono">
              ⚠️ Select between 2 and 4 sites to compare
            </span>
          )}
        </div>

        {loadingCart ? (
          <div className="py-8 text-center text-xs text-[#BBCABF] font-mono">Loading cart portfolio...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {cartItems.map((item) => {
              const isSelected = selectedIds.includes(item.cart_item_id);
              return (
                <div
                  key={item.cart_item_id}
                  onClick={() => toggleSelect(item.cart_item_id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all flex items-center gap-3 ${
                    isSelected
                      ? "bg-[#0566D9]/20 border-[#4EDEA3] text-white"
                      : "bg-[#0D121C] border-white/5 text-[#BBCABF] hover:border-white/20"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => {}}
                    className="w-4 h-4 rounded accent-[#4EDEA3]"
                  />
                  <div className="overflow-hidden flex-1">
                    <div className="text-xs font-semibold text-white truncate">{item.listing_title || item.address}</div>
                    <div className="text-[10px] text-[#BBCABF] truncate mt-0.5">{item.address}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Part B: Comparison Results Matrix & Narrative ─────────────────── */}
      {comparing && (
        <div className="p-12 glass-panel rounded-xl text-center space-y-4">
          <div className="w-10 h-10 border-3 border-[#4EDEA3] border-t-transparent rounded-full animate-spin mx-auto"></div>
          <h3 className="font-display font-semibold text-lg text-white">Synthesizing Side-by-Side Trade-Offs</h3>
          <p className="text-xs text-[#BBCABF] max-w-sm mx-auto font-mono">
            Evaluating energy, water, surface, transport, and risk agent scores across selected sites...
          </p>
        </div>
      )}

      {!comparing && comparisonResult && (
        <div className="space-y-8">
          {/* Executive Comparison Narrative & Trade-Offs Banner */}
          <div className="p-6 glass-panel rounded-xl border border-[#4EDEA3]/30 space-y-4 bg-gradient-to-br from-[#10B981]/10 to-transparent">
            <div className="flex items-center gap-2 text-xs font-mono text-[#4EDEA3] uppercase tracking-wider">
              <span className="material-symbols-outlined text-base">auto_awesome</span>
              <span>Executive Comparison Takeaways</span>
            </div>

            <p className="text-sm text-white leading-relaxed font-body">
              {comparisonResult.comparison_narrative}
            </p>

            {comparisonResult.trade_offs && comparisonResult.trade_offs.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-white/10">
                <div className="text-xs font-mono uppercase text-[#BBCABF]">Key Discipline Trade-Offs:</div>
                <ul className="space-y-1.5 list-disc pl-5 text-xs text-[#DFE2EE] font-mono">
                  {comparisonResult.trade_offs.map((t, idx) => (
                    <li key={idx}>{t}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Matrix Comparison Grid */}
          <div className="glass-panel rounded-xl overflow-x-auto p-6 space-y-6">
            <h3 className="font-display font-semibold text-base text-white">Discipline Category Score Matrix</h3>

            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="p-3 text-[#BBCABF] uppercase w-44">Discipline</th>
                  {comparisonResult.sites.map((site) => (
                    <th key={site.cart_item_id} className="p-3 text-white min-w-[200px]">
                      <div className="font-display font-bold text-sm text-white line-clamp-1">{site.listing_title || site.address}</div>
                      <div className="text-[10px] text-[#BBCABF] truncate font-normal mt-0.5">{site.address}</div>

                      {site.missing_evaluation ? (
                        <div className="mt-2 text-[10px] px-2 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-500/40 inline-block">
                          Not Evaluated Yet
                        </div>
                      ) : (
                        <div className="mt-2 flex items-center gap-2">
                          <span className="font-bold text-[#4EDEA3] text-base">{site.overall_score} / 100</span>
                          <span className="text-[10px] text-[#BBCABF] truncate">({site.recommendation})</span>
                        </div>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {/* 1. Energy */}
                <tr>
                  <td className="p-3 font-semibold text-[#BBCABF] flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-yellow-400 text-base">bolt</span>
                    <span>Energy Infrastructure</span>
                  </td>
                  {comparisonResult.sites.map((site) => (
                    <td key={site.cart_item_id} className="p-3 font-bold">
                      {site.missing_evaluation || !site.agent_scores?.energy ? (
                        <span className="text-white/30">—</span>
                      ) : (
                        <span className="text-[#4EDEA3]">{site.agent_scores.energy} / 100</span>
                      )}
                    </td>
                  ))}
                </tr>

                {/* 2. Water */}
                <tr>
                  <td className="p-3 font-semibold text-[#BBCABF] flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-blue-400 text-base">water_drop</span>
                    <span>Water & Wastewater</span>
                  </td>
                  {comparisonResult.sites.map((site) => (
                    <td key={site.cart_item_id} className="p-3 font-bold">
                      {site.missing_evaluation || !site.agent_scores?.water ? (
                        <span className="text-white/30">—</span>
                      ) : (
                        <span className="text-[#4EDEA3]">{site.agent_scores.water} / 100</span>
                      )}
                    </td>
                  ))}
                </tr>

                {/* 3. Surface */}
                <tr>
                  <td className="p-3 font-semibold text-[#BBCABF] flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-emerald-400 text-base">terrain</span>
                    <span>Surface & Terrain</span>
                  </td>
                  {comparisonResult.sites.map((site) => (
                    <td key={site.cart_item_id} className="p-3 font-bold">
                      {site.missing_evaluation || !site.agent_scores?.surface ? (
                        <span className="text-white/30">—</span>
                      ) : (
                        <span className="text-[#4EDEA3]">{site.agent_scores.surface} / 100</span>
                      )}
                    </td>
                  ))}
                </tr>

                {/* 4. Transport */}
                <tr>
                  <td className="p-3 font-semibold text-[#BBCABF] flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[#0566D9] text-base">local_shipping</span>
                    <span>Transportation Access</span>
                  </td>
                  {comparisonResult.sites.map((site) => (
                    <td key={site.cart_item_id} className="p-3 font-bold">
                      {site.missing_evaluation || !site.agent_scores?.transport ? (
                        <span className="text-white/30">—</span>
                      ) : (
                        <span className="text-[#4EDEA3]">{site.agent_scores.transport} / 100</span>
                      )}
                    </td>
                  ))}
                </tr>

                {/* 5. Risk */}
                <tr>
                  <td className="p-3 font-semibold text-[#BBCABF] flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-red-400 text-base">warning</span>
                    <span>Environmental & Risk</span>
                  </td>
                  {comparisonResult.sites.map((site) => (
                    <td key={site.cart_item_id} className="p-3 font-bold">
                      {site.missing_evaluation || !site.agent_scores?.risk ? (
                        <span className="text-white/30">—</span>
                      ) : (
                        <span className="text-[#4EDEA3]">{site.agent_scores.risk} / 100</span>
                      )}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
