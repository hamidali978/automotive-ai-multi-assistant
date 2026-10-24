"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchSession, streamChat } from "@/lib/api";
import type { AgentState, ChatMessage, ToolCallInfo } from "@/lib/types";

const KEY = "autoagent.session";
const ACTIVITY: Record<string, string> = {
  list_vehicles: "Checking the model line-up",
  get_vehicle_info: "Looking up the catalog",
  save_lead_details: "Noting your details",
  create_lead: "Preparing your enquiry",
  verify_identity: "Verifying your details",
  get_deal_status: "Checking your deal",
  update_followup: "Preparing the follow-up update",
  get_booking_status: "Checking your booking",
  save_service_details: "Noting the service details",
  create_service_case: "Preparing the service request",
};
const uid = () => Math.random().toString(36).slice(2);

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCallInfo[]>([]);
  const [agent, setAgent] = useState<AgentState | null>(null);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const sessionRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const turnRef = useRef(0);

  useEffect(() => {
    const saved = localStorage.getItem(KEY);
    if (!saved) return;
    fetchSession(saved)
      .then((s) => {
        if (!s) return localStorage.removeItem(KEY);
        sessionRef.current = saved;
        turnRef.current = s.state.turn;
        setAgent(s.state);
        setMessages(s.messages.map((m) => ({ id: uid(), role: m.role, content: m.content })));
      })
      .catch(() => undefined);
  }, []);

  const patchLast = (fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => prev.map((m, i) => (i === prev.length - 1 ? fn(m) : m)));

  const send = useCallback(async (text: string) => {
    const message = text.trim();
    if (!message || abortRef.current) return;
    setNotice(null);
    turnRef.current += 1;
    const turn = turnRef.current;
    setMessages((p) => [
      ...p,
      { id: uid(), role: "user", content: message },
      { id: uid(), role: "assistant", content: "", streaming: true },
    ]);
    setSending(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      for await (const ev of streamChat(sessionRef.current, message, ctrl.signal)) {
        if (ev.event === "session") {
          sessionRef.current = ev.data.session_id;
          localStorage.setItem(KEY, ev.data.session_id);
        } else if (ev.event === "token") {
          patchLast((m) => ({ ...m, content: m.content + ev.data.text, activity: null }));
        } else if (ev.event === "tool_call") {
          const d = ev.data;
          setToolCalls((p) => [...p, { id: d.id, turn, name: d.name, args: d.args, ok: d.ok, ms: d.ms, result: d.result }]);
          patchLast((m) => ({ ...m, activity: ACTIVITY[d.name] ?? "Working on it" }));
        } else if (ev.event === "state") {
          setAgent(ev.data);
        } else if (ev.event === "security") {
          setNotice(ev.data.message);
        } else if (ev.event === "error") {
          patchLast((m) => ({ ...m, error: ev.data.message }));
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError")
        patchLast((m) => ({ ...m, error: "Could not reach the assistant. Please check your connection and try again." }));
    } finally {
      patchLast((m) => ({ ...m, streaming: false, activity: null }));
      abortRef.current = null;
      setSending(false);
    }
  }, []);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    localStorage.removeItem(KEY);
    sessionRef.current = null;
    turnRef.current = 0;
    setMessages([]);
    setToolCalls([]);
    setAgent(null);
    setNotice(null);
  }, []);

  return { messages, toolCalls, agent, sending, notice, send, stop, reset };
}
