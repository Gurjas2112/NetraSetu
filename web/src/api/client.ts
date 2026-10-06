import type { components } from "./schema";

export type Study = components["schemas"]["StudyResponse"];
export type Health = components["schemas"]["HealthStatus"];
export type Consent = components["schemas"]["ConsentResponse"];
export type ConsentRequest = components["schemas"]["ConsentRequest"];
export type Decision = Study["decision"];

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

// Held in memory only. The OIDC login flow (M5) calls setAccessToken; the dev server can be
// given a token for end-to-end tests, and production builds drop that branch entirely.
let accessToken: string | null = import.meta.env.DEV
  ? (import.meta.env.VITE_DEV_ACCESS_TOKEN ?? null)
  : null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

function authHeaders(): Record<string, string> {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function readError(response: Response): Promise<ApiError> {
  let detail = response.statusText;
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object") {
      if ("detail" in body && typeof body.detail === "string") detail = body.detail;
      else if ("reason" in body && typeof body.reason === "string") detail = body.reason;
    }
  } catch {
    // body was not JSON; keep the status text
  }
  return new ApiError(response.status, detail);
}

export async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function giveConsent(body: ConsentRequest): Promise<Consent> {
  const response = await fetch(`${API_BASE}/consent`, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", ...authHeaders() },
    cache: "no-store",
  });
  if (!response.ok) throw await readError(response);
  return (await response.json()) as Consent;
}

export async function analyze(file: File, patientRef: string, consentId: string): Promise<Study> {
  const form = new FormData();
  form.append("file", file);
  form.append("patientRef", patientRef);
  form.append("consentId", consentId);
  const response = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    body: form,
    headers: { "Idempotency-Key": crypto.randomUUID(), ...authHeaders() },
    cache: "no-store",
  });
  if (!response.ok) throw await readError(response);
  return (await response.json()) as Study;
}

export async function health(): Promise<Health> {
  const response = await fetch(`${API_BASE}/healthz`, { cache: "no-store" });
  if (!response.ok) throw await readError(response);
  return (await response.json()) as Health;
}
