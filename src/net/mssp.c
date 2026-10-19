/* MSSP requires a current PLAYERS count. Refuse it while public population is
 * private; a delayed count would misrepresent the protocol's meaning. */
#include "net/mssp.h"
#include "core/prototypes.h"
#include "net/telnet.h"

void mssp_send(P_desc d)
{
	static const unsigned char wont_mssp[] = { IAC, WONT, TELOPT_MSSP };

	if (!d || d->websocket || d->mssp_sent)
		return;
	d->mssp_sent = 1;
	write_to_descriptor_binary(d, wont_mssp, sizeof wont_mssp);
}
