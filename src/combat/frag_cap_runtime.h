#ifndef DURIS_FRAG_CAP_RUNTIME_H
#define DURIS_FRAG_CAP_RUNTIME_H

#include "combat/frag_cap.h"
#include <string>

// Boot adopts/settles durable authority before ordinary gameplay is admitted.
bool frag_cap_runtime_boot(int64_t now);
// Game-thread calls only. Refresh observes committed state on the existing writer.
void frag_cap_runtime_refresh();
void frag_cap_runtime_pulse();
const frag_cap_state *frag_cap_runtime_state();
std::string frag_cap_runtime_status(uint32_t faction, int64_t now);

#endif
