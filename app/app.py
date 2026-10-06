import base64
import datetime
import os
import threading

from flask import Flask, jsonify, request, send_file, render_template

import data_store
import pdf_engine
import timesheet
import updater

# The app's own page lives in "web" -- "templates" holds the TRA/TBT PDFs.
app = Flask(__name__, template_folder="web")
_folder_dialog_lock = threading.Lock()

with open(os.path.join(os.path.dirname(__file__), "VERSION"), encoding="utf-8") as _vf:
    APP_VERSION = _vf.read().strip()


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    from werkzeug.exceptions import HTTPException

    if isinstance(e, HTTPException):
        return jsonify({"error": e.description}), e.code
    app.logger.exception("Unhandled error")
    return jsonify({"error": f"Unexpected error: {e}"}), 500


@app.route("/")
def index():
    return render_template("index.html", version=APP_VERSION)


# ---------- Hitch setup ----------

_FOLDER_PICKER_SCRIPT = """
import sys, tkinter as tk
from tkinter import filedialog
initial = sys.argv[1] or None
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
folder = filedialog.askdirectory(initialdir=initial, title="Select the output folder for signed TRAs/TBTs", parent=root)
root.destroy()
print(folder)
"""


@app.route("/api/browse-folder", methods=["POST"])
def api_browse_folder():
    """Pop a native Windows folder-picker and return the chosen path.

    Runs as its own short-lived subprocess rather than importing tkinter
    into the Flask process itself -- tkinter expects to own a process's
    main thread/event loop, which doesn't mix reliably with a long-running
    web server handling repeated requests over hours of use. A fresh
    subprocess per click sidesteps that entirely: each one gets a clean
    Tcl/Tk environment and fully exits afterward, so there's nothing to
    leak or hang between uses no matter how many times it's clicked.
    """
    import subprocess
    import sys

    body = request.get_json(silent=True) or {}
    initial = body.get("initial") or ""
    if initial and not os.path.isdir(initial):
        initial = ""

    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    frozen = getattr(sys, "frozen", False)
    if frozen:
        # Packaged .exe: there's no separate python.exe to run a script with,
        # so the .exe itself runs the picker ("--pick-folder", see
        # start_app.pyw) and writes the choice to a temp file.
        import tempfile
        fd, out_file = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        cmd = [sys.executable, "--pick-folder", initial, out_file]
    else:
        cmd = [sys.executable, "-c", _FOLDER_PICKER_SCRIPT, initial]
    with _folder_dialog_lock:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, creationflags=creationflags)
        except subprocess.TimeoutExpired:
            return jsonify({"error": "The folder picker timed out without a selection."}), 504

    if result.returncode != 0:
        return jsonify({"error": f"Couldn't open the folder picker: {(result.stderr or '').strip()[:300]}"}), 500

    if frozen:
        with open(out_file, encoding="utf-8") as fh:
            folder = fh.read().strip()
        os.remove(out_file)
    else:
        folder = result.stdout.strip()
    return jsonify({"folder": folder or None})

@app.route("/api/hitch", methods=["GET"])
def api_get_hitch():
    return jsonify(data_store.get_hitch())


@app.route("/api/hitch", methods=["POST"])
def api_save_hitch():
    data = request.get_json(force=True)
    saved = data_store.save_hitch(data)
    return jsonify(saved)


# ---------- Hitch profiles (switching between hitches) ----------

@app.route("/api/hitches", methods=["GET"])
def api_list_hitches():
    return jsonify({"hitches": data_store.list_hitches(), "active": data_store.get_active_hitch_id()})


@app.route("/api/hitches", methods=["POST"])
def api_create_hitch():
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    hitch_id, data = data_store.create_hitch(name)
    return jsonify({"id": hitch_id, "hitch": data})


@app.route("/api/hitches/<hitch_id>/activate", methods=["POST"])
def api_activate_hitch(hitch_id):
    try:
        data_store.set_active_hitch(hitch_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"ok": True, "hitch": data_store.get_hitch()})


@app.route("/api/hitches/<hitch_id>", methods=["DELETE"])
def api_remove_hitch(hitch_id):
    try:
        active = data_store.remove_hitch(hitch_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "active": active})


# ---------- Template catalog ----------

