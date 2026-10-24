import { memo, type ReactNode } from "react";
import type { ChatMessage } from "@/lib/types";
import type { VehicleSpecs } from "@/lib/vehicles";
import BotAvatar from "./BotAvatar";
import RichText from "./RichText";
import SpecStrip from "./SpecStrip";
import { card, cx } from "./ui";

/** Avatar + white bubble. Shared by streamed assistant messages and the static welcome. */
export function AssistantRow({ children, time, extra }: { children: ReactNode; time?: string; extra?: ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <BotAvatar />
      <div className="min-w-0 max-w-[88%]">
        <div className={cx(card, "break-words rounded-tl-sm px-4 py-3 text-[15px] leading-relaxed text-ink")}>{children}</div>
        {time && <p className="mt-1 px-1 text-xs text-steel">{time}</p>}
        {extra}
      </div>
    </div>
  );
}

type Props = { m: ChatMessage; time?: string; specs?: VehicleSpecs };

/**
 * Memoised: while a reply streams, only the streaming message gets a new `m`,
 * so earlier messages skip re-render and RichText re-parsing.
 */
function MessageBase({ m, time, specs }: Props) {
  if (m.role === "user") {
    return (
      <div className="flex flex-col items-end">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-ink px-4 py-2.5 text-[15px] leading-relaxed text-white">
          {m.content}
        </div>
        {time && <p className="mt-1 px-1 text-xs text-steel">{time}</p>}
      </div>
    );
  }
  return (
    <AssistantRow time={m.streaming ? undefined : time} extra={specs ? <SpecStrip specs={specs} /> : null}>
      {m.content ? <RichText text={m.content} /> : null}
      {m.streaming && !m.content && (
        <span className="flex items-center gap-2 text-sm text-steel" role="status">
          <span className="flex gap-1" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <span key={i} className="dot h-1.5 w-1.5 rounded-full bg-signal" />
            ))}
          </span>
          {m.activity ?? "Thinking"}
        </span>
      )}
      {m.streaming && m.content && m.activity && <p className="mt-1 text-xs text-steel">{m.activity}…</p>}
      {m.error && <p className="mt-2 border-l-2 border-signal pl-2 text-sm text-signalDark">{m.error}</p>}
    </AssistantRow>
  );
}

export default memo(MessageBase);