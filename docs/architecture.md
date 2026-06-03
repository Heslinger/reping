# Reping OOB Testing SaaS Architecture

## 1. Database schema

Reping stores identity, subscription state, generated payloads, and captured interactions in PostgreSQL. The schema is provider-agnostic for billing and protocol-agnostic for pingbacks.

```sql
CREATE TYPE subscription_provider AS ENUM ('stripe', 'paypal');
CREATE TYPE subscription_status AS ENUM ('none', 'incomplete', 'trialing', 'active', 'past_due', 'canceled', 'unpaid');
CREATE TYPE pingback_protocol AS ENUM ('http', 'dns');

CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR(320) UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE subscriptions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider subscription_provider NOT NULL,
  provider_customer_id TEXT,
  provider_subscription_id TEXT,
  status subscription_status NOT NULL,
  price_usd NUMERIC(6, 2) NOT NULL,
  current_period_end TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE payloads (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token VARCHAR(64) UNIQUE NOT NULL,
  subdomain VARCHAR(255) NOT NULL,
  http_url TEXT NOT NULL,
  dns_name VARCHAR(255) NOT NULL,
  label VARCHAR(120),
  created_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ
);

CREATE TABLE pingbacks (
  id UUID PRIMARY KEY,
  payload_id UUID REFERENCES payloads(id) ON DELETE SET NULL,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  protocol pingback_protocol NOT NULL,
  source_ip INET,
  method VARCHAR(16),
  host VARCHAR(255),
  path TEXT,
  query_params JSONB NOT NULL,
  headers JSONB NOT NULL,
  body TEXT,
  dns_record_type VARCHAR(16),
  dns_query_name VARCHAR(255),
  raw_event JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
```

The executable schema is in `backend/migrations/001_initial.sql`; SQLAlchemy models live in `backend/app/db/models.py`.

## 2. Backend API and listener structure

FastAPI runs the public API, WebSocket endpoint, HTTP capture endpoint, retention worker, and custom DNS UDP listener.

| Component | File | Purpose |
| --- | --- | --- |
| Auth API | `backend/app/api/auth.py` | Register/login users, issue JWTs, return account state. |
| Payload API | `backend/app/api/payloads.py` | Create/list/revoke randomized payloads for subscribed users. |
| Pingback API | `backend/app/api/pingbacks.py` | List captured interactions and expose public `/p/{token}` capture URLs. |
| WebSocket API | `backend/app/api/websocket.py` | Stream user-scoped pingbacks from Redis pub/sub to the dashboard. |
| DNS listener | `backend/app/listeners/dns.py` | Receive DNS queries, log source IP/query name/record type, and answer A queries. |
| Retention worker | `backend/app/services/cleanup.py` | Purge `pingbacks` older than `RETENTION_DAYS` every hour. |
| Pingback ingestion | `backend/app/services/pingbacks.py` | Normalize HTTP and DNS events, store them, and publish live updates. |

Payloads are generated as:

- HTTP: `https://pingback.yourdomain.com/p/<random-token>`
- DNS: `<random-token>.pingback.yourdomain.com`

The HTTP listener logs source IP, full headers, body, query parameters, host, method, path, and timestamp. The DNS listener logs source IP, query name, record type, source port, and timestamp.

## 3. Stripe subscription logic

Stripe integration is in `backend/app/payments/stripe.py`.

1. The frontend calls `POST /api/billing/stripe/checkout`.
2. The backend creates a Stripe Checkout session in `subscription` mode using `STRIPE_PRICE_ID`.
3. The single tier is capped in app configuration with `SUBSCRIPTION_PRICE_USD=4.99`; the Stripe Price should be configured to match `$4.99/month`.
4. Stripe redirects users to the frontend success/cancel URLs.
5. Stripe webhooks hit `POST /api/billing/webhooks/stripe`.
6. Webhook signatures are verified with `STRIPE_WEBHOOK_SECRET`.
7. `checkout.session.completed` and subscription lifecycle events update the normalized `subscriptions.status` value.
8. `POST /api/billing/stripe/portal` creates a Stripe customer portal session for subscription management and cancellation.

Recommended Stripe events:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`

## 4. PayPal subscription logic

PayPal integration is in `backend/app/payments/paypal.py`.

1. Create a PayPal monthly plan priced at `$4.99`.
2. Set `PAYPAL_PLAN_ID`, client credentials, and webhook ID.
3. The frontend calls `POST /api/billing/paypal/subscription`.
4. The backend creates a PayPal subscription with `custom_id` set to the Reping user ID.
5. The frontend redirects to PayPal's approval URL.
6. PayPal webhooks hit `POST /api/billing/webhooks/paypal`.
7. Webhook signatures are verified through PayPal's `verify-webhook-signature` API when `PAYPAL_WEBHOOK_ID` is set.
8. PayPal statuses are normalized into the same `subscriptions.status` enum used by Stripe.

## 5. Frontend dashboard layout

The React dashboard in `frontend/src/main.tsx` has four main sections:

1. **Authentication hero**: registration/login for researchers.
2. **Subscription card**: shows account status and starts Stripe Checkout, PayPal approval, or Stripe portal flows.
3. **Payload generator**: creates randomized HTTP and DNS payloads for subscribed users.
4. **Payload and pingback panes**: shows generated payloads, live interactions, and a detail panel with headers, body, query params, and raw DNS/HTTP metadata.

The frontend opens a WebSocket at `/ws/pingbacks?token=<jwt>` and prepends new interactions to the list as they arrive.

## 6. Domain and DNS setup

For a production deployment, use a dedicated subdomain such as `pingback.yourdomain.com`.

### Option A: Delegate a subdomain to the Reping VPS

At the parent DNS zone (`yourdomain.com`), create NS records:

```text
pingback.yourdomain.com.  NS  ns1.pingback.yourdomain.com.
ns1.pingback.yourdomain.com. A   <VPS_PUBLIC_IP>
```

Forward UDP port 53 to the backend container. With the included Compose file, host port `53/udp` maps to backend port `5353/udp`.

### Option B: Wildcard HTTP with external authoritative DNS

If you only need HTTP OOB payloads through your normal DNS provider, create:

```text
*.pingback.yourdomain.com. A <VPS_PUBLIC_IP>
pingback.yourdomain.com.   A <VPS_PUBLIC_IP>
```

This sends wildcard HTTP hostnames to the FastAPI capture endpoint, but DNS lookups themselves will not be visible to Reping unless the subdomain is delegated to the custom DNS listener.

### Reverse proxy notes

Terminate TLS with Caddy, nginx, Traefik, or a cloud load balancer:

- `app.yourdomain.com` -> frontend service port `5173`
- `pingback.yourdomain.com` and `*.pingback.yourdomain.com` -> backend port `8000`
- UDP `53` for `pingback.yourdomain.com` delegation -> backend DNS listener

Preserve the original `Host` header so token extraction from wildcard subdomains works.