@app.route("/api/templates", methods=["GET"])
def api_templates():
    return jsonify(data_store.list_templates())


# ---------- Signatures ----------

@app.route("/api/signatures", methods=["GET"])
def api_list_signatures():
    return jsonify(data_store.get_signatures_index())


@app.route("/api/signatures/<path:person_name>", methods=["POST"])
def api_save_signature(person_name):
    body = request.get_json(force=True)
    data_url = body.get("image")  # "data:image/png;base64,...."
    if not data_url or "," not in data_url:
        return jsonify({"error": "no image data"}), 400
    png_bytes = base64.b64decode(data_url.split(",", 1)[1])
    data_store.save_signature(person_name, png_bytes)
    return jsonify({"ok": True})


@app.route("/api/signatures/<path:person_name>", methods=["DELETE"])
def api_clear_signature(person_name):
    data_store.clear_signature(person_name)
    return jsonify({"ok": True})


@app.route("/api/signatures/<path:person_name>/image", methods=["GET"])
def api_get_signature_image(person_name):
    path = data_store.get_signature_path(person_name)
    if not path:
        return "", 404
    return send_file(path, mimetype="image/png")


# ---------- Daily dashboard ----------

@app.route("/api/day/<date_str>", methods=["GET"])
def api_get_day(date_str):
    return jsonify(data_store.get_day(date_str))


@app.route("/api/days", methods=["GET"])
def api_list_days():
    """Summary of every day that has at least one generated TRA, newest first."""
    summaries = []
    for date_str in data_store.list_days():
        day = data_store.get_day(date_str)
        tras = day.get("tras", [])
        def _tra_fully_signed(t):
            approver2_ok = t.get("approver2_signed") is not False
            return t.get("approver_signed") and approver2_ok and all(s.get("signed") for s in t.get("signers", []))

        all_signed = all(_tra_fully_signed(t) for t in tras) if tras else False
        summaries.append({"date": date_str, "count": len(tras), "all_signed": all_signed})
    return jsonify(summaries)


def _default_out_name(tra_key, date_str):
    mmddyyyy = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%m%d%Y")
    return f"{tra_key} {mmddyyyy}.pdf"


# Signed documents are filed inside the project's HSE folder (the hitch's
# output folder) as:  01 SIGNED TRA's\03 March\<file>.pdf  /  02 SIGNED TBT's\...
SIGNED_FOLDERS = {"TRA": "01 SIGNED TRA's", "TBT": "02 SIGNED TBT's"}
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


def _out_dir(output_folder, category, date_str):
    """Folder a document is saved into, by its type and its date's month.
    Month names are spelled out here (not strftime) so they never depend
    on the computer's language settings."""
    month = datetime.datetime.strptime(date_str, "%Y-%m-%d").month
    return os.path.join(output_folder, SIGNED_FOLDERS.get(category, SIGNED_FOLDERS["TRA"]),
                        f"{month:02d} {MONTH_NAMES[month - 1]}")


def _validate_generate_request(body):
    """Shared checks for both the existence-check and the real generate
    call, so the two can never drift out of sync on what's allowed."""
    date_str = body["date"]
    tra_key = body["tra_key"]
    crew = body.get("crew", [])

    hitch = data_store.get_hitch()
    catalog = data_store.list_templates()
    if tra_key not in catalog:
        return None, (jsonify({"error": f"unknown TRA/TBT key {tra_key}"}), 400)

    if catalog[tra_key].get("altered"):
        return None, (jsonify({
            "error": f"'{tra_key}' has changed since it was first cataloged as a blank template (someone may have edited or signed it directly). Restore the original blank file in the DOUS Deckhand\\templates folder before generating from it."
        }), 409)

    row_limit = catalog[tra_key]["num_crew_rows"]
    if len(crew) > row_limit:
        return None, (jsonify({
            "error": f"This document only has {row_limit} signature row(s) available, but {len(crew)} crew were selected."
        }), 400)

    output_folder = (hitch.get("output_folder") or "").strip()
    output_folder = os.path.normpath(output_folder) if output_folder else ""
    if not output_folder:
        return None, (jsonify({"error": "No output folder is set for this hitch. Go to Hitch Setup and choose one before generating."}), 400)
    if not os.path.isdir(output_folder):
        try:
            os.makedirs(output_folder, exist_ok=True)
        except OSError as e:
            return None, (jsonify({"error": f"Can't create/access the output folder '{output_folder}': {e}"}), 400)

    return {"hitch": hitch, "catalog": catalog, "output_folder": output_folder}, None


