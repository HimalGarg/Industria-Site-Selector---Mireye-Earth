import React, { useEffect, useState } from "react";
import { CartItem, fetchCartItems } from "../api";
import RadiusRecommendations from "../components/RadiusRecommendations";

interface RecommendationsPageProps {
  sessionId: string;
  onBack: () => void;
  onOpenSite: (id: string) => void;
}

export default function RecommendationsPage({ sessionId, onBack, onOpenSite }: RecommendationsPageProps) {
  const [items, setItems] = useState<CartItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadItems();
  }, [sessionId]);

  const loadItems = async () => {
    setLoading(true);
    try {
      const all = await fetchCartItems();
      setItems(all);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const radiusItems = items.filter(i => (i as any).is_radius_recommendation);
  const parentIds = Array.from(new Set(radiusItems.map(i => (i as any).parent_cart_item_id).filter(Boolean)));
  
  const parentItems = items.filter(i => parentIds.includes(i.cart_item_id));

  return (
    <div className="w-full flex-1 flex flex-col relative min-h-0">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-[#0A1017]/95 backdrop-blur-md border-b border-white/5 p-4 md:p-6 shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 md:p-2 rounded hover:bg-white/5 text-[#BBCABF] transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">arrow_back</span>
          </button>
          <div className="flex flex-col">
            <h1 className="font-display font-bold text-lg md:text-xl text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-[#4EDEA3]">my_location</span>
              Radius Recommendations
            </h1>
          </div>
        </div>
        <button onClick={loadItems} className="text-[#BBCABF] hover:text-white transition-colors">
          <span className="material-symbols-outlined text-[20px]">refresh</span>
        </button>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-10">
        {loading ? (
          <div className="text-[#BBCABF] animate-pulse">Loading recommendations...</div>
        ) : parentItems.length === 0 ? (
          <div className="bg-[#151C28] border border-white/5 rounded-xl p-10 text-center">
            <span className="material-symbols-outlined text-4xl text-[#BBCABF]/30 mb-4">radar</span>
            <h3 className="font-display font-bold text-xl text-white mb-2">No Radius Scans Yet</h3>
            <p className="text-[#BBCABF]">
              Open the extension popup and click "Scan 2km Radius" to let the agent find comparables.
            </p>
          </div>
        ) : (
          parentItems.map(parent => (
            <div key={parent.cart_item_id} className="bg-[#151C28] border border-white/5 rounded-xl p-6 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1 h-full bg-[#0566D9]"></div>
              
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-6">
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-1">Target Property</div>
                  <h2 
                    className="font-display font-bold text-xl text-white cursor-pointer hover:text-[#0566D9] transition-colors"
                    onClick={() => onOpenSite(parent.cart_item_id)}
                  >
                    {parent.listing_title || parent.address}
                  </h2>
                  <p className="text-sm text-[#BBCABF] mt-1">{parent.address}</p>
                </div>
                
                <button
                  onClick={() => onOpenSite(parent.cart_item_id)}
                  className="px-4 py-2 rounded bg-white/5 hover:bg-white/10 text-white font-medium text-xs flex items-center gap-1.5 transition-all"
                >
                  View Details & Chat
                  <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                </button>
              </div>

              {/* Directly embed the existing component but styled inline */}
              <div className="bg-[#0A1017] rounded-lg -mx-2 -mb-2 p-2">
                <RadiusRecommendations parentCartItemId={parent.cart_item_id} />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
