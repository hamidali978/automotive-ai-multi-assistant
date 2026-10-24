import type { VehicleSpecs } from "@/lib/vehicles";
import { Icon, type IconName } from "./icons";
import { card, cx } from "./ui";

const ITEMS: { key: keyof VehicleSpecs; label: string; icon: IconName }[] = [
  { key: "engine", label: "Engine", icon: "engine" },
  { key: "mileage", label: "Mileage", icon: "gauge" },
  { key: "safety", label: "Safety", icon: "shield" },
  { key: "seating", label: "Seating", icon: "users" },
  { key: "variants", label: "Variants", icon: "layers" },
];

export default function SpecStrip({ specs }: { specs: VehicleSpecs }) {
  return (
    <dl className={cx(card, "mt-2 grid grid-cols-2 gap-3 p-3 sm:grid-cols-3 2xl:grid-cols-5")}>
      {ITEMS.map((i) => (
        <div key={i.key} className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-signal/10 text-signal">
            <Icon name={i.icon} />
          </span>
          <div className="min-w-0">
            <dt className="text-xs font-semibold text-ink">{i.label}</dt>
            <dd className="break-words text-xs text-steel">{specs[i.key]}</dd>
          </div>
        </div>
      ))}
    </dl>
  );
}
