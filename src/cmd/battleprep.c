#include "cmd/battleprep.h"
#include "classes/epic_skills.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/item_actions.h"
#include "magic/spells.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "persistence/persistence_checkpoint.h"
#include "world/db.h"

extern Skill skills[];
extern P_char character_list;
extern void tranquilize(P_char, P_char);
extern void event_abort_spell(P_char, P_char, P_obj, void *);
extern void event_acidimmolate(P_char, P_char, P_obj, void *);
extern void event_magma_burst(P_char, P_char, P_obj, void *);

// Legacy kit damage pulses are scheduled outside item_actions. Include incoming
// references, but leave other actors' effects on unrelated targets intact.
static bool battle_damage_events(P_char target, bool cancel)
{
	bool pending = false;
	for (P_char actor = character_list; actor; actor = actor->next)
		for (P_nevent event = actor->nevents, next; event; event = next)
		{
			next = event->next_char_nev;
			if ((event->func != event_acidimmolate &&
			     event->func != event_magma_burst && event->func != event_poison) ||
			    (event->ch != target && event->victim != target))
				continue;
			pending = true;
			if (cancel)
			{
				P_char affected = event->func == event_poison ? event->ch :
										event->victim;
				int effect = event->func == event_magma_burst ? SPELL_MAGMA_BURST :
										0;
				if (event->func == event_poison && event->data)
				{
					const int poison = *static_cast<short *>(event->data);
					if (poison >= FIRST_POISON && poison <= LAST_POISON)
						effect = poison;
				}
				nevent_cancel(nevent_handle_from_event(event));
				if (effect && affected && IS_ALIVE(affected))
					affect_from_char(affected, effect);
			}
		}
	return pending;
}

static void battle_stop_status(P_char staff, char *argument, bool stop)
{
	char name[MAX_INPUT_LENGTH];
	if (!*argument)
	{
		send_to_char("Usage: battleprep stop|status <exact-player-names>\r\n", staff);
		return;
	}
	for (;;)
	{
		argument = one_argument(argument, name);
		if (!*name)
			break;
		P_char victim = get_char_vis(staff, name);
		if (!victim || str_cmp(GET_NAME(victim), name))
		{
			send_to_char_f(staff, "Battleprep status %s missing.\r\n", name);
			continue;
		}
		if (IS_NPC(victim) || GET_LEVEL(victim) > MAXLVLMORTAL)
		{
			send_to_char_f(staff, "Battleprep status %s refused.\r\n", name);
			continue;
		}
		if (!IS_ALIVE(victim) || victim->in_room == NOWHERE)
		{
			send_to_char_f(staff, "Battleprep status %s unavailable.\r\n", name);
			continue;
		}
		if (stop)
		{
			if (victim->desc)
				flush_input_queue(victim->desc);
			StopCasting(victim);
			disarm_char_nevents(victim, event_abort_spell);
			stop_memorizing(victim, memorization_stop_reason::voluntary);
			stop_singing(victim);
			item_actions_stop(victim);
			battle_damage_events(victim, true);
			tranquilize(staff, victim);
			// Normal sleep permits standing, whose later collapse can hurt and
			// wake the participant. Settle only a successfully sleeping target.
			if (GET_STAT(victim) == STAT_SLEEPING && GET_POS(victim) == POS_STANDING)
			{
				SET_POS(victim, STAT_SLEEPING + POS_SITTING);
				gmcp_char_vitals(victim);
			}
			logit(LOG_WIZ, "%s stopped battle participant %s", GET_NAME(staff),
			      GET_NAME(victim));
		}
		const bool queued = victim->desc &&
				    (victim->desc->input.head || victim->desc->buflen);
		bool incoming = false;
		for (P_char other = world[victim->in_room].people; other;
		     other = other->next_in_room)
			if (GET_OPPONENT(other) == victim)
				incoming = true;
		const bool quiet = !queued && !incoming && !GET_OPPONENT(victim) &&
				   !IS_CASTING(victim) && !IS_AFFECTED2(victim, AFF2_MEMORIZING) &&
				   !SINGING(victim) && !item_actions_pending(victim) &&
				   !battle_damage_events(victim, false);
		send_to_char_f(staff, "Battleprep status %s %s.\r\n", name,
			       quiet ? "quiet" : "pending");
	}
}

// Use the live class tables even on Chaos, whose normal advancement deliberately
// grants a blanket 100. Battle characters need the actual unspecialized ceilings.
static void prepare_battle_baseline(P_char victim)
{
	for (int stat = 0; stat < MAX_ATTRIBUTES; ++stat)
		victim->base_stats[stat] = 100;
	affect_total(victim, FALSE);
	advance_to_level(victim, MAXLVLMORTAL);

	for (int skill = FIRST_SPELL; skill <= LAST_SONG; ++skill)
	{
		if (IS_EPIC_SKILL(skill) || !(IS_SPELL(skill) || IS_SKILL(skill) ||
					      IS_INSTRUMENT_SKILL(skill) || IS_BARD_SONG(skill)))
			continue;
		const ClassSkillInfo data = SKILL_DATA_ALL(victim, skill);
		const int required = IS_SPELL(skill) ? get_spell_circle(victim, skill) :
						       data.rlevel[0];
		const int available = IS_SPELL(skill) ? get_max_circle(victim) : GET_LEVEL(victim);
		const int cap = required > 0 && required <= available ?
					BOUNDED(0, data.maxlearn[0], 100) :
					0;
		victim->only.pc->skills[skill].learned = cap;
		victim->only.pc->skills[skill].taught = cap;
	}
	grant_epic_skills_without_specialization(victim);
	affect_total(victim, FALSE);
	GET_HIT(victim) = GET_MAX_HIT(victim);
	GET_MANA(victim) = GET_MAX_MANA(victim);
	GET_VITALITY(victim) = GET_MAX_VITALITY(victim);
	if (USES_SPELL_SLOTS(victim))
	{
		victim->specials.undead_spell_slots[0] = 0;
		for (int circle = 1; circle <= MAX_CIRCLE; ++circle)
			victim->specials.undead_spell_slots[circle] =
				max_spells_in_circle(victim, circle);
	}
	mark_player_dirty_components(GET_PID(victim), PLAYER_COMPONENT_STATUS |
							      PLAYER_COMPONENT_SKILLS |
							      PLAYER_COMPONENT_UNDEAD_SLOTS);
}

