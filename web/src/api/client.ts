import type { components } from "./schema";

export type Study = components["schemas"]["StudyResponse"];
export type Health = components["schemas"]["HealthStatus"];
export type Decision = Study["decision"];

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

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
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      detail = body.detail;
    }
  } catch {
    // body was not JSON; keep the status text
  }
  return new ApiError(response.status, detail);
}

export async function analyze(file: File, patientRef: string, consentId: string): Promise<Study> {
  const form = new FormData();
  form.append("file", file);
  form.append("patientRef", patientRef);
  form.append("consentId", consentId);
  const response = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    body: form,
    headers: { "Idempotency-Key": crypto.randomUUID() },
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

export function artifactUrl(path: string | null | undefined): string | null {
  return path ? `${API_BASE}${path}` : null;
}
