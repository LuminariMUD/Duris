/* Test-only lost COMMIT reply for the disposable recovery journey. The marker
 * holds the reply until the controller has checked storage and live sessions. */
#define _GNU_SOURCE
#include <mysql/mysql.h>
#include <dlfcn.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static _Thread_local MYSQL *recovery_connection;
static _Thread_local MYSQL *lost_reply_connection;

unsigned int STDCALL mysql_errno(MYSQL *connection)
{
	typedef unsigned int (*errno_fn)(MYSQL *);
	errno_fn real_errno = (errno_fn)dlsym(RTLD_NEXT, "mysql_errno");
	if (!real_errno)
		_exit(125);
	return connection == lost_reply_connection ? 2013 : real_errno(connection);
}

int STDCALL mysql_real_query(MYSQL *connection, const char *query, unsigned long length)
{
	typedef int (*query_fn)(MYSQL *, const char *, unsigned long);
	query_fn real_query = (query_fn)dlsym(RTLD_NEXT, "mysql_real_query");
	if (!real_query)
		_exit(125);
	lost_reply_connection = NULL;
	const int committing = connection == recovery_connection && length == 6 &&
			       !memcmp(query, "COMMIT", 6);
	const char *arm = getenv("DURIS_TEST_RECOVERY_COMMIT_FAULT");
	FILE *control = committing && arm ? fopen(arm, "r") : NULL;
	if (control)
	{
		const int before = fgetc(control) == 'b';
		fclose(control);
		const int result = before ? real_query(connection, "ROLLBACK", 8) :
					    real_query(connection, query, length);
		if (result)
			_exit(125);
		recovery_connection = NULL;
		char marker[PATH_MAX];
		if (snprintf(marker, sizeof(marker), "%s.reached", arm) >= (int)sizeof(marker))
			_exit(125);
		FILE *reached = fopen(marker, "w");
		if (!reached)
			_exit(125);
		fclose(reached);
		for (unsigned int waits = 0; access(arm, F_OK) == 0; ++waits)
		{
			if (waits == 12000)
				_exit(125);
			usleep(10000);
		}
		shutdown(mysql_get_socket(connection), SHUT_RDWR);
		lost_reply_connection = connection;
		return 1;
	}
	const int result = real_query(connection, query, length);
	const char update[] = "UPDATE accounts SET password=";
	if (!result && length >= sizeof(update) - 1 && !memcmp(query, update, sizeof(update) - 1))
		recovery_connection = connection;
	if (committing || (length == 8 && !memcmp(query, "ROLLBACK", 8)))
		recovery_connection = NULL;
	return result;
}
