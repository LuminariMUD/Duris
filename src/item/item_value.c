// Shared numeric item valuation. Quantization follows all credits and multipliers.
#include "item/item_value.h"
#include "item/objmisc.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <climits>
#include <tuple>

bool item_value_material_quantities(int score, double scale, int &high, int &low)
{
	if (score < 1 || !std::isfinite(scale) || scale <= 0)
		return false;
	const auto material_value = static_cast<long long>(score) + 4;
	// Round up, but not on float noise: 25 * 2.2 is 55, not 56. A positive need stays positive.
	const auto units = [scale](long long count)
	{ return count ? std::max(1.0, std::ceil(count * scale - 1e-9)) : 0.0; };
	const double high_count = units(material_value / 5);
	const double low_count = units(material_value % 5);
	if (!std::isfinite(high_count) || !std::isfinite(low_count) || high_count > INT_MAX ||
	    low_count > INT_MAX)
		return false;
	high = static_cast<int>(high_count);
	low = static_cast<int>(low_count);
	return true;
}

bool item_value_has_packed_proc(const item_value_input &input)
{
	const auto *obj = &input;
	return ((obj->wear_flags & ITEM_WIELD) ||
		(((obj->type == ITEM_ARMOR || obj->type == ITEM_WORN) &&
		  (obj->wear_flags & ITEM_WEAR_HANDS) && (obj->extra2_flags & ITEM2_MONK_PROC)) &&
		 obj->value[6] > 0)) &&
	       obj->value[5] > 0 && obj->value[7] > 0;
}

const char *item_value_proc_policy_name(item_value_proc_policy policy)
{
	switch (policy)
	{
	case item_value_proc_policy::none:
		return "none";
	case item_value_proc_policy::priced:
		return "priced";
	case item_value_proc_policy::utility:
		return "utility";
	case item_value_proc_policy::unclassified:
		return "unclassified";
	}
	return "unclassified";
}

unsigned int item_value_packed_cast_mask(const item_value_input &input,
					 unsigned int callable_spells)
{
	if (!item_value_has_packed_proc(input))
		return 0;
	unsigned int populated = 0;
	int count = 0;
	for (int packed = input.value[5] % 1000000000, i = 0; i < 3; ++i, packed /= 1000)
		if (packed % 1000)
		{
			populated |= 1u << i;
			++count;
		}
	const unsigned int prefix = (1u << count) - 1;
	if ((input.type == ITEM_ARMOR || input.type == ITEM_WORN) &&
	    (input.wear_flags & ITEM_WEAR_HANDS) && (input.extra2_flags & ITEM2_MONK_PROC) &&
	    (populated != prefix || (callable_spells & populated) != populated))
		return 0;
	return prefix & populated & callable_spells;
}

