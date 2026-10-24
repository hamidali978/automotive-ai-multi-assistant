"use client";
import { useEffect, useState } from "react";
import { fetchHealth } from "@/lib/api";
import type { AgentState, ToolCallInfo } from "@/lib/types";

const json = (v: unknown) => JSON.stringify(v, null, 2);

export default function DebugDrawer({ open, onClose, toolCalls, agent }: {
  open: boolean; onClose: () => void; toolCalls: ToolCallInfo[]; agent: AgentState | null;
}) {
  const [tab, setTab] = useState<"tools" | "state">("tools");
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (open && tab === "state") fetchHealth().then(setHealth);
  }, [open, tab, agent?.turn]);

  if (!open) return null;
  const turns = Array.from(new Set(toolCalls.map((t) => t.turn)));

  return (
    <aside
      aria-label="Debug drawer"
      className="fixed inset-y-0 right-0 z-30 flex w-full flex-col border-l border-line bg-paper shadow-xl sm:w-[26rem] lg:static lg:z-auto lg:shadow-none"
    >
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 className="font-display text-lg">Debug</h2>
        <button onClick={onClose} aria-label="Close debug drawer" className="rounded-md px-2 py-1 text-steel hover:bg-mist">✕</button>
      </div>
      <div role="tablist" className="flex border-b border-line text-sm">
        {(["tools", "state"] as const).map((t) => (
          <button
            key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`flex-1 border-b-2 px-3 py-2 ${tab === t ? "border-signal font-semibold" : "border-transparent text-steel"}`}
          >
            {t === "tools" ? `Tool calls (${toolCalls.length})` : "Session"}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-3 text-sm">
        {tab === "tools" ? (
          toolCalls.length === 0 ? (
            <p className="text-steel">No tool calls yet. Ask about a vehicle to see the agent route to a tool.</p>
          ) : (
            turns.map((turn) => (
              <section key={turn} className="mb-4">
                <h3 className="mb-1 text-xs font-semibold text-steel">Turn {turn}</h3>
                <ul className="space-y-1.5">
                  {toolCalls.filter((t) => t.turn === turn).map((t) => (
                    <li key={t.id} className="rounded-lg border border-line">
                      <details>
                        <summary className="flex cursor-pointer items-center gap-2 px-3 py-2">
                          <span className={`h-2 w-2 rounded-full ${t.ok ? "bg-ok" : "bg-signal"}`} aria-label={t.ok ? "ok" : "error"} />
                          <span className="flex-1 font-mono text-[13px]">{t.name}</span>
                          <span className="text-xs text-steel">{t.ms} ms</span>
                        </summary>
                        <div className="space-y-2 border-t border-line p-3">
                          <div>
                            <p className="mb-1 text-xs text-steel">Arguments (contact details masked)</p>
                            <pre className="max-h-40 overflow-auto rounded bg-mist p-2 font-mono text-xs">{json(t.args)}</pre>
                          </div>
                          <div>
                            <p className="mb-1 text-xs text-steel">Result</p>
                            <pre className="max-h-64 overflow-auto rounded bg-mist p-2 font-mono text-xs">{json(t.result)}</pre>
                          </div>
                        </div>
                      </details>
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )
        ) : (
          <div className="space-y-4">
            <div>
              <h3 className="mb-1 text-xs font-semibold text-steel">Session state</h3>
              <pre className="overflow-auto rounded bg-mist p-2 font-mono text-xs">{json(agent ?? { stage: "general" })}</pre>
            </div>
            <div>
              <h3 className="mb-1 text-xs font-semibold text-steel">Backend health</h3>
              <pre className="overflow-auto rounded bg-mist p-2 font-mono text-xs">{health ? json(health) : "unreachable"}</pre>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
