import argparse, glob, json, os, re, sys
from collections import Counter, defaultdict
from datetime import datetime

ELECTION_TYPES = {
    "GEN": "General",
    "PRI": "Primary",
    "RUN": "Runoff",
    "PPP": "Presidential Preference Primary",
    "OTH": "Other / Special / Local",
}

HISTORY_CODES = {
    "A": "Voted by mail",
    "B": "Mail ballot not counted",
    "E": "Voted early",
    "L": "Vote-by-Mail Ballot Not Counted, Received Late",
    "N": "Did not vote (not all counties use this code nor are required to report this data)",
    "P": "Provisional ballot not counted",
    "Y": "Voted at polls"
}

# Codes that mean a ballot was actually counted.
VOTED_CODES = {"Y", "A", "E"}

def iter_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    yield os.path.join(root, f)
        else:
            hits = glob.glob(p)
            yield from (sorted(hits) if hits else [p])


def parse_date(s):
    try:
        return datetime.strptime(s, "%m/%d/%Y").date()
    except ValueError:
        return None


def load_ids(args):
    ids = {i.strip() for i in args.voter_ids if i.strip()}
    if args.ids_file:
        fh = sys.stdin if args.ids_file == "-" else open(args.ids_file)
        with fh:
            ids |= {ln.strip() for ln in fh if ln.strip()}
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="history folder, file, or glob")
    ap.add_argument("voter_ids", nargs="*", help="one or more voter IDs")
    ap.add_argument("--ids-file", help="file with one voter ID per line ('-' = stdin)")
    ap.add_argument("--type", help="only these election types, comma-separated (GEN,PRI,PPP,OTH)")
    ap.add_argument("--code", help="only these history codes, comma-separated (e.g. Y,A,E)")
    ap.add_argument("--voted", action="store_true", help="only elections where a ballot was counted")
    ap.add_argument("--since", type=int, metavar="YEAR", help="only elections in or after YEAR")
    ap.add_argument("--until", type=int, metavar="YEAR", help="only elections in or before YEAR")
    ap.add_argument("--desc", action="store_true", help="newest first (default: oldest first)")
    ap.add_argument("--compact", action="store_true", help="summary only, omit per-election list")
    ap.add_argument("--source", action="store_true", help="include source file for each record")
    ap.add_argument("--encoding", default="utf-8")
    args = ap.parse_args()

    ids = load_ids(args)
    if not ids:
        ap.error("give at least one voter ID (or --ids-file)")

    types = {t.strip().upper() for t in args.type.split(",")} if args.type else None
    codes = {c.strip().upper() for c in args.code.split(",")} if args.code else None

    found = defaultdict(list)
    seen = defaultdict(set)          # for dropping exact duplicate lines
    bad_lines = 0

    for path in iter_files([args.folder]):
        try:
            fh = open(path, encoding=args.encoding, errors="replace")
        except OSError as e:
            print(f"skip {path}: {e}", file=sys.stderr)
            continue
        with fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 5:
                    if parts:
                        bad_lines += 1
                    continue
                vid = parts[1]
                if vid not in ids:
                    continue
                county, _, edate, etype, hcode = parts[:5]
                key = (county, edate, etype, hcode)
                if key in seen[vid]:
                    continue
                seen[vid].add(key)
                d = parse_date(edate)
                if d is None:
                    bad_lines += 1
                    continue
                etype, hcode = etype.upper(), hcode.upper()
                if types and etype not in types:
                    continue
                if codes and hcode not in codes:
                    continue
                if args.voted and hcode not in VOTED_CODES:
                    continue
                if args.since and d.year < args.since:
                    continue
                if args.until and d.year > args.until:
                    continue
                rec = {
                    "date": d,
                    "election_date": edate,
                    "election_type": etype,
                    "election_type_desc": ELECTION_TYPES.get(etype, ""),
                    "history_code": hcode,
                    "history_desc": HISTORY_CODES.get(hcode, ""),
                    "county_code": county,
                }
                if args.source:
                    rec["_source"] = path
                found[vid].append(rec)

    results = []
    for vid in sorted(ids):
        recs = sorted(found.get(vid, []), key=lambda r: r["date"], reverse=args.desc)
        by_type = Counter(r["election_type"] for r in recs)
        by_code = Counter(r["history_code"] for r in recs)
        out = {
            "voter_id": vid,
            "total_records": len(recs),
            "ballots_counted": sum(1 for r in recs if r["history_code"] in VOTED_CODES),
            "by_election_type": dict(sorted(by_type.items())),
            "by_history_code": dict(sorted(by_code.items())),
        }
        counties = sorted({r["county_code"] for r in recs})
        if counties:
            out["county_codes"] = counties
        if not args.compact:
            out["history"] = [{k: v for k, v in r.items() if k not in ("date", "county_code")}
                              | ({"county_code": r["county_code"]} if len(counties) > 1 else {})
                              for r in recs]
        results.append(out)

    # One ID -> a single object; several -> an array.
    print(json.dumps(results[0] if len(results) == 1 else results, indent=2, ensure_ascii=False))

    missing = [v for v in sorted(ids) if v not in found]
    if missing:
        print(f"note: no history found for: {', '.join(missing)}", file=sys.stderr)
    if bad_lines:
        print(f"note: {bad_lines} malformed line(s) skipped", file=sys.stderr)


if __name__ == "__main__":
    main()