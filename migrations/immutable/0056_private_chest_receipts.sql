-- Additive receipts: metadata is the purchase receipt while its completion is pending.
-- Nullable columns preserve every existing chest and audit row. Re-runnable on both engines.
DROP PROCEDURE IF EXISTS duris_private_chest_receipts;
DELIMITER //
CREATE PROCEDURE duris_private_chest_receipts()
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='private_chests' AND column_name='purchase_operation') THEN
        ALTER TABLE private_chests ADD COLUMN purchase_operation BINARY(16) NULL,
            ADD UNIQUE KEY uq_private_chest_purchase (purchase_operation);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='private_chest_log' AND column_name='event_id') THEN
        ALTER TABLE private_chest_log ADD COLUMN event_id BINARY(16) NULL,
            ADD UNIQUE KEY uq_private_chest_event (event_id);
    END IF;
END//
DELIMITER ;
CALL duris_private_chest_receipts();
DROP PROCEDURE duris_private_chest_receipts;
