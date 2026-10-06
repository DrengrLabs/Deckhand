"""Local JSON-file storage for the TRA app. No database, no network -
everything lives under app_data/ next to this file.

Data is organized per hitch/project profile so you can switch between
multiple ongoing hitches without losing each one's setup and day history.
The signature library is the one thing kept global/shared across all
hitches, by design -- a crew member's signature is reused everywhere.
"""
import glob
import json
import os
import re
import shutil
import sys
import threading

# The "app" folder. For the packaged "DOUS Deckhand.exe" that's the folder the
# .exe sits in -- its own code unpacks to a temporary folder each run, which
# must never be where hitches/signatures are saved.
if getattr(sys, "frozen", False):
    # Packaged: DOUS Deckhand\DOUS Deckhand.exe, with templates\ and app_data\ beside it
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    TEMPLATES_ROOT = os.path.join(BASE_DIR, "templates")
else:
    # Source: DOUS Deckhand\app\*.py, with templates\ one level up
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TEMPLATES_ROOT = os.path.normpath(os.path.join(BASE_DIR, "..", "templates"))
TRA_TEMPLATES_DIR = os.path.join(TEMPLATES_ROOT, "TRA")
TBT_TEMPLATES_DIR = os.path.join(TEMPLATES_ROOT, "TBT")
TEMPLATE_DIRS = {"TRA": TRA_TEMPLATES_DIR, "TBT": TBT_TEMPLATES_DIR}
DATA_DIR = os.path.join(BASE_DIR, "app_data")
SIGNATURES_DIR = os.path.join(DATA_DIR, "signatures")
HITCHES_DIR = os.path.join(DATA_DIR, "hitches")
DAYS_DIR = os.path.join(DATA_DIR, "days")
ACTIVE_HITCH_FILE = os.path.join(DATA_DIR, "active_hitch.json")
SIGNATURES_INDEX = os.path.join(DATA_DIR, "signatures.json")
CATALOG_FILE = os.path.join(DATA_DIR, "template_catalog.json")

# Pre-multi-hitch location; only read during the one-time migration below.
# (days/*.json used to be flat; now it's days/<hitch_id>/*.json under DAYS_DIR)
_LEGACY_HITCH_FILE = os.path.join(DATA_DIR, "hitch.json")

_lock = threading.Lock()


def _ensure_dirs():
    os.makedirs(SIGNATURES_DIR, exist_ok=True)
    os.makedirs(HITCHES_DIR, exist_ok=True)
    os.makedirs(DAYS_DIR, exist_ok=True)


def _read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        # A corrupted file (bad shutdown mid-write, disk hiccup, etc.) must
        # never blank the whole app for everyone from then on. Quarantine
        # it with a timestamp so nothing is silently lost, log it, and
        # carry on as if that file had never existed.
        import datetime
        import shutil

        quarantined = f"{path}.corrupted-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            shutil.move(path, quarantined)
        except OSError:
            quarantined = "(could not move it)"
        print(f"[data_store] WARNING: {path} was corrupted and unreadable; "
              f"moved to {quarantined} and continuing with defaults.")
        return default


