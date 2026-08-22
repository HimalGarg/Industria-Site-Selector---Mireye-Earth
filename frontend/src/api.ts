/**
 * frontend/src/api.ts — API Client for Site Ranker Cart & Evaluation Engine
 */

export const API_BASE = "http://localhost:8000";

export interface CartItem {
  cart_item_id: string;
  session_id: string;
  address: string;
  source_url?: string;
  listing_title?: string;
  image_url?: string;
  added_at: string;
  details: Record<string, any>;
  llm_structured?: {
    schema_version?: string;
    financials?: {
      asking_price_display?: string;
      asking_price?: number;
      cap_rate_percent?: number;
      noi_annual?: number;
      occupancy_percent?: number;
      price_per_sqft?: number;
    };
    property?: {
      property_type?: string;
      building_sqft?: number;
      building_class?: string;
      year_built?: number;
    };
    asking_price?: number;
    building_sqft?: number;
    cap_rate_pct?: number;
    noi_annual?: number;
    occupancy_pct?: number;
    price_per_sqft?: number;
    building_class?: string;
    year_built?: number;
    property_type?: string;
    [key: string]: any;
  };
}

export interface AgentResult {
  agent_name: string;
  score: number;
  summary: string;
  memo: string;
  citations: Array<{
    source: string;
    field: string;
    value: any;
  }>;
  data_availability: "full" | "partial" | "unavailable";
}

export interface EvaluationResult {
  evaluation_id: string;
  cart_item_id: string;
  status: "processing" | "done" | "error";
  overall_score?: number;
  recommendation?: string;
  conflicts_flagged?: string[];
  agent_results?: AgentResult[];
  created_at?: string;
  error?: string;
}

export async function fetchHealth(): Promise<{ status: string; service: string; version: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function fetchCartItems(sessionId?: string): Promise<CartItem[]> {
  const url = sessionId && sessionId.trim()
    ? `${API_BASE}/cart-items?session_id=${encodeURIComponent(sessionId.trim())}`
    : `${API_BASE}/cart-items`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch cart items");
  const data = await res.json();
  return Array.isArray(data) ? data : (data.items || []);
}

export async function startEvaluation(cartItemId: string): Promise<{ evaluation_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/evaluate-site`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cart_item_id: cartItemId }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to start evaluation");
  }
  return res.json();
}

export async function pollEvaluation(evaluationId: string): Promise<EvaluationResult> {
  const res = await fetch(`${API_BASE}/evaluate-site/${evaluationId}`);
  if (!res.ok) throw new Error("Failed to fetch evaluation status");
  return res.json();
}

export async function fetchEvaluationsForCartItem(cartItemId: string): Promise<EvaluationResult[]> {
  const res = await fetch(`${API_BASE}/evaluate-site?cart_item_id=${encodeURIComponent(cartItemId)}`);
  if (!res.ok) throw new Error("Failed to fetch evaluations");
  return res.json();
}
