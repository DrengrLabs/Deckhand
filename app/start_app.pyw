"""Start / open the app with no console window.

Runs under pythonw.exe (the .pyw extension), so no black window appears.

    start_app.pyw               open the app (starting it first if needed)
    start_app.pyw --background  just make sure it's running (used at
                                Windows sign-in, so a Chrome bookmark to
                                http://127.0.0.1:5000/ always works)

The app opens in its own Chrome/Edge window (no tabs or address bar) so it
looks and behaves like a normal desktop program; if neither browser is
found it opens in the default browser instead. Server output goes to
app_data\\app.log. For troubleshooting with a visible console, use run.bat.
"""
import os
import socket
import subprocess
import sys
import threading
import webbrowser

FROZEN = getattr(sys, "frozen", False)      # running as the packaged "DOUS Deckhand.exe"
# The "app" folder: where app_data lives (and the .exe, when packaged).
HERE = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
PORT = int(os.environ.get("TRA_APP_PORT", "5000"))   # override only for testing
URL = f"http://127.0.0.1:{PORT}/"
os.chdir(HERE)
sys.path.insert(0, HERE)

BROWSERS = [
    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
    os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
]


def already_running():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def open_window():
    for exe in BROWSERS:
        if os.path.exists(exe):
            subprocess.Popen([exe, f"--app={URL}"])
            return
    webbrowser.open(URL)


def show_error(message):
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("DOUS Deckhand", message)
        root.destroy()
    except Exception:
        pass


def pick_folder(initial, out_file):
    """"--pick-folder" mode for the packaged .exe: show the native folder
    picker and write the chosen path to out_file (see app.api_browse_folder)."""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(initialdir=initial or None,
                                     title="Select the project's HSE folder", parent=root)
    root.destroy()
    with open(out_file, "w", encoding="utf-8") as fh:
        fh.write(folder or "")


def _run_hidden(args, **kw):
    return subprocess.run(args, capture_output=True, text=True,
                          creationflags=subprocess.CREATE_NO_WINDOW, **kw)


def _ask_yes_no(title, message):
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        answer = messagebox.askyesno(title, message, parent=root)
        root.destroy()
        return answer
    except Exception:
        return False


def _show_info(title, message):
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(title, message, parent=root)
        root.destroy()
    except Exception:
        pass


def first_run_setup():
    """Packaged .exe only: the first time it's opened from a new location,
    do what "INSTALL - run once.bat" does for the Python version, so there's
    no separate installer -- just double-click DOUS Deckhand.exe.

      * clear Windows' "downloaded/blocked" mark from the app's files
      * put back the templates' read-only protection (lost when unzipping)
      * desktop icon + start-with-Windows shortcut
      * offer to set up Topaz SigWeb for the signature pad (one admin prompt)
      * remind about PC Matic SuperShield, if it's on this computer

    Runs again only if the folder is moved (the shortcuts would be stale).
    """
    import json
    import stat

    marker = os.path.join(HERE, "app_data", "setup.json")
    try:
        with open(marker, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        state = {}
    exe = os.path.abspath(sys.executable)
    if state.get("exe") == exe:
        return
    first_time = not state

    for root, _dirs, files in os.walk(HERE):
        for name in files:
            path = os.path.join(root, name)
            try:
                os.remove(path + ":Zone.Identifier")      # the "blocked" mark
            except OSError:
                pass
            if name.lower().endswith(".pdf") and os.path.join(HERE, "templates") in path:
                try:
                    os.chmod(path, stat.S_IREAD)
                except OSError:
                    pass

    # (DOUS_LINK_DIR is only for testing: puts the shortcuts somewhere harmless)
    ps_links = (
        "$exe = $env:DOUS_EXE; $dir = Split-Path $exe; $sh = New-Object -ComObject WScript.Shell;"
        "$desk = [Environment]::GetFolderPath('Desktop'); $start = [Environment]::GetFolderPath('Startup');"
        "if ($env:DOUS_LINK_DIR) { $desk = $env:DOUS_LINK_DIR; $start = $env:DOUS_LINK_DIR };"
        "Remove-Item -LiteralPath ($desk + '\\DOUS TRA-TBT App.lnk'), ($start + '\\DOUS TRA-TBT App (background).lnk') -ErrorAction SilentlyContinue;"
        "$d = $sh.CreateShortcut($desk + '\\DOUS Deckhand.lnk');"
        "$d.TargetPath = $exe; $d.WorkingDirectory = $dir; $d.IconLocation = $exe + ',0';"
        "$d.Description = 'Open the DOUS Daily TRA / TBT app'; $d.Save();"
        "$s = $sh.CreateShortcut($start + '\\DOUS Deckhand (background).lnk');"
        "$s.TargetPath = $exe; $s.Arguments = '--background'; $s.WorkingDirectory = $dir; $s.IconLocation = $exe + ',0';"
        "$s.Description = 'Keeps the DOUS TRA / TBT app running'; $s.Save()"
    )
    _run_hidden(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_links],
                env={**os.environ, "DOUS_EXE": exe})

    # Topaz SigWeb: installed and set to the T-LBK460? (see setup_sigweb.ps1)
    sigweb_ok = _run_hidden(["sc", "query", "SigREST"]).returncode == 0
    try:
        with open(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "SigPlus.ini"), encoding="latin-1") as fh:
            sigweb_ok = sigweb_ok and "tabletmodel=siglitelcd1x5" in fh.read().lower().replace(" ", "")
    except OSError:
        sigweb_ok = False
    setup_ps1 = os.path.join(HERE, "installers", "setup_sigweb.ps1")
    if not sigweb_ok and os.path.exists(setup_ps1) and _ask_yes_no(
            "DOUS Deckhand - signature pad",
            "Set up the Topaz signature pad now?\n\n"
            "Windows will ask for permission - click Yes. If the Topaz installer "
            "opens, click through it accepting the defaults; the pad model is set "
            "automatically afterwards.\n\n"
            "(Choose No if this computer has no Topaz pad - signatures can still "
            "be drawn with the mouse.)"):
        _run_hidden(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                     "Start-Process powershell -Verb RunAs -Wait -ArgumentList "
                     "('-NoProfile -ExecutionPolicy Bypass -File \"' + $env:DOUS_PS1 + '\"')"],
                    env={**os.environ, "DOUS_PS1": setup_ps1})

    pcmatic = _run_hidden(["powershell", "-NoProfile", "-Command",
                           "if ((Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match 'pcmatic|pcpitstop|supershield' }) -or "
                           "(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'PC Matic|PC Pitstop|SuperShield' }) -or "
                           "(Get-ChildItem 'C:\\Program Files*\\PC Matic*','C:\\Program Files*\\PC Pitstop*' -Directory -ErrorAction SilentlyContinue)) { exit 0 } else { exit 1 }"]
                          ).returncode == 0

    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump({"exe": exe}, fh)

    message = ("Setup complete.\n\nFrom now on, open the app with the \"DOUS Deckhand\" icon "
               "on the desktop (or a Chrome bookmark to http://127.0.0.1:5000/). It also starts "
               "automatically whenever this computer starts.\n\nLeave this DOUS Deckhand folder where it "
               "is - the app runs from here." if first_time else
               "The DOUS Deckhand folder was moved - the desktop icon and start-up shortcut now point "
               "to its new location.")
    if pcmatic:
        message += ("\n\nPC MATIC: in the app that opens next, capture a signature and generate one "
                    "PDF, clicking ALWAYS ALLOW on any PC Matic pop-up. Then set SuperShield back: "
                    "green SuperShield icon > Protection Level > Block Notification Method > Display Only.")
    _show_info("DOUS Deckhand", message)


