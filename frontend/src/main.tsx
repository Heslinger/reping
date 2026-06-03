import { Activity, CreditCard, KeyRound, Radio, ShieldAlert, Trash2 } from "lucide-react";
import React, { FormEvent, useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";

import {
  Payload,
  Pingback,
  User,
  apiFetch,
  authenticate,
  websocketUrl
} from "./lib/api";
import "./styles.css";

const storedToken = localStorage.getItem("reping_token");

function App() {
  const [token, setToken] = useState<string | null>(storedToken);
  const [user, setUser] = useState<User | null>(null);
  const [payloads, setPayloads] = useState<Payload[]>([]);
  const [pingbacks, setPingbacks] = useState<Pingback[]>([]);
  const [selected, setSelected] = useState<Pingback | null>(null);
  const [label, setLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const subscribed = user?.subscription_status === "active" || user?.subscription_status === "trialing";

  useEffect(() => {
    if (!token) return;
    void refreshData(token);
  }, [token]);

  useEffect(() => {
    if (!token || !subscribed) return;
    const socket = new WebSocket(websocketUrl(token));
    socket.onmessage = (event) => {
      const pingback = JSON.parse(event.data) as Pingback;
      setPingbacks((current) => [pingback, ...current.filter((item) => item.id !== pingback.id)]);
      setSelected(pingback);
    };
    return () => socket.close();
  }, [token, subscribed]);

  async function refreshData(authToken = token) {
    if (!authToken) return;
    setError(null);
    try {
      const me = await apiFetch<User>("/auth/me", authToken);
      setUser(me);
      if (me.subscription_status === "active" || me.subscription_status === "trialing") {
        const [payloadData, pingbackData] = await Promise.all([
          apiFetch<Payload[]>("/payloads", authToken),
          apiFetch<Pingback[]>("/pingbacks", authToken)
        ]);
        setPayloads(payloadData);
        setPingbacks(pingbackData);
        setSelected(pingbackData[0] ?? null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard");
    }
  }

  async function createPayload() {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await apiFetch<Payload>("/payloads", token, {
        method: "POST",
        body: JSON.stringify({ label: label || null })
      });
      setPayloads((current) => [payload, ...current]);
      setLabel("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create payload");
    } finally {
      setLoading(false);
    }
  }

  async function revokePayload(payload: Payload) {
    if (!token) return;
    await apiFetch<void>(`/payloads/${payload.id}`, token, { method: "DELETE" });
    setPayloads((current) =>
      current.map((item) => (item.id === payload.id ? { ...item, revoked_at: new Date().toISOString() } : item))
    );
  }

  async function startStripeCheckout() {
    if (!token) return;
    const response = await apiFetch<{ checkout_url: string }>("/billing/stripe/checkout", token, { method: "POST" });
    window.location.href = response.checkout_url;
  }

  async function startPayPalCheckout() {
    if (!token) return;
    const response = await apiFetch<{ approval_url: string }>("/billing/paypal/subscription", token, { method: "POST" });
    window.location.href = response.approval_url;
  }

  async function openStripePortal() {
    if (!token) return;
    const response = await apiFetch<{ portal_url: string }>("/billing/stripe/portal", token, { method: "POST" });
    window.location.href = response.portal_url;
  }

  function logout() {
    localStorage.removeItem("reping_token");
    setToken(null);
    setUser(null);
    setPayloads([]);
    setPingbacks([]);
    setSelected(null);
  }

  if (!token) {
    return <AuthScreen onToken={(nextToken) => {
      localStorage.setItem("reping_token", nextToken);
      setToken(nextToken);
    }} />;
  }

  return (
    <main className="app">
      <header className="header">
        <div>
          <div className="pill"><Radio size={14} />&nbsp; Reping OOB testing</div>
          <h1>Interaction dashboard</h1>
          <p className="muted">Detect SSRF, blind XSS, blind RCE, and asynchronous callbacks in real time.</p>
        </div>
        <div className="row">
          <span className="pill">{user?.email ?? "Loading..."}</span>
          <button className="secondary" onClick={logout}>Sign out</button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="grid">
        <div className="card span-4">
          <h2><CreditCard size={20} /> Subscription</h2>
          <p className="muted">Single researcher tier capped at $4.99/month.</p>
          <p>Status: <strong>{user?.subscription_status ?? "loading"}</strong></p>
          <div className="row">
            <button onClick={startStripeCheckout}>Stripe Checkout</button>
            <button className="secondary" onClick={startPayPalCheckout}>PayPal</button>
            <button className="secondary" onClick={openStripePortal}>Customer Portal</button>
          </div>
        </div>

        <div className="card span-8">
          <h2><KeyRound size={20} /> Generate payload</h2>
          <p className="muted">Create randomized HTTP and DNS payloads mapped to your account.</p>
          <div className="row">
            <input
              placeholder="Optional label, e.g. target-app SSRF"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              disabled={!subscribed}
            />
            <button onClick={createPayload} disabled={!subscribed || loading}>
              {loading ? "Creating..." : "Create payload"}
            </button>
          </div>
          {!subscribed && <p className="error">Activate the $4.99/month plan to generate payloads.</p>}
        </div>

        <div className="card span-5">
          <h2>Payloads</h2>
          <div className="list">
            {payloads.map((payload) => (
              <article className="item" key={payload.id}>
                <div className="item-title">
                  <strong>{payload.label || payload.token}</strong>
                  <button className="secondary" onClick={() => void revokePayload(payload)} title="Revoke">
                    <Trash2 size={16} />
                  </button>
                </div>
                <div className="code">{payload.http_url}</div>
                <div className="code">{payload.dns_name}</div>
                {payload.revoked_at && <p className="muted">Revoked</p>}
              </article>
            ))}
            {payloads.length === 0 && <p className="muted">No payloads yet.</p>}
          </div>
        </div>

        <div className="card span-7">
          <h2><Activity size={20} /> Live pingbacks</h2>
          <div className="list">
            {pingbacks.map((pingback) => (
              <article
                className={`item ${selected?.id === pingback.id ? "active" : ""}`}
                key={pingback.id}
                onClick={() => setSelected(pingback)}
              >
                <div className="item-title">
                  <strong>{pingback.protocol.toUpperCase()} {pingback.method ?? pingback.dns_record_type}</strong>
                  <span className="muted">{new Date(pingback.created_at).toLocaleString()}</span>
                </div>
                <p className="muted">{pingback.source_ip ?? "unknown source"} - {pingback.host ?? pingback.dns_query_name}</p>
              </article>
            ))}
            {pingbacks.length === 0 && <p className="muted">Waiting for interactions...</p>}
          </div>
        </div>

        <PingbackDetail pingback={selected} />
      </section>
    </main>
  );
}

function AuthScreen({ onToken }: { onToken: (token: string) => void }) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      onToken(await authenticate(mode, email, password));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    }
  }

  return (
    <main className="app">
      <section className="hero">
        <div>
          <div className="pill"><ShieldAlert size={14} />&nbsp; Built for security researchers</div>
          <h1>Out-of-band vulnerability evidence.</h1>
          <p className="muted">
            Generate unique subdomains and HTTP endpoints, capture blind callbacks, and stream proof to your dashboard.
          </p>
        </div>
        <form className="card stack" onSubmit={submit}>
          <h2>{mode === "register" ? "Create account" : "Sign in"}</h2>
          <input placeholder="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          <input
            placeholder="Password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {error && <p className="error">{error}</p>}
          <button type="submit">{mode === "register" ? "Register" : "Login"}</button>
          <button
            className="secondary"
            type="button"
            onClick={() => setMode(mode === "register" ? "login" : "register")}
          >
            Switch to {mode === "register" ? "login" : "register"}
          </button>
        </form>
      </section>
    </main>
  );
}

function PingbackDetail({ pingback }: { pingback: Pingback | null }) {
  const detail = useMemo(() => {
    if (!pingback) return null;
    return JSON.stringify(
      {
        query_params: pingback.query_params,
        headers: pingback.headers,
        body: pingback.body,
        raw_event: pingback.raw_event
      },
      null,
      2
    );
  }, [pingback]);

  return (
    <div className="card span-12">
      <h2>Request detail</h2>
      {pingback ? (
        <div className="stack">
          <div className="row">
            <span className="pill">{pingback.protocol}</span>
            <span>{pingback.path ?? pingback.dns_query_name}</span>
          </div>
          <pre className="code detail">{detail}</pre>
        </div>
      ) : (
        <p className="muted">Select a pingback to inspect headers, body, DNS metadata, and query parameters.</p>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