@app.route("/api/generate/check", methods=["POST"])
def api_generate_check():
    """Resolve what filename a generate call would use and whether a file
    already sits there, so the UI can offer Replace/Rename/Cancel instead
    of silently overwriting (or the server silently losing track of) an
    existing document."""
    body = request.get_json(force=True)
    ctx, error_response = _validate_generate_request(body)
    if error_response:
        return error_response
    filename_override = (body.get("filename") or "").strip()
    out_name = f"{filename_override}.pdf" if filename_override else _default_out_name(body["tra_key"], body["date"])
    category = ctx["catalog"][body["tra_key"]]["category"]
    out_path = os.path.join(_out_dir(ctx["output_folder"], category, body["date"]), out_name)
    return jsonify({"name": out_name, "path": out_path, "exists": os.path.exists(out_path)})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Generate (or regenerate) one TRA/TBT for a given day.

    Body: {
      "date": "2026-10-03",
      "tra_key": "DOUS-TRA-006 WORKING AT HEIGHTS",
      "crew": [{"name": "...", "position": "..."}],   # subset participating today
      "approver_name": "...", "approver_position": "...",
      "approver2_name": "...", "approver2_position": "...",   # optional 2nd approver (e.g. night supervisor)
      "task_value": "...",   # optional, only used if the template has that field
      "filename": "..."      # optional override (no extension); from the Rename prompt
    }
    """
    body = request.get_json(force=True)
    date_str = body["date"]
    tra_key = body["tra_key"]
    crew = body.get("crew", [])
    approver_name = body.get("approver_name") or None
    approver_position = body.get("approver_position") or None
    approver2_name = body.get("approver2_name") or None
    approver2_position = body.get("approver2_position") or None
    task_value = body.get("task_value") or None
    filename_override = (body.get("filename") or "").strip()

    ctx, error_response = _validate_generate_request(body)
    if error_response:
        return error_response
    hitch, catalog, output_folder = ctx["hitch"], ctx["catalog"], ctx["output_folder"]

    template_path = catalog[tra_key]["path"]

    # Template field name -> hitch value. Each template only has some of
    # these (TRAs have Sub Location/Equipment, TBTs have Offshore Manager); the fill step ignores any a given template doesn't contain.
    # "Project If Applicable" is the TRA's Project box and the TBT's
    # Project No. box -- both are the hitch's Project #. The TBT's Offshore
    # Manager is the same information as the TRA's Approver (dept).
    common_values = {
        "Project If Applicable": hitch.get("project", ""),
        "Location  Worksite": hitch.get("location", ""),
        "Sub Location  Area": hitch.get("sub_location", ""),
        "Approver": hitch.get("approver", ""),
        "Responsible Person": hitch.get("responsible_person", ""),
        "Equipment": hitch.get("equipment", ""),
        "Offshore Manager": hitch.get("approver", ""),
    }
    approver_name = approver_name or hitch.get("approver_name", "")
    approver_position = approver_position or hitch.get("approver_position", "")
    approver2_name = approver2_name or hitch.get("approver2_name", "")
    approver2_position = approver2_position or hitch.get("approver2_position", "")

    # Most templates have exactly one Name/Position text pair for the
    # approval block (not one per approver) -- existing records already use
    # one combined "Day Supervisor / Night Supervisor" name for a day +
    # night supervisor. Combine the same way here when there's a 2nd approver.
    combined_approver_name = " / ".join(n for n in [approver_name, approver2_name] if n)
    positions = [p for p in [approver_position, approver2_position] if p]
    if len(positions) == 2 and positions[0].strip().lower() == positions[1].strip().lower():
        positions = positions[:1]  # "Supervisor / Supervisor" just reads as "Supervisor"
    combined_approver_position = " / ".join(positions)

    try:
        today_display = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d/%Y")
    except ValueError:
        today_display = date_str

    signature_images = {}
    signers_status = []
    for i, person in enumerate(crew):
        name = person.get("name", "")
        sig_path = data_store.get_signature_path(name) if name else None
        if sig_path:
            signature_images[i] = sig_path
        signers_status.append({"name": name, "position": person.get("position", ""), "signed": bool(sig_path)})

    approver_sig_path = data_store.get_signature_path(approver_name) if approver_name else None
    approver2_sig_path = data_store.get_signature_path(approver2_name) if approver2_name else None
    approver_images = [p for p in (approver_sig_path, approver2_sig_path) if p]
    if approver_images:
        signature_images["approver"] = approver_images

    out_name = f"{filename_override}.pdf" if filename_override else _default_out_name(tra_key, date_str)
    out_dir = _out_dir(output_folder, catalog[tra_key]["category"], date_str)
    out_path = os.path.join(out_dir, out_name)
    try:
        os.makedirs(out_dir, exist_ok=True)   # "01 SIGNED TRA's\03 March" etc., created on first use
    except OSError as e:
        return jsonify({"error": f"Can't create the folder '{out_dir}': {e}"}), 400

    try:
        pdf_engine.fill_template(
            template_path=template_path,
            output_path=out_path,
            common_values=common_values,
            crew=crew,
            today_str=today_display,
            task_value=task_value,
            approver_name=combined_approver_name,
            approver_position=combined_approver_position,
            signature_images=signature_images,
        )
    except PermissionError:
        return jsonify({
            "error": f"Couldn't save to '{out_path}' -- it's likely open in another program (e.g. Acrobat). Close it and try again."
        }), 409
    except Exception as e:
        return jsonify({"error": f"Failed to generate the PDF: {e}"}), 500

    def _record_tra(day):
        day["tras"] = [t for t in day["tras"] if t["tra_key"] != tra_key]
        day["tras"].append({
            "tra_key": tra_key,
            "file": out_path,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "crew": crew,
            "approver_name": approver_name,
            "approver_position": approver_position,
            "approver2_name": approver2_name,
            "approver2_position": approver2_position,
            "task_value": task_value,
            "signers": signers_status,
            "approver_signed": bool(approver_sig_path),
            "approver2_signed": bool(approver2_sig_path) if approver2_name else None,
        })

    day = data_store.update_day(date_str, _record_tra)

    try:
        os.startfile(out_path)  # noqa: S606 -- local Windows app, opens the PDF the app just saved
    except OSError:
        pass  # no default PDF viewer configured; the file is still saved fine

    return jsonify({"ok": True, "file": out_path, "day": day})


@app.route("/api/day/<date_str>/tra/<path:tra_key>/open", methods=["POST"])
def api_open_tra(date_str, tra_key):
    """Open a generated TRA/TBT (only files this app recorded for that day)."""
    entry = next((t for t in data_store.get_day(date_str)["tras"] if t["tra_key"] == tra_key), None)
    if not entry or not os.path.exists(entry.get("file", "")):
        return jsonify({"error": "That PDF wasn't found - it may have been moved or deleted."}), 404
    os.startfile(entry["file"])  # noqa: S606 -- local app opening a file it saved
    return jsonify({"ok": True})


@app.route("/api/day/<date_str>/tra/<path:tra_key>", methods=["DELETE"])
def api_remove_tra(date_str, tra_key):
    removed = []

    def _remove(day):
        removed.extend(t for t in day["tras"] if t["tra_key"] == tra_key)
        day["tras"] = [t for t in day["tras"] if t["tra_key"] != tra_key]

    day = data_store.update_day(date_str, _remove)
    for t in removed:
        try:
            if os.path.exists(t["file"]):
                os.remove(t["file"])
        except OSError:
            pass
    return jsonify({"ok": True, "day": day})


# ---------- App updates (from the private GitHub repository) ----------

@app.route("/api/version", methods=["GET"])
def api_version():
    return jsonify({"version": updater.current_version()})


@app.route("/api/update/check", methods=["GET"])
def api_update_check():
    if getattr(__import__("sys"), "frozen", False):
        return jsonify({"current": APP_VERSION, "available": False, "reason": "not available in the .exe build"})
    return jsonify(updater.check(force=request.args.get("force") == "1"))


@app.route("/api/update/install", methods=["POST"])
def api_update_install():
    """Download + verify + apply the latest release, then restart the app
    (a fresh copy starts once this one has let go of the port)."""
    import subprocess
    import sys

    if getattr(sys, "frozen", False):
        return jsonify({"error": "Updates aren't available in the .exe build."}), 400
    try:
        summary = updater.install()
    except Exception as e:
        return jsonify({"error": f"The update didn't install: {e}"}), 500

    launcher = os.path.join(os.path.dirname(os.path.abspath(__file__)), "start_app.pyw")
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    subprocess.Popen([pythonw, launcher, "--background", "--wait-port"],
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                     close_fds=True)
    threading.Timer(1.0, lambda: os._exit(0)).start()
    return jsonify({"ok": True, **summary})


# ---------- Weekly timesheets ----------

def _parse_week(week_str):
    """The week-ending date; timesheets only ever end on a Sunday."""
    try:
        d = datetime.datetime.strptime(week_str, "%Y-%m-%d").date()
    except ValueError:
        return None, (jsonify({"error": "Invalid date."}), 400)
    if d.weekday() != 6:
        return None, (jsonify({"error": "The week-ending date must be a Sunday."}), 400)
    return d, None


def _crew_member(hitch, name):
    return next((c for c in hitch.get("crew", []) if c.get("name") == name), None)


def _shift(member):
    slot = member.get("slot") or ""
    if slot.startswith("night"):
        return "night"
    if slot.startswith("day"):
        return "day"
    return member.get("shift") or "day"


def _ts_supervisor(hitch, member):
    """Day-shift crew get the Day Shift Supervisor's signature, night-shift
    crew the Night Shift Supervisor's; supervisors sign their own as both."""
    if member.get("slot") in ("day_supervisor", "night_supervisor"):
        return member["name"]
    if _shift(member) == "night":
        return hitch.get("approver2_name") or ""
    return hitch.get("approver_name") or ""


