"use client";
import { useRef, useState } from "react";
import { Icon } from "./icons";
import { primaryBtn } from "./ui";

export default function Composer({ sending, onSend, onStop }: { sending: boolean; onSend: (t: string) => void; onStop: () => void }) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    if (!text.trim() || sending) return;
    onSend(text);
    setText("");
    if (ref.current) ref.current.style.height = "auto";
  };

  return (
    <div className="border-t border-line bg-mist px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-line bg-paper p-2 shadow-[0_8px_24px_-16px_rgba(16,20,23,.25)] focus-within:border-signal focus-within:ring-2 focus-within:ring-signal/20">
        <label htmlFor="msg" className="sr-only">
          Message
        </label>
        <textarea
          id="msg"
          ref={ref}
          rows={1}
          value={text}
          maxLength={2000}
          placeholder="Ask about a model, your test drive, booking or service…"
          onChange={(e) => {
            setText(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          className="max-h-36 min-h-[44px] flex-1 resize-none bg-transparent px-2.5 py-2.5 text-[15px] text-ink placeholder:text-steel/70 focus:outline-none"
        />
        {sending ? (
          <button type="button" onClick={onStop} className="h-11 rounded-xl border border-ink px-4 text-sm font-semibold text-ink hover:bg-mist">
            Stop
          </button>
        ) : (
          <button type="button" onClick={submit} disabled={!text.trim()} className={`${primaryBtn} h-11`}>
            Send <Icon name="send" className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