static void item_value_coverage(const item_value_input &input, item_value_breakdown &detail)
{
	const unsigned long long priced[5] = {
		AFF_AWARE | AFF_BARKSKIN | AFF_BIOFEEDBACK | AFF_DETECT_INVISIBLE | AFF_FARSEE |
			AFF_FLY | AFF_HASTE | AFF_HIDE | AFF_INFRAVISION | AFF_INVISIBLE |
			AFF_LEVITATE | AFF_MINOR_GLOBE | AFF_PROTECT_EVIL | AFF_PROTECT_GOOD |
			AFF_PROT_FIRE | AFF_SENSE_LIFE | AFF_SLOW_POISON | AFF_SNEAK |
			AFF_STONE_SKIN | AFF_UD_VISION | AFF_WATERBREATH,
		AFF2_AIR_AURA | AFF2_CONCEALMENT | AFF2_DETECT_EVIL | AFF2_DETECT_GOOD |
			AFF2_DETECT_MAGIC | AFF2_EARTH_AURA | AFF2_FIRESHIELD | AFF2_FIRE_AURA |
			AFF2_FLURRY | AFF2_GLOBE | AFF2_PASSDOOR | AFF2_PROT_ACID | AFF2_PROT_COLD |
			AFF2_PROT_GAS | AFF2_PROT_LIGHTNING | AFF2_SOULSHIELD | AFF2_ULTRAVISION |
			AFF2_VAMPIRIC_TOUCH | AFF2_WATER_AURA,
		AFF3_BLUR | AFF3_COLDSHIELD | AFF3_ENLARGE | AFF3_GR_SPIRIT_WARD |
			AFF3_INERTIAL_BARRIER | AFF3_PASS_WITHOUT_TRACE | AFF3_PROT_ANIMAL |
			AFF3_REDUCE | AFF3_SPIRIT_WARD | AFF3_TOWER_IRON_WILL,
		AFF4_BATTLE_ECSTASY | AFF4_DAZZLER | AFF4_DETECT_ILLUSION | AFF4_GLOBE_OF_DARKNESS |
			AFF4_HAWKVISION | AFF4_HELLFIRE | AFF4_HOLY_SACRIFICE | AFF4_ICE_AURA |
			AFF4_NEG_SHIELD | AFF4_NOFEAR | AFF4_PHANTASMAL_FORM | AFF4_PROT_LIVING |
			AFF4_REGENERATION | AFF4_SANCTUARY | AFF4_SENSE_HOLINESS |
			AFF4_VAMPIRE_FORM | AFF4_WILDMAGIC,
		0,
	};
	const unsigned long long present[] = { input.bitvector, input.bitvector2, input.bitvector3,
					       input.bitvector4, input.bitvector5 };
	for (int bank = 0; bank < 5; ++bank)
	{
		detail.unpriced_affects[bank] = present[bank] & ~priced[bank];
		if (bank == 0)
			detail.unpriced_affects[bank] &= ~(
				static_cast<unsigned long long>(AFF_SLEEP) | AFF_FEAR | AFF_CHARM);
		if (detail.unpriced_affects[bank])
			detail.context_complete = false;
	}
	for (int slot = 0; slot < MAX_OBJ_AFFECT; ++slot)
	{
		if (!input.affected[slot].modifier || input.affected[slot].location == APPLY_NONE)
			continue;
		switch (input.affected[slot].location)
		{
		case APPLY_AC:
		case APPLY_AGI:
		case APPLY_AGI_MAX:
		case APPLY_AGI_RACE:
		case APPLY_CHA:
		case APPLY_CHA_MAX:
		case APPLY_CHA_RACE:
		case APPLY_COMBAT_PULSE:
		case APPLY_CON:
		case APPLY_CON_MAX:
		case APPLY_CON_RACE:
		case APPLY_DAMROLL:
		case APPLY_DEX:
		case APPLY_DEX_MAX:
		case APPLY_DEX_RACE:
		case APPLY_HIT:
		case APPLY_HITROLL:
		case APPLY_HIT_REG:
		case APPLY_INT:
		case APPLY_INT_MAX:
		case APPLY_INT_RACE:
		case APPLY_LUCK:
		case APPLY_LUCK_MAX:
		case APPLY_MANA:
		case APPLY_MANA_REG:
		case APPLY_MOVE:
		case APPLY_MOVE_REG:
		case APPLY_POW:
		case APPLY_POW_MAX:
		case APPLY_SAVING_BREATH:
		case APPLY_SAVING_FEAR:
		case APPLY_SAVING_PARA:
		case APPLY_SAVING_ROD:
		case APPLY_SAVING_SPELL:
		case APPLY_SPELL_PULSE:
		case APPLY_STR:
		case APPLY_STR_MAX:
		case APPLY_STR_RACE:
		case APPLY_WIS:
		case APPLY_WIS_MAX:
		case APPLY_WIS_RACE:
			break;
		default:
			detail.unpriced_apply_slots |= 1u << slot;
			detail.context_complete = false;
		}
	}
	detail.unpriced_type = !detail.utility_override && input.type != ITEM_WEAPON &&
			       input.type != ITEM_ARMOR && input.type != ITEM_WORN;
	if (detail.unpriced_type)
		detail.context_complete = false;
}

