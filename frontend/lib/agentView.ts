/**
 * Single adapter between the backend `agent` state (from useChat) and the UI.
 * It searches the whole state (any depth, camelCase or snake_case), so the exact
 * nesting doesn't matter. If a field still shows "Not Available", open the Debug
 * drawer, find the key that holds it, and add that key (normalised: lowercase,
 * letters and digits only) to KEYS below.
 */

export type StageId = 0 | 1 | 2 | 3 | 4;

export const STAGES = [
  { id: 1, label: "New Lead" },
  { id: 2, label: "Ongoing pipeline" },
  { id: 3, label: "Booked vehicle" },
  { id: 4, label: "Post-purchase & service" },
] as const;

export type CustomerView = { name?: string; phone?: string; email?: string; city?: string };

export type AgentView = {
  stage: StageId;
  stageLabel: string;
  verified: boolean;
  customer: CustomerView;
};

/** Candidate keys per field, highest priority first. */
const KEYS = {
  name: ["customername", "contactname", "fullname", "name", "displayname", "firstname"],
  phone: ["customerphone", "contactphone", "phone", "phonenumber", "mobile", "mobilenumber", "contactmobile"],
  email: ["customeremail", "contactemail", "email", "emailaddress"],
  city: ["customercity", "contactcity", "city", "location", "mailingcity"],
  stage: ["stage", "currentstage", "workflow", "activeworkflow", "flow", "intent"],
  verified: ["verified", "identityverified", "isverified", "customerverified", "authenticated"],
} as const;

/** Parent keys whose children describe something other than the customer (e.g. dealer.phone). */
const NOT_CUSTOMER = /dealer|vehicle|model|variant|tool|quotation|center/;

type Flat = { parents: string[]; key: string; value: string };

const norm = (k: string) => k.toLowerCase().replace(/[^a-z0-9]/g, "");

function flatten(v: unknown, parents: string[] = [], out: Flat[] = [], depth = 0): Flat[] {
  if (v === null || v === undefined || depth > 5) return out;
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
    const value = String(v).trim();
    if (value && parents.length) out.push({ parents: parents.slice(0, -1), key: parents[parents.length - 1], value });
  } else if (typeof v === "object" && !Array.isArray(v)) {
    for (const [k, x] of Object.entries(v as Record<string, unknown>)) flatten(x, [...parents, norm(k)], out, depth + 1);
  }
  return out;
}

const find = (flat: Flat[], keys: readonly string[], opts: { customerOnly?: boolean } = {}) => {
  for (const k of keys) {
    const hit = flat.find((f) => f.key === k && (!opts.customerOnly || !f.parents.some((p) => NOT_CUSTOMER.test(p))));
    if (hit) return hit.value;
  }
  return undefined;
};

export function stageOf(raw: unknown): StageId {
  const n = typeof raw === "string" && /^\d$/.test(raw.trim()) ? Number(raw) : raw; // flatten() stringifies numbers
  if (typeof n === "number" && Number.isInteger(n) && n >= 1 && n <= 4) return n as StageId;
  const s = (typeof raw === "string" ? raw : "").toLowerCase();
  if (/service|case|post/.test(s)) return 4;
  if (/book|deliver/.test(s)) return 3;
  if (/pipeline|deal|ongoing|test/.test(s)) return 2;
  if (/lead|new/.test(s)) return 1;
  return 0;
}

export function readAgent(agent: unknown): AgentView {
  const flat = flatten({ agent }).map((f) => ({ ...f, parents: f.parents.slice(1) })); // drop synthetic root key
  const stage = stageOf(find(flat, KEYS.stage));
  const first = find(flat, ["firstname"], { customerOnly: true });
  const last = find(flat, ["lastname"], { customerOnly: true });
  return {
    stage,
    stageLabel: stage ? STAGES[stage - 1].label : "Welcome",
    verified: find(flat, KEYS.verified) === "true",
    customer: {
      name: find(flat, KEYS.name.filter((k) => k !== "firstname"), { customerOnly: true }) ?? ([first, last].filter(Boolean).join(" ") || undefined),
      phone: find(flat, KEYS.phone, { customerOnly: true }),
      email: find(flat, KEYS.email, { customerOnly: true }),
      city: find(flat, KEYS.city, { customerOnly: true }),
    },
  };
}

/** Show the date/location picker when the assistant is offering to book a test drive. */
export function offersTestDrive(text: string): boolean {
  return /test[\s-]?drive/i.test(text) && /\b(book|schedule|arrange)\b/i.test(text) && text.includes("?");
}