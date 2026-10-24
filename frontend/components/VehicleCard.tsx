import { formatFrom, type Vehicle } from "@/lib/vehicles";
import { Icon } from "./icons";

const SHADE = "linear-gradient(to top,rgba(16,20,23,.85),rgba(16,20,23,.05) 62%)";

export default function VehicleCard({
  vehicle,
  onSelect,
  disabled,
}: {
  vehicle: Vehicle;
  onSelect: (v: Vehicle) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onSelect(vehicle)}
      aria-label={`${vehicle.name}. ${formatFrom(vehicle)}. Ask about this model`}
      className="group relative aspect-[4/3] min-w-[72%] snap-start overflow-hidden rounded-xl bg-ink text-left text-white shadow-[0_4px_12px_-6px_rgba(16,20,23,.5)] transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 disabled:opacity-60 sm:min-w-0"
      style={{
        backgroundImage: vehicle.image ? `${SHADE},url(${vehicle.image}),${vehicle.tint}` : `${SHADE},${vehicle.tint}`,
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      {!vehicle.image && <Icon name="car" className="absolute right-3 top-3 h-14 w-14 text-white/15" />}
      <span className="absolute inset-x-3 bottom-3 flex items-end justify-between gap-2">
        <span className="min-w-0">
          <span className="block font-display text-2xl leading-none tracking-wide">{vehicle.name}</span>
          <span className="mt-1 block text-sm text-white/85">{formatFrom(vehicle)}</span>
        </span>
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white text-ink transition-colors group-hover:bg-signal group-hover:text-white">
          <Icon name="arrow" className="h-4 w-4" />
        </span>
      </span>
    </button>
  );
}