#!/usr/bin/env python3
"""
Manor House attachment assessment - KoboToolbox data pipeline.

What it does
  1. Connects to KoboToolbox with the URL / username / password (or API token) from .env
  2. Finds the LATEST DEPLOYED version of the assessment form
       - uses KOBO_ASSET_UID if you set it, otherwise searches your deployed forms
         for KOBO_FORM_NAME / KOBO_FORM_ID and picks the most recently deployed one
  3. Downloads every submission (handles paging)
  4. Normalises them and writes the files the dashboard reads:
       dashboard/data/entries.json   (used when the dashboard is served over http)
       dashboard/data/entries.js     (used when index.html is opened straight from disk)
       dashboard/data/entries_flat.csv  (one row per entry, for Excel)

Usage
  python pipeline/kobo_pipeline.py                 # normal run
  python pipeline/kobo_pipeline.py --list-forms    # show deployed forms and which one would be used
  python pipeline/kobo_pipeline.py --from-file raw.json   # offline test with raw submissions
"""
import argparse, csv, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Run: pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "dashboard" / "data"

SECTIONS = {
    "soil": 11, "pest": 8, "lvst": 10, "nutr": 11,
    "agro": 7, "tech": 4, "clim": 2, "watr": 4,
}
ITEM_KEYS = [f"{sid}_{i:02d}" for sid, n in SECTIONS.items() for i in range(1, n + 1)]
BANDS = {"poor", "good", "very_good", "na"}
MAX_REPEATS = 10  # challenge_1..10 / comment_1..10 in the form


# ----------------------------------------------------------------- config
def load_config():
    """Read .env (if present) then let real environment variables override it."""
    cfg = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    for k in list(os.environ):
        if k.startswith("KOBO_") or k == "ROSTER_CSV":
            cfg[k] = os.environ[k]
    return cfg


def load_roster(cfg):
    """Class list (reg,name per line). Comes from the ROSTER_CSV setting (GitHub secret) or a local roster.csv.
    It is kept out of the repository because it is personal data."""
    text = cfg.get("ROSTER_CSV", "")
    f = ROOT / "roster.csv"
    if not text.strip() and f.exists():
        text = f.read_text(encoding="utf-8-sig")
    out = []
    for row in csv.reader(text.replace("\\n", "\n").splitlines()):
        if len(row) >= 2 and row[0].strip() and row[0].strip().lower() != "reg":
            out.append({"reg": row[0].strip(), "name": row[1].strip()})
    return out


def make_session(cfg):
    url = cfg.get("KOBO_URL", "").rstrip("/")
    if not url or "your-" in url:
        sys.exit("Set KOBO_URL in .env (for example https://kf.kobotoolbox.org)")
    s = requests.Session()
    token = cfg.get("KOBO_API_TOKEN", "")
    if token and "your-" not in token:
        s.headers["Authorization"] = f"Token {token}"
    else:
        user, pwd = cfg.get("KOBO_USERNAME", ""), cfg.get("KOBO_PASSWORD", "")
        if not user or not pwd or "your-" in user or "your-" in pwd:
            sys.exit("Set KOBO_USERNAME and KOBO_PASSWORD (or KOBO_API_TOKEN) in .env")
        s.auth = (user, pwd)
    s.headers["Accept"] = "application/json"
    return s, url


# ----------------------------------------------------------------- Kobo API
def paged(session, url, params=None):
    """Yield every result from a paginated Kobo list endpoint."""
    while url:
        r = session.get(url, params=params, timeout=60)
        if r.status_code in (401, 403):
            sys.exit(f"Kobo refused the login ({r.status_code}). Check KOBO_URL, username and password.")
        r.raise_for_status()
        body = r.json()
        if isinstance(body, list):
            yield from body
            return
        yield from body.get("results", [])
        url, params = body.get("next"), None


def deployed_forms(session, base):
    forms = []
    for a in paged(session, f"{base}/api/v2/assets/", {"limit": 200, "asset_type": "survey"}):
        if a.get("asset_type", "survey") == "survey" and (a.get("deployment__active") or a.get("has_deployment")):
            forms.append(a)
    return forms


def when_deployed(session, base, asset):
    """Return (deployed_at, deployed_version_id) for an asset."""
    detail = session.get(f"{base}/api/v2/assets/{asset['uid']}/", timeout=60)
    detail.raise_for_status()
    d = detail.json()
    vid = d.get("deployed_version_id")
    stamp = None
    dv = d.get("deployed_versions")
    results = dv.get("results", []) if isinstance(dv, dict) else (dv or [])
    for v in results:
        if v.get("uid") == vid or stamp is None:
            stamp = v.get("date_deployed") or v.get("date_modified") or stamp
            if v.get("uid") == vid:
                break
    return (stamp or d.get("date_modified") or ""), vid, d


def pick_latest_form(session, base, cfg):
    uid = cfg.get("KOBO_ASSET_UID", "").strip()
    if uid and "your-" not in uid:
        stamp, vid, d = when_deployed(session, base, {"uid": uid})
        return d, vid
    needle_id = (cfg.get("KOBO_FORM_ID") or "").lower()
    needle_name = (cfg.get("KOBO_FORM_NAME") or "").lower()
    matches = []
    for a in deployed_forms(session, base):
        name = (a.get("name") or "").lower()
        if (needle_name and needle_name in name) or (needle_id and needle_id in name.replace(" ", "_")):
            matches.append(a)
    if not matches:
        sys.exit("No deployed form matches KOBO_FORM_NAME / KOBO_FORM_ID. Run with --list-forms, "
                 "or set KOBO_ASSET_UID in .env.")
    ranked = []
    for a in matches:
        stamp, vid, d = when_deployed(session, base, a)
        ranked.append((stamp, vid, d))
    ranked.sort(key=lambda x: x[0], reverse=True)  # most recently deployed first
    return ranked[0][2], ranked[0][1]


