#!/usr/bin/env python3
"""Multi-grant and per-character instance contracts."""
from _paths import SRC
from pathlib import Path
from contract_text import contains, index

ROOT = Path(__file__).resolve().parents[2]
source = (SRC / "account_reward.c").read_text()
bootstrap = (ROOT / "migrations/bootstrap_multithread_safe.sql").read_text().lower().replace("`", "")
migration = (ROOT / "migrations/account_bound_rewards.sql").read_text().lower().replace("`", "")

# Every grant of an account, ordered by account and id, from memory.
loader = source[source.index("static std::vector<RewardGrant> query_grants"):source.index("static void forget_grant")]
assert contains(loader, "std::vector<RewardGrant>")
assert contains(loader, "for (const auto &[id, stored] : stored_grants)")
assert contains(loader, "std::stable_sort")

# One physical instance per grant and character; instances on other account
# characters are deliberately left in place.
instance = source[source.index("static P_obj existing_character_instance"):source.index("static bool summon_one")]
assert contains(instance, "reward_item_owner(obj)!=ch")
assert contains(instance, "if (!keep) keep=obj")
assert contains(instance, "extract_obj(obj)")
assert not contains(source, "previous_owner")
assert not contains(source, "clear_saved_rewards(account, 0)")
assert contains(source, "account_bound_reward_summons")
assert contains(source, "ON DUPLICATE KEY UPDATE last_summoned_at=VALUES(last_summoned_at)")
assert contains(source, "grant_marker_matches")
assert contains(source, "reward_marker_matches(obj, grant.account.c_str(), grant.id)")
assert contains(source, "grant.template_version == 0 && reward_marker_matches")
summon = source[source.index("static bool summon_one"):source.index("static bool parse_positive")]
assert contains(summon, "item_creation_grant_submit_to_player(ch,obj,ch)")
assert index(summon, "account_bound_reward_summons") < index(
    summon, "item_creation_grant_submit_to_player(ch,obj,ch)"
)
assert not contains(summon, "OBJ_CARRIED(obj)")

# Stable IDs allow multiple exact rewards sharing a vnum and precise removal;
# the old account/vnum and account/all forms remain as compatibility paths.
assert contains(source, "divineclaim remove <claim-id>")
assert contains(source, "divineclaim remove <account> <reward vnum|all>")
assert contains(source, "divineclaim list [account]")
assert contains(source, "WHERE id=%llu")
assert contains(source, "stored.grant.vnum == vnum && stored.grant.template_version == 0")
assert "primary key (id)" in migration
assert "primary key (grant_id, pid)" in migration or "primary key(grant_id,pid)" in migration
assert "primary key (id)" in bootstrap
assert "primary key (grant_id, pid)" in bootstrap or "primary key (grant_id,pid)" in bootstrap

print("multi-claim account reward runtime contract passed")