def _ts_default_ops(hitch):
    return {"client": hitch.get("client", ""), "vessel": hitch.get("location", ""),
            "project": hitch.get("project", ""), "system": hitch.get("equipment", "")}


def _ts_plan(hitch, member, week_ending):
    """Where this person's timesheet goes and who signs it -- shared by the
    pre-check and the real generate so they can't disagree."""
    name = member["name"]
    folder = (hitch.get("ts_output_folder") or "").strip()
    folder = os.path.normpath(folder) if folder else ""   # the picker returns C:/... style paths
    supervisor = _ts_supervisor(hitch, member)
    problems = []
    if not folder:
        problems.append("No timesheet output folder is set. On Hitch Setup, choose the project's "
                        "\"7 - TIMESHEETS & MILEAGE REPORT\" folder.")
    elif not os.path.isdir(folder):
        problems.append(f"The timesheet output folder can't be reached: {folder}")
    if not member.get("official_position"):
        problems.append(f"{name} has no official position set on Hitch Setup.")
    if not supervisor:
        problems.append(f"No {'Night' if _shift(member) == 'night' else 'Day'} Shift Supervisor "
                        "is entered in the crew roster on Hitch Setup.")
    elif not data_store.get_signature_path(supervisor):
        problems.append(f"{supervisor} (supervisor) has no signature saved yet - capture it on the "
                        "Signatures tab first.")
    out_dir = timesheet.output_dir(folder, name, bool(member.get("contractor")), week_ending) if folder else ""
    out_path = os.path.join(out_dir, timesheet.file_name(name, week_ending)) if folder else ""
    return {"name": name, "supervisor": supervisor, "path": out_path,
            "exists": bool(out_path) and os.path.exists(out_path),
            "has_signature": bool(data_store.get_signature_path(name)),
            "contractor": bool(member.get("contractor")), "shift": _shift(member),
            "official_position": member.get("official_position", ""), "problems": problems}


