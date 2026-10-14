/*
 * mssp.h - MUD Server Status Protocol, so MUD listing crawlers can read game status
 */

#ifndef _MSSP_H_
#define _MSSP_H_

#include "core/structs.h"

#define TELOPT_MSSP 70
#define MSSP_VAR 1
#define MSSP_VAL 2

void mssp_advertise(P_desc d);
void mssp_send(P_desc d);

#endif /* _MSSP_H_ */
