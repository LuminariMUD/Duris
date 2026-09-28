-- One row each time a save takes an item from another owner. Memory is the
-- authority for where an item is: a save writes what its owner holds and makes
-- item_current_owner agree, and this audit is how staff follow an item's owners.
-- The table is additive, has no foreign keys so it can never refuse a save, and
-- CREATE IF NOT EXISTS is rerunnable.
CREATE TABLE IF NOT EXISTS item_owner_audit (
  audit_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  item_uid BIGINT UNSIGNED NOT NULL,
  vnum INT NOT NULL,
  old_owner_type TINYINT UNSIGNED NOT NULL,
  old_owner_id BIGINT UNSIGNED NOT NULL,
  old_owner_context_id BIGINT UNSIGNED NOT NULL,
  new_owner_type TINYINT UNSIGNED NOT NULL,
  new_owner_id BIGINT UNSIGNED NOT NULL,
  new_owner_context_id BIGINT UNSIGNED NOT NULL,
  claimed_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (audit_id),
  KEY idx_item_owner_audit_item (item_uid,audit_id),
  KEY idx_item_owner_audit_claimed (claimed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
