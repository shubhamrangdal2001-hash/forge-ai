-- Forge relational schema (PostgreSQL)

CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    name          TEXT,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id      UUID REFERENCES users(id),
    name          TEXT NOT NULL,
    repo_url      TEXT,
    default_branch TEXT DEFAULT 'main',
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS code_files (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID REFERENCES projects(id) ON DELETE CASCADE,
    path          TEXT NOT NULL,
    language      TEXT,
    last_indexed  TIMESTAMPTZ,
    UNIQUE(project_id, path)
);

CREATE TABLE IF NOT EXISTS code_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id       UUID REFERENCES code_files(id) ON DELETE CASCADE,
    symbol        TEXT,
    kind          TEXT,                 -- function|class|method|module
    start_line    INT,
    end_line      INT,
    vector_id     TEXT                   -- Qdrant point id
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID REFERENCES projects(id) ON DELETE CASCADE,
    goal          TEXT NOT NULL,
    status        TEXT DEFAULT 'planning',  -- planning|running|verified|halted|failed
    token_budget  INT DEFAULT 200000,
    tokens_used   INT DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_steps (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID REFERENCES agent_runs(id) ON DELETE CASCADE,
    agent_role    TEXT,                  -- planner|coder|tester|debugger|critic
    model         TEXT,
    phase         TEXT,                  -- plan|patch|test|verify|explain|rollback
    checkpoint_id TEXT,
    detail        JSONB,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS diffs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID REFERENCES agent_runs(id) ON DELETE CASCADE,
    file_path     TEXT NOT NULL,
    patch         TEXT NOT NULL,
    accepted      BOOLEAN,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verifications (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID REFERENCES agent_runs(id) ON DELETE CASCADE,
    kind          TEXT,                  -- ruff|mypy|eslint|pytest|jest|build|runtime
    passed        BOOLEAN,
    output        TEXT,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID REFERENCES projects(id) ON DELETE CASCADE,
    actor         TEXT,                  -- user id or agent role
    action        TEXT,
    payload       JSONB,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hardware_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID REFERENCES users(id),
    hostname        TEXT,
    os              TEXT,
    ram_gb          NUMERIC,
    gpu_name        TEXT,
    gpu_vram_gb     NUMERIC,
    compatibility_tier INT,
    detected_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS local_model_catalog (
    id              TEXT PRIMARY KEY,
    family          TEXT NOT NULL,
    name            TEXT NOT NULL,
    parameter_size  TEXT,
    best_use_case   TEXT,
    min_ram_gb      NUMERIC,
    recommended_ram_gb NUMERIC,
    min_vram_gb     NUMERIC,
    recommended_vram_gb NUMERIC,
    cpu_only        BOOLEAN,
    coding_score    TEXT,
    debugging_score TEXT,
    repo_reasoning_score TEXT,
    quantization    TEXT,
    ollama_command  TEXT,
    lm_studio_support TEXT,
    vllm_support    TEXT,
    product_role    TEXT
);

CREATE TABLE IF NOT EXISTS local_model_installs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID REFERENCES users(id),
    model_id        TEXT REFERENCES local_model_catalog(id),
    runtime         TEXT NOT NULL, -- ollama|lmstudio|vllm
    quantization    TEXT,
    path            TEXT,
    status          TEXT DEFAULT 'detected', -- detected|downloading|ready|failed|removed
    installed_at    TIMESTAMPTZ DEFAULT now(),
    last_seen_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_provider_settings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID REFERENCES users(id),
    provider_id     TEXT NOT NULL,
    enabled         BOOLEAN DEFAULT false,
    connection_status TEXT DEFAULT 'not_configured',
    default_model_id TEXT,
    provider_priority JSONB DEFAULT '["local","nvidia","secondary_cloud","user_fallback"]'::jsonb,
    streaming_enabled BOOLEAN DEFAULT true,
    context_limit   INT,
    require_file_upload_approval BOOLEAN DEFAULT true,
    excluded_folders JSONB DEFAULT '[".git","node_modules",".env","secrets","credentials"]'::jsonb,
    credential_reference TEXT,
    last_validated_at TIMESTAMPTZ,
    last_error      TEXT,
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(owner_id, provider_id)
);

CREATE TABLE IF NOT EXISTS ai_model_catalog (
    id              TEXT PRIMARY KEY,
    provider_id     TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    model_provider  TEXT,
    parameter_size  TEXT,
    context_window  INT,
    max_output_tokens INT,
    capabilities    JSONB DEFAULT '[]'::jsonb,
    supported_languages JSONB DEFAULT '[]'::jsonb,
    coding_capability TEXT,
    reasoning_capability TEXT,
    vision_support  BOOLEAN DEFAULT false,
    embedding_support BOOLEAN DEFAULT false,
    chat_capability BOOLEAN DEFAULT true,
    function_calling_support BOOLEAN DEFAULT false,
    structured_output_support BOOLEAN DEFAULT false,
    recommended_use_cases JSONB DEFAULT '[]'::jsonb,
    relative_latency TEXT,
    relative_quality TEXT,
    relative_cost   TEXT,
    availability_status TEXT,
    rate_limits     JSONB DEFAULT '{}'::jsonb,
    raw_metadata    JSONB DEFAULT '{}'::jsonb,
    discovered_at   TIMESTAMPTZ DEFAULT now(),
    refreshed_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_model_favorites (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID REFERENCES users(id),
    provider_model_id TEXT REFERENCES ai_model_catalog(id) ON DELETE CASCADE,
    is_default      BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(owner_id, provider_model_id)
);

CREATE TABLE IF NOT EXISTS ai_provider_request_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID REFERENCES users(id),
    provider_id     TEXT NOT NULL,
    model_id        TEXT,
    request_kind    TEXT,
    prompt_tokens   INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    total_tokens    INT DEFAULT 0,
    status          TEXT DEFAULT 'completed',
    error_code      TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_benchmarks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        TEXT REFERENCES local_model_catalog(id),
    hardware_profile_id UUID REFERENCES hardware_profiles(id),
    runtime         TEXT,
    quantization    TEXT,
    tokens_per_second NUMERIC,
    first_token_ms  NUMERIC,
    memory_gb       NUMERIC,
    context_tokens  INT,
    prompt_hash     TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS provider_model_benchmarks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_model_id TEXT REFERENCES ai_model_catalog(id) ON DELETE CASCADE,
    owner_id        UUID REFERENCES users(id),
    latency_ms      NUMERIC,
    first_token_ms  NUMERIC,
    tokens_per_second NUMERIC,
    prompt_tokens   INT,
    completion_tokens INT,
    status          TEXT DEFAULT 'completed',
    error_detail    TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_router_decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID REFERENCES agent_runs(id) ON DELETE CASCADE,
    task_complexity TEXT,
    mode            TEXT,
    privacy         TEXT,
    selected_model  TEXT,
    fallback_chain  JSONB,
    reason          TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_safety_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID REFERENCES users(id),
    model_id        TEXT,
    event_type      TEXT, -- ram_warning|vram_warning|load_failed|fallback
    detail          JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS selected_workspaces (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      TEXT UNIQUE NOT NULL,
    root_path       TEXT NOT NULL,
    warnings        JSONB DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staged_diffs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'staged',
    risk_level      TEXT NOT NULL DEFAULT 'low',
    risk_reasons    JSONB DEFAULT '[]'::jsonb,
    created_by      TEXT DEFAULT 'agent',
    created_at      TIMESTAMPTZ DEFAULT now(),
    decided_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS staged_diff_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    diff_id         UUID REFERENCES staged_diffs(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,
    patch           TEXT NOT NULL,
    approved        BOOLEAN DEFAULT false,
    applied         BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS file_backups (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    diff_id         UUID REFERENCES staged_diffs(id) ON DELETE SET NULL,
    project_id      TEXT NOT NULL,
    original_path   TEXT NOT NULL,
    backup_path     TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_action_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          TEXT,
    project_id      TEXT,
    action_type     TEXT NOT NULL,
    actor           TEXT NOT NULL DEFAULT 'agent',
    details         JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_steps_run ON agent_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_diffs_run ON diffs(run_id);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON code_chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_model_benchmarks_model ON model_benchmarks(model_id);
CREATE INDEX IF NOT EXISTS idx_ai_model_catalog_provider ON ai_model_catalog(provider_id, availability_status);
CREATE INDEX IF NOT EXISTS idx_ai_request_history_provider_created ON ai_provider_request_history(provider_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_provider_model_benchmarks_model ON provider_model_benchmarks(provider_model_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_router_decisions_run ON model_router_decisions(run_id);
CREATE INDEX IF NOT EXISTS idx_staged_diffs_project_created ON staged_diffs(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_action_log_run ON agent_action_log(run_id, created_at DESC);
