#ifndef DURIS_PWIPE_LAUNCH_H
#define DURIS_PWIPE_LAUNCH_H

#include <ctime>
#include <string>

/* Loaded once before listeners or copyover recovery. Failure leaves admission closed. */
bool pwipe_launch_load(const char *path, std::string &error);
bool pwipe_launch_closed_at(time_t now);
bool pwipe_launch_allows_at(const char *account_name, time_t now);
const std::string &pwipe_launch_opens_utc();
std::string pwipe_launch_status(time_t now);

struct descriptor_data;
std::string pwipe_launch_notice();
std::string pwipe_launch_screen(bool color);
/* Call only at authenticated pre-entry boundaries, never as proof of authentication. */
bool pwipe_launch_admit(descriptor_data *d);
void pwipe_launch_deny(descriptor_data *d);

#endif
