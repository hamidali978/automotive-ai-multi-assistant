import { ALL_MODELS_PROMPT, VEHICLES } from "@/lib/vehicles";
import { Icon } from "./icons";
import VehicleCard from "./VehicleCard";
import { card } from "./ui";

export default function ModelShowcase({ onAsk, disabled }: { onAsk: (text: string) => void; disabled: boolean }) {
  return (
    <section aria-label="Popular models" className={`${card} p-4`}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="font-semibold text-ink">Explore Our Popular Models</h2>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onAsk(ALL_MODELS_PROMPT)}
          className="inline-flex items-center gap-1 whitespace-nowrap text-sm font-medium text-signal hover:text-signalDark disabled:opacity-40"
        >
          View All Models <Icon name="arrow" className="h-4 w-4" />
        </button>
      </div>
      <div className="flex snap-x gap-3 overflow-x-auto pb-1 sm:grid sm:grid-cols-3 sm:overflow-visible">
        {VEHICLES.map((v) => (
          <VehicleCard key={v.id} vehicle={v} disabled={disabled} onSelect={() => onAsk(`Tell me about the ${v.name}: variants and prices`)} />
        ))}
      </div>
      <p className="mt-2 text-xs text-steel">*Indicative ex-showroom prices.</p>
    </section>
  );
}
