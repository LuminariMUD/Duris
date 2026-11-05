#ifndef DURIS_NAMED_SET_EFFECTS_H
#define DURIS_NAMED_SET_EFFECTS_H

#include "core/structs.h"
#include "magic/spells.h"
#include <array>
#include <vector>

// Records only affects created during the invocation. Keep the native context
// and character/object links independent of the equipment source.
class named_set_grant
{
    public:
	named_set_grant(P_char wearer, P_char recipient, int zone, int spell)
		: wearer_(wearer)
		, recipient_(recipient)
		, zone_(zone)
		, spell_(spell)
		, previous_(current_)
	{
		current_ = this;
	}
	~named_set_grant() { current_ = previous_; }
	named_set_grant(const named_set_grant &) = delete;
	named_set_grant &operator=(const named_set_grant &) = delete;
	bool created_affects() const { return created_; }
	static bool active() { return current_ != nullptr; }

	static void mark(P_char target, affected_type *affect)
	{
		affect->set_zone = 0;
		affect->set_spell = 0;
		affect->set_owner = 0;
		if (affect->flags & AFFTYPE_SET_SUSPENDED)
			affect->flags &= ~AFFTYPE_NOAPPLY;
		affect->flags &= ~(AFFTYPE_SET_AFFECT | AFFTYPE_SET_SUSPENDED);
		if (!current_ || !current_->wearer_ || current_->zone_ <= 0 ||
		    (target != current_->wearer_ && target != current_->recipient_))
			return;
		// Summons and instant vitality retain their native timed consequences.
		if (current_->spell_ == SPELL_CONJURE_ELEMENTAL ||
		    current_->spell_ == SPELL_INVIGORATE)
			return;
		// The song's wards retain their ordinary durations, including on the wearer.
		if (current_->spell_ == SONG_DRAGONS && affect->type != SONG_DRAGONS)
			return;
		affect->set_zone = current_->zone_;
		affect->set_spell = current_->spell_;
		affect->set_owner = current_->wearer_->runtime_id;
		affect->flags |= AFFTYPE_SET_AFFECT | AFFTYPE_NOSAVE;
		if (current_->spell_ == SONG_DRAGONS)
			affect->duration = current_->wearer_->player.level / 3;
		current_->created_ = true;
	}

    private:
	P_char wearer_;
	P_char recipient_;
	int zone_;
	int spell_;
	bool created_ = false;
	named_set_grant *previous_;
	inline static thread_local named_set_grant *current_ = nullptr;
};

// Retain one buff while any currently worn set supports it. Returns whether
// unsupported, wearer-owned effects were removed; ordinary casts are untouched.
bool reconcile_named_set_spell(P_char ch, int spell);

// Temporarily hide only overlapping set nodes from a native ordinary cast.
// Retain nodes, links and durations.
class named_set_ordinary_cast
{
    public:
	named_set_ordinary_cast(P_char target, int spell)
		: named_set_ordinary_cast(nullptr, target, spell)
	{
	}
	named_set_ordinary_cast(P_char caster, P_char target, int spell);
	~named_set_ordinary_cast();
	named_set_ordinary_cast(const named_set_ordinary_cast &) = delete;
	named_set_ordinary_cast &operator=(const named_set_ordinary_cast &) = delete;

    private:
	struct held_affects
	{
		P_char target = nullptr;
		std::vector<affected_type *> affects;
	};
	std::array<held_affects, 2> held_{};
};

// Reconcile application only: removal/support remains with normal set cleanup.
// The optional retiring node is ignored before its wear-off message/removal.
void update_named_set_suspension(P_char ch, const affected_type *retiring = nullptr);

#endif
