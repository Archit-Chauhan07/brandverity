-- BrandVerity schema (PostgreSQL DDL, mirrors the SQLAlchemy models).
-- Demo default is SQLite; set DATABASE_URL to a postgresql:// URL to use this.
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL UNIQUE,
    password_hash VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id)
);
CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);

CREATE TABLE IF NOT EXISTS rules (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    rule_code VARCHAR NOT NULL,
    version VARCHAR NOT NULL DEFAULT 'v1',
    category VARCHAR NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_rules_rule_code ON rules (rule_code);

CREATE TABLE IF NOT EXISTS drafts (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    creator_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    content_type VARCHAR NOT NULL DEFAULT 'text',
    meta JSONB,
    status VARCHAR NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS findings (
    id SERIAL PRIMARY KEY,
    draft_id INTEGER NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
    rule_code VARCHAR NOT NULL,
    rule_version VARCHAR NOT NULL DEFAULT 'v1',
    quoted_span TEXT NOT NULL DEFAULT '',
    why TEXT NOT NULL DEFAULT '',
    suggested_edit TEXT NOT NULL DEFAULT '',
    status VARCHAR NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS approvals (
    id SERIAL PRIMARY KEY,
    draft_id INTEGER NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
    from_status VARCHAR NOT NULL,
    to_status VARCHAR NOT NULL,
    actor_id INTEGER NOT NULL REFERENCES users(id),
    comment TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    draft_id INTEGER NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES users(id),
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    actor_id INTEGER REFERENCES users(id),
    action VARCHAR NOT NULL,
    entity VARCHAR NOT NULL,
    entity_id INTEGER,
    detail TEXT DEFAULT ''
);
