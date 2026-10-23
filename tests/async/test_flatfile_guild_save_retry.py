#!/usr/bin/env python3
"""A failed real synchronous guild save stays dirty and retries its current snapshot."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function
functions = "\n".join(extract_function("guild/assocs.c", signature) for signature in
    ("bool Guild::save()", "bool Guild::save_pending(", "bool Guild::apply_delivery("))
harness = r'''#include <algorithm>
#include <array>
#include <cassert>
#include <climits>
#include <cstdint>
#include <string>
#include <vector>
#define __NO_MYSQL__
#define AVATAR 1
struct critical_operation_id {std::array<uint8_t,16> bytes{};};
constexpr size_t ARTIFACT_GUILD_PENDING_MAX=256;
struct flatfile_association_record {};
enum class flatfile_association_result {ok, unchanged, io_error};
bool failing=true; int writes=0; unsigned long stored=0;
const char *persistence_mode_flatfile_root() {return "fixture";}
void persistence_alert(int,const char *,const char *,const char *,const char *,const char *,const char *,...) {}
struct Guild {
 const char *name="fixture"; unsigned id_number=7;
 unsigned long prestige=95,construction=0; bool save_dirty=false;
 std::vector<std::array<uint8_t,16>> delivery_ids;
 bool build_flatfile_record(const std::string &,flatfile_association_record *,std::string *) {return true;}
 bool save(); bool save_pending(bool); bool apply_delivery(const critical_operation_id &,uint64_t,uint64_t);
};
Guild *current;
flatfile_association_result flatfile_association_save(const std::string &,const flatfile_association_record &,std::string *) {
 ++writes; if(failing)return flatfile_association_result::io_error;
 stored=current->prestige; return flatfile_association_result::ok;
}
// METHODS
int main() {
 Guild guild; current=&guild;
 critical_operation_id id{}; id.bytes.back()=1;
 assert(guild.apply_delivery(id,20,100));
 assert(guild.prestige==115 && guild.construction==1 && guild.save_pending(false));
 assert(guild.save_pending(true) && writes==2);
 guild.prestige-=7; failing=false;
 assert(!guild.save_pending(true) && writes==3 && stored==108);
 assert(guild.apply_delivery(id,20,100) && guild.prestige==108 && writes==3);
}
'''
out=ROOT/"bin/tests";out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="guild-retry-",dir=out) as directory:
    source=Path(directory)/"retry.cpp";binary=Path(directory)/"retry"
    source.write_text(harness.replace("// METHODS", functions))
    subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-fsanitize=address,undefined","-fno-pie","-no-pie",str(source),"-o",str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
print("PASS failed flat guild snapshot retries without repeating delivery or losing later spending")
