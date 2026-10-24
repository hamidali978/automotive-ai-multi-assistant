export type VehicleSpecs = {
  engine: string;
  mileage: string;
  safety: string;
  seating: string;
  variants: string;
};

export type Vehicle = {
  id: string;
  name: string;
  fromLakh: number;
  /**
   * Optional photo. Leave undefined until the file exists in /public,
   * otherwise every page load fires a 404 (slow in `next dev`).
   * Example: image: "/vehicles/xuv700.jpg"
   */
  image?: string;
  tint: string;
  /** Used to detect which model an assistant message is about. */
  match: RegExp;
  /** Illustrative display data. Keep in sync with the backend catalog. */
  specs?: VehicleSpecs;
};

export const VEHICLES: readonly Vehicle[] = [
  {
    id: "xuv700",
    name: "XUV700",
    fromLakh: 14.49,
    tint: "linear-gradient(135deg,#27365e,#101417)",
    match: /xuv\s?-?700/i,
    specs: {
      engine: "2.0L Turbo",
      mileage: "13–16 kmpl",
      safety: "5 Star Rating",
      seating: "6 / 7 Seater",
      variants: "MX, AX3, AX5, AX7",
    },
  },
  {
    id: "thar",
    name: "Thar",
    fromLakh: 11.35,
    tint: "linear-gradient(135deg,#9b2415,#101417)",
    match: /\bthar\b/i,
  },
  {
    id: "scorpio-n",
    name: "Scorpio-N",
    fromLakh: 13.99,
    tint: "linear-gradient(135deg,#3a4049,#101417)",
    match: /scorpio[\s-]?n\b/i,
  },
];

export const ALL_MODELS_PROMPT = "Show me the Mahindra range: XUV700, Thar and Scorpio-N";

export const formatFrom = (v: Vehicle) => `From ₹${v.fromLakh.toFixed(2)} Lakh*`;

/** Earliest-mentioned catalog model in `text`, if any. */
export function findVehicle(text: string): Vehicle | undefined {
  let best: Vehicle | undefined;
  let at = Infinity;
  for (const v of VEHICLES) {
    const i = text.search(v.match);
    if (i >= 0 && i < at) {
      best = v;
      at = i;
    }
  }
  return best;
}