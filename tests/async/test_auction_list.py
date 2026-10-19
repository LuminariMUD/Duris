#!/usr/bin/env python3
"""Execute SQL auction-list formatting with production fortification enabled."""
from pathlib import Path
import resource
import subprocess
import tempfile

from _paths import ROOT, SRC, extract_function


HARNESS = r'''
#include "core/safe_format.h"
#include <cassert>
#include <cctype>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sstream>
#include <string>
#include <vector>
using namespace std;
#define MAX_STRING_LENGTH 65536
#define MAX_INPUT_LENGTH 2048
#define TRUE 1
#define LOG_SYS 0
#define AUCTION_STATUS_OPEN 1
static_assert(__USE_FORTIFY_LEVEL == 3);
using P_char = void *;
char buff[MAX_STRING_LENGTH];
void *DB = nullptr;
vector<string> output, queries;
struct EqSort {
    vector<string> keywords = {"horns", "nose", "head"};
    string getKeyword(int i) { return keywords.at(i); }
    int getSize() { return keywords.size(); }
    bool isKeyword(const char *key) {
        for (const auto &word : keywords) if (word == key) return true;
        return false;
    }
    string getDescString(const char *key) { return key; }
} catalogue, *sorter = &catalogue;
void logit(int, const char *, ...) { abort(); }
void send_to_char(const char *text, P_char) { output.emplace_back(text); }
bool isname(const char *key, const char *names) {
    istringstream input(names); string word;
    while (input >> word) if (word == key) return true;
    return false;
}
unsigned long mysql_real_escape_string(void *, char *dest, const char *src, unsigned long n) {
    memcpy(dest, src, n); dest[n] = 0; return n;
}
using sql_row = vector<string>;
using sql_rows = vector<sql_row>;
string sql_format(const char *format, ...) {
    char query[MAX_STRING_LENGTH * 2];
    va_list args;
    va_start(args, format);
    int length = vsnprintf(query, sizeof(query), format, args);
    va_end(args);
    assert(length >= 0 && static_cast<size_t>(length) < sizeof(query));
    return query;
}
void auction_list_row(P_char, const sql_row &) { abort(); }
template<class Callback> bool sql_read_for(P_char ch, string query, Callback callback) {
    queries.push_back(query);
    callback(ch, sql_rows{});
    return true;
}
'''

CHECKS = r'''
void run(const string &input) {
    char args[MAX_STRING_LENGTH] = {};
    assert(input.size() < MAX_INPUT_LENGTH);
    strcpy(args, input.c_str());
    memset(buff, 'X', sizeof(buff)); // Do not rely on an already-empty display buffer.
    output.clear(); queries.clear();
    assert(auction_list(nullptr, args));
}
void help(const string &input, bool syntax) {
    run(input);
    assert(queries.empty());
    assert(output.size() == (syntax ? 2 : 1));
    if (syntax) assert(output.front().find("Auction list syntax:") != string::npos);
    string expected = "&+WValid keywords: &+Y" + catalogue.keywords.front();
    for (size_t i = 1; i < catalogue.keywords.size(); ++i)
        expected += ", " + catalogue.keywords[i];
    expected += ".\n\r";
    assert(output.back() == expected.substr(0, sizeof(buff) - 1));
    assert(buff[output.back().size()] == '\0');
}
int main() {
    for (const char *input : {"plate 1000", "plate", "1", "nonsense", "%s%n", "unknown extra args"})
        help(input, true);
    help("sort", false);
    help("s", false);
    for (const char *input : {"", "all", "a"}) {
        run(input);
        assert(queries.size() == 1);
        assert(queries.front().find("where status = 1  order by") != string::npos);
        assert(output.front() == "&+WAuctions closing soon:\r\n");
        assert(output.back().find("No auctions") != string::npos);
    }
    run("player synthetic");
    assert(queries.size() == 1);
    assert(queries.front().find("and seller_name like 'Synthetic'") != string::npos);
    assert(output.front() == "&+WAuctions by &nSynthetic&+W:\r\n");
    run("sort horns nose");
    assert(queries.size() == 1);
    assert(queries.front().find("and id_keywords like '% horns,%' and id_keywords like '% nose,%'") != string::npos);
    assert(output.front().find("Auctions for items") != string::npos);
    run("player");
    assert(queries.empty() && output.front().find("Please enter the name") != string::npos);
    run("sort not-a-keyword");
    assert(queries.empty() && output.front().find("is an invalid keyword") != string::npos);
    // Initial text, a later keyword, and the final punctuation can each fill the buffer.
    for (int boundary = 0; boundary < 3; ++boundary) {
        catalogue.keywords = {"horns", "nose", "head"};
        if (boundary == 0) catalogue.keywords[0] = string(MAX_STRING_LENGTH, 'x');
        if (boundary == 1) catalogue.keywords[1] = string(MAX_STRING_LENGTH, 'y');
        if (boundary == 2) catalogue.keywords = {string(MAX_STRING_LENGTH - 22, 'z')};
        help("plate", true);
        help("sort", false);
    }
}
'''


def main():
    source = (SRC / 'auction_houses.c').read_text()
    # The SQL implementation follows the independent flat-file implementation.
    start = source.rindex('bool auction_list(P_char ch, char *args)')
    end = source.index('\n// The answer to `auction info`', start)
    (ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='auction-list-', dir=ROOT / 'bin/tests') as directory:
        path = Path(directory)
        harness, binary = path / 'harness.cpp', path / 'harness'
        harness.write_text(HARNESS + extract_function(
            'interp.c', 'void half_chop(char *string, char *arg1, char *arg2)') +
            '\n' + source[start:end] + CHECKS)
        subprocess.run(['g++', '-std=c++20', '-O2', '-g', '-D_FORTIFY_SOURCE=3',
                        f'-I{SRC}', str(harness), str(SRC / 'safe_format.c'),
                        '-o', str(binary)], check=True)
        # A reintroduced abort should fail the regression without leaving a core file.
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        subprocess.run([str(binary)], check=True)
    print('PASS: fortified SQL auction list help, filtering, and truncation boundaries')


if __name__ == '__main__':
    main()
