-- The zone-story document no longer fits one statement as the shared history grows:
-- a single row stops at max_allowed_packet. The document's first part stays in
-- zone_story_quest_state and the rest are stored here in order, so a state saved before
-- this migration is already a complete one-part document.

CREATE TABLE IF NOT EXISTS zone_story_quest_state_part (
    part_index INT UNSIGNED NOT NULL,
    part_blob MEDIUMTEXT NOT NULL,
    PRIMARY KEY (part_index),
    CONSTRAINT chk_zone_story_quest_state_part_index CHECK (part_index > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
