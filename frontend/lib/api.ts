import type { AgentState, ServerEvent } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchSession(
  id: string,
): Promise<{ state: AgentState; messages: { role: "user" | "assistant"; content: string }[] } | null> {
  const r = await fetch(`${API_URL}/api/sessions/${id}`, { cache: "no-store" });
  return r.ok ? r.json() : null;
}

export async function fetchHealth(): Promise<Record<string, unknown> | null> {
  try {
    const r = await fetch(`${API_URL}/api/health`, { cache: "no-store" });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

/** POST + read the SSE stream (EventSource cannot POST). Yields parsed server events. */
export async function* streamChat(
  sessionId: string | null,
  message: string,
  signal: AbortSignal,
): AsyncGenerator<ServerEvent> {
  const resp = await fetch(`${API_URL}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
    signal,
  });
  if (!resp.ok || !resp.body) throw new Error(`Server returned ${resp.status}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trim());
      }
      if (data.length) yield { event, data: JSON.parse(data.join("\n")) } as ServerEvent;
    }
  }
}
