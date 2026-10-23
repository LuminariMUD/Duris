// Isolated journey only: advance the real server across a UTC hour without waiting.
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

time_t time(time_t *value)
{
	struct timespec now;
	if (clock_gettime(CLOCK_REALTIME, &now))
		return (time_t)-1;
	long instant = 0;
	const char *path = getenv("DURIS_TEST_CLOCK_FILE");
	FILE *file = path ? fopen(path, "r") : NULL;
	if (file)
	{
		if (fscanf(file, "%ld", &instant) != 1)
			instant = 0;
		fclose(file);
	}
	time_t result = instant > 0 ? instant : now.tv_sec;
	if (value)
		*value = result;
	return result;
}
