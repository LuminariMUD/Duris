#include "combat/combat_outcome_intent.h"
#include "persistence/critical_command_coordinator.h"
#include "player/player_save_worker.h"

#include <cassert>
#include <filesystem>
#include <fstream>
#include <poll.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

// Exercise the real queue boundary in a killed process, then recover the exact
// command through each native repository, including a failed repair attempt.
template <class Apply, class Corrupt, class Repair>
critical_apply_result check_combat_intent_recovery(const critical_command &command, Apply apply,
						   Corrupt corrupt, Repair repair)
{
	char parent[] = "/tmp/duris-combat-intent-XXXXXX";
	assert(mkdtemp(parent));
	int ready[2];
	assert(pipe(ready) == 0);
	const pid_t child = fork();
	assert(child >= 0);
	if (!child)
	{
		close(ready[0]);
		std::vector<critical_command> retained;
		assert(combat_outcome_intent_init(parent, &retained) && retained.empty());
		assert(combat_outcome_intent_write(command));
		assert(player_save_worker_init(
			[](const player_snapshot &, void *) {
				return player_save_apply_result{ player_save_apply_outcome::applied,
								 0, 0 };
			},
			nullptr));
		assert(critical_command_coordinator_init(
			[](const critical_command &, void *context) -> critical_apply_result
			{
				const int fd = *static_cast<int *>(context);
				const char byte = 'q';
				assert(write(fd, &byte, 1) == 1);
				for (;;)
					pause(); // Killed after enqueue, before any repository commit.
			},
			&ready[1]));
		assert(critical_command_coordinator_submit(command) ==
		       critical_submit_result::accepted);
		for (;;)
			pause();
	}
	close(ready[1]);
	pollfd readable{ ready[0], POLLIN, 0 };
	const bool enqueued = poll(&readable, 1, 10000) == 1 && (readable.revents & POLLIN);
	assert(kill(child, SIGKILL) == 0);
	int status;
	assert(waitpid(child, &status, 0) == child && WIFSIGNALED(status) &&
	       WTERMSIG(status) == SIGKILL);
	close(ready[0]);
	assert(enqueued);
	std::vector<critical_command> retained;
	assert(combat_outcome_intent_init(parent, &retained) && retained.size() == 1);
	assert(critical_command_equal(retained[0], command));
	corrupt();
	const auto failed = apply(retained[0]);
	assert((failed.outcome == critical_apply_outcome::terminal_failure ||
		failed.outcome == critical_apply_outcome::retryable_failure) &&
	       !failed.result_size);
	combat_outcome_intent_shutdown(); // The failed command survives another restart.
	retained.clear();
	assert(combat_outcome_intent_init(parent, &retained) && retained.size() == 1);
	assert(critical_command_equal(retained[0], command));
	repair();
	const auto recovered = apply(retained[0]);
	assert(recovered.outcome == critical_apply_outcome::applied);
	assert(apply(retained[0]).outcome == critical_apply_outcome::already_applied);
	assert(combat_outcome_intent_complete(command.operation_id));
	combat_outcome_intent_shutdown();
	assert(combat_outcome_intent_init(parent, &retained) && retained.empty());
	char reference[CRITICAL_COMMAND_ID_HEX_SIZE];
	assert(critical_operation_id_to_hex(command.operation_id, reference, sizeof(reference)));
	assert(std::filesystem::is_regular_file(std::filesystem::path(parent) / "combat-intents" /
						(std::string(reference) + ".recorded")));
	combat_outcome_intent_shutdown();
	const auto recorded = std::filesystem::path(parent) / "combat-intents" /
			      (std::string(reference) + ".recorded");
	std::ifstream file(recorded, std::ios::binary);
	std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)), {});
	critical_command original;
	assert(bytes.size() > 32 &&
	       critical_command_decode(bytes.data(), bytes.size() - 32, &original) ==
		       critical_command_codec_result::ok &&
	       critical_command_equal(original, command));
	file.close();
	const auto damaged = recorded.parent_path() / (std::string(reference) + ".intent");
	std::filesystem::rename(recorded, damaged);
	std::fstream corrupt_file(damaged, std::ios::binary | std::ios::in | std::ios::out);
	char byte;
	corrupt_file.read(&byte, 1);
	byte ^= 1;
	corrupt_file.seekp(0);
	corrupt_file.write(&byte, 1);
	corrupt_file.close();
	assert(!combat_outcome_intent_init(parent, &retained));
	assert(std::filesystem::is_regular_file(damaged)); // Fail closed without deleting evidence.
	std::filesystem::remove_all(parent);
	return recovered;
}