def fetch_submissions(session, base, uid, only_version=None):
    rows = list(paged(session, f"{base}/api/v2/assets/{uid}/data/", {"format": "json", "limit": 1000}))
    if only_version:
        rows = [r for r in rows if (r.get("__version__") or r.get("_version_")) == only_version]
    return rows


# ----------------------------------------------------------------- normalise
def norm_band(v):
    s = str(v or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not s:
        return ""
    if "very" in s or s == "5_6":
        return "very_good"
    if "poor" in s or s == "0_2":
        return "poor"
    if "good" in s or s == "3_4":
        return "good"
    if s == "na" or "not" in s or "applic" in s:
        return "na"
    return ""


def flatten_keys(row):
    """Kobo returns grouped fields as 'group/field'. Keep only the last segment."""
    out = {}
    for k, v in row.items():
        key = str(k).split("/")[-1].strip().lower()
        if key not in out or out[key] in ("", None):
            out[key] = v
    return out


def normalise(row):
    m = flatten_keys(row)
    reg = str(m.get("reg_no") or "").strip()
    if not reg:
        return None
    key = str(m.get("_uuid") or m.get("meta/instanceid") or "").replace("uuid:", "") \
        or f"{reg}_{m.get('assess_date','')}_{m.get('_id','')}"
    ratings = {k: norm_band(m.get(k)) for k in ITEM_KEYS}
    ratings = {k: v for k, v in ratings.items() if v}

    def listed(prefix):
        vals = [str(m.get(f"{prefix}_{i}") or "").strip() for i in range(1, MAX_REPEATS + 1)]
        return [v for v in vals if v]

    return {
        "id": "e_" + "".join(c if c.isalnum() or c in "_-.~:@+" else "_" for c in key)[:150],
        "reg": reg,
        "name": str(m.get("student_name") or "").strip(),
        "assessor": str(m.get("assessor") or "").strip(),
        "date": str(m.get("assess_date") or "")[:10],
        "org": str(m.get("organization") or "").strip(),
        "place": str(m.get("place") or "").strip(),
        "village": str(m.get("village") or "").strip(),
        "r": ratings,
        "challenges": listed("challenge"),
        "comments": listed("comment"),
        "supName": str(m.get("sup_name") or "").strip(),
        "supDesig": str(m.get("sup_designation") or "").strip(),
        "supDate": str(m.get("sup_date") or "")[:10],
        "submitted": str(m.get("_submission_time") or m.get("end") or "")[:19],
    }


# ----------------------------------------------------------------- output
def write_outputs(entries, meta):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "entries": entries}
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    (OUT_DIR / "entries.json").write_text(text, encoding="utf-8")
    (OUT_DIR / "entries.js").write_text("window.ASSESSMENT_DATA = " + text + ";\n", encoding="utf-8")
    cols = ["reg", "name", "assessor", "date", "org", "place", "village"] + ITEM_KEYS + \
           ["challenges", "comments", "supName", "supDesig", "supDate", "submitted"]
    with open(OUT_DIR / "entries_flat.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for e in entries:
            row = [e.get(c, "") for c in cols[:7]] + [e["r"].get(k, "") for k in ITEM_KEYS] + \
                  [" | ".join(e["challenges"]), " | ".join(e["comments"]), e["supName"], e["supDesig"], e["supDate"], e["submitted"]]
            w.writerow(row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-forms", action="store_true", help="list deployed forms and the one that would be used")
    ap.add_argument("--from-file", help="read raw Kobo submissions (JSON list) instead of calling Kobo")
    args = ap.parse_args()
    cfg = load_config()
    meta = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": "file" if args.from_file else "kobo"}

    if args.from_file:
        raw = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
        raw = raw.get("results", raw) if isinstance(raw, dict) else raw
    else:
        session, base = make_session(cfg)
        if args.list_forms:
            for a in deployed_forms(session, base):
                print(f"{a['uid']}  {a.get('name')}  (submissions: {a.get('deployment__submission_count', '?')})")
            asset, vid = pick_latest_form(session, base, cfg)
            print(f"\nWould use: {asset.get('name')} [{asset['uid']}] version {vid}")
            return
        asset, vid = pick_latest_form(session, base, cfg)
        only_latest = str(cfg.get("KOBO_ONLY_LATEST_VERSION", "false")).lower() in ("1", "true", "yes")
        raw = fetch_submissions(session, base, asset["uid"], vid if only_latest else None)
        meta.update({"form_name": asset.get("name"), "asset_uid": asset["uid"], "deployed_version_id": vid,
                     "only_latest_version": only_latest, "kobo_url": base})

    seen, entries = set(), []
    for row in raw:
        e = normalise(row)
        if e and e["id"] not in seen:
            seen.add(e["id"])
            entries.append(e)
    entries.sort(key=lambda e: (e["date"], e["submitted"]))
    meta["count"] = len(entries)
    meta["roster"] = load_roster(cfg)
    write_outputs(entries, meta)
    print(f"Wrote {len(entries)} entries to {OUT_DIR}")
    if meta.get("form_name"):
        print(f"Form: {meta['form_name']} [{meta['asset_uid']}] deployed version {meta['deployed_version_id']}")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        sys.exit(f"Could not reach KoboToolbox: {exc.__class__.__name__}. Check KOBO_URL and your internet connection.")
