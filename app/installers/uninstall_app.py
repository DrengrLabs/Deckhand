"""Remove the app from this computer (run via UNINSTALL.bat).

Removes the desktop icon, the start-with-Windows shortcut, and the
"DOUS Deckhand" folder (templates included). Everything is sent
to the Recycle Bin (not permanently deleted), so a mistaken uninstall can
be undone from there. Signed PDFs already saved to project output folders
are never touched.
"""
import ctypes
import os
import subprocess
import sys

# This helper lives in DOUS Deckhand\app\installers; DOUS Deckhand is three levels up.
APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PORT = int(os.environ.get("TRA_APP_PORT", "5000"))   # override only for testing
NO_WINDOW = subprocess.CREATE_NO_WINDOW


def shell_folder(csidl):
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return buf.value


def powershell(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                          capture_output=True, text=True, creationflags=NO_WINDOW)


def ps_quote(s):
    return "'" + s.replace("'", "''") + "'"


def stop_running_app():
    """Stop the app's background process (whatever Python is serving the port)."""
    powershell(
        f"Get-NetTCPConnection -LocalPort {PORT} -State Listen -ErrorAction SilentlyContinue | "
        "ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; "
        "if ($p -and $p.ProcessName -like 'python*') { Stop-Process -Id $p.Id -Force } }"
    )


def recycle(folder):
    # Templates are read-only on purpose; clear that so they can be recycled.
    for dirpath, _, files in os.walk(folder):
        for f in files:
            try:
                os.chmod(os.path.join(dirpath, f), 0o666)
            except OSError:
                pass
    r = powershell(
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory({ps_quote(folder)}, "
        "'OnlyErrorDialogs', 'SendToRecycleBin')"
    )
    return r.returncode == 0 and not os.path.exists(folder), r.stderr.strip()


def main():
    shortcuts = [p for p in (
        os.path.join(shell_folder(0x10), "DOUS Deckhand.lnk"),                # desktop
        os.path.join(shell_folder(0x07), "DOUS Deckhand (background).lnk"),   # startup
        # names used before v1.1
        os.path.join(shell_folder(0x10), "DOUS TRA-TBT App.lnk"),
        os.path.join(shell_folder(0x07), "DOUS TRA-TBT App (background).lnk"),
    ) if os.path.exists(p)]
    # The TRA/TBT templates live inside the app folder (DOUS Deckhand\templates).
    folders = [APP] if os.path.isdir(APP) else []

    print("UNINSTALL - DOUS Deckhand")
    print("=" * 40)
    print("\nThis will remove from this computer:")
    for p in shortcuts + folders:
        print("   ", p)
    print("\nThat includes ALL saved hitch setups, crew rosters, the signature")
    print("library and History. Signed PDFs already saved to your project")
    print("output folders are NOT touched.")
    print("\nEverything goes to the Recycle Bin, so it can be restored from there")
    print("if this was a mistake.\n")
    if input("Type YES to uninstall (anything else cancels): ").strip() != "YES":
        print("\nCancelled - nothing was removed.")
        return

    stop_running_app()
    for p in shortcuts:
        os.remove(p)
        print("Removed", p)
    problems = []
    for p in folders:
        ok, err = recycle(p)
        print(("Recycled " if ok else "COULD NOT REMOVE ") + p)
        if not ok:
            problems.append((p, err))

    if problems:
        print("\nSome folders couldn't be removed -- a file inside may be open")
        print("(e.g. a PDF in Acrobat). Close it and run UNINSTALL.bat again,")
        print("or delete the folder by hand.")
        for p, err in problems:
            if err:
                print("   ", p, "-", err[:200])
    else:
        print("\nUninstall complete.")


if __name__ == "__main__":
    try:
        main()
    finally:
        input("\nPress Enter to close this window...")
