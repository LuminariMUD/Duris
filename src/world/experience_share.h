#ifndef EXPERIENCE_SHARE_H
#define EXPERIENCE_SHARE_H

struct char_data;

// Combat producers retain their fractional share for qualifying Divine awards.
// All other awards use the producer's exact existing integer calculation.
int gain_exp_combat_share(char_data *recipient, char_data *victim, double precise_share,
			  int ordinary_share, int type);

#endif
