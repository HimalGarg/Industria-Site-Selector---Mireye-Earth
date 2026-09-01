import React, { useEffect, useState } from "react";
import { CartItem, EvaluationResult, fetchCartItems, fetchEvaluationsForCartItem, startEvaluation, pollEvaluation } from "../api";

interface RadiusRecommendationsProps {
  parentCartItemId: string;
}

export default function RadiusRecommendations({ parentCartItemId }: RadiusRecommendationsProps) {
  const [comparables, setComparables] = useState<CartItem[]>([]);
  const [evals, setEvals] = useState<Record<string, EvaluationResult>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadComparables();
  }, [parentCartItemId]);

  const loadComparables = async () => {
    setLoading(true);
    try {
      const allItems = await fetchCartItems();
      const radiusItems = allItems.filter(i => (i as any).parent_cart_item_id === parentCartItemId && (i as any).is_radius_recommendation);
      setComparables(radiusItems);
      
      const evalMap: Record<string, EvaluationResult> = {};
      for (const item of radiusItems) {
        const itemEvals = await fetchEvaluationsForCartItem(item.cart_item_id);
        if (itemEvals.length > 0) {
          evalMap[item.cart_item_id] = itemEvals[0];
        }
      }
      setEvals(evalMap);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleStartEval = async (cartItemId: string) => {
    setEvals(prev => ({ ...prev, [cartItemId]: { evaluation_id: "starting", cart_item_id: cartItemId, status: "processing" } }));
    try {
      const job = await startEvaluation(cartItemId);
      const interval = setInterval(async () => {
        const res = await pollEvaluation(job.evaluation_id);
        if (res.status === "done" || res.status === "error") {
          clearInterval(interval);
          setEvals(prev => ({ ...prev, [cartItemId]: res }));
        }
      }, 3000);
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return <div className="text-sm text-[#BBCABF] animate-pulse">Checking for radius comparables...</div>;
  }

  if (comparables.length === 0) {
    return null;
  }

  return (
    <div className="bg-[#151C28] rounded-xl border border-white/5 p-6 space-y-4">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-[#6366f1]">radar</span>
        <h3 className="font-display font-bold text-lg text-white">2km Radius Comparables (Top {comparables.length})</h3>
      </div>
      <p className="text-sm text-[#BBCABF]">
        These properties were automatically found within a 2km radius using the stealth agent, pre-filtered for relevance.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
        {comparables.map(comp => {
          const struct = comp.llm_structured || {};
          const ev = evals[comp.cart_item_id];
          const price = struct.financials?.asking_price_display || struct.asking_price_display || "N/A";
          const type = struct.property?.property_type || struct.property_type || "Unknown";
          
          return (
            <div key={comp.cart_item_id} className="bg-[#0A1017] rounded-lg p-4 border border-white/5 hover:border-white/20 transition-colors">
              <div className="flex justify-between items-start mb-2">
                <h4 className="font-bold text-white text-sm line-clamp-1 flex-1 pr-2" title={comp.listing_title || comp.address}>
                  {comp.listing_title || comp.address}
                </h4>
                {ev?.status === "done" ? (
                  <div className="bg-green-900/40 text-[#4EDEA3] px-2 py-1 rounded text-xs font-bold border border-green-500/20 shrink-0">
                    {ev.overall_score || 0} / 100
                  </div>
                ) : ev?.status === "processing" ? (
                  <div className="text-xs text-yellow-500 animate-pulse">Evaluating...</div>
                ) : (
                  <button onClick={() => handleStartEval(comp.cart_item_id)} className="text-xs bg-[#0566D9] text-white px-2 py-1 rounded hover:bg-blue-600 transition-colors shrink-0">
                    Evaluate
                  </button>
                )}
              </div>
              <p className="text-xs text-[#BBCABF] line-clamp-1 mb-3">{comp.address}</p>
              
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-[#151C28] p-2 rounded">
                  <div className="text-[10px] text-gray-500 uppercase">Price</div>
                  <div className="font-mono text-white">{price}</div>
                </div>
                <div className="bg-[#151C28] p-2 rounded">
                  <div className="text-[10px] text-gray-500 uppercase">Type</div>
                  <div className="font-mono text-white line-clamp-1">{type}</div>
                </div>
              </div>
              
              {comp.source_url && (
                <a href={comp.source_url} target="_blank" rel="noreferrer" className="block mt-4 text-center text-xs text-[#6366f1] hover:underline">
                  View Original Listing &rarr;
                </a>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
