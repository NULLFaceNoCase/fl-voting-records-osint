import argparse, glob, json, os, re, sys
from datetime import date, datetime

FIELDS = [
    "county_code", "voter_id", "name_last", "name_suffix", "name_first",
    "name_middle", "public_records_exemption", "res_address_1", "res_address_2",
    "res_city", "res_state", "res_zip", "mail_address_1", "mail_address_2",
    "mail_address_3", "mail_city", "mail_state", "mail_zip", "mail_country",
    "gender", "race", "birth_date", "registration_date", "party", "precinct",
    "precinct_group", "precinct_split", "precinct_suffix", "voter_status",
    "congressional_district", "house_district", "senate_district",
    "county_commission_district", "school_board_district",
    "phone_area_code", "phone_number", "phone_ext", "email",
]

N = len(FIELDS)
ALL_FIELDS = FIELDS + ["age", "race_desc"]

RACE_CODES = {
    "1": "American Indian / Alaskan Native",
    "2": "Asian / Pacific Islander",
    "3": "Black, not Hispanic",
    "4": "Hispanic",
    "5": "White, not Hispanic",
    "6": "Other",
    "7": "Multi-racial",
    "9": "Unknown",
}

RACE_NAMES = {
    "native": "1",
    "asian": "2",
    "black": "3",
    "african american": "3",
    "hispanic": "4", 
    "latino": "4",
    "white": "5",
    "caucasian": "5",
    "other": "6",
    "multi": "7", 
    "multiracial": "7",
    "unknown": "9",
}

GENDER_CODES = {"F": "Female", "M": "Male", "U": "Unknown"}
GENDER_NAMES = {"female": "F", "male": "M", "unknown": "U"}

ALIASES = {
    "id": "voter_id", "last": "name_last", "first": "name_first",
    "middle": "name_middle", "city": "res_city", "zip": "res_zip",
    "street": "res_address_1", "party": "party", "status": "voter_status",
    "email": "email", "county": "county_code", "precinct": "precinct",
}

DEFAULT_OUT = [
    "county_code", "voter_id", "name_last", "name_suffix", "name_first",
    "name_middle", "res_address_1", "res_address_2", "res_city", "res_state",
    "res_zip", "birth_date", "age", "gender", "race", "race_desc", "party",
    "voter_status", "phone_area_code", "phone_number", "email",
]


def calc_age(birth_date, today):
    try:
        b = datetime.strptime(birth_date, "%m/%d/%Y").date()
    except ValueError:
        return None
    age = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
    return age if 0 <= age < 130 else None


def parse_age_spec(spec):
    """'24' -> (24,24); '20s' -> (20,29); '20-29' -> (20,29); '65+' -> (65,129)."""
    s = spec.strip().lower()
    m = re.fullmatch(r"(\d+)", s)
    if m:
        return int(m[1]), int(m[1])
    if re.fullmatch(r"\d+s", s):
        lo = int(s[:-1])
        return lo, lo + 9
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", s)
    if m:
        return int(m[1]), int(m[2])
    m = re.fullmatch(r"(\d+)\+", s)
    if m:
        return int(m[1]), 129
    raise ValueError(f"bad age spec {spec!r} (use 24, 20s, 20-29 or 65+)")


def parse_choices(spec, names, codes, label):
    """'black,hispanic' / '3,4' / 'f' -> set of codes. Accepts names or raw codes."""
    out = set()
    for tok in re.split(r"[,\s]+", spec.strip().lower()):
        if not tok:
            continue
        if tok in names:
            out.add(names[tok])
        elif tok.upper() in codes:
            out.add(tok.upper())
        else:
            valid = sorted(set(names) | {c.lower() for c in codes})
            raise ValueError(f"unknown {label} {tok!r}. Use: {', '.join(valid)}")
    return out


def parse_line(line):
    line = line.rstrip("\r\n")
    if not line.strip():
        return None
    parts = line.split("\t")
    if len(parts) < N // 2:
        # Not tab-delimited: fall back to splitting on runs of 2+ spaces.
        # (Fragile if fields are empty; real extracts are tab-delimited.)
        parts = re.split(r"\t|\s{2,}", line)
    ok = len(parts) == N
    parts = (parts + [""] * N)[:N]
    return dict(zip(FIELDS, (p.strip() for p in parts))), ok


