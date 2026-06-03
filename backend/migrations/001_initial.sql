CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE subscription_provider AS ENUM ('stripe', 'paypal');
CREATE TYPE subscription_status AS ENUM ('none', 'incomplete', 'trialing', 'active', 'past_due', 'canceled', 'unpaid');
CREATE TYPE pingback_protocol AS ENUM ('http', 'dns');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider subscription_provider NOT NULL,
    provider_customer_id TEXT,
    provider_subscription_id TEXT,
    status subscription_status NOT NULL DEFAULT 'incomplete',
    price_usd NUMERIC(6, 2) NOT NULL,
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_subscription_provider_subscription UNIQUE (provider, provider_subscription_id)
);

CREATE TABLE payloads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(64) NOT NULL,
    subdomain VARCHAR(255) NOT NULL,
    http_url TEXT NOT NULL,
    dns_name VARCHAR(255) NOT NULL,
    label VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    CONSTRAINT uq_payloads_token UNIQUE (token)
);

CREATE TABLE pingbacks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payload_id UUID REFERENCES payloads(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    protocol pingback_protocol NOT NULL,
    source_ip INET,
    method VARCHAR(16),
    host VARCHAR(255),
    path TEXT,
    query_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    body TEXT,
    dns_record_type VARCHAR(16),
    dns_query_name VARCHAR(255),
    raw_event JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_subscriptions_user_status ON subscriptions(user_id, status);
CREATE INDEX ix_payloads_user_created ON payloads(user_id, created_at DESC);
CREATE INDEX ix_pingbacks_user_created ON pingbacks(user_id, created_at DESC);
CREATE INDEX ix_pingbacks_payload_created ON pingbacks(payload_id, created_at DESC);

GRANT ALL ON ALL TABLES IN SCHEMA public TO reping;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO reping;
GRANT USAGE ON SCHEMA public TO reping;
