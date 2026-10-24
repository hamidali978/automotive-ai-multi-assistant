"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useChat } from "@/hooks/useChat";
import { useMessageTimes } from "@/hooks/useMessageTimes";
import { offersTestDrive, readAgent } from "@/lib/agentView";
import type { ChatMessage } from "@/lib/types";
import { findVehicle, type VehicleSpecs } from "@/lib/vehicles";
import Composer from "./Composer";
import CustomerPanel from "./CustomerPanel";
import DebugDrawer from "./DebugDrawer";
import { Icon, type IconName } from "./icons";
import LifecycleTracker from "./LifecycleTracker";
import Message, { AssistantRow } from "./Message";
import ModelShowcase from "./ModelShowcase";
import RichText from "./RichText";
import Sidebar from "./Sidebar";
import TestDriveCard from "./TestDriveCard";
import TopBar from "./TopBar";
import { card, cx } from "./ui";

const WELCOME =
  "Namaste, and welcome to Mahindra. I'm your virtual assistant. I can walk you through the **XUV700, Thar and Scorpio-N**, check your test drive or quotation, track a booked vehicle, or arrange a service visit.";

const STARTERS: { text: string; icon: IconName }[] = [
  { text: "What are the variants and prices of the XUV700?", icon: "search" },
  { text: "I'd like to check my test drive and quotation", icon: "bookings" },
  { text: "Where is my booked Scorpio-N?", icon: "car" },
  { text: "I need to book a service for my vehicle", icon: "wrench" },
];

export default function Chat() {
  const { messages, toolCalls, agent, sending, notice, send, stop, reset } = useChat();
  const [debug, setDebug] = useState(false);
  const [nav, setNav] = useState(false);
  const [panel, setPanel] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const times = useMessageTimes(messages);
  const view = readAgent(agent);

  // Smooth scrolling restarts on every streamed token and makes replies feel laggy:
  // jump instantly while streaming, animate once when it finishes.
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      bottom.current?.scrollIntoView({ behavior: sending ? "auto" : "smooth", block: "end" });
    });
    return () => cancelAnimationFrame(id);
  }, [messages, sending]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setNav(false);
        setPanel(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Spec highlights: shown once per model, under the first finished reply that mentions it.
  const specFor = useMemo(() => {
    const shown = new Set<string>();
    const out = new Map<ChatMessage["id"], VehicleSpecs>();
    for (const m of messages) {
      if (m.role !== "assistant" || m.streaming || !m.content) continue;
      const v = findVehicle(m.content);
      if (v?.specs && !shown.has(v.id)) {
        shown.add(v.id);
        out.set(m.id, v.specs);
      }
    }
    return out;
  }, [messages]);

  const last = messages[messages.length - 1];
  const showTestDrive = !!last && last.role === "assistant" && !last.streaming && !sending && offersTestDrive(last.content ?? "");

  const recent = messages
    .filter((m) => m.role === "user")
    .slice(-4)
    .reverse()
    .map((m) => ({ id: m.id, text: m.content, time: times.get(m.id) }));

  return (
    <div className="flex h-dvh bg-mist text-ink">
      <Sidebar open={nav} onClose={() => setNav(false)} onAsk={send} disabled={sending} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar debug={debug} onToggleDebug={() => setDebug((d) => !d)} onNewChat={reset} onMenu={() => setNav(true)} onPanel={() => setPanel(true)} />
        <div className="flex min-h-0 flex-1">
          <main className="flex min-w-0 flex-1 flex-col">
            <LifecycleTracker view={view} />
            <div className="flex-1 overflow-y-auto px-4 py-5" role="log" aria-live="polite" aria-label="Conversation">
              <div className="mx-auto flex max-w-3xl flex-col gap-4">
                <AssistantRow>
                  <RichText text={WELCOME} />
                </AssistantRow>
                {messages.length === 0 && (
                  <div className="space-y-4 pl-12">
                    <div className="flex flex-wrap gap-2">
                      {STARTERS.map((s) => (
                        <button
                          key={s.text}
                          type="button"
                          disabled={sending}
                          onClick={() => send(s.text)}
                          className={cx(card, "inline-flex items-center gap-2.5 px-3.5 py-2.5 text-left text-sm transition-colors hover:border-signal hover:text-signalDark disabled:opacity-50")}
                        >
                          <Icon name={s.icon} className="h-4 w-4 shrink-0 text-signal" />
                          {s.text}
                        </button>
                      ))}
                    </div>
                    <ModelShowcase onAsk={send} disabled={sending} />
                  </div>
                )}
                {messages.map((m) => (
                  <Message key={m.id} m={m} time={times.get(m.id)} specs={specFor.get(m.id)} />
                ))}
                {showTestDrive && (
                  <div className="pl-12">
                    <TestDriveCard onSubmit={send} disabled={sending} />
                  </div>
                )}
                {notice && <p className="text-center text-xs text-steel">{notice}</p>}
                <div ref={bottom} />
              </div>
            </div>
            <Composer sending={sending} onSend={send} onStop={stop} />
          </main>
          <DebugDrawer open={debug} onClose={() => setDebug(false)} toolCalls={toolCalls} agent={agent} />
          <CustomerPanel view={view} recent={recent} onAsk={send} disabled={sending} open={panel} onClose={() => setPanel(false)} debugOpen={debug} />
        </div>
      </div>
    </div>
  );
}