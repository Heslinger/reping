export type SubscriptionStatus =
  | "none"
  | "incomplete"
  | "trialing"
  | "active"
  | "past_due"
  | "canceled"
  | "unpaid";

export type User = {
  id: string;
  email: string;
  created_at: string;
  subscription_status: SubscriptionStatus;
};

export type Payload = {
  id: string;
  token: string;
  subdomain: string;
  http_url: string;
  dns_name: string;
  label: string | null;
  created_at: string;
  revoked_at: string | null;
};

export type Pingback = {
  id: string;
  payload_id: string | null;
  protocol: "http" | "dns";
  source_ip: string | null;
  method: string | null;
  host: string | null;
  path: string | null;
  query_params: Record<string, unknown>;
  headers: Record<string, string>;
  body: string | null;
  dns_record_type: string | null;
  dns_query_name: string | null;
  raw_event: Record<string, unknown>;
  created_at: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function websocketUrl(token: string): string {
  const url = new URL(API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/pingbacks";
  url.searchParams.set("token", token);
  return url.toString();
}

export async function apiFetch<T>(path: string, token?: string | null, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers
    }
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? "Request failed");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function authenticate(mode: "login" | "register", email: string, password: string): Promise<string> {
  const data = await apiFetch<{ access_token: string }>(`/auth/${mode}`, null, {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
  return data.access_token;
}

export { API_BASE };