def ensure_requirements():
    """First run on a new computer: install the packages, without a window."""
    if FROZEN:
        return True                                 # everything is sealed inside the .exe
    try:
        import flask, pypdf, pymupdf  # noqa: F401
        return True
    except ImportError:
        pass
    python = os.path.join(os.path.dirname(sys.executable), "python.exe")
    # Bundled packages first (no internet needed), then the internet.
    for extra in (["--no-index", "--find-links", os.path.join("installers", "wheels")], []):
        result = subprocess.run(
            [python, "-m", "pip", "install", "-q", *extra, "-r", "requirements.txt"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            break
    if result.returncode != 0:
        show_error("Couldn't install the app's required packages (an internet "
                   "connection is needed the first time).\n\nTry double-clicking "
                   "run.bat instead to see the details.\n\n" + result.stderr[-800:])
        return False
    return True


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "--pick-folder":
        pick_folder(sys.argv[2], sys.argv[3])
        return
    background = "--background" in sys.argv
    if "--wait-port" in sys.argv:
        # Restart after an update: wait for the old copy to let go of the port.
        import time
        for _ in range(40):
            if not already_running():
                break
            time.sleep(0.5)
    if FROZEN and not background:
        try:
            first_run_setup()
        except Exception as e:                      # never let setup stop the app opening
            show_error(f"First-time setup hit a problem (the app will still open):\n\n{e}")
    if already_running():
        if not background:
            open_window()
        return
    if not ensure_requirements():
        return

    # pythonw has no console: anything printed (including Flask's request
    # log) must go to a file, or writing to the missing console can crash.
    os.makedirs(os.path.join(HERE, "app_data"), exist_ok=True)
    log_path = os.path.join(HERE, "app_data", "app.log")
    if os.path.exists(log_path) and os.path.getsize(log_path) > 2_000_000:
        os.replace(log_path, log_path + ".old")   # keep the log from growing forever
    log = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log

    try:
        import app
    except Exception as e:
        show_error(f"The app failed to start:\n\n{e}\n\nTry run.bat to see the details.")
        raise

    if not background:
        threading.Timer(1.0, open_window).start()
    try:
        app.app.run(host="127.0.0.1", port=PORT, debug=False)
    except OSError as e:
        show_error(f"The app couldn't start on port {PORT}:\n\n{e}")


if __name__ == "__main__":
    main()
