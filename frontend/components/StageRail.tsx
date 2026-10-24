import type { AgentState, StageKey } from "@/lib/types";

const STAGES: { key: StageKey; label: string }[] = [
  { key: "new_lead", label: "New lead" },
  { key: "ongoing_pipeline", label: "Ongoing pipeline" },
  { key: "booked_vehicle", label: "Booked vehicle" },
  { key: "service", label: "Post-purchase & service" },
];

/** The four lifecycle stages are a real sequence, so they are numbered; the active one is the stage badge. */
export default function StageRail({ agent }: { agent: AgentState | null }) {
  const active = agent?.stage ?? "general";
  return (
    <nav aria-label="Customer lifecycle stage" className="border-b border-line bg-paper">
      <ol className="mx-auto flex max-w-5xl items-stretch gap-0 overflow-x-auto px-4">
        {STAGES.map((s, i) => {
          const on = s.key === active;
          return (
            <li
              key={s.key}
              aria-current={on ? "step" : undefined}
              data-testid={on ? "stage-badge" : undefined}
              className={`flex min-w-[8.5rem] flex-1 items-center gap-2 border-b-[3px] py-2.5 pr-3 text-sm transition-colors ${
                on ? "border-signal text-ink" : "border-transparent text-steel"
              }`}
            >
              <span
                className={`grid h-6 w-6 shrink-0 place-items-center rounded-full font-display text-xs ${
                  on ? "bg-signal text-white" : "border border-line text-steel"
                }`}
              >
                {i + 1}
              </span>
              <span className={on ? "font-semibold" : ""}>{s.label}</span>
            </li>
          );
        })}
      </ol>
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-1 px-4 pb-2 text-xs text-steel">
        <span>
          Stage: <strong className="text-ink">{agent?.stage_label ?? "Welcome"}</strong>
        </span>
        <span className={agent?.identity_verified ? "text-ok" : ""}>
          {agent?.identity_verified ? "Identity verified" : "Identity not verified"}
        </span>
        {agent?.pending_confirmation && <span className="text-signalDark">Awaiting your confirmation</span>}
      </div>
    </nav>
  );
}
