// Native mail producer/index/reader and memory pool. Process invocations model
// separate boots; presentation/networking and allocation bookkeeping are excluded.
#include "core/prototypes.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <unistd.h>

int no_mail = 0;
void fatal_boot_error(const char *, const char *, ...)
{
	std::abort();
}
void *__malloc(size_t size, const char *, const char *, int)
{
	return calloc(1, size);
}
void *__realloc(void *pointer, size_t size, const char *, int)
{
	return realloc(pointer, size);
}
void __free(void *pointer, const char *, int)
{
	free(pointer);
}

int main(int argc, char **argv)
{
	assert(argc == 3 && chdir(argv[1]) == 0);
	assert(scan_mail_file() && !no_mail);
	char recipient[] = "reusedname", sender[] = "oldsender";
	std::string old_text = "OLD CHARACTER PRIVATE MAIL " + std::string(400, 'x');
	if (!strcmp(argv[2], "seed"))
	{
		store_mail(recipient, sender, old_text.data());
		assert(has_mail(recipient) && !no_mail);
	}
	else if (!strcmp(argv[2], "old"))
	{
		// A new character's PID/account is never passed to this reader. A reused
		// name alone can select the previous character's complete message.
		assert(has_mail(recipient));
		char *message = read_delete(recipient, recipient);
		assert(message && strstr(message, old_text.c_str()));
		__free(message, __FILE__, __LINE__);
	}
	else
	{
		assert(!strcmp(argv[2], "fresh") && !has_mail(recipient));
		std::string fresh = "FRESH SEASON MESSAGE";
		store_mail(recipient, sender, fresh.data());
		assert(has_mail(recipient));
		char *message = read_delete(recipient, recipient);
		assert(message && strstr(message, fresh.c_str()) &&
		       !strstr(message, "OLD CHARACTER"));
		__free(message, __FILE__, __LINE__);
		assert(!has_mail(recipient));
	}
	std::cout << "PASS actual native mail " << argv[2] << '\n';
}