int evaluate_item_value(const item_value_input &input, const item_value_context &context,
			item_value_breakdown *breakdown)
{
	// Context participates in canonical ordering; reject NaNs before comparison.
	for (double credit : context.racial_credits)
		if (!std::isfinite(credit))
		{
			if (breakdown)
			{
				*breakdown = {};
				breakdown->invalid = true;
			}
			return 0;
		}
	const auto *obj = &input;
	double workingvalue = 0;
	double multiplier = 1;
	double mod;
	double packed_credit = 0;
	const unsigned int packed_cast_mask =
		context.packed_proc_disabled ?
			0 :
			item_value_packed_cast_mask(input, context.callable_packed_spells);

	if ((obj->wear_flags & ITEM_WEAR_EYES))
		multiplier *= 1.3;

	if ((obj->wear_flags & ITEM_WEAR_EARRING))
		multiplier *= 1.2;

	if ((obj->wear_flags & ITEM_WEAR_FACE))
		multiplier *= 1.3;

	if ((obj->wear_flags & ITEM_WEAR_QUIVER))
		multiplier *= 1.1;

	if ((obj->wear_flags & ITEM_WEAR_FINGER))
		multiplier *= 1.2;

	if ((obj->wear_flags & ITEM_GUILD_INSIGNIA))
		multiplier *= 1.5;

	if ((obj->wear_flags & ITEM_WEAR_NECK))
		multiplier *= 1.2;

	if ((obj->wear_flags & ITEM_WEAR_WAIST))
		multiplier *= 1.1;

	if ((obj->wear_flags & ITEM_WEAR_WRIST))
		multiplier *= 1.1;

	const double after_wear = multiplier;
	// Aff's add to the base value.
	if ((obj->bitvector & AFF_STONE_SKIN))
		workingvalue += 125;

	if ((obj->bitvector & AFF_BIOFEEDBACK))
		workingvalue += 110;

	if ((obj->bitvector & AFF_FARSEE))
		workingvalue += 45;

	if ((obj->bitvector & AFF_DETECT_INVISIBLE))
		workingvalue += 90;

	if ((obj->bitvector & AFF_HASTE))
		workingvalue += 75;

	if ((obj->bitvector & AFF_INVISIBLE))
		workingvalue += 35;

	if ((obj->bitvector & AFF_SENSE_LIFE))
		workingvalue += 45;

	if ((obj->bitvector & AFF_MINOR_GLOBE))
		workingvalue += 28;

	if ((obj->bitvector & AFF_UD_VISION))
		workingvalue += 40;

	if ((obj->bitvector & AFF_WATERBREATH))
		workingvalue += 45;

	if ((obj->bitvector & AFF_PROTECT_EVIL))
		workingvalue += 35;

	if ((obj->bitvector & AFF_PROTECT_GOOD))
		workingvalue += 35;

	if ((obj->bitvector & AFF_SLOW_POISON))
		workingvalue += 20;

	if ((obj->bitvector & AFF_SNEAK))
		workingvalue += 125;

	if ((obj->bitvector & AFF_BARKSKIN))
		workingvalue += 25;

	if ((obj->bitvector & AFF_INFRAVISION))
		workingvalue += 7;

	if ((obj->bitvector & AFF_LEVITATE))
		workingvalue += 13;

	if ((obj->bitvector & AFF_HIDE))
		workingvalue += 85;

	if ((obj->bitvector & AFF_FLY))
		workingvalue += 75;

	if ((obj->bitvector & AFF_AWARE))
		workingvalue += 75;

	if ((obj->bitvector & AFF_PROT_FIRE))
		workingvalue += 20;

	if ((obj->bitvector2 & AFF2_FIRESHIELD))
		workingvalue += 45;

	if ((obj->bitvector2 & AFF2_ULTRAVISION))
		workingvalue += 80;

	if ((obj->bitvector2 & AFF2_DETECT_EVIL))
		workingvalue += 5;

	if ((obj->bitvector2 & AFF2_DETECT_GOOD))
		workingvalue += 5;

	if ((obj->bitvector2 & AFF2_DETECT_MAGIC))
		workingvalue += 10;

	if ((obj->bitvector2 & AFF2_PROT_COLD))
		workingvalue += 20;

	if ((obj->bitvector2 & AFF2_PROT_LIGHTNING))
		workingvalue += 30;

	if ((obj->bitvector2 & AFF2_GLOBE))
		workingvalue += 80;

	if ((obj->bitvector2 & AFF2_PROT_GAS))
		workingvalue += 30;

	if ((obj->bitvector2 & AFF2_PROT_ACID))
		workingvalue += 30;

	if ((obj->bitvector2 & AFF2_SOULSHIELD))
		workingvalue += 45;

	if ((obj->bitvector2 & AFF2_CONCEALMENT))
		workingvalue += 15;

	if ((obj->bitvector2 & AFF2_VAMPIRIC_TOUCH))
		workingvalue += 65;

	if ((obj->bitvector2 & AFF2_EARTH_AURA))
		workingvalue += 110;

	if ((obj->bitvector2 & AFF2_WATER_AURA))
		workingvalue += 115;

	if ((obj->bitvector2 & AFF2_FIRE_AURA))
		workingvalue += 120;

	if ((obj->bitvector2 & AFF2_AIR_AURA))
		workingvalue += 130;

	if ((obj->bitvector2 & AFF2_PASSDOOR))
		workingvalue += 80;

	if ((obj->bitvector2 & AFF2_FLURRY))
		workingvalue += 150;

	if ((obj->bitvector3 & AFF3_PROT_ANIMAL))
		workingvalue += 20;

	if ((obj->bitvector3 & AFF3_SPIRIT_WARD))
		workingvalue += 35;

	if ((obj->bitvector3 & AFF3_GR_SPIRIT_WARD))
	{
		workingvalue += 25;
		multiplier += 1.20;
	}

	if ((obj->bitvector3 & AFF3_ENLARGE))
		workingvalue += 120;

	if ((obj->bitvector3 & AFF3_REDUCE))
		workingvalue += 120;

	if ((obj->bitvector3 & AFF3_INERTIAL_BARRIER))
		workingvalue += 135;

	if ((obj->bitvector3 & AFF3_COLDSHIELD))
		workingvalue += 45;

	if ((obj->bitvector3 & AFF3_TOWER_IRON_WILL))
		workingvalue += 45;

	if ((obj->bitvector3 & AFF3_BLUR))
		workingvalue += 65;

	if ((obj->bitvector3 & AFF3_PASS_WITHOUT_TRACE))
		workingvalue += 45;

	if ((obj->bitvector4 & AFF4_VAMPIRE_FORM))
		workingvalue += 90;

	if ((obj->bitvector4 & AFF4_HOLY_SACRIFICE))
		workingvalue += 105;

	if ((obj->bitvector4 & AFF4_BATTLE_ECSTASY))
		workingvalue += 105;

	if ((obj->bitvector4 & AFF4_DAZZLER))
		workingvalue += 45;

	if ((obj->bitvector4 & AFF4_PHANTASMAL_FORM))
		workingvalue += 105;

	if ((obj->bitvector4 & AFF4_NOFEAR))
		workingvalue += 40;

	if ((obj->bitvector4 & AFF4_REGENERATION))
		workingvalue += 60;

	if ((obj->bitvector4 & AFF4_GLOBE_OF_DARKNESS))
		workingvalue += 15;

	if ((obj->bitvector4 & AFF4_HAWKVISION))
		workingvalue += 20;

	if ((obj->bitvector4 & AFF4_SANCTUARY))
		workingvalue += 105;

	if ((obj->bitvector4 & AFF4_HELLFIRE))
		workingvalue += 110;

	if ((obj->bitvector4 & AFF4_SENSE_HOLINESS))
		workingvalue += 15;

	if ((obj->bitvector4 & AFF4_PROT_LIVING))
		workingvalue += 45;

	if ((obj->bitvector4 & AFF4_DETECT_ILLUSION))
		workingvalue += 40;

	if ((obj->bitvector4 & AFF4_ICE_AURA))
		workingvalue += 90;

	if ((obj->bitvector4 & AFF4_NEG_SHIELD))
		workingvalue += 45;

	if ((obj->bitvector4 & AFF4_WILDMAGIC))
		workingvalue += 240;

	const double flags_base = workingvalue;
	const double after_flags = multiplier;
	// Has a old school proc (Up to three spells).
	if (packed_cast_mask)
	{
		int spells[3];
		double spellcirclesum;
		int numspells;

		// val5 : 3 spells + all or one.
		spells[0] = obj->value[5] % 1000;
		spells[1] = obj->value[5] % 1000000 / 1000;
		spells[2] = obj->value[5] % 1000000000 / 1000000;

		// val6 = level * val7 = chance -> 1/30 chance = 1, 1/60 chance = .5, 1/15 chance = 2, etc.
		// Integer numerator, so one division keeps a whole credit whole.
		const int level_tenths = (obj->value[6] > 19) ? obj->value[6] : 10;

		spellcirclesum = 0;
		for (int i = 0; i < 3; ++i)
			if (packed_cast_mask & (1u << i))
				spellcirclesum += context.spell_circles[i];

		// 1 lvl 10 spell  2nd circle 1/60 chance = 1*1* 2*.5 =  1
		// 1 lvl 60 spell  1st circle 1/30 chance = 1*6* 1*1  =  6
		// 1 lvl 40 spell  3rd circle 1/30 chance = 1*4* 3*1  = 12
		// 1 lvl 60 spell 12th circle 1/30 chance = 1*6*12*1  = 72 etc.
		// val5 / 1000000000 -> 1, otherwise casts all.
		if (obj->value[5] / 1000000000)
		{
			// Add up number of spells
			numspells = ((spells[0]) ? 1 : 0) + ((spells[1]) ? 1 : 0) +
				    ((spells[2]) ? 1 : 0);
			// If there are none?!, set to 1 anyway.
			numspells = numspells ? numspells : 1;
			// Keep the mean and scaled contribution fractional until final quantization.
			packed_credit = 3.0 * level_tenths * spellcirclesum /
					(double(obj->value[7]) * numspells);
		}
		else
		{
			packed_credit = 3.0 * level_tenths * spellcirclesum / obj->value[7];
		}
	}
	workingvalue += packed_credit;

	workingvalue += context.native_proc_credit;

	// Order only local indexes: persisted slots and their racial context stay paired.
	// A canonical sum also avoids floating-point differences between permutations.
	std::array<int, MAX_OBJ_AFFECT> order{};
	for (int i = 0; i < MAX_OBJ_AFFECT; ++i)
		order[i] = i;
	std::sort(order.begin(), order.end(),
		  [&](int left, int right)
		  {
			  return std::tie(obj->affected[left].location,
					  obj->affected[left].modifier,
					  context.racial_credits[left]) <
				 std::tie(obj->affected[right].location,
					  obj->affected[right].modifier,
					  context.racial_credits[right]);
		  });
	double apply_additions[MAX_OBJ_AFFECT]{};
	std::array<double, MAX_OBJ_AFFECT> apply_factors;
	apply_factors.fill(1);
	for (size_t first = 0; first < order.size();)
	{
		const int i = order[first];
		const int location = obj->affected[i].location;
		const bool racial = location >= APPLY_STR_RACE && location <= APPLY_LUCK_RACE;
		double racial_credit = 0, invalid_racial_credit = 0;
		bool has_racial_credit = false;
		mod = 0;
		// Ordinary stats add live; racial overrides select the greatest stat factor.
		// Widen the total locally, never consolidate or narrow persisted slots.
		do
		{
			const int slot = order[first++];
			const int modifier = obj->affected[slot].modifier;
			if (!racial)
				mod += modifier;
			else if (modifier > RACE_NONE && modifier <= LAST_RACE)
			{
				if (!has_racial_credit ||
				    context.racial_credits[slot] > racial_credit)
					racial_credit = context.racial_credits[slot];
				has_racial_credit = true;
			}
			else if (modifier != 0)
				invalid_racial_credit += context.racial_credits[slot];
		} while (first < order.size() && obj->affected[order[first]].location == location);
		if (racial)
		{
			workingvalue += racial_credit + invalid_racial_credit;
			continue;
		}
		if (mod == 0)
			continue;
		// dam/hitroll are normal values
		if ((obj->affected[i].location == APPLY_DAMROLL) ||
		    (obj->affected[i].location == APPLY_HITROLL))
		{
			if (obj->type == ITEM_WEAPON)
			{
				// 1:1, 2:2, 3:6, 4:12, 5:20, 6:30, 7:42, 8:56, 9:72, 10:90, 11: 110..
				workingvalue += (mod <= 2) ? mod : mod * (mod - 1);
			}
			else
			{
				// 1:2, 2:5, 3:30, 4:51, 5:78, 6:111
				// 1:2, 2:6, 3:37, 4:63, 5:97 after multiplier (note: wear flag will raise 5 over 100).
				workingvalue += (mod <= 2) ? (3 * mod - 1) : 3 * mod * mod + 3;
			}
			// Translates to 1:1, 2:2, 3:7, 4:15, 5:25, 6:37, 7:52, 8:70, 9:90, 10:112
			apply_factors[i] = 1.25;
			// So a 5/5 weapon is essentially 40 * 1.25 * 1.25 = 62.5 (before adding other stats).
			// A 6/6 item (no other stats) is 93, a 2d2 6/6 sword would be 62 * 1.25^2 = 96, and 5d5 6/6 = 112.
		}

		// Regular stats can be high numbers - half them
		if ((obj->affected[i].location == APPLY_STR) ||
		    (obj->affected[i].location == APPLY_DEX) ||
		    (obj->affected[i].location == APPLY_INT) ||
		    (obj->affected[i].location == APPLY_WIS) ||
		    (obj->affected[i].location == APPLY_CON) ||
		    (obj->affected[i].location == APPLY_AGI))
		{
			// 1:2, 2:4, 3:6, 4:9, 5:16, 6:25, 7:36, 8:49, 9:64, 10:81, 11:100
			workingvalue += (mod <= 3) ? 2 * mod : (mod - 1) * (mod - 1);
		}

		// These are used a little less
		if ((obj->affected[i].location == APPLY_POW) ||
		    (obj->affected[i].location == APPLY_CHA) ||
		    (obj->affected[i].location == APPLY_LUCK))
		{
			// 1:2, 2:4, 3:6, 4:8, 5:10, 6:12, 7:15, 8:26, 9:39, 10:54, 11:71, 12:90, 13: 111
			workingvalue += (mod <= 6) ? 2 * mod : (mod - 2) * (mod - 2) - 10;
		}

		// Hitpoints.
		if (obj->affected[i].location == APPLY_HIT)
		{
			// 1 : 2, 4 : 8, 5 : 11, 10 : 29, 20 : 65, 30 : 101, 32 : 108.
			workingvalue += (mod <= 4) ? 2 * mod : (18 * mod) / 5 - 7;
		}

		// Moves and mana are generally large #'s
		if ((obj->affected[i].location == APPLY_MOVE) ||
		    (obj->affected[i].location == APPLY_MANA))
		{
			// 25 : 25, 35 : 65, 44 : 101, 45 : 105.
			workingvalue += (mod <= 25) ? mod : 4 * mod - 75;
		}

		// Hit, move, mana, regen are generally large #'s, but we don't want above 9.
		if ((obj->affected[i].location == APPLY_HIT_REG) ||
		    (obj->affected[i].location == APPLY_MOVE_REG) ||
		    (obj->affected[i].location == APPLY_MANA_REG))
		{
			// 1:1, 2:2, 3:3, 4:5, 5:8, 6:12, 7:16, 8:21, 9:27, 10:33
			// 11:40, 12:48, 13:56, 14:65, 15:75, 16:85, 17:96, 18:108
			workingvalue += (mod < 4) ? mod : (mod * mod) / 3;
		}

		// AC negative is good, not reducing itemvalue for items that make ac worse.
		if ((obj->affected[i].location == APPLY_AC) && mod != 0)
		{
			// 1.5 points for each point of armor class.
			// 1 : 1, 2 : 3, 3 : 4, 5 : 7, ... 50 : 75, 67 : 100, 68 : 102 (!craft), 70 : 105 (!enhance).
			if (mod < 0)
			{
				mod *= -1;
			}
			workingvalue += (3 * mod) / 2;
			// +10% at 50ac.
			apply_additions[i] = mod / 500.;
		}

		// saving throw values (good) are negative
		if ((obj->affected[i].location == APPLY_SAVING_PARA) ||
		    (obj->affected[i].location == APPLY_SAVING_ROD) ||
		    (obj->affected[i].location == APPLY_SAVING_FEAR) ||
		    (obj->affected[i].location == APPLY_SAVING_BREATH) ||
		    (obj->affected[i].location == APPLY_SAVING_SPELL))
		{
			// -1:2, -2:8, -3:18, -4:32, -5:50, -6:72, -7:98, -8:128
			workingvalue += mod * mod * ((mod <= 0) ? 2 : -2);
		}

		// pulse is quite valuable and negative is good
		if ((obj->affected[i].location == APPLY_COMBAT_PULSE) ||
		    (obj->affected[i].location == APPLY_SPELL_PULSE))
		{
			apply_factors[i] = 2;
			workingvalue += mod * -75;
		}

		// Max_stats double points
		if ((obj->affected[i].location == APPLY_STR_MAX) ||
		    (obj->affected[i].location == APPLY_DEX_MAX) ||
		    (obj->affected[i].location == APPLY_INT_MAX) ||
		    (obj->affected[i].location == APPLY_WIS_MAX) ||
		    (obj->affected[i].location == APPLY_CON_MAX) ||
		    (obj->affected[i].location == APPLY_CHA_MAX) ||
		    (obj->affected[i].location == APPLY_AGI_MAX) ||
		    (obj->affected[i].location == APPLY_POW_MAX) ||
		    (obj->affected[i].location == APPLY_LUCK_MAX))
		{
			// 1:3, 2:13, 3:24, 4:36, 5:51, 6:66, 7:83, 8:100
			workingvalue += (mod < 2) ? 3.0 * mod : 3.52 * mod * sqrt(mod) + mod;
			apply_additions[i] = .15;
		}
	}
	// Apply additions precede apply factors. Keep the existing wear/flag prefix
	// and weapon/armor/two-hand stages in their original positions.
	for (int i : order)
		multiplier += apply_additions[i];
	for (int i : order)
		multiplier *= apply_factors[i];

	const double applies_base =
		workingvalue - flags_base - packed_credit - context.native_proc_credit;
	const double after_applies = multiplier;
	if (obj->type == ITEM_WEAPON)
	{
		// Negative dice deal no damage; they must not flip the multiplier's sign.
		const double dice_count = std::max(obj->value[1], 0);
		const double dice_sides = std::max(obj->value[2], 0);
		const double maximum_damage = dice_count * dice_sides;
		// Maximum dice damage is the historical valuation term.
		workingvalue += maximum_damage;
		// 1d1 = .5%, 5d5 = 12.5%, 10d10 = 50%.
		multiplier += maximum_damage * .005;
		// Backstabbing weapons get a big ival for big dice.
		if (IS_BACKSTABBER(obj))
		{
			mod = dice_sides;
			// workingvalue increases quadratic for every die roll and cubic for dice size.
			// For number of dice: 1:1, 2:1.15, 3:1.4, 4:1.75, 5:2.2, 6:2.75, 7:3.4, 8:4.15, 9:5, 10:5.95
			// For number of die sides: 1:0, 2:1, 3:5, 4:12, 5:25, 6:43, 7: 68, 8:102, 9:145, 10: 200
			// So, 1d8 / 3d7 stabber is !forge and !enhance (115 ival when combined with above).
			workingvalue +=
				((dice_count * dice_count + 19.) / 20.) * (mod * mod * mod) / 5.;
		}
	}
	if (obj->type == ITEM_ARMOR)
	{
		mod = obj->value[0];
		// Same as APPLY_AC.  1.5 points for each point of armor class.
		if (mod < 0)
		{
			mod *= -1;
		}
		workingvalue += (3 * mod) / 2;
		// +10% at 50ac.
		multiplier += mod / 500.;
	}

	const double type_base = workingvalue - flags_base - packed_credit -
				 context.native_proc_credit - applies_base;
	const double after_type = multiplier;
	// Two handed items have less ival.
	if ((obj->extra_flags & ITEM_TWOHANDS))
	{
		multiplier *= .80;
	}

	const double unrounded = workingvalue * multiplier;
	const bool floored = unrounded < 1;
	const bool utility_override =
		context.native_proc_policy == item_value_proc_policy::utility ||
		(!(obj->wear_flags & ITEM_TAKE) && obj->type == ITEM_TELEPORT) ||
		obj->type == ITEM_KEY || obj->type == ITEM_SWITCH || obj->type == ITEM_VEHICLE ||
		obj->type == ITEM_SHIP || obj->type == ITEM_STORAGE;
	const bool invalid = !std::isfinite(workingvalue) || !std::isfinite(multiplier) ||
			     !std::isfinite(unrounded) ||
			     (!utility_override && unrounded > INT_MAX);
	int score = 0;
	// Quantize once after every base credit and multiplier, truncating toward zero.
	if (!invalid)
		score = utility_override || floored ? 1 : static_cast<int>(unrounded);
	if (breakdown)
	{
		*breakdown = { workingvalue,	 multiplier, unrounded, floored,
			       utility_override, score,	     invalid };
		breakdown->native_proc_policy = context.native_proc_policy;
		breakdown->packed_credit = packed_credit;
		breakdown->packed_cast_mask = packed_cast_mask;
		breakdown->flags_base = flags_base;
		breakdown->applies_base = applies_base;
		breakdown->type_base = type_base;
		breakdown->native_base = context.native_proc_credit;
		breakdown->after_wear = after_wear;
		breakdown->after_flags = after_flags;
		breakdown->after_applies = after_applies;
		breakdown->after_type = after_type;
		item_value_coverage(input, *breakdown);
	}
	return score;
}
