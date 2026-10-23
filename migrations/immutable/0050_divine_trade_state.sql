-- Exact account/boon manifests and the market writer generation. Gameplay
-- prepares the values in memory; this stores its atomic commit/replay boundary.
CREATE TABLE IF NOT EXISTS divine_trade_state (
    account_key BIGINT UNSIGNED NOT NULL,
    boon_id BIGINT UNSIGNED NOT NULL,
    revision BIGINT UNSIGNED NOT NULL,
    snapshot MEDIUMBLOB NOT NULL,
    PRIMARY KEY (account_key, boon_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
-- Never reset an existing generation or a player's spent allowance on replay.
INSERT IGNORE INTO divine_trade_state(account_key,boon_id,revision,snapshot)
VALUES(0,0,0,'');
