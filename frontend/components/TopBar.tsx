import { Icon } from "./icons";
import { cx } from "./ui";

const STRIPES = "repeating-linear-gradient(115deg,rgba(255,255,255,.55) 0 1px,transparent 1px 14px)";
const btn =
  "inline-flex h-10 items-center gap-2 rounded-lg border px-3.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70";

export default function TopBar({
  debug,
  onToggleDebug,
  onNewChat,
  onMenu,
  onPanel,
}: {
  debug: boolean;
  onToggleDebug: () => void;
  onNewChat: () => void;
  onMenu: () => void;
  onPanel: () => void;
}) {
  return (
    <header className="relative z-10 isolate flex min-h-[76px] items-center gap-3 overflow-hidden bg-gradient-to-r from-ink via-signalDark to-signal px-4 py-3 pt-[max(0.75rem,env(safe-area-inset-top))] text-white shadow-[0_4px_12px_-6px_rgba(16,20,23,.5)] sm:px-6">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 opacity-[.07]" style={{ backgroundImage: STRIPES }} />
      <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-px bg-white/20" />

      <button
        type="button"
        onClick={onMenu}
        aria-label="Open menu"
        className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-white/30 bg-white/10 hover:bg-white/20 lg:hidden"
      >
        <Icon name="menu" />
      </button>

      <div className="min-w-0">
        <h1 className="truncate font-display text-xl leading-tight tracking-wide sm:text-2xl">
          <span className="lg:hidden">Mahindra Virtual Assistant</span>
          <span className="hidden lg:inline">Chat Assistant</span>
        </h1>
        <p className="hidden truncate text-xs text-white/75 lg:block">Ask about models, test drives, bookings and service</p>
      </div>

      <span className="ml-1 hidden shrink-0 items-center gap-1.5 rounded-full border border-white/20 bg-black/25 px-2.5 py-1 text-xs text-white/90 sm:inline-flex">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        Synced with Zoho CRM
      </span>

      <div className="ml-auto flex shrink-0 items-center gap-2">
        <button type="button" onClick={onNewChat} className={cx(btn, "border-white/30 bg-white/10 hover:bg-white/20")}>
          <Icon name="chat" className="h-4 w-4" />
          <span className="hidden sm:inline">New chat</span>
          <span className="sr-only sm:hidden">New chat</span>
        </button>
        <button
          type="button"
          onClick={onToggleDebug}
          aria-pressed={debug}
          className={cx(btn, debug ? "border-white bg-white text-ink" : "border-white/30 bg-white/10 hover:bg-white/20")}
        >
          <Icon name="engine" className="h-4 w-4" />
          <span className="hidden sm:inline">Debug</span>
          <span className="sr-only sm:hidden">Debug</span>
        </button>
        <button
          type="button"
          onClick={onPanel}
          aria-label="Customer details"
          className="grid h-10 w-10 place-items-center rounded-lg border border-white/30 bg-white/10 hover:bg-white/20 xl:hidden"
        >
          <Icon name="user" />
        </button>
      </div>
    </header>
  );
}