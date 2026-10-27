#!/usr/bin/env python3
"""Run real send/act/queue/pager functions with production types and boundary stubs."""
import os
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function
from _paths import HARNESS_STUBS

BUILD = ROOT / "bin/tests"
BUILD.mkdir(parents=True, exist_ok=True)
comm = (ROOT / "src/net/comm.c").read_text()
globals_start = comm.index("#define MAX_COMMAND_OUTPUT")
globals_end = comm.index("#define MIN_SOCKET_BUFFER_SIZE", globals_start)
functions = [comm[globals_start:globals_end],
             extract_function("comm.c", "void write_to_pc_log(").replace("void write_to_pc_log(", "void production_write_to_pc_log("),
             extract_function("comm.c", "void initialize_logs("),
             extract_function("comm.c", "void clear_logs(")]
for filename, signatures in [
    ("utility.c", ["int yes_no(", "int strn_cmp(", "bool is_ansi_char(", "void CAP(char *str)", "int BOUNDED(int a, int b, int c)"]),
    ("interp.c", ["int old_search_block(", "int search_block(", "int fill_word(", "char *one_argument(", "char *lohrr_chop(", "bool is_abbrev(", "static int input_command_number(", "bool input_is_afk_toggle("]),
    ("actoth.c", ["static const char *term_name(", "void show_toggles(", "static int plr_tog(", "void do_toggle("]),
    ("comm.c", ["static void note_player_input_activity(P_desc t, const char *input)\n{", "int get_from_q(", "void write_to_q(", "void escape_act_dollars(", "void delete_doubledollar(",
                "static void finalize_styled_command(", "void process_with_paging(",
                "bool send_paged_text(", "void send_to_char_f(P_char ch, const char *fmt, ...)",
                "void send_to_char_f(P_char ch, const OutputContext &context, const char *fmt, ...)",
                "void send_to_char(const char *messg, P_char ch)",
                "void send_to_char(const char *messg, P_char ch, const OutputContext &context)",
                "void send_to_char(const char *messg, P_char ch, int log)",
                "void send_to_char(const char *messg, P_char ch, int log, const OutputContext &context)",
                "void act(const char *str, int hide_invisible, P_char ch, P_obj obj, void *vict_obj, int type)",
                "void act(const char *str, int hide_invisible, P_char ch, P_obj obj, void *vict_obj, int type,",
                "void format_to_snoopers(char *from_string, char *to_string)\n{"]),
    ("modify.c", ["char *next_page(", "void free_paging_data(", "void show_string(", "void page_string_real("]),
    ("actcomm.c", ["void do_tell(", "void do_reply(", "int say(", "void do_gcc(", "void do_whisper(", "void do_ask("]),
    ("actnew.c", ["void do_gsay("]),
    ("alliances.c", ["void do_acc("]),
    ("actinf.c", ["void do_news(", "char *show_obj_to_char(P_obj object, P_char ch, int mode, bool print)",
                  "char *show_obj_to_char(P_obj object, P_char ch, int mode, bool print,",
                  "void list_obj_to_char(P_obj list, P_char ch, int mode, bool show)",
                  "void list_obj_to_char(P_obj list, P_char ch, int mode, bool show,",
                  "void show_exits_to_char(", "void display_room_auras("]),
    ("weather.c", ["void send_to_weather_sector("]),
    ("fight.c", ["void dam_message(", "static combat_outcome_participant *combat_outcome_add_participant("]),
    ("specs.object.c", ["int totem_of_mastery(", "int circlet_of_light("]),
    ("prompt.c", ["void make_prompt("]),
    ("player_load_materialize.c", ["bool apply_string("]),
    ("json_utils.c", ["char *json_build_comm_channel("]),
    ("gmcp.c", ["void gmcp_broadcast_channel("])
]:
    functions.extend(extract_function(filename, signature) for signature in signatures)

# Execute the login-announcement block verbatim without booting a world/database.
nanny = (ROOT / "src/account/nanny.c").read_text()
notice = nanny.index("has just logged on.")
start = nanny.rfind("\tif (!IS_TRUSTED(ch))", 0, notice)
end = nanny.index("\n\t// inform gods that a newbie", notice)
functions.append("static void login_notice(P_char ch) { char Gbuf1[MAX_STRING_LENGTH]; P_desc i;\n" + nanny[start:end] + "\n}")

actoth = (ROOT / "src/cmd/actoth.c").read_text()
arrays = actoth[actoth.index("static const char *toggles_list[]"):actoth.index("void do_more(")]
functions.insert(0, '#define ONOFF(a) ((a) ? "ON" : "OFF")\n#define TOG_OFF 0\n#define TOG_ON 1\n' + arrays)
functions.insert(0, "#define PLR_TOG(flag) plr_tog(PLR_FLAGS(ch), flag, arg)\n#define PLR2_TOG(flag) plr_tog(PLR2_FLAGS(ch), flag, arg)\n#define PLR3_TOG(flag) plr_tog(PLR3_FLAGS(ch), flag, arg)")

functions.insert(0, extract_function("interp.c", "const char *command[MAX_CMD]") + ";")
functions.insert(0, extract_function("interp.c", "const char *fill_words[]") + ";")

benchmark = os.environ.get("OUTPUT_BENCHMARK") == "1"

flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie"] if os.environ.get("SANITIZE") == "1" else []
if benchmark:
    flags += ["-DCOLORIZATION_BENCHMARK", "-Wl,--wrap=malloc", "-Wl,--wrap=calloc", "-Wl,--wrap=realloc"]
with tempfile.TemporaryDirectory(prefix="word-output-", dir=BUILD) as directory:
    temp = Path(directory)
    (temp / "production_output.inc").write_text("\n\n".join(functions))
    binary = temp / "harness"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Og", "-g", "-D__NO_MYSQL__", *flags,
        f"-I{ROOT / 'src'}", f"-I{ROOT / 'src/no_mysql'}", f"-I{temp}",
        str(ROOT / "tests/async/word_output_integration_harness.cpp"),
        str(ROOT / "src/combat/combat_outcome_command.c"), str(ROOT / "src/guild/artifact_guild_command.c"), str(ROOT / "src/persistence/critical_command.c"),
        str(ROOT / "src/economy/currency_command.c"), str(ROOT / "src/net/ansi.c"), str(ROOT / "src/net/unicode.c"),
        str(ROOT / "src/net/chat_presentation.c"),
        str(ROOT / "src/net/output_style.c"), str(ROOT / "src/core/safe_format.c"),
        str(ROOT / "src/net/output_profiles.c"), str(ROOT / "src/player/output_preferences.c"),
        str(ROOT / "src/player/output_message.c"), str(ROOT / "src/player/news.c"),
        str(ROOT / "src/flatfile/flatfile_help_catalog.c"), "-lcrypto", "-lcjson", "-pthread", str(HARNESS_STUBS), "-o", str(binary)
    ], check=True, timeout=120)
    subprocess.run([str(binary)], check=True, timeout=120)
