import { STAGES, type AgentView } from "@/lib/agentView";
import { Icon } from "./icons";
import { cx } from "./ui";

export default function LifecycleTracker({ view }: { view: AgentView }) {
  const active = view.stage || 1;
  return (
    <nav aria-label="Customer lifecycle" className="border-b border-line bg-paper">
      <div className="overflow-x-auto px-4 pt-4">
        <ol className="flex min-w-[600px] items-center">
          {STAGES.map((s, i) => {
            const state = s.id === active ? "active" : s.id < active ? "done" : "todo";
            const last = i === STAGES.length - 1;
            return (
              <li key={s.id} aria-current={state === "active" ? "step" : undefined} className={cx("flex items-center", !last && "flex-1")}>
                <span
                  className={cx(
                    "grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-semibold transition",
                    state === "active" && "bg-signal text-white ring-4 ring-signal/20",
                    state === "done" && "bg-ink text-white",
                    state === "todo" && "border border-line bg-paper text-steel",
                  )}
                >
                  {state === "done" ? <Icon name="check" className="h-4 w-4" /> : s.id}
                </span>
                <span className={cx("ml-2.5 whitespace-nowrap text-sm", state === "active" ? "font-semibold text-ink" : "text-steel")}>{s.label}</span>
                {!last && <span aria-hidden="true" className={cx("mx-4 h-px flex-1", state === "done" ? "bg-signal" : "bg-line")} />}
              </li>
            );
          })}
        </ol>
      </div>
      <p className="flex flex-wrap items-center gap-x-3 px-4 pb-3 pt-2 text-xs text-steel">
        <span>
          Stage: <b className="font-semibold text-ink">{view.stageLabel}</b>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className={cx("h-1.5 w-1.5 rounded-full", view.verified ? "bg-emerald-500" : "bg-steel/50")} />
          {view.verified ? "Identity verified" : "Identity not verified"}
        </span>
      </p>
    </nav>
  );
}
