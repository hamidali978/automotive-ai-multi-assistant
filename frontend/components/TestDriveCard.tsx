"use client";
import { useState, type FormEvent } from "react";
import { Icon } from "./icons";
import { card, cx, inputCls, primaryBtn } from "./ui";

const pad = (n: number) => String(n).padStart(2, "0");
// Local-date formatting: toISOString() would shift the day for UTC+05:30 users.
const toInput = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const inDays = (n: number) => {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d;
};

export default function TestDriveCard({ onSubmit, disabled }: { onSubmit: (text: string) => void; disabled: boolean }) {
  const [date, setDate] = useState(() => toInput(inDays(1)));
  const [place, setPlace] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!date || disabled) return;
    const pretty = new Date(`${date}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
    const where = place.trim();
    onSubmit(`I'd like a test drive on ${pretty}${where ? ` in ${where}` : ""}. Please check availability.`);
  };

  return (
    <form onSubmit={submit} aria-label="Book a test drive" className={cx(card, "flex flex-col gap-3 p-4 sm:flex-row sm:items-end")}>
      <span className="hidden h-11 w-11 shrink-0 place-items-center rounded-xl bg-signal/10 text-signal sm:grid">
        <Icon name="bookings" />
      </span>
      <label className="block flex-1 text-xs font-semibold text-ink">
        Select Date
        <input type="date" required min={toInput(new Date())} value={date} onChange={(e) => setDate(e.target.value)} className={cx(inputCls, "mt-1.5 font-normal")} />
      </label>
      <label className="block flex-1 text-xs font-semibold text-ink">
        Preferred Location
        <input type="text" maxLength={80} value={place} placeholder="City or dealership" onChange={(e) => setPlace(e.target.value)} className={cx(inputCls, "mt-1.5 font-normal")} />
      </label>
      <button type="submit" disabled={disabled || !date} className={cx(primaryBtn, "h-11")}>
        Check Availability
      </button>
    </form>
  );
}
