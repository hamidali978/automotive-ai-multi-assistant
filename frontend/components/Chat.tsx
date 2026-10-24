"use client";
import { useEffect, useRef, useState } from "react";
import { useChat } from "@/hooks/useChat";
import Composer from "./Composer";
import DebugDrawer from "./DebugDrawer";
import Message from "./Message";
import RichText from "./RichText";
import StageRail from "./StageRail";

const WELCOME =
  "Namaste, and welcome to Mahindra. I'm your virtual assistant. I can walk you through the **XUV700, Thar and Scorpio-N**, check your test drive or quotation, track a booked vehicle, or arrange a service visit.";

const STARTERS = [
  "What are the variants and prices of the XUV700?",
  "I'd like to check my test drive and quotation",
  "Where is my booked Scorpio-N?",
  "I need to book a service for my vehicle",
];

export default function Chat() {
  const { messages, toolCalls, agent, sending, notice, send, stop, reset } = useChat();
  const [debug, setDebug] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center justify-between border-b border-line bg-ink px-4 py-3 pt-[max(0.75rem,env(safe-area-inset-top))] text-white">
        <div>
          <h1 className="font-display text-xl tracking-wide">Mahindra Virtual Assistant</h1>
          <p className="text-xs text-white/60">synced with Zoho CRM</p>
        </div>
        <div className="flex gap-2">
          <button onClick={reset} className="rounded-lg border border-white/25 px-3 py-1.5 text-sm hover:bg-white/10">New chat</button>
          <button
            onClick={() => setDebug((d) => !d)} aria-pressed={debug}
            className={`rounded-lg border px-3 py-1.5 text-sm ${debug ? "border-signal bg-signal" : "border-white/25 hover:bg-white/10"}`}
          >
            Debug
          </button>
        </div>
      </header>
      <StageRail agent={agent} />
      <div className="flex min-h-0 flex-1">
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto px-4 py-5" role="log" aria-live="polite" aria-label="Conversation">
            <div className="mx-auto flex max-w-3xl flex-col gap-3">
              <div className="flex justify-start">
                <div className="max-w-[88%] rounded-2xl rounded-bl-sm border border-line bg-paper px-4 py-2.5 text-[15px] leading-relaxed">
                  <RichText text={WELCOME} />
                </div>
              </div>
              {messages.length === 0 && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {STARTERS.map((s) => (
                    <button key={s} onClick={() => send(s)} className="rounded-full border border-line bg-paper px-3.5 py-1.5 text-sm hover:border-signal hover:text-signalDark">
                      {s}
                    </button>
                  ))}
                </div>
              )}
              {messages.map((m) => <Message key={m.id} m={m} />)}
              {notice && <p className="text-center text-xs text-steel">{notice}</p>}
              <div ref={bottom} />
            </div>
          </div>
          <Composer sending={sending} onSend={send} onStop={stop} />
        </main>
        <DebugDrawer open={debug} onClose={() => setDebug(false)} toolCalls={toolCalls} agent={agent} />
      </div>
    </div>
  );
}
