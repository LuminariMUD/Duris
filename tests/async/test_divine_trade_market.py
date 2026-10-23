#!/usr/bin/env python3
"""Prepared market after-images match the existing live price/adjustment functions."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function
source=r'''
#include "economy/divine_trade_command.h"
#include "ships/ships.h"
#include "ships/ship_cargo_transaction.h"
#include <algorithm>
#include <cassert>
#include <cmath>
float ship_cargo_market_mod[NUM_PORTS][NUM_PORTS]{};
float ship_contra_market_mod[NUM_PORTS][NUM_PORTS]{};
float ship_cargo_market_mod_delayed[NUM_PORTS][NUM_PORTS]{};
struct prices {float base_cost_cargo,base_cost_contra;};
prices cargo_location_data[NUM_PORTS]{};
float cargo_location_mod[NUM_PORTS][NUM_PORTS]{};
float get_property(const char *,double value) {return value;}
float bound_market_mod(bool,float value) {return std::clamp(value,.05f,2.f);}
int write_cargo() {return true;}
void logit(const char *,const char *,...) {}
'''
for signature in ["int cargo_sell_price(","int cargo_buy_price(","int contra_sell_price(","int contra_buy_price(",
                  "divine_trade_market_cell cargo_trade_prepare_cell(","void adjust_ship_market("]:
    source+=extract_function("ship_cargo.c",signature)+"\n"
source+=r'''
int main()
{
 for (int port=0;port<NUM_PORTS;++port)
 {
  cargo_location_data[port]={2.125f,3.375f};
  for (int type=0;type<NUM_PORTS;++type)
   cargo_location_mod[port][type]=117;
 }
 for (int mode:{SOLD_CARGO,BOUGHT_CARGO,SOLD_CONTRA,BOUGHT_CONTRA})
  for (int port:{2,4})
   for (int quantity:{1,10,100})
   {
    ship_cargo_market_mod[port][2]=1.03f;ship_contra_market_mod[port][2]=1.17f;
    const auto cell=cargo_trade_prepare_cell(mode,port,2,quantity);
    assert(ship_cargo_market_mod[port][2]==1.03f && ship_contra_market_mod[port][2]==1.17f);
    adjust_ship_market(mode,port,2,quantity);
    const bool contra=mode==SOLD_CONTRA || mode==BOUGHT_CONTRA;
    assert(cell.modifier==(contra ? ship_contra_market_mod : ship_cargo_market_mod)[port][2]);
    const int price=contra ? (port==2 ? contra_sell_price(port) : contra_buy_price(port,2)) :
      (port==2 ? cargo_sell_price(port,false) : cargo_buy_price(port,2,false));
    assert(cell.price==price);
   }
}
'''
with tempfile.TemporaryDirectory(prefix="divine-market-",dir=ROOT / "bin/tests") as temporary:
    path=Path(temporary);(path / "market.cpp").write_text(source)
    subprocess.run(["g++","-std=c++20","-Wall","-Wextra","-Werror","-g","-fsanitize=address,undefined",
        "-Isrc","-I/usr/include/mysql",str(path / "market.cpp"),"-o",str(path / "market")],cwd=ROOT,check=True)
    subprocess.run([str(path / "market")],check=True)
print("PASS: shared trade market preview matches ordinary adjustments and source/destination quote caches for both goods")