@app.route("/api/timesheets/<week_str>", methods=["GET"])
def api_get_timesheet_week(week_str):
    week_ending, err = _parse_week(week_str)
    if err:
        return err
    hitch = data_store.get_hitch()
    rec = data_store.get_timesheet_week(week_str)
    people = []
    for member in hitch.get("crew", []):
        if not member.get("name"):
            continue
        plan = _ts_plan(hitch, member, week_ending)
        plan["codes"] = rec["codes"].get(member["name"], ["O"] * 7)
        plan["generated"] = rec["generated"].get(member["name"])
        people.append(plan)
    return jsonify({
        "week_ending": week_str,
        "week_number": timesheet.week_number(week_ending),
        "days": [str(week_ending - datetime.timedelta(days=6 - i)) for i in range(7)],
        "ops": rec["ops"] or _ts_default_ops(hitch),
        "people": people,
        "positions": timesheet.OFFICIAL_POSITIONS,
        "acknowledgement": timesheet.ACKNOWLEDGEMENT,
    })


@app.route("/api/timesheets/<week_str>", methods=["POST"])
def api_save_timesheet_week(week_str):
    """Save the week's day codes / operations line as they're edited."""
    _, err = _parse_week(week_str)
    if err:
        return err
    body = request.get_json(force=True)

    def mutate(rec):
        for name, codes in (body.get("codes") or {}).items():
            rec["codes"][name] = [c if c in timesheet.DAY_CODES else "" for c in list(codes)[:7]]
        if body.get("ops") is not None:
            rec["ops"] = {k: str(body["ops"].get(k, "")) for k in ("client", "vessel", "project", "system")}
    data_store.update_timesheet_week(week_str, mutate)
    return jsonify({"ok": True})


