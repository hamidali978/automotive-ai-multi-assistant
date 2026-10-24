import type { ReactNode } from "react";
import type { AgentView } from "@/lib/agentView";
import type { ChatMessage } from "@/lib/types";
import { Icon, type IconName } from "./icons";
import { card, cx } from "./ui";

export type RecentItem = { id: ChatMessage["id"]; text: string; time?: string };

const CRM_URL = process.env.NEXT_PUBLIC_ZOHO_CRM_URL;

const ACTIONS: { label: string; icon: IconName; prompt: string }[] = [
  { label: "Create Lead", icon: "leads", prompt: "I'm interested in a Mahindra SUV and would like a quotation and test drive" },
  { label: "Create Deal", icon: "chart", prompt: "I'd like to check my test drive and quotation" },
  { label: "New Booking", icon: "car", prompt: "I'd like to track my booked vehicle" },
  { label: "Service Ticket", icon: "wrench", prompt: "I need to book a service for my vehicle" },
];

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className={cx(card, "p-4")}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="font-semibold text-ink">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

const initials = (name?: string) =>
  name
    ? name
        .split(/\s+/)
        .slice(0, 2)
        .map((p) => p[0]?.toUpperCase() ?? "")
        .join("")
    : "";

function Row({ icon, value }: { icon: IconName; value?: string }) {
  return (
    <li className="flex items-center gap-3 text-sm">
      <Icon name={icon} className="h-4 w-4 shrink-0 text-ink" />
      <span className={cx("min-w-0 break-words", value ? "text-ink" : "text-steel")}>{value ?? "Not Available"}</span>
    </li>
  );
}

export default function CustomerPanel({
  view,
  recent,
  onAsk,
  disabled,
  open,
  onClose,
  debugOpen,
}: {
  view: AgentView;
  recent: RecentItem[];
  onAsk: (text: string) => void;
  disabled: boolean;
  open: boolean;
  onClose: () => void;
  debugOpen: boolean;
}) {
  const { customer, verified } = view;
  return (
    <>
      <div onClick={onClose} aria-hidden="true" className={cx("fixed inset-0 z-30 bg-black/50 xl:hidden", open ? "block" : "hidden")} />
      <aside
        aria-label="Customer details"
        className={cx(
          "fixed inset-y-0 right-0 z-40 w-[22rem] max-w-[92vw] space-y-4 overflow-y-auto bg-mist p-4 shadow-2xl transition-transform duration-200 xl:static xl:z-auto xl:w-80 xl:shrink-0 xl:translate-x-0 xl:shadow-none",
          open ? "translate-x-0" : "max-xl:invisible max-xl:translate-x-full",
          debugOpen && "xl:max-2xl:hidden",
        )}
      >
        <Section
          title="Customer Information"
          action={
            CRM_URL ? (
              <a href={CRM_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs font-medium text-signal hover:text-signalDark">
                View in CRM <Icon name="external" className="h-3.5 w-3.5" />
              </a>
            ) : (
              <button type="button" onClick={onClose} aria-label="Close panel" className="rounded-lg p-1 text-steel hover:bg-mist xl:hidden">
                <Icon name="close" className="h-4 w-4" />
              </button>
            )
          }
        >
          <div className="flex items-center gap-3">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-mist text-lg font-semibold text-ink ring-1 ring-line">
              {initials(customer.name) || <Icon name="user" className="h-5 w-5 text-steel" />}
            </span>
            <div className="min-w-0">
              <p className="truncate font-semibold text-ink">{customer.name ?? "Not Identified"}</p>
              <span
                className={cx(
                  "mt-1 inline-block rounded-md px-2 py-0.5 text-xs font-medium",
                  verified ? "bg-ink text-white" : "bg-signal/10 text-signalDark",
                )}
              >
                {verified ? "Verified" : "New Visitor"}
              </span>
            </div>
          </div>
          <ul className="mt-4 space-y-2.5">
            <Row icon="phone" value={customer.phone} />
            <Row icon="mail" value={customer.email} />
            <Row icon="pin" value={customer.city} />
          </ul>
        </Section>

        <Section title="Quick Actions">
          <div className="grid grid-cols-4 gap-2">
            {ACTIONS.map((a) => (
              <button
                key={a.label}
                type="button"
                disabled={disabled}
                onClick={() => {
                  onAsk(a.prompt);
                  onClose();
                }}
                className="group flex flex-col items-center gap-1.5 rounded-xl p-1 text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal disabled:opacity-40"
              >
                <span className="grid h-12 w-12 place-items-center rounded-full bg-signal/10 text-signal transition group-hover:bg-signal group-hover:text-white">
                  <Icon name={a.icon} className="h-5 w-5" />
                </span>
                <span className="text-[11px] leading-tight text-ink">{a.label}</span>
              </button>
            ))}
          </div>
        </Section>

        <Section title="Recent in this chat">
          {recent.length === 0 ? (
            <p className="text-sm text-steel">No messages yet.</p>
          ) : (
            <ul className="space-y-1">
              {recent.map((r, i) => (
                <li key={r.id} className={cx("flex items-center gap-3 rounded-xl px-2 py-2", i === 0 && "bg-signal/5")}>
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-paper text-ink ring-1 ring-line">
                    <Icon name="chat" className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm text-ink">{r.text}</p>
                    {r.time && <p className="text-xs text-steel">{r.time}</p>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </aside>
    </>
  );
}
