/*
 * mssp.h - refusal of population-bearing MSSP negotiation
 */

#ifndef _MSSP_H_
#define _MSSP_H_

#include "core/structs.h"

#define TELOPT_MSSP 70

void mssp_send(P_desc d);

#endif /* _MSSP_H_ */