@app.route("/api/timesheets/<week_str>/generate", methods=["POST"])
def api_generate_timesheet(week_str):
    """Generate one person's timesheet. Only called after that person has
    confirmed the acknowledgement prompt in the app."""
    week_ending, err = _parse_week(week_str)
    if err:
        return err
    body = request.get_json(force=True)
    if not body.get("acknowledged"):
        return jsonify({"error": "The employee must acknowledge the timesheet first."}), 400
    hitch = data_store.get_hitch()
    member = _crew_member(hitch, body.get("name", ""))
    if not member:
        return jsonify({"error": "That person isn't on this hitch's crew roster."}), 400
    plan = _ts_plan(hitch, member, week_ending)
    if plan["problems"]:
        return jsonify({"error": " ".join(plan["problems"])}), 400
    employee_sig = data_store.get_signature_path(member["name"])
    if not employee_sig:
        return jsonify({"error": f"{member['name']} has no signature saved yet."}), 400
    codes = [c if c in timesheet.DAY_CODES else "" for c in list(body.get("codes") or [])[:7]]
    codes += [""] * (7 - len(codes))
    ops = {k: str((body.get("ops") or {}).get(k, "")) for k in ("client", "vessel", "project", "system")}

    template = os.path.join(data_store.TEMPLATES_ROOT, "TS", "DOUS Weekly Timesheet.pdf")
    try:
        timesheet.fill_timesheet(template, plan["path"], name=member["name"],
                                 official_position=member["official_position"], week_ending=week_ending,
                                 ops=ops, codes=codes, employee_sig=employee_sig,
                                 supervisor_sig=data_store.get_signature_path(plan["supervisor"]))
    except PermissionError:
        return jsonify({"error": f"Couldn't save '{plan['path']}' - it's probably open in another program. Close it and try again."}), 409
    except OSError as e:
        return jsonify({"error": f"Couldn't save the timesheet: {e}"}), 400

    entry = {"file": plan["path"], "supervisor": plan["supervisor"],
             "acknowledged_at": datetime.datetime.now().isoformat(timespec="seconds")}

    def mutate(rec):
        rec["codes"][member["name"]] = codes
        rec["ops"] = ops
        rec["generated"][member["name"]] = entry
    data_store.update_timesheet_week(week_str, mutate)
    return jsonify({"ok": True, **entry})


@app.route("/api/timesheets/<week_str>/open", methods=["POST"])
def api_open_timesheet(week_str):
    """Open a generated timesheet (only files this app recorded)."""
    body = request.get_json(force=True)
    entry = data_store.get_timesheet_week(week_str)["generated"].get(body.get("name", ""))
    if not entry or not os.path.exists(entry["file"]):
        return jsonify({"error": "That timesheet file wasn't found."}), 404
    os.startfile(entry["file"])  # noqa: S606 -- local app opening a file it saved
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
