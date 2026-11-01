#!/usr/bin/env python3
"""Exercise actual copyover version gates and historical NPC record sizes."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "src/persistence/copyover.c").read_text()
header = (ROOT / "src/persistence/copyover.h").read_text()

def function(signature):
    start = source.index(signature)
    cursor = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[cursor] == "{") - (source[cursor] == "}")
        cursor += 1
    return source[start:cursor]

legacy = header[header.index("struct copyover_mob\n"):header.index("// affect data for copyover")]
legacy = legacy.replace("struct copyover_mob", "struct copyover_mob_v15")
legacy = "\n".join(line for line in legacy.splitlines() if "shopkeeper_shop_id" not in line)
program = r'''
#include "persistence/copyover.h"
#include <cassert>
#include <cstddef>
#include <cstdio>
#include <cstring>
const char *copyover_state_file() { return "compat-copyover.dat"; }
static const copyover_boot_snapshot *selected=nullptr;
const copyover_boot_snapshot *copyover_boot_evidence() { return selected; }
copyover_boot_result copyover_boot_state() { return selected ? copyover_boot_result::ready : copyover_boot_result::unprepared; }
'''+legacy+"\n"+"\n".join(function(s) for s in (
    "static bool copyover_version_supported(",
    "static size_t copyover_mob_bytes_for_version(",
    "bool copyover_has_durable_shopkeepers(",
))+r'''
int main() {
    static_assert(sizeof(copyover_mob_v15) == offsetof(copyover_mob, shopkeeper_shop_id));
    assert(!copyover_version_supported(11));
    assert(!copyover_version_supported(COPYOVER_VERSION+1));
    for (int version=12; version<=COPYOVER_VERSION; ++version) {
        assert(copyover_version_supported(version));
        assert(copyover_mob_bytes_for_version(version) ==
               (version==12 ? offsetof(copyover_mob_v15, transport) :
                version<16 ? sizeof(copyover_mob_v15) : sizeof(copyover_mob)));
        copyover_header h={};
        memcpy(h.magic, COPYOVER_MAGIC, 4); h.version=version;
        FILE *f=fopen(COPYOVER_FILE,"wb"); assert(f);
        assert(fwrite(&h,sizeof(h),1,f)==1); assert(fclose(f)==0);
        assert(copyover_has_durable_shopkeepers() == (version>=13));
    }
    assert(remove(COPYOVER_FILE)==0);
    puts("copyover versions 12-18: record widths and durable shopkeeper provenance PASS");
}
'''
db = (ROOT / "src/world/db.c").read_text()
selection_start = db.index("if (!copyover_boot || copyover_has_durable_shopkeepers() ||")
selection = db[selection_start:db.index("remember_boot_shopkeepers();", selection_start)]
setup = r"""
int copyover_boot=0, backend=0, restored_shops=0;
constexpr int PERSISTENCE_MODE_FLATFILE_PRIMARY=1;
int persistence_mode_get() { return backend; }
void restore_shopkeepers() { ++restored_shops; }
void restore_selected_stock() {
"""+selection+r"""
}
"""
checks = r"""
    for(backend=0;backend<2;++backend) {
        copyover_boot=0; selected=nullptr; restored_shops=0;
        restore_selected_stock(); assert(restored_shops==1);
        copyover_boot=1;
        for(int version=12;version<=COPYOVER_VERSION;++version) {
            copyover_boot_snapshot snapshot; snapshot.header.version=version; selected=&snapshot;
            restored_shops=0; restore_selected_stock();
            assert(restored_shops==(backend==PERSISTENCE_MODE_FLATFILE_PRIMARY || version>=13));
        }
    }
    selected=nullptr;
"""
program=program.replace("int main() {",setup+"\nint main() {")
program=program.replace('    puts("copyover versions',checks+'    puts("copyover versions')
with tempfile.TemporaryDirectory(prefix="duris-shop-copyover-") as tmp:
    p=Path(tmp); (p/"test.cpp").write_text(program)
    subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-I",str(ROOT/"src"),str(p/"test.cpp"),"-o",str(p/"test")],check=True)
    subprocess.run([str(p/"test")],cwd=p,check=True)
