/**
 * frontend/src/api.ts — API Client for Site Ranker Cart, Evaluation, Chat & Comparison Engine
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

export interface ChatCitation {
  source: "mireye" | "listing" | "memory" | string;
  field?: string;
  value?: any;
  fact?: string;
  [key: string]: any;
}

export interface ChatMessage {
  message_id: string;
  cart_item_id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  citations?: ChatCitation[];
  created_at: string;
}

export interface ListingMemory {
  memory_id: string;
  cart_item_id: string;
  session_id: string;
  fact: string;
  created_at: string;
}

export interface AgentScores {
  energy?: number | null;
  water?: number | null;
  surface?: number | null;
  transport?: number | null;
  risk?: number | null;
}

export interface ComparedSite {
  cart_item_id: string;
  address: string;
  listing_title?: string;
  image_url?: string;
  overall_score?: number | null;
  recommendation?: string;
  agent_scores?: AgentScores | null;
  missing_evaluation: boolean;
}

export interface ComparisonResponse {
  sites: ComparedSite[];
  comparison_narrative: string;
  trade_offs: string[];
}

// ---------------------------------------------------------------------------
// Health & Cart API Calls
// ---------------------------------------------------------------------------

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

export async function deleteCartItem(cartItemId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/cart-items/${encodeURIComponent(cartItemId)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to delete cart item");
  }
}

// ---------------------------------------------------------------------------
// Evaluation Pipeline API Calls
// ---------------------------------------------------------------------------

export async function startEvaluation(cartItemId: string, userRequirements?: string): Promise<{ evaluation_id: string; status: string }> {
  const body: any = { cart_item_id: cartItemId };
  if (userRequirements) {
    body.user_requirements = userRequirements;
  }
  const res = await fetch(`${API_BASE}/evaluate-site`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
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

export async function fetchAllEvaluations(): Promise<EvaluationResult[]> {
  const res = await fetch(`${API_BASE}/evaluate-site`);
  if (!res.ok) throw new Error("Failed to fetch evaluations");
  return res.json();
}

export async function fetchEvaluationsForCartItem(cartItemId: string): Promise<EvaluationResult[]> {
  const res = await fetch(`${API_BASE}/evaluate-site?cart_item_id=${encodeURIComponent(cartItemId)}`);
  if (!res.ok) throw new Error("Failed to fetch evaluations");
  return res.json();
}

// ---------------------------------------------------------------------------
// Site Chat & Memory API Calls
// ---------------------------------------------------------------------------

export async function sendChatMessage(cartItemId: string, sessionId: string, message: string): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cart_item_id: cartItemId, session_id: sessionId, message }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to send chat message");
  }
  return res.json();
}

export async function fetchChatHistory(cartItemId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${API_BASE}/chat?cart_item_id=${encodeURIComponent(cartItemId)}`);
  if (!res.ok) throw new Error("Failed to fetch chat history");
  return res.json();
}

export async function fetchListingMemory(cartItemId: string): Promise<ListingMemory[]> {
  const res = await fetch(`${API_BASE}/listing-memory?cart_item_id=${encodeURIComponent(cartItemId)}`);
  if (!res.ok) throw new Error("Failed to fetch listing memory");
  return res.json();
}

// ---------------------------------------------------------------------------
// Multi-Site Comparison API Calls
// ---------------------------------------------------------------------------

export async function compareSites(cartItemIds: string[]): Promise<ComparisonResponse> {
  const res = await fetch(`${API_BASE}/compare-sites`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cart_item_ids: cartItemIds }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to generate comparison");
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Compliance Agent API Calls
// ---------------------------------------------------------------------------

export interface ComplianceFinding {
  finding: string;
  source: string;
  source_type: string;
  record_id?: string;
  date?: string;
  status?: string;
  confidence?: number;
}

export interface ComplianceCategoryResult {
  status: string;
  score?: number;
  findings: ComplianceFinding[];
}

export interface ComplianceReport {
  property: { address: string; latitude?: number; longitude?: number };
  overall: { risk: string; score: number; confidence: number; summary?: string };
  environmental: ComplianceCategoryResult;
  building: ComplianceCategoryResult;
  fire: ComplianceCategoryResult;
  zoning: ComplianceCategoryResult;
  occupancy: ComplianceCategoryResult;
  data_sources: string[];
  limitations: string[];
}

export async function fetchComplianceReport(cartItemId: string): Promise<ComplianceReport> {
  const res = await fetch(`${API_BASE}/compliance/${encodeURIComponent(cartItemId)}`);
  if (!res.ok) throw new Error("Failed to fetch compliance report");
  return res.json();
}
