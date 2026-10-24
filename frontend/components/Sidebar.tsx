import { ALL_MODELS_PROMPT } from "@/lib/vehicles";
import { Icon, type IconName } from "./icons";
import { cx } from "./ui";

const NAV: { label: string; icon: IconName; active?: boolean }[] = [
  { label: "Chat Assistant", icon: "chat", active: true },
  { label: "Dashboard", icon: "dashboard" },
  { label: "Leads", icon: "leads" },
  { label: "Deals / Pipeline", icon: "deals" },
  { label: "Bookings / Orders", icon: "bookings" },
  { label: "Service Tickets", icon: "wrench" },
  { label: "Customers", icon: "users" },
  { label: "Vehicle Catalog", icon: "car" },
  { label: "Knowledge Base", icon: "book" },
  { label: "Reports & Analytics", icon: "chart" },
  { label: "Settings", icon: "settings" },
];

const SLIM_SCROLL = "[scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,.25)_transparent]";

export default function Sidebar({
  open,
  onClose,
  onAsk,
  disabled,
}: {
  open: boolean;
  onClose: () => void;
  onAsk: (text: string) => void;
  disabled: boolean;
}) {
  return (
    <>
      <div onClick={onClose} aria-hidden="true" className={cx("fixed inset-0 z-30 bg-black/50 lg:hidden", open ? "block" : "hidden")} />
      <aside
        aria-label="Primary"
        className={cx(
          "fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r border-white/10 bg-ink text-white transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0",
          open ? "translate-x-0" : "max-lg:invisible max-lg:-translate-x-full",
        )}
      >
        <div className="flex items-start justify-between px-5 pb-4 pt-5">
          <div>
            <p className="font-display text-3xl leading-none tracking-wide">Mahindra</p>
            <p className="mt-2 text-sm text-white/80">Virtual Assistant</p>
            <p className="text-xs text-white/50">Synced with Zoho CRM</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close menu" className="rounded-lg p-1.5 text-white/70 hover:bg-white/10 lg:hidden">
            <Icon name="close" />
          </button>
        </div>

        <nav aria-label="Sections" className={cx("min-h-0 flex-1 space-y-1 overflow-y-auto px-3 pb-2", SLIM_SCROLL)}>
          {NAV.map((n) =>
            n.active ? (
              <div
                key={n.label}
                aria-current="page"
                className="flex items-center gap-3 rounded-xl bg-gradient-to-r from-signal to-signalDark px-4 py-2.5 text-sm font-semibold shadow-[0_4px_12px_-4px_rgba(200,16,46,.6)]"
              >
                <Icon name={n.icon} />
                {n.label}
              </div>
            ) : (
              <button
                key={n.label}
                type="button"
                aria-disabled="true"
                title="Coming soon"
                className="flex w-full cursor-not-allowed items-center gap-3 rounded-xl px-4 py-2.5 text-left text-sm text-white/55"
              >
                <Icon name={n.icon} />
                {n.label}
              </button>
            ),
          )}
        </nav>

        <div className="relative m-3 shrink-0 overflow-hidden rounded-2xl bg-gradient-to-br from-signal via-signalDark to-ink p-4">
          <Icon name="car" className="absolute -right-2 top-2 h-20 w-20 text-white/10" />
          <p className="relative font-display text-lg uppercase leading-tight tracking-wide">
            Explore the
            <br />
            Mahindra range
          </p>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              onAsk(ALL_MODELS_PROMPT);
              onClose();
            }}
            className="relative mt-6 inline-flex items-center gap-2 rounded-lg border border-white/40 bg-black/20 px-3 py-1.5 text-sm font-medium hover:bg-black/40 disabled:opacity-40"
          >
            View all models <Icon name="arrow" className="h-4 w-4" />
          </button>
        </div>
      </aside>
    </>
  );
}