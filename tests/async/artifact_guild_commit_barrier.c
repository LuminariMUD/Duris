/* Test-only interposer: hold the writer after a real type-9 COMMIT and before
 * the repository can publish its completion. Loaded only by the crash journey. */
#define _GNU_SOURCE
#include <mysql/mysql.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static _Thread_local MYSQL *history_connection;

int STDCALL mysql_real_query(MYSQL *connection, const char *query, unsigned long length)
{
	typedef int (*query_fn)(MYSQL *, const char *, unsigned long);
	query_fn real_query = (query_fn)dlsym(RTLD_NEXT, "mysql_real_query");
	if (!real_query)
		_exit(125);
	const int result = real_query(connection, query, length);
	const char history_insert[] = "INSERT INTO artifact_guild_outcome(";
	if (!result && length >= sizeof(history_insert) - 1 &&
	    !memcmp(query, history_insert, sizeof(history_insert) - 1))
		history_connection = connection;
	if (length == 8 && !memcmp(query, "ROLLBACK", 8))
		history_connection = NULL;
	if (!result && connection == history_connection && length == 6 &&
	    !memcmp(query, "COMMIT", 6))
	{
		history_connection = NULL;
		const char *arm = getenv("DURIS_TEST_ARTIFACT_COMMIT_BARRIER");
		if (arm && access(arm, F_OK) == 0)
		{
			char marker[PATH_MAX];
			if (snprintf(marker, sizeof(marker), "%s.committed", arm) >=
			    (int)sizeof(marker))
				_exit(125);
			const int file = open(marker, O_WRONLY | O_CREAT | O_TRUNC, 0600);
			if (file < 0 || write(file, "committed\n", 10) != 10)
				_exit(125);
			close(file);
			for (unsigned int waits = 0; access(arm, F_OK) == 0; ++waits)
			{
				if (waits == 12000)
					_exit(125); // A lost test controller must not leave a held writer.
				usleep(10000);
			}
		}
	}
	return result;
}
