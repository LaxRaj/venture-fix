"""Round-2 screen: new ventures, converted to monthly revenue per account. Standalone; does not edit vstress/.
E = my conversion/pool guess from agent reports (see analysis/ideas_*.md). Prices are agents' vendor-sourced figures."""
DELIV = 190; OUT_WK = 100; CONVS = (0.003, 0.001); BAR_HR = 57.74; CHURN = 0.10
# name, $/acct/mo, delivery hrs/acct/mo, addressable pool (E unless noted), note
ROWS = [
 ("Short-form repurposing",       750, 10,  50_000, "$50/short x15; hrs from agent $50-100/hr"),
 ("Podcast edit + clips",         600,  8,  20_000, "retainer $300-1,500"),
 ("Long-form YouTube editing",   1700, 24,  50_000, "$1,700-3,500/mo experienced"),
 ("Appointment setting (trades)",1200, 15,  20_000, "8 kept appts x $150, one metro first"),
 ("Newsletter sponsor brokerage", 400,  8,  20_000, "20% of ~$2k, thin"),
 ("Bookkeeping cleanup retainer", 300, 3.5, 200_000, "project $500-3,000 then $150-400/mo"),
 ("GBP / review mgmt",            300, 3.5, 300_000, "$125-500/location"),
 ("AI receptionist (trades)",     100,  1,  200_000, "setup $1.5k one-off, thin retainer"),
 ("Newsletter ghostwriting",     1800, 10,  20_000, "slow sale 3-6 wks"),
 ("Clipper tracker SaaS @ $9",      9, 0.1, 62_000, "tool; churn kills"),
]
print(f"delivery={DELIV}h/mo, {OUT_WK} contacts/wk, bar ${BAR_HR}/hr, assumed churn {CHURN:.0%}/mo (cheap services)")
for target in (3000, 5000):
    print(f"\n=== target ${target:,} MRR ===")
    print(f"{'offer':30}{'$/hr':>6}{'acc':>7}{'cap':>6}{'0.3%: contacts':>16}{'verdict':>8}{'wk1st':>7}{'wk tgt':>8}{'0.1%: verdict':>14}{'wk tgt':>8}{'new/mo to hold':>16}")
    for name, price, hrs, pool, note in ROWS:
        acc = target/price; cap = DELIV/hrs; line = f"{name:30}{price/hrs:>6.0f}{acc:>7.1f}{cap:>6.0f}"
        for i, c in enumerate(CONVS):
            contacts = acc/c
            ok = acc <= cap and contacts <= pool*0.5
            v = "OK" if ok else ("CAP" if acc > cap else "POOL")
            if i == 0: line += f"{contacts:>16,.0f}{v:>8}{1/(OUT_WK*c):>7.1f}{contacts/OUT_WK:>8.0f}"
            else: line += f"{v:>14}{contacts/OUT_WK:>8.0f}"
        line += f"{acc*CHURN:>16.1f}"
        print(line)
