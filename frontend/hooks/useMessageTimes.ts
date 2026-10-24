import { useRef } from "react";
import type { ChatMessage } from "@/lib/types";

const fmt = new Intl.DateTimeFormat("en-IN", { hour: "2-digit", minute: "2-digit" });

/** Client-side timestamp per message id, captured the first time the message is seen. */
export function useMessageTimes(messages: ChatMessage[]) {
  const seen = useRef(new Map<ChatMessage["id"], string>());
  if (messages.length === 0) seen.current.clear();
  for (const m of messages) {
    if (!seen.current.has(m.id)) seen.current.set(m.id, fmt.format(new Date()));
  }
  return seen.current;
}
