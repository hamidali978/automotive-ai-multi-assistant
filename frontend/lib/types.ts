export type StageKey = "general" | "new_lead" | "ongoing_pipeline" | "booked_vehicle" | "service";

export interface AgentState {
  stage: StageKey;
  stage_label: string;
  turn: number;
  identity_verified: boolean;
  verify_failures: number;
  lead_draft_fields: string[];
  service_draft_fields: string[];
  pending_confirmation: string | null;
  completed: string[];
}

export interface ToolCallInfo {
  id: string;
  turn: number;
  name: string;
  args: Record<string, unknown>;
  ok: boolean;
  ms: number;
  result: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  activity?: string | null;
  error?: string | null;
}

export type ServerEvent =
  | { event: "session"; data: { session_id: string } }
  | { event: "token"; data: { text: string } }
  | { event: "tool_call"; data: Omit<ToolCallInfo, "turn"> & { round: number } }
  | { event: "state"; data: AgentState }
  | { event: "security"; data: { message: string } }
  | { event: "error"; data: { message: string; detail?: string } }
  | { event: "done"; data: { session_id: string } };
