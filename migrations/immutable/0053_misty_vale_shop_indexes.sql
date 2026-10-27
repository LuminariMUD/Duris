-- Misty Vale inserted shop 300036 at index 534 in the AREA catalogue.
-- Match the following shops by identity, never by a local database row ID.
-- Run with writers stopped: their in-memory indexes still name the old shops.
-- Stock/affect children reference shopkeepers.id, which must remain unchanged.
DROP PROCEDURE IF EXISTS duris_reindex_misty_vale_shops;
DELIMITER //
CREATE PROCEDURE duris_reindex_misty_vale_shops()
BEGIN
    DECLARE finished INT DEFAULT 0;
    DECLARE old_shop INT;
    DECLARE new_shop INT;
    DECLARE keeper_id INT;
    DECLARE moves CURSOR FOR
        SELECT s.id, s.shop_id, m.new_id
        FROM shopkeepers s JOIN misty_vale_shop_map m
          ON s.mob_vnum=m.mob_vnum AND (m.room_vnum=0 OR s.room_vnum=m.room_vnum)
        WHERE s.shop_id=m.new_id-1 ORDER BY s.shop_id DESC;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET finished=1;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        DROP TEMPORARY TABLE IF EXISTS misty_vale_shop_map;
        RESIGNAL;
    END;

    -- A transaction must cover every catalogue/custody change, including failures.
    IF (SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema=DATABASE() AND engine='InnoDB'
          AND table_name IN ('shopkeepers','item_current_owner','item_owner_revision')) <> 3 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Misty Vale shop repair requires InnoDB';
    END IF;
    CREATE TEMPORARY TABLE misty_vale_shop_map (
        new_id INT PRIMARY KEY, mob_vnum INT NOT NULL, room_vnum INT NOT NULL
    );
    -- room_vnum=0 denotes a roaming keeper: preserve its actual saved room.
    INSERT INTO misty_vale_shop_map VALUES
        (535,400004,400000), (536,402027,0), (537,402028,0),
        (538,402039,402113), (539,402047,402136), (540,402048,402137),
        (541,101,36329), (542,101,37718), (543,101,97685), (544,101,132767),
        (545,91401,91401), (546,91406,91469), (547,91414,91476),
        (548,91415,91460), (549,91419,91471), (550,91426,91457),
        (551,91456,91468), (552,91483,91505);

    START TRANSACTION;
    SELECT id FROM shopkeepers ORDER BY id FOR UPDATE;
    IF EXISTS (
        SELECT 1 FROM shopkeepers s LEFT JOIN misty_vale_shop_map m
          ON s.mob_vnum=m.mob_vnum AND (m.room_vnum=0 OR s.room_vnum=m.room_vnum)
        WHERE (m.new_id IS NOT NULL AND
               (s.shop_id NOT IN (m.new_id-1,m.new_id) OR COALESCE(s.room_vnum,0)<=0))
           OR (m.new_id IS NULL AND (s.shop_id BETWEEN 534 AND 552 OR s.mob_vnum=300036)
               AND NOT (s.shop_id=534 AND s.mob_vnum<=>300036 AND s.room_vnum<=>300056))
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Misty Vale shop catalogue conflicts; no rows repaired';
    END IF;
    IF EXISTS (
        SELECT m.new_id FROM shopkeepers s JOIN misty_vale_shop_map m
          ON s.mob_vnum=m.mob_vnum AND (m.room_vnum=0 OR s.room_vnum=m.room_vnum)
        GROUP BY m.new_id HAVING COUNT(*)>1
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Misty Vale shop identity is duplicated; no rows repaired';
    END IF;

    OPEN moves;
    move_shops: LOOP
        FETCH moves INTO keeper_id, old_shop, new_shop;
        IF finished THEN LEAVE move_shops; END IF;
        -- Descending order frees each destination before the preceding shop moves.
        -- A populated destination outside that chain is ambiguous; never merge it.
        IF EXISTS (SELECT 1 FROM shopkeepers WHERE shop_id=new_shop)
           OR EXISTS (SELECT 1 FROM item_current_owner WHERE owner_type=9 AND owner_id=new_shop+1)
           OR EXISTS (SELECT 1 FROM item_owner_revision WHERE owner_type=9 AND owner_id=new_shop+1) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Misty Vale shop destination is occupied; no rows repaired';
        END IF;
        UPDATE item_current_owner SET owner_id=new_shop+1, updated_at=updated_at
          WHERE owner_type=9 AND owner_id=old_shop+1;
        UPDATE item_owner_revision SET owner_id=new_shop+1, updated_at=updated_at
          WHERE owner_type=9 AND owner_id=old_shop+1;
        UPDATE shopkeepers SET shop_id=new_shop, updated_at=updated_at WHERE id=keeper_id;
    END LOOP;
    CLOSE moves;
    COMMIT;
    DROP TEMPORARY TABLE misty_vale_shop_map;
END//
DELIMITER ;
CALL duris_reindex_misty_vale_shops();
DROP PROCEDURE duris_reindex_misty_vale_shops;
