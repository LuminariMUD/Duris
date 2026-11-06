#include "item/named_set_effects.h"

#include "core/prototypes.h"
#include "core/utils.h"
#include "item/named_set_origin.h"
#include "item/named_sets.h"
#include "world/vnum.obj.h"

extern P_index obj_index;
extern Skill skills[];

static bool same_spell(int first, int second)
{
	return first == second || (first > 0 && first <= MAX_AFFECT_TYPES && second > 0 &&
				   second <= MAX_AFFECT_TYPES && skills[first].spell_pointer &&
				   skills[first].spell_pointer == skills[second].spell_pointer);
}

void update_named_set_suspension(P_char ch, const affected_type *retiring)
{
	for (affected_type *source = ch->affected; source; source = source->next)
	{
		if (!(source->flags & AFFTYPE_SET_AFFECT) || source == retiring ||
		    (source->set_spell >= FIRST_SKILL && source->set_spell != SONG_DRAGONS) ||
		    ((source->flags & AFFTYPE_NOAPPLY) && !(source->flags & AFFTYPE_SET_SUSPENDED)))
			continue;
		bool ordinary = false;
		for (const affected_type *other = ch->affected; other; other = other->next)
			if (other != retiring &&
			    !(other->flags & (AFFTYPE_SET_AFFECT | AFFTYPE_NOAPPLY)) &&
			    !(other->type == SPELL_REGENERATION &&
			      (other->flags & AFFTYPE_ARAMUS_CROWN_REGENERATION)) &&
			    (other->type == source->type ||
			     same_spell(other->type, source->set_spell)))
			{
				ordinary = true;
				break;
			}
		if (ordinary && !(source->flags & AFFTYPE_SET_SUSPENDED))
		{
			source->flags |= AFFTYPE_NOAPPLY | AFFTYPE_SET_SUSPENDED;
		}
		else if (!ordinary && (source->flags & AFFTYPE_SET_SUSPENDED))
		{
			source->flags &= ~(AFFTYPE_NOAPPLY | AFFTYPE_SET_SUSPENDED);
		}
	}
}

named_set_ordinary_cast::named_set_ordinary_cast(P_char caster, P_char target, int spell)
{
	if (named_set_grant::active())
		return;
	held_[0].target = caster;
	held_[1].target = target == caster ? nullptr : target;
	for (auto &held : held_)
	{
		if (!IS_ALIVE(held.target))
			continue;
		for (affected_type *affect = held.target->affected; affect; affect = affect->next)
			if ((affect->flags & AFFTYPE_SET_AFFECT) &&
			    same_spell(affect->set_spell, spell))
				held.affects.push_back(affect);
	}
	for (const auto &held : held_)
	{
		if (held.affects.empty())
			continue;
		all_affects(held.target, FALSE);
		for (affected_type *affect : held.affects)
		{
			affected_type **cursor = &held.target->affected;
			while (*cursor != affect)
				cursor = &(*cursor)->next;
			*cursor = affect->next;
		}
		all_affects(held.target, TRUE);
	}
}

named_set_ordinary_cast::~named_set_ordinary_cast()
{
	for (const auto &held : held_)
	{
		if (held.affects.empty())
			continue;
		all_affects(held.target, FALSE);
		for (affected_type *affect : held.affects)
		{
			affect->next = held.target->affected;
			held.target->affected = affect;
		}
		update_named_set_suspension(held.target);
		all_affects(held.target, TRUE);
		balance_affects(held.target);
	}
}

static int supporting_zone(P_char ch, int spell)
{
	for (size_t i = 0; i < named_set_count; ++i)
		for (const auto &tier : named_sets[i].proc_spells)
		{
			if (!tier[0] || tier[1] != spell)
				continue;
			int count = 0;
			bool armor_driver = false;
			for (int slot = 0; slot < MAX_WEAR; ++slot)
			{
				P_obj object = ch->equipment[slot];
				if (!object || object->R_num < 0)
					continue;
				const int vnum = obj_index[object->R_num].virtual_number;
				if ((vnum != VOBJ_RANDOM_ARMOR && vnum != VOBJ_RANDOM_WEAPON) ||
				    named_set_origin(object).zone != named_sets[i].zone)
					continue;
				armor_driver = armor_driver || vnum == VOBJ_RANDOM_ARMOR;
				if (slot != WEAR_ATTACH_BELT_2 && slot != WEAR_ATTACH_BELT_3)
					++count;
			}
			if (armor_driver && count >= tier[0])
				return named_sets[i].zone;
		}
	return 0;
}

bool reconcile_named_set_spell(P_char ch, int spell)
{
	const int support = supporting_zone(ch, spell);
	bool removed = false;
	for (affected_type *affect = ch->affected, *next; affect; affect = next)
	{
		next = affect->next;
		if (!(affect->flags & AFFTYPE_SET_AFFECT) || affect->set_spell != spell ||
		    affect->set_owner != ch->runtime_id)
			continue;
		if (support)
			affect->set_zone = support;
		else
		{
			wear_off_message(ch, affect);
			affect_remove(ch, affect);
			removed = true;
		}
	}
	return removed;
}