def _write_json(path, data):
    _ensure_dirs()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def slugify(name):
    s = re.sub(r"[^A-Za-z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "unnamed"


DEFAULT_HITCH = {
    "name": "",
    "project": "",
    "location": "",
    "sub_location": "ROV Deck",              # pre-filled for a new hitch
    "approver": "OCM",
    "responsible_person": "SHIFT SUPERVISOR",
    "equipment": "",
    # Derived on save from the crew roster's Day / Night Supervisor slots
    # (not typed in separately any more).
    "approver_name": "",
    "approver_position": "",
    "approver2_name": "",
    "approver2_position": "",
    # [{name, position, slot?, official_position, shift, contractor}] --
    # slot marks the 6 standard rows; position is the HSE shorthand used on
    # TRAs/TBTs, official_position the title used on timesheets.
    "crew": [],
    "output_folder": "",
    # Timesheets
    "client": "",             # timesheet Client; the timesheet System is the Equipment field
    "ts_output_folder": "",   # the project's "7 - TIMESHEETS & MILEAGE REPORT" folder
}

_migrated = False


def _migrate_legacy_once():
    """One-time move of the old single-hitch layout into a 'default'
    hitch profile, so upgrading this app never loses in-progress work."""
    global _migrated
    if _migrated:
        return
    with _lock:
        if _migrated:
            return
        _ensure_dirs()
        legacy_hitch_exists = os.path.exists(_LEGACY_HITCH_FILE)
        already_migrated = len(glob.glob(os.path.join(HITCHES_DIR, "*.json"))) > 0
        if legacy_hitch_exists and not already_migrated:
            legacy = _read_json(_LEGACY_HITCH_FILE, dict(DEFAULT_HITCH))
            legacy.setdefault("name", legacy.get("project") or "Default Hitch")
            hitch_id = "default"
            _write_json(os.path.join(HITCHES_DIR, f"{hitch_id}.json"), legacy)
            _write_json(ACTIVE_HITCH_FILE, {"active": hitch_id})

            # Old flat day files: app_data/days/<date>.json -> days/default/<date>.json
            flat_day_files = [
                p for p in glob.glob(os.path.join(DAYS_DIR, "*.json"))
                if os.path.isfile(p)
            ]
            if flat_day_files:
                dest_dir = os.path.join(DAYS_DIR, hitch_id)
                os.makedirs(dest_dir, exist_ok=True)
                for p in flat_day_files:
                    shutil.move(p, os.path.join(dest_dir, os.path.basename(p)))

            os.remove(_LEGACY_HITCH_FILE)
        _migrated = True


# ---------- hitch profiles ----------

def list_hitches():
    _migrate_legacy_once()
    out = []
    for p in sorted(glob.glob(os.path.join(HITCHES_DIR, "*.json"))):
        hitch_id = os.path.splitext(os.path.basename(p))[0]
        data = _read_json(p, {})
        out.append({"id": hitch_id, "name": data.get("name") or data.get("project") or hitch_id})
    return out


def get_active_hitch_id():
    _migrate_legacy_once()
    active = _read_json(ACTIVE_HITCH_FILE, {}).get("active")
    if active and os.path.exists(os.path.join(HITCHES_DIR, f"{active}.json")):
        return active
    # Fall back to whatever hitch exists, or None if there truly are none yet.
    existing = list_hitches()
    return existing[0]["id"] if existing else None


def set_active_hitch(hitch_id):
    with _lock:
        if not os.path.exists(os.path.join(HITCHES_DIR, f"{hitch_id}.json")):
            raise ValueError(f"no such hitch: {hitch_id}")
        _write_json(ACTIVE_HITCH_FILE, {"active": hitch_id})


def create_hitch(name):
    with _lock:
        base_id = slugify(name)
        hitch_id = base_id
        n = 2
        while os.path.exists(os.path.join(HITCHES_DIR, f"{hitch_id}.json")):
            hitch_id = f"{base_id}_{n}"
            n += 1
        data = dict(DEFAULT_HITCH)
        data["name"] = name
        _write_json(os.path.join(HITCHES_DIR, f"{hitch_id}.json"), data)
        _write_json(ACTIVE_HITCH_FILE, {"active": hitch_id})
        return hitch_id, data


REMOVED_HITCHES_DIR = os.path.join(DATA_DIR, "removed_hitches")


def remove_hitch(hitch_id):
    """Take a hitch out of the app: its setup and its day history.

    Nothing is permanently deleted -- both are moved into
    app_data/removed_hitches/<id>_<timestamp>/ so a removal made by mistake
    can still be recovered by hand. Generated PDFs in the hitch's output
    folder are never touched. The last remaining hitch can't be removed.
    Returns the id of the hitch that's active afterward.
    """
    import datetime

    _migrate_legacy_once()
    with _lock:
        existing = [h["id"] for h in list_hitches()]
        if hitch_id not in existing:
            raise ValueError(f"no such hitch: {hitch_id}")
        if len(existing) == 1:
            raise ValueError("This is the only hitch -- create another one before removing it.")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(REMOVED_HITCHES_DIR, f"{hitch_id}_{stamp}")
        os.makedirs(dest, exist_ok=True)
        shutil.move(os.path.join(HITCHES_DIR, f"{hitch_id}.json"), os.path.join(dest, "hitch.json"))
        days = os.path.join(DAYS_DIR, hitch_id)
        if os.path.isdir(days):
            shutil.move(days, os.path.join(dest, "days"))
        timesheets = os.path.join(DATA_DIR, "timesheets", hitch_id)
        if os.path.isdir(timesheets):
            shutil.move(timesheets, os.path.join(dest, "timesheets"))
        active = _read_json(ACTIVE_HITCH_FILE, {}).get("active")
        if active == hitch_id:
            active = next(h for h in existing if h != hitch_id)
            _write_json(ACTIVE_HITCH_FILE, {"active": active})
        return active


def get_hitch():
    _migrate_legacy_once()
    hitch_id = get_active_hitch_id()
    if hitch_id is None:
        return {**DEFAULT_HITCH, "crew": []}
    with _lock:
        stored = _read_json(os.path.join(HITCHES_DIR, f"{hitch_id}.json"), {})
    # Fill in any fields added to the app after this hitch was saved.
    return {**DEFAULT_HITCH, "crew": [], **stored}


def save_hitch(data):
    hitch_id = get_active_hitch_id()
    if hitch_id is None:
        hitch_id, _ = create_hitch(data.get("name") or data.get("project") or "Default Hitch")
    with _lock:
        merged = dict(DEFAULT_HITCH)
        merged.update(data)
        _write_json(os.path.join(HITCHES_DIR, f"{hitch_id}.json"), merged)
        return merged


# ---------- signatures (global, shared across all hitches) ----------

def get_signatures_index():
    with _lock:
        return _read_json(SIGNATURES_INDEX, {})


def _signature_filename(person_name):
    """A filesystem-safe, collision-proof filename for a person's signature.

    Two different names that merely *look* similar once slugified (e.g.
    "J. Smith" and "J Smith" both slugify to "j_smith") must never share a
    file -- that would silently show one person's signature under another
    person's name. The short hash of the exact name guarantees uniqueness;
    the slug prefix is just there so the filename stays human-readable.
    """
    import hashlib

    digest = hashlib.sha1(person_name.encode("utf-8")).hexdigest()[:10]
    return f"{slugify(person_name)}_{digest}.png"


def save_signature(person_name, png_bytes):
    """Save a signature PNG for a person, keyed by name. Overwrites any
    previous signature for that person."""
    import datetime

    with _lock:
        _ensure_dirs()
        filename = _signature_filename(person_name)
        path = os.path.join(SIGNATURES_DIR, filename)
        with open(path, "wb") as f:
            f.write(png_bytes)
        index = _read_json(SIGNATURES_INDEX, {})
        index[person_name] = {
            "file": filename,
            "captured_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        _write_json(SIGNATURES_INDEX, index)
        return path


def get_signature_path(person_name):
    index = get_signatures_index()
    entry = index.get(person_name)
    if not entry:
        return None
    path = os.path.join(SIGNATURES_DIR, entry["file"])
    return path if os.path.exists(path) else None


def clear_signature(person_name):
    with _lock:
        index = _read_json(SIGNATURES_INDEX, {})
        entry = index.pop(person_name, None)
        if entry:
            path = os.path.join(SIGNATURES_DIR, entry["file"])
            if os.path.exists(path):
                os.remove(path)
            _write_json(SIGNATURES_INDEX, index)


TEMPLATE_BASELINES_FILE = os.path.join(DATA_DIR, "template_baselines.json")


def _file_hash(path):
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def list_templates():
    """Build (and cache) a catalog of the TRA/TBT templates with their
    introspected layout. Rebuilt if the templates folder changes.

    Each template's content hash is checked against a stored baseline
    (set the first time that file is ever seen) so an accidental edit to
    a "blank" template -- e.g. someone signing it directly in Acrobat
    again -- gets flagged instead of silently becoming the new normal.
    """
    import pdf_engine

    with _lock:
        # (category, path) for every blank template -- TRAs and TBTs each
        # live in their own folder, and the folder decides the category.
        # Only top-level PDFs count, so source files kept in a subfolder
        # (e.g. the original Word TBTs) are ignored.
        entries = []
        for category, folder in TEMPLATE_DIRS.items():
            for p in sorted(glob.glob(os.path.join(folder, "*.pdf"))):
                if "master" not in os.path.basename(p).lower():
                    entries.append((category, p))
        sig = {f"{c}/{os.path.basename(p)}": os.path.getmtime(p) for c, p in entries}

        cached = _read_json(CATALOG_FILE, None)
        if cached and cached.get("_sig") == sig:
            return cached["templates"]

        baselines = _read_json(TEMPLATE_BASELINES_FILE, {})
        baselines_changed = False

        templates = {}
        for category, p in entries:
            base = os.path.basename(p)
            key = os.path.splitext(base)[0]
            try:
                info = pdf_engine.introspect(p)
            except Exception as e:
                info = {"error": str(e)}

            # TRA baselines predate the TBT folder and are keyed by bare
            # filename; keep that so existing fingerprints stay valid.
            baseline_key = base if category == "TRA" else f"{category}/{base}"
            file_hash = _file_hash(p)
            if baseline_key not in baselines:
                baselines[baseline_key] = file_hash
                baselines_changed = True
                altered = False
            else:
                altered = baselines[baseline_key] != file_hash

            title = re.sub(r"^(DOUS-TRA-\d+|DO-TRA-\d+|DOUS-TBT-\d+|TBT-\d+|TRA|TBT)[\s-]*", "", key, flags=re.IGNORECASE).strip() or key
            templates[key] = {
                "key": key,
                "file": base,
                "path": p,
                "title": title,
                "category": category,
                "num_crew_rows": len(info.get("crew_rows", [])),
                "num_approver_sigs": len(info.get("approver_sig_fields", [])),
                "has_task_field": bool(info.get("task_field")),
                "common_fields": info.get("common_fields", []),
                "altered": altered,
            }
        if baselines_changed:
            _write_json(TEMPLATE_BASELINES_FILE, baselines)
        _write_json(CATALOG_FILE, {"_sig": sig, "templates": templates})
        return templates


# ---------- day records (per active hitch) ----------

def _days_dir_for_active_hitch():
    hitch_id = get_active_hitch_id() or "default"
    return os.path.join(DAYS_DIR, hitch_id)


TIMESHEETS_DIR = os.path.join(DATA_DIR, "timesheets")


def _timesheet_path(week_ending):
    hitch_id = get_active_hitch_id() or "default"
    return os.path.join(TIMESHEETS_DIR, hitch_id, f"{week_ending}.json")


def get_timesheet_week(week_ending):
    """One week's timesheet record for the active hitch: day codes per
    person, the operations line, and which PDFs were generated/acknowledged."""
    return _read_json(_timesheet_path(week_ending),
                      {"week_ending": week_ending, "codes": {}, "ops": {}, "generated": {}})


def update_timesheet_week(week_ending, mutate_fn):
    """Atomic read-modify-write of a week's timesheet record (see update_day)."""
    path = _timesheet_path(week_ending)
    with _lock:
        rec = _read_json(path, {"week_ending": week_ending, "codes": {}, "ops": {}, "generated": {}})
        mutate_fn(rec)
        _write_json(path, rec)
        return rec


def get_day(date_str):
    path = os.path.join(_days_dir_for_active_hitch(), f"{date_str}.json")
    return _read_json(path, {"date": date_str, "tras": []})


def save_day(date_str, data):
    path = os.path.join(_days_dir_for_active_hitch(), f"{date_str}.json")
    _write_json(path, data)


def update_day(date_str, mutate_fn):
    """Atomically read-modify-write a day's record.

    `mutate_fn(day_dict)` is called with the current record (or a fresh
    `{"date": ..., "tras": []}` if none exists yet) and should mutate it in
    place; the result is written back before the lock is released. Holding
    the lock across the whole read-modify-write (rather than two separate
    get_day()/save_day() calls) is what prevents two near-simultaneous
    requests -- e.g. a double-clicked Generate button -- from each reading
    the same starting state and one of them clobbering the other's change.
    """
    path = os.path.join(_days_dir_for_active_hitch(), f"{date_str}.json")
    with _lock:
        day = _read_json(path, {"date": date_str, "tras": []})
        mutate_fn(day)
        _write_json(path, day)
        return day


def list_days():
    days_dir = _days_dir_for_active_hitch()
    if not os.path.isdir(days_dir):
        return []
    files = sorted(glob.glob(os.path.join(days_dir, "*.json")), reverse=True)
    return [os.path.splitext(os.path.basename(f))[0] for f in files]
