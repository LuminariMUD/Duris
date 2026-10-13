#!/usr/bin/env python3
"""Real artifact/guild snapshots, dirty retries and cache-generation fences."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, HARNESS_STUBS, extract_function

out=ROOT/'bin/tests'
out.mkdir(parents=True,exist_ok=True)
source=(ROOT/'tests/async/artifact_guild_snapshots.cpp').read_text()
utility=(ROOT/'src/core/utility.c').read_text()
reporter=utility[utility.index('static int persistence_alert_format_is_numeric('):utility.index('unsigned long long persistence_next_item_uid(')]
source=source.replace('// PERSISTENCE_REPORTER', reporter)
# Link the real guild methods; extract only their SQL builders to avoid linking
# unrelated account/player loading. Both functions retain their actual bodies.
source=source.replace('// GUILD_SQL_CAPTURE',
    extract_function('sql_player.c','std::vector<std::string> sql_save_guild_statements(Guild *guild)')+'\n'+
    extract_function('sql_player.c','/* Save one guild: its statements are one writer job. */\nbool sql_save_guild(Guild *guild)'))
with tempfile.TemporaryDirectory(prefix='artifact-snapshots-',dir=out) as directory:
    cpp=Path(directory)/'snapshot.cpp'; binary=Path(directory)/'snapshot'
    cpp.write_text(source)
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-pthread',
        '-ffunction-sections','-fdata-sections','-Isrc','-I/usr/include/mysql',
        str(cpp),'src/guild/assocs.c','src/core/safe_format.c',str(HARNESS_STUBS),
        '-Wl,--gc-sections','-lcjson','-lmysqlclient','-o',str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],check=True,timeout=30)
