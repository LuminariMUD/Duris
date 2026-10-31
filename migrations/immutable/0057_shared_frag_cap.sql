-- Storage only. Runtime activation validates/adopts the legacy cap and clock
-- under the singleton lock; this migration never changes current progression.
DROP PROCEDURE IF EXISTS duris_shared_frag_cap;
DELIMITER //
CREATE PROCEDURE duris_shared_frag_cap()
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='level_cap' AND column_name='snapshot') THEN
        ALTER TABLE level_cap ADD COLUMN snapshot MEDIUMBLOB NULL;
    END IF;
END//
DELIMITER ;
CALL duris_shared_frag_cap();
DROP PROCEDURE duris_shared_frag_cap;
