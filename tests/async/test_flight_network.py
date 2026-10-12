#!/usr/bin/env python3
"""Exercise production flight commands, paths and tickets with the singleton fixture."""
from pathlib import Path
import os
import subprocess
import tempfile

from _paths import ROOT, HARNESS_STUBS

base = (ROOT / 'tests/async/world_singletons_harness.cpp').read_text()
base = base[:base.index('int main()')]
base = base.replace('index_data mob_indexes[4]', 'index_data mob_indexes[27]')
base = base.replace('room_data rooms[6]', 'room_data rooms[30]')
base = base.replace('int top_of_world = 5;', 'int top_of_world = 29;')
base = base.replace('int top_of_mobt = 3;', 'int top_of_mobt = 26;')
base = base.replace('int flying_transport(P_char, P_char, int, char *)\n{\n\treturn 0;\n}', '')
base = base.replace('// TRANSPORT_PRODUCTION', (ROOT / 'src/world/transport.c').read_text())

CASES = r'''
long new_exp_table[TOTALLVLS] = {};
std::string output;
int awards = 0;
void send_to_char(const char *text, P_char) { output += text; }
void send_to_char_f(P_char, const char *format, ...) {
    char buffer[4096];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    output += buffer;
}
void mark_player_dirty_components(int, player_component_mask_t mask) {
    assert(mask == PLAYER_COMPONENT_STATUS);
}
int gain_exp(P_char ch, P_char, int reward, int type) {
    assert(type == EXP_QUEST && ch->only.pc->learned_flight_stops);
    ++awards;
    GET_EXP(ch) += reward;
    return reward;
}
int SUB_MONEY(P_char ch, int amount, int) {
    assert(GET_COPPER(ch) >= amount);
    GET_COPPER(ch) -= amount;
    return 1;
}
char *coin_stringv(int amount, int) {
    static char text[64];
    snprintf(text, sizeof(text), "%dp %dg", amount / 1000, (amount % 1000) / 100);
    return text;
}
char *one_argument(const char *text, char *word) {
    while (*text && isspace(*text)) ++text;
    while (*text && !isspace(*text)) *word++ = *text++;
    *word = 0;
    while (*text && isspace(*text)) ++text;
    return const_cast<char *>(text);
}
P_char recipient = nullptr;
P_char get_char_room_vis(P_char ch, const char *) {
    return recipient && recipient->in_room == ch->in_room ? recipient : nullptr;
}
P_obj get_obj_in_list_vis(P_char, const char *, P_obj list, bool) { return list; }
int maproom_of_zone(int) { return NOWHERE; }
bool calculate_map_coords(int a, int b, int &x, int &y) { x = b - a; y = 0; return true; }

int main() {
    zone_data map{};
    map.flags = ZONE_MAP;
    map.mapx = 30;
    map.mapy = 1;
    zone_table = &map;
    top_of_zone_table = 0;
    room_direction_data east[29]{}, west[29]{};
    for (int i = 0; i < 27; ++i) {
        rooms[i].number = transports[i].origin_vnum;
        mob_indexes[i].virtual_number = transports[i].mob_vnum;
    }
    rooms[27].number = 579365;
    rooms[28].number = 620606;
    rooms[29].number = 637082;
    for (int i = 0; i < 29; ++i) {
        east[i].to_room = i + 1;
        west[i].to_room = i;
        rooms[i].dir_option[1] = &east[i];
        rooms[i + 1].dir_option[3] = &west[i];
    }
    obj_index[0].virtual_number = 420;
    obj_index[1].virtual_number = 47008;
    initialize_transport();
    initialize_transport();
    assert(obj_index[0].number == 27);
    for (int i = 0; i < 27; ++i) {
        assert(mob_indexes[i].number == 1);
        rooms[i].people->specials.position = STAT_NORMAL;
    }
    // The catalog has stable unique identities and every computed path reaches its endpoint.
    uint64_t all_stops = 0;
    for (const auto &stop : transports) {
        if (!stop.mob_vnum || stop.discovery_bit < 0) continue;
        assert(!(all_stops & (uint64_t{1} << stop.discovery_bit)));
        all_stops |= uint64_t{1} << stop.discovery_bit;
    }
    assert(std::popcount(all_stops) == 25 && !(all_stops & 1) && !(all_stops & (1 << 12)));
    for (const auto &route : transport_routes) {
        if (!route.origin_vnum) continue;
        assert(!route.path.empty());
        int room = real_room(route.origin_vnum);
        for (int dir : route.path) room = TOROOM(room, dir);
        assert(rooms[room].number == route.destination_vnum);
        if (route.discovery_bit >= 0) {
            assert(route.cost_in_copper == static_cast<int>(route.path.size()) * 500);
            assert(route.service_vnum != 47015 && route.service_vnum != 47027);
            assert(route.destination_vnum != 576577 && route.destination_vnum != 619771);
        }
    }
    pc_only_data pc{}, other_pc{};
    const auto player = [&](pc_only_data *data, const char *name) {
        P_char ch = new char_data{};
        ch->only.pc = data;
        ch->player.name = const_cast<char *>(name);
        ch->player.level = 1;
        ch->specials.position = STAT_NORMAL;
        ch->in_room = -1;
        ch->next = character_list;
        character_list = ch;
        return ch;
    };
    P_char ch = player(&pc, "Explorer");
    P_char other = player(&other_pc, "Other");
    for (auto &xp : new_exp_table) xp = 8100;
    const auto visit = [&](int service) {
        char_from_room(ch);
        char_to_room(ch, service, -1);
        recipient = nullptr;
        for (P_char mob = rooms[service].people; mob; mob = mob->next_in_room)
            if (IS_NPC(mob) && GET_RNUM(mob) == service) recipient = mob;
        assert(recipient);
    };
    const auto command = [&](int cmd, const char *args = "") {
        std::string argument(args);
        output.clear();
        return flying_transport(recipient, ch, cmd, argument.data());
    };
    visit(1);
    do_flights(ch, nullptr, CMD_FLIGHTS);
    assert(output.find("None yet") != std::string::npos && !pc.learned_flight_stops);
    assert(command(CMD_LIST));
    assert(pc.learned_flight_stops == 2 && awards == 1 && GET_EXP(ch) == 100);
    assert(command(CMD_LIST) && awards == 1);
    assert(command(CMD_BUY, "1") && !ch->carrying);
    visit(2);
    ch->player.race = RACE_DROW;
    assert(command(CMD_LIST));
    assert(pc.learned_flight_stops == 6 && awards == 2 && GET_EXP(ch) == 300);
    assert(output.find("0p 5g") != std::string::npos);
    assert(command(CMD_BUY, "1") && !ch->carrying); // no money
    GET_COPPER(ch) = 1000000;
    const auto money = GET_MONEY(ch);
    obj_index[1].virtual_number = 0;
    command(CMD_BUY, "1");
    assert(GET_MONEY(ch) == money && !ch->carrying);
    obj_index[1].virtual_number = 47008;
    command(CMD_BUY, "1oops");
    assert(GET_MONEY(ch) == money && !ch->carrying);
    command(CMD_BUY, "1");
    assert(GET_MONEY(ch) == money - 500 && ch->carrying);
    P_obj ticket = ch->carrying;
    assert(ticket->value[6] == 47017 && ticket->value[7] == 635756);
    char_to_room(other, 2, -1);
    obj_from_char(ticket); obj_to_char(ticket, other);
    char give[] = "ticket carrier";
    assert(flying_transport_cmd_give(other, recipient, give));
    assert(other->carrying == ticket && !GET_MOUNT(other)); // recipient has not learned it
    obj_from_char(ticket); obj_to_char(ticket, ch);
    for (int bad : {-1, 0, 16, 999999, 620606, 576577, 619771}) {
        ticket->value[7] = bad;
        command(CMD_GIVE, "ticket carrier");
        assert(ch->carrying == ticket && !GET_MOUNT(ch));
    }
    ticket->value[7] = 635756;
    ch->specials.fighting = other;
    command(CMD_GIVE, "ticket carrier");
    assert(ch->carrying == ticket && !GET_MOUNT(ch));
    ch->specials.fighting = nullptr;
    command(CMD_GIVE, "ticket carrier");
    assert(!ch->carrying && GET_MOUNT(ch) == recipient);
    assert(command(CMD_FLIGHTS) == 0); // proc lets the interpreter run the anywhere command
    do_flights(ch, nullptr, CMD_FLIGHTS);
    assert(output.find("Quietus") != std::string::npos && awards == 2);
    while (!scheduled.empty()) run_event(recipient);
    assert(ch->in_room == 1 && recipient->in_room == 2 && !GET_MOUNT(ch));
    // Busy, wrong-origin and already-mounted attempts keep the ticket and money.
    visit(2);
    const auto before_busy = GET_MONEY(ch);
    TRANSPORT_STATE(recipient) = TRANSPORT_STATE_MOVING;
    char buy[] = "1";
    flying_transport_cmd_buy(ch, recipient, buy);
    assert(GET_MONEY(ch) == before_busy && !ch->carrying);
    TRANSPORT_STATE(recipient) = TRANSPORT_STATE_WAITING;
    command(CMD_BUY, "1");
    ticket = ch->carrying;
    visit(1);
    command(CMD_GIVE, "ticket carrier");
    assert(ch->carrying == ticket && !GET_MOUNT(ch));
    visit(2);
    link_char(ch, other, LNK_RIDING);
    command(CMD_GIVE, "ticket carrier");
    assert(ch->carrying == ticket);
    unlink_char(ch, other, LNK_RIDING);
    command(CMD_GIVE, "ticket carrier");
    TRANSPORT_ROUTE(recipient) = 999999;
    run_event(recipient);
    assert(!GET_MOUNT(ch) && ch->in_room == 2 && recipient->in_room == 2 && scheduled.empty());
    // Reordering the catalog cannot change learned identities or the anywhere listing.
    std::swap(transports[1], transports[26]);
    output.clear();
    do_flights(ch, nullptr, CMD_FLIGHTS);
    assert(output.find("Quietus") != std::string::npos && output.find("Moonshae") == std::string::npos);
    std::swap(transports[1], transports[26]);
    // The same path length uses the permanent bit as its tie-breaker.
    pc.learned_flight_stops |= uint64_t{1} << 3;
    auto choices = transport_choices(ch, recipient);
    assert(transport_routes[choices[0]].discovery_bit == 1);
    assert(transport_routes[choices[1]].discovery_bit == 3);
    pc.learned_flight_stops = 6;
    // Epic-only services never teach their origin; their level gates survive ticket transfers.
    for (int service : {0, 12}) {
        visit(service);
        command(CMD_LIST);
        assert(pc.learned_flight_stops == 6 && awards == 2);
        command(CMD_BUY, "1");
        assert(!ch->carrying);
        ch->player.level = 51;
        command(CMD_LIST);
        command(CMD_BUY, "1");
        assert(ch->carrying);
        ticket = ch->carrying;
        ch->player.level = 1;
        command(CMD_GIVE, "ticket carrier");
        assert(ch->carrying == ticket && !GET_MOUNT(ch));
        ch->player.level = 51;
        command(CMD_GIVE, "ticket carrier");
        assert(GET_MOUNT(ch) == recipient);
        const int landing = service == 0 ? 27 : 28;
        while (!scheduled.empty()) run_event(recipient);
        assert(ch->in_room == landing && recipient->in_room == service);
        ch->player.level = 1;
    }
    // The anywhere command maps a zone entrance without dereferencing a NOWHERE exit.
    zone_data maps[2] = {map, {}};
    zone_table = maps;
    top_of_zone_table = 1;
    maps[1].real_bottom = maps[1].real_top = 29;
    rooms[29].zone = 1;
    room_direction_data invalid_exit{};
    invalid_exit.to_room = NOWHERE;
    rooms[29].dir_option[0] = &invalid_exit;
    char_from_room(ch);
    char_to_room(ch, 29, -1);
    assert(maproom_of_zone(1) == rooms[28].number);
    output.clear();
    do_flights(ch, nullptr, CMD_FLIGHTS);
    assert(output.find("Quietus") != std::string::npos);
    rooms[29].dir_option[3] = nullptr;
    assert(maproom_of_zone(1) == NOWHERE);
    output.clear();
    do_flights(ch, nullptr, CMD_FLIGHTS);
    assert(output.find("distance unavailable") != std::string::npos);
    clear_world();
    puts("flight catalog, paths, discoveries, fares, commands, tickets and epic exclusions passed");
}
'''
utility = (ROOT / 'src/core/utility.c').read_text()
map_lookup = utility[utility.index('int maproom_of_zone(int zone_num)'):utility.index('/* real rooms only! */')]
CASES = CASES.replace('int maproom_of_zone(int) { return NOWHERE; }', map_lookup)
base = '#include <bit>\n' + base
build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='flight-network-', dir=build) as temporary:
    source = Path(temporary) / 'harness.cpp'
    source.write_text(base + CASES)
    binary = Path(temporary) / 'harness'
    subprocess.run(['g++', '-std=c++20', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                    '-I', str(ROOT / 'src'), '-I/usr/include/mysql', '-I/usr/include/libxml2',
                    str(source), str(ROOT / 'src/world/world_singletons.c'),
                    '-lbsd', str(HARNESS_STUBS), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True,
                   env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1'})