// The player queues spells with memorize/pray. Validate the entire queue before
// finishing any entry: stale saves and changed class tables must not grant casts
// outside today's eligibility or circle capacity.
static bool prepare_battle_spells(P_char staff, P_char victim)
{
	int counts[MAX_CIRCLE + 1] = {};
	int pending = 0;
	for (auto *af = victim->affected; af; af = af->next)
	{
		if (af->type != TAG_MEMORIZE)
			continue;
		const int spell = af->modifier;
		if (!IS_SPELL(spell) || USES_MANA(victim) || USES_SPELL_SLOTS(victim))
		{
			send_to_char("Battleprep: invalid memorization queue.\r\n", staff);
			return false;
		}
		const int circle = get_spell_circle(victim, spell);
		if (circle < 1 || circle > get_max_circle(victim) ||
		    !SKILL_DATA_ALL(victim, spell).maxlearn[0] ||
		    ++counts[circle] > max_spells_in_circle(victim, circle))
		{
			send_to_char("Battleprep: ineligible spell or overfull circle.\r\n", staff);
			return false;
		}
		if (!(af->flags & MEMTYPE_FULL))
		{
			if (book_class(victim) &&
			    !SpellInSpellBook(victim, spell,
					      SBOOK_MODE_IN_INV | SBOOK_MODE_AT_HAND |
						      SBOOK_MODE_ON_BELT | SBOOK_MODE_ON_GROUND))
			{
				send_to_char("Battleprep: a queued spell is missing its book.\r\n",
					     staff);
				return false;
			}
			++pending;
		}
	}
	stop_memorizing(victim, memorization_stop_reason::voluntary);
	for (auto *af = victim->affected; af; af = af->next)
		if (af->type == TAG_MEMORIZE)
			af->flags |= MEMTYPE_FULL;
	mark_player_dirty_components(GET_PID(victim), PLAYER_COMPONENT_AFFECTS);
	send_to_char_f(staff, "Battleprep: %s has %d newly prepared spells.\r\n", GET_NAME(victim),
		       pending);
	return true;
}

void do_battleprep(P_char ch, char *argument, int /*cmd*/)
{
	if (!ch || IS_NPC(ch) || GET_LEVEL(ch) < OVERLORD)
		return;
	char name[MAX_INPUT_LENGTH], operation[MAX_INPUT_LENGTH], extra[MAX_INPUT_LENGTH];
	argument = one_argument(argument, name);
	if (!str_cmp(name, "stop") || !str_cmp(name, "status"))
	{
		battle_stop_status(ch, argument, !str_cmp(name, "stop"));
		return;
	}
	argument = one_argument(argument, operation);
	one_argument(argument, extra);
	if (!*name || *extra ||
	    (str_cmp(operation, "baseline") && str_cmp(operation, "spells") &&
	     str_cmp(operation, "equipment") && str_cmp(operation, "equip")))
	{
		send_to_char(
			"Usage: battleprep <exact-player-name> baseline|spells|equip|equipment\r\n"
			"       battleprep stop|status <exact-player-names>\r\n",
			ch);
		return;
	}
	P_char victim = get_char_vis(ch, name);
	if (!victim || IS_NPC(victim) || str_cmp(GET_NAME(victim), name) || !victim->desc ||
	    victim->desc->connected != CON_PLAYING || GET_LEVEL(victim) > MAXLVLMORTAL ||
	    !IS_ALIVE(victim))
	{
		send_to_char("Battleprep: name an exact, connected, living mortal.\r\n", ch);
		return;
	}
	if (victim->player.spec || victim->player.secondary_class)
	{
		send_to_char("Battleprep: requires an unspecialized single-class character.\r\n",
			     ch);
		return;
	}
	bool fighting = GET_OPPONENT(victim) != nullptr;
	for (P_char other = world[victim->in_room].people; other; other = other->next_in_room)
		fighting = fighting || GET_OPPONENT(other) == victim;
	if (fighting || IS_CASTING(victim) || item_action_active(victim))
	{
		send_to_char("Battleprep: finish combat and pending actions first.\r\n", ch);
		return;
	}
	if (!str_cmp(operation, "baseline"))
	{
		if (IS_AFFECTED2(victim, AFF2_MEMORIZING))
		{
			send_to_char(
				"Battleprep: stop memorizing before preparing the baseline.\r\n",
				ch);
			return;
		}
		prepare_battle_baseline(victim);
		send_to_char_f(ch, "Battleprep: %s baseline ready at level %d.\r\n",
			       GET_NAME(victim), GET_LEVEL(victim));
	}
	else if (!str_cmp(operation, "equipment") || !str_cmp(operation, "equip"))
	{
		if (!str_cmp(operation, "equip"))
			equip_chaos_kit(victim);
		send_to_char_f(ch, "Battleprep: %s equipment %s.\r\n", GET_NAME(victim),
			       chaos_kit_equipment_ready(victim, ch) ? "ready" : "incomplete");
		return;
	}
	else if (!prepare_battle_spells(ch, victim))
		return;
	logit(LOG_WIZ, "%s used battleprep %s on %s", GET_NAME(ch), operation, GET_NAME(victim));
}