def iter_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    yield os.path.join(root, f)
        else:
            hits = glob.glob(p)
            yield from (sorted(hits) if hits else [p])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="files, directories or globs")
    for a in ALIASES:
        ap.add_argument(f"--{a}", help=f"regex on {ALIASES[a]}")
    ap.add_argument("--age", help="age filter: 24, 20s, 20-29 or 65+ (computed from birth_date)")
    ap.add_argument("--race", help="race name(s) or code(s), comma-separated: native, asian, black, "
                                   "hispanic, white, other, multi, unknown (or 1-7, 9)")
    ap.add_argument("--gender", help="female, male, unknown (or F, M, U); comma-separate for several")
    ap.add_argument("--as-of", metavar="YYYY-MM-DD", help="compute ages as of this date (default: today)")
    ap.add_argument("--where", action="append", default=[], metavar="FIELD=REGEX",
                    help="regex on any field (repeatable)")
    ap.add_argument("--fields", help="comma list of output fields (default: common set); 'all' for everything")
    ap.add_argument("--limit", type=int, help="stop after N matches")
    ap.add_argument("--count", action="store_true", help="only print the match count")
    ap.add_argument("--ndjson", action="store_true", help="one compact JSON object per line")
    ap.add_argument("--source", action="store_true", help="include source file name")
    ap.add_argument("--encoding", default="utf-8")
    args = ap.parse_args()

    flags = re.I
    today = date.today()
    if args.as_of:
        try:
            today = datetime.strptime(args.as_of, "%Y-%m-%d").date()
        except ValueError:
            ap.error("--as-of must be YYYY-MM-DD")
    age_range = None
    if args.age:
        try:
            age_range = parse_age_spec(args.age)
        except ValueError as e:
            ap.error(str(e))
    race_set = gender_set = None
    try:
        if args.race:
            race_set = parse_choices(args.race, RACE_NAMES, RACE_CODES, "race")
        if args.gender:
            gender_set = parse_choices(args.gender, GENDER_NAMES, GENDER_CODES, "gender")
    except ValueError as e:
        ap.error(str(e))
    filters = []
    for a, f in ALIASES.items():
        v = getattr(args, a)
        if v:
            filters.append((f, re.compile(v, flags)))
    for w in args.where:
        if "=" not in w:
            ap.error(f"--where needs FIELD=REGEX, got {w!r}")
        k, v = w.split("=", 1)
        k = ALIASES.get(k, k)
        if k not in ALL_FIELDS:
            ap.error(f"unknown field {k!r}. Valid: {', '.join(ALL_FIELDS)}")
        filters.append((k, re.compile(v, flags)))

    if args.fields == "all":
        out_fields = ALL_FIELDS
    elif args.fields:
        out_fields = [ALIASES.get(x.strip(), x.strip()) for x in args.fields.split(",")]
        bad = [x for x in out_fields if x not in ALL_FIELDS]
        if bad:
            ap.error(f"unknown output fields: {bad}")
    else:
        out_fields = DEFAULT_OUT

    matches, bad_lines, results = 0, 0, []
    done = False
    for path in iter_files(args.paths):
        try:
            fh = open(path, encoding=args.encoding, errors="replace")
        except OSError as e:
            print(f"skip {path}: {e}", file=sys.stderr)
            continue
        with fh:
            for line in fh:
                parsed = parse_line(line)
                if not parsed:
                    continue
                rec, ok = parsed
                if not ok:
                    bad_lines += 1
                age = calc_age(rec["birth_date"], today)
                rec["age"] = "" if age is None else str(age)
                if age_range and (age is None or not age_range[0] <= age <= age_range[1]):
                    continue
                rec["race_desc"] = RACE_CODES.get(rec["race"], "")
                if race_set is not None and rec["race"] not in race_set:
                    continue
                if gender_set is not None and rec["gender"].upper() not in gender_set:
                    continue
                if all(rx.search(rec[f]) for f, rx in filters):
                    matches += 1
                    if not args.count:
                        out = {k: (int(rec[k]) if k == "age" else rec[k])
                               for k in out_fields if rec[k]}
                        if args.source:
                            out["_source"] = path
                        if args.ndjson:
                            print(json.dumps(out, ensure_ascii=False))
                        else:
                            results.append(out)
                    if args.limit and matches >= args.limit:
                        done = True
                        break
        if done:
            break

    if args.count:
        print(json.dumps({"matches": matches}, indent=2))
    elif not args.ndjson:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    if bad_lines:
        print(f"note: {bad_lines} line(s) did not have exactly {N} fields "
              f"(check delimiter)", file=sys.stderr)

if __name__ == "__main__":
    main()