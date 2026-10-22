-- Additive and re-runnable. The snapshot includes version, revision and SHA-256.
-- Compare-and-swap writes prevent stale saves or retries from rerolling an hour.
CREATE TABLE IF NOT EXISTS divine_boon_state (
    state_id TINYINT UNSIGNED NOT NULL,
    revision BIGINT UNSIGNED NOT NULL,
    snapshot VARBINARY(4096) NOT NULL,
    PRIMARY KEY (state_id),
    CONSTRAINT divine_boon_singleton CHECK (state_id = 1),
    CONSTRAINT divine_boon_revision CHECK (revision > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
