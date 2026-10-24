# Grumbar hammer artifact rollout

Object 131200 becomes an unsellable artifact for new creation. The owner chose to
preserve existing ordinary copies with their saved flags. Do not flip flags or
delete player items during rollout. Ordinary copies still count against the zone
limit and can prevent a new hammer from loading.

The standard artifact rule applies: with `artifact.respawn=1`, Grumbar can receive
the hammer only during a full boot, subject to artifact admission and the zone
limit. Zone repops and copyover do not create another one. Incomplete population
evidence can prevent creation for that uptime.

Before deployment, run these **read-only** queries on the target database and
retain the counts with the deployment record:

```sql
SELECT 'player_items', COUNT(*) FROM player_items WHERE vnum=131200
UNION ALL SELECT 'player_pet_items', COUNT(*) FROM player_pet_items WHERE vnum=131200
UNION ALL SELECT 'locker_items', COUNT(*) FROM locker_items WHERE vnum=131200
UNION ALL SELECT 'account_locker_items', COUNT(*) FROM account_locker_items WHERE vnum=131200
UNION ALL SELECT 'corpse_items', COUNT(*) FROM corpse_items WHERE vnum=131200
UNION ALL SELECT 'saved_items', COUNT(*) FROM saved_items WHERE vnum=131200;
SELECT COUNT(*) FROM auction_item_custody WHERE vnum=131200 AND claimed_at IS NULL;
SELECT COUNT(*) FROM auctions WHERE obj_vnum=131200 AND status=1;
-- Legacy frames use native little-endian int vnum at byte offset 6 on x86-64.
SELECT COUNT(*) FROM auction_item_pickups
 WHERE retrieved=0 AND HEX(SUBSTRING(obj_blob_str,7,4))='80000200';
```

On flat-file installations, inspect the corresponding auction custody/pickup
records and saved owners. Do not assume an SQL audit covers flat-file state.

Old auction blobs can inherit today's prototype flags. Both claim completion
paths now withhold decoded artifacts, raise `artifact_withheld`, and tell the
claimant to contact an immortal. The committed custody record retains the blob,
UID and claimant for recovery. Before rollout, arrange recovery of any affected
listing as an ordinary saved copy under the preservation policy; do not simply
clear auction rows, refund a completed claim twice, or admit duplicate artifacts.
No target production audit or player-data mutation is performed by this PR.
