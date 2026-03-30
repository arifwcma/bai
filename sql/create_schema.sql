-- GH Archive normalized schema for PostgreSQL
-- Designed for the UniChat GitHub Activity Assistant
--
-- Raw GH Archive events are denormalized JSON (every event repeats
-- full actor/repo/org details). This schema normalizes into proper
-- relational tables with foreign keys, enabling efficient SQL joins
-- and aggregation queries.

-- Core entity tables (deduplicated from events)

CREATE TABLE IF NOT EXISTS actors (
    id BIGINT PRIMARY KEY,
    login VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS repos (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS orgs (
    id BIGINT PRIMARY KEY,
    login VARCHAR(255) NOT NULL,
    avatar_url TEXT
);

-- Main events table

CREATE TABLE IF NOT EXISTS events (
    id BIGINT PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    actor_id BIGINT REFERENCES actors(id),
    repo_id BIGINT REFERENCES repos(id),
    org_id BIGINT REFERENCES orgs(id),
    created_at TIMESTAMPTZ NOT NULL
);

-- Specialized event tables (extracted from JSON payload)
-- Each links back to the main events table via event_id.

CREATE TABLE IF NOT EXISTS push_events (
    event_id BIGINT PRIMARY KEY REFERENCES events(id),
    push_id BIGINT,
    size INT,
    distinct_size INT,
    ref VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS pull_request_events (
    event_id BIGINT PRIMARY KEY REFERENCES events(id),
    action VARCHAR(50),
    pr_number INT,
    pr_title TEXT,
    pr_state VARCHAR(20),
    pr_merged BOOLEAN,
    pr_additions INT,
    pr_deletions INT,
    pr_changed_files INT,
    pr_created_at TIMESTAMPTZ,
    pr_merged_at TIMESTAMPTZ,
    pr_closed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS issue_events (
    event_id BIGINT PRIMARY KEY REFERENCES events(id),
    action VARCHAR(50),
    issue_number INT,
    issue_title TEXT,
    issue_state VARCHAR(20),
    issue_labels JSONB,
    issue_created_at TIMESTAMPTZ,
    issue_closed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS issue_comment_events (
    event_id BIGINT PRIMARY KEY REFERENCES events(id),
    action VARCHAR(50),
    issue_number INT,
    comment_body TEXT,
    comment_created_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS watch_events (
    event_id BIGINT PRIMARY KEY REFERENCES events(id),
    action VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS fork_events (
    event_id BIGINT PRIMARY KEY REFERENCES events(id),
    fork_id BIGINT,
    fork_full_name VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS create_events (
    event_id BIGINT PRIMARY KEY REFERENCES events(id),
    ref_type VARCHAR(50),
    ref VARCHAR(255),
    master_branch VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS release_events (
    event_id BIGINT PRIMARY KEY REFERENCES events(id),
    action VARCHAR(50),
    tag_name VARCHAR(255),
    release_name TEXT
);

-- Indexes for common query patterns

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_actor_id ON events(actor_id);
CREATE INDEX IF NOT EXISTS idx_events_repo_id ON events(repo_id);
CREATE INDEX IF NOT EXISTS idx_repos_name ON repos(name);
CREATE INDEX IF NOT EXISTS idx_actors_login ON actors(login);
