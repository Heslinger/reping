# Reping

Reping is an out-of-band (OOB) testing SaaS platform for security researchers, penetration testers, and bug bounty hunters. It generates unique HTTP and DNS payloads, captures asynchronous callbacks, and streams pingbacks to a real-time dashboard.

Inspired by tools such as pingback.sh and Interactsh, this scaffold includes:

- FastAPI backend with JWT auth, randomized payload generation, HTTP capture, WebSocket streaming, and retention cleanup.
- Custom Python DNS UDP listener for DNS interaction logging.
- PostgreSQL schema for users, provider-agnostic subscriptions, payloads, and pingbacks.
- Redis pub/sub for rapid WebSocket brokering.
- Stripe Checkout, Stripe customer portal, Stripe webhooks, PayPal subscriptions, and PayPal webhooks.
- React/Vite dashboard for subscription management, payload generation, and live pingback inspection.
- Docker Compose deployment for a Linux VPS.

## Project layout

```text
backend/                  FastAPI app, DNS listener, payment adapters
backend/migrations/       Initial PostgreSQL schema
frontend/                 React dashboard
docs/architecture.md      Schema, API, payment, dashboard, DNS setup details
docker-compose.yml        Postgres, Redis, backend, frontend
.env.example              Production configuration template
```

## Quickstart

```bash
cp .env.example .env
docker compose up --build
```

Local services:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000>
- HTTP payload capture: <http://localhost:8000/p/example-token>
- DNS listener: UDP `localhost:53` mapped to backend UDP `5353`

For full implementation notes, start with [docs/architecture.md](docs/architecture.md). It is organized in the requested order: database schema, backend/listener API structure, Stripe logic, PayPal logic, frontend dashboard, and deployment DNS records.

## Production checklist

1. Configure a strong `JWT_SECRET` and production PostgreSQL/Redis credentials.
2. Create a Stripe monthly price for `$4.99` and set `STRIPE_PRICE_ID`.
3. Create a PayPal monthly plan for `$4.99` and set `PAYPAL_PLAN_ID`.
4. Register Stripe and PayPal webhook endpoints:
   - `https://pingback.yourdomain.com/api/billing/webhooks/stripe`
   - `https://pingback.yourdomain.com/api/billing/webhooks/paypal`
5. Delegate `pingback.yourdomain.com` to the VPS if DNS interaction logging is required.
6. Configure wildcard HTTP routing for `*.pingback.yourdomain.com`.
7. Put TLS termination/reverse proxying in front of the backend and frontend.
