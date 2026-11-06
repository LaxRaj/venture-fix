"""Phase 3: corrected screen on evidence-adjusted inputs. Standalone; does not edit vstress/.
Every input is labelled C(ited by a phase-2 agent) or E(stimate)."""
import math
DELIV = 190      # delivery hrs/month (60-80 hrs/wk x ~65-70%)
TARGET = 10_000
OUT_WK = 100     # contacts/week while outreach is the main job (assumption)
CONVS = (0.003, 0.001)   # base, stress (phase2_channels.md)

# name, price/mo, hrs/acct/mo, pool, price_src, pool_src
ROWS = [
 ("Customs HTS (firms pool)",   750, 3.0,  2365, "C", "C"),
 ("Customs HTS @ $1,400",      1400, 3.0,  2365, "E", "C"),
 ("Grant compliance @ $400",    400, 4.0, 20000, "C", "E"),   # pool: 100k reported grants; 20% addressable is MY guess
 ("DOT 1-10 trucks @ $150",     150, 3.0, 50000, "C", "E"),   # 787k carriers; for-hire small subset is a guess
 ("Trademark watch @ $33",       33, 1.0, 45000, "C", "E"),
 ("RFP drafting @ $1,500",     1500, 6.0,  1500, "C", "E"),
]
def screen(name, price, hrs, pool, target, conv):
    acc = target / price
    cap = DELIV / hrs
    contacts = acc / conv
    ok_cap, ok_reach = acc <= cap, contacts <= pool * 0.5
    return acc, cap, contacts, ok_cap, ok_reach
print(f"delivery={DELIV}h/mo, outreach={OUT_WK} contacts/wk")
for target in (3000, 10000):
    print(f"\n=== target ${target:,} MRR ===")
    print(f"{'venture':28}{'$/hr':>6}{'acc':>6}{'cap':>6}  " + "  ".join(f"conv{c:.1%}: contacts verdict  wk1st  wk$" for c in CONVS))
    for r in ROWS:
        name, price, hrs, pool = r[:4]
        line = f"{name:28}{price/hrs:>6.0f}"
        first = True
        for c in CONVS:
            acc, cap, contacts, okc, okr = screen(name, price, hrs, pool, target, c)
            v = "OK" if (okc and okr) else ("CAP" if not okc else "POOL")
            wk1 = 1/(OUT_WK*c); wkT = contacts/OUT_WK
            if first:
                line += f"{acc:>6.1f}{cap:>6.0f}  "; first = False
            line += f"  {contacts:>8,.0f} {v:>5} {wk1:>6.1f} {wkT:>5.0f}   "
        print(line)
