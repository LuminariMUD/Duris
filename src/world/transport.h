/****************************************************************************
 *
 *  File: transport.h                                           Part of Duris
 *  Usage: transport snapshot type and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _TRANSPORT_H_
#define _TRANSPORT_H_

struct transport_snapshot
{
	int origin;
	int destination;
	int state;
	int step;
	char rider[50];
};

void transport_capture(P_char mob, transport_snapshot *snapshot);
void transport_restore(P_char mob, const transport_snapshot &snapshot);
void initialize_transport();
int flying_transport(P_char ch, P_char victim, int cmd, char *arg);
void event_flying_transport_move(P_char ch, P_char victim, P_obj obj, void *data);
void event_flying_transport_return(P_char ch, P_char victim, P_obj obj, void *data);

#endif // _TRANSPORT_H_
