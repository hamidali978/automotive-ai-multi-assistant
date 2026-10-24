export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/** Shared surface: white card, hairline border, light shadow (kept cheap to repaint while streaming). */
export const card =
  "rounded-2xl border border-line bg-paper shadow-[0_1px_2px_rgba(16,20,23,.06),0_4px_12px_-6px_rgba(16,20,23,.12)]";

export const primaryBtn =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-b from-signal to-signalDark px-5 text-sm font-semibold text-white shadow-[0_4px_10px_-4px_rgba(200,16,46,.5)] transition-colors hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal/60 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none";

export const inputCls =
  "h-11 w-full rounded-xl border border-line bg-white px-3 text-sm text-ink placeholder:text-steel/70 focus:border-signal focus:outline-none focus:ring-2 focus:ring-signal/20";