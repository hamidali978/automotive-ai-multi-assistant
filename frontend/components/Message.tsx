import type { ChatMessage } from "@/lib/types";
import RichText from "./RichText";

export default function Message({ m }: { m: ChatMessage }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-ink px-4 py-2.5 text-[15px] leading-relaxed text-white">
          {m.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[88%] break-words rounded-2xl rounded-bl-sm border border-line bg-paper px-4 py-2.5 text-[15px] leading-relaxed shadow-[0_1px_0_rgba(16,20,23,.04)]">
        {m.content ? <RichText text={m.content} /> : null}
        {m.streaming && !m.content && (
          <span className="flex items-center gap-2 text-sm text-steel" role="status">
            <span className="flex gap-1" aria-hidden>
              {[0, 1, 2].map((i) => (
                <span key={i} className="dot h-1.5 w-1.5 rounded-full bg-signal" />
              ))}
            </span>
            {m.activity ?? "Thinking"}
          </span>
        )}
        {m.streaming && m.content && m.activity && <p className="mt-1 text-xs text-steel">{m.activity}…</p>}
        {m.error && <p className="mt-2 border-l-2 border-signal pl-2 text-sm text-signalDark">{m.error}</p>}
      </div>
    </div>
  );
}
