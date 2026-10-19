-- Restore only Marduk and Enlil. Validate both before any catalogue write;
-- retrying a partial apply must preserve existing alignment and touch timestamps.
DROP PROCEDURE IF EXISTS duris_seed_nexus_phase1;
DELIMITER //
CREATE PROCEDURE duris_seed_nexus_phase1()
BEGIN
    DECLARE conflict_message VARCHAR(128) DEFAULT NULL;
    SELECT CONCAT('Nexus stone ', n.id, ' conflicts in ',
        CASE
            WHEN BINARY n.name <> BINARY expected.name THEN 'name'
            WHEN n.room_vnum <> expected.room_vnum THEN 'room_vnum'
            WHEN n.stat_affect <> 0 THEN 'stat_affect'
            WHEN n.affect_amount <> 0 THEN 'affect_amount'
            WHEN n.bonus <> expected.bonus THEN 'bonus'
            ELSE 'align'
        END)
    INTO conflict_message
    FROM nexus_stones n
    JOIN (SELECT 1 AS id, 'Marduk' AS name, 130199 AS room_vnum, 1 AS bonus
          UNION ALL SELECT 3, 'Enlil', 130399, 3) expected ON n.id=expected.id
    WHERE BINARY n.name <> BINARY expected.name OR n.room_vnum <> expected.room_vnum
       OR n.stat_affect <> 0 OR n.affect_amount <> 0 OR n.bonus <> expected.bonus
       OR n.align NOT BETWEEN -3 AND 3
    ORDER BY n.id LIMIT 1;
    IF conflict_message IS NOT NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT=conflict_message;
    END IF;

    SELECT CONCAT('Nexus stone name ', name, ' belongs to conflicting ID ', id)
    INTO conflict_message FROM nexus_stones
    WHERE (name='Marduk' AND id<>1) OR (name='Enlil' AND id<>3)
    ORDER BY id LIMIT 1;
    IF conflict_message IS NOT NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT=conflict_message;
    END IF;

    INSERT INTO nexus_stones
        (id,name,room_vnum,align,stat_affect,affect_amount,bonus,last_touched_at)
    SELECT 1,'Marduk',130199,0,0,0,1,NULL
    WHERE NOT EXISTS (SELECT 1 FROM nexus_stones WHERE id=1);
    INSERT INTO nexus_stones
        (id,name,room_vnum,align,stat_affect,affect_amount,bonus,last_touched_at)
    SELECT 3,'Enlil',130399,0,0,0,3,NULL
    WHERE NOT EXISTS (SELECT 1 FROM nexus_stones WHERE id=3);
END//
DELIMITER ;
CALL duris_seed_nexus_phase1();
DROP PROCEDURE duris_seed_nexus_phase1;
