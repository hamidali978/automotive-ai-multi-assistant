"use client";
import { useRef, useState } from "react";

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
    <div className="border-t border-line bg-paper px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <label htmlFor="msg" className="sr-only">Message</label>
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
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          className="max-h-36 min-h-[44px] flex-1 resize-none rounded-xl border border-line bg-white px-3.5 py-2.5 text-[15px] placeholder:text-steel/70"
        />
        {sending ? (
          <button onClick={onStop} className="h-11 rounded-xl border border-ink px-4 text-sm font-semibold hover:bg-mist">
            Stop
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!text.trim()}
            className="h-11 rounded-xl bg-signal px-5 text-sm font-semibold text-white hover:bg-signalDark disabled:cursor-not-allowed disabled:opacity-40"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}
