"""Publish a DOUS Deckhand release to the private GitHub repo.

    python tools\\make_release.py 1.2.0 "What changed, one line per item"

What it does:
  1. Sets app\\VERSION.
  2. Builds a clean copy (no saved data, caches, logs or these tools) and
     adds app\\update_config.json with the READ-ONLY update key, read from
     update-token.txt in the folder above this repository.
  3. Makes the release files:
       DOUS-Deckhand.zip   full package for new computers (GitHub doesn't allow
                           spaces in release file names)
       app-update.zip      program files only (small) -- for in-app updates
       templates.zip       the templates (computers only download it if
                           their templates differ)
       manifest.json       version, notes and SHA-256 of every file
  4. Commits and pushes the code, then creates the GitHub release with
     those files attached. Every installed copy then offers the update.

Needs: git, the GitHub CLI (gh) logged in as the repo owner, and the
one-time installers in app\\installers (they're kept out of git).
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

REPO = "DrengrLabs/Deckhand"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # repo root
TOKEN_FILE = os.path.join(os.path.dirname(ROOT), "update-token.txt")
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"

# One-time installers: in the full package, never pushed out as updates.
NOT_UPDATED = ("app/installers/python-", "app/installers/sigweb.exe", "app/installers/wheels/")
SKIP_DIRS = {".git", "tools", "__pycache__", "dist"}
SKIP_FILES = {"install_error_log.txt", "update_config.json"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def run(*cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def staged_files():
    """(relative path with /, absolute path) of everything that ships."""
    for root, dirs, files in os.walk(ROOT):
        rel_root = os.path.relpath(root, ROOT).replace("\\", "/")
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            rel = name if rel_root == "." else f"{rel_root}/{name}"
            if name in SKIP_FILES or name.endswith((".log", ".pyc", ".updating")):
                continue
            if rel.startswith("app/app_data/") and rel != "app/app_data/template_baselines.json":
                continue                                   # never ship anyone's saved data
            if rel.startswith(".git"):
                continue
            yield rel, os.path.join(root, name)


def build_zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel, data in entries:
            z.writestr(rel, data)
    return buf.getvalue()


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    version, notes = sys.argv[1].lstrip("vV"), sys.argv[2]
    if not os.path.exists(TOKEN_FILE):
        sys.exit(f"Update key not found: {TOKEN_FILE}")
    token = open(TOKEN_FILE, encoding="utf-8").read().strip()
    for need in ("app/installers/sigweb.exe", "app/installers/wheels"):
        if not os.path.exists(os.path.join(ROOT, *need.split("/"))):
            sys.exit(f"Missing {need} - the full package needs the one-time installers.")

    with open(os.path.join(ROOT, "app", "VERSION"), "w", encoding="utf-8") as fh:
        fh.write(version + "\n")

    files = {rel: open(path, "rb").read() for rel, path in staged_files()}
    files["app/update_config.json"] = json.dumps({"repo": REPO, "token": token}, indent=1).encode()

    updatable = {rel: data for rel, data in files.items() if not rel.startswith(NOT_UPDATED)}
    app_zip = build_zip((r, d) for r, d in sorted(updatable.items()) if not r.startswith("templates/"))
    tpl_zip = build_zip((r, d) for r, d in sorted(updatable.items()) if r.startswith("templates/"))
    full_zip = build_zip(sorted(files.items()))
    manifest = {
        "version": version, "notes": notes,
        "app_zip_sha256": sha256(app_zip), "templates_zip_sha256": sha256(tpl_zip),
        "files": {rel: sha256(data) for rel, data in sorted(updatable.items())},
    }

    out = tempfile.mkdtemp(prefix="deckhand_release_")
    assets = {"DOUS-Deckhand.zip": full_zip, "app-update.zip": app_zip,
              "templates.zip": tpl_zip, "manifest.json": json.dumps(manifest, indent=1).encode()}
    for name, data in assets.items():
        with open(os.path.join(out, name), "wb") as fh:
            fh.write(data)
        print(f"  {name:20} {len(data) / 1048576:7.1f} MB")

    run("git", "add", "-A")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0:
        run("git", "commit", "-m", f"Release v{version}")
    run("git", "push", "origin", "HEAD")
    run(GH, "release", "create", f"v{version}", "--repo", REPO,
        "--title", f"DOUS Deckhand v{version}", "--notes", notes,
        *[os.path.join(out, name) for name in assets])
    shutil.rmtree(out, ignore_errors=True)
    print(f"\nPublished v{version}. Installed copies will offer it next time they open.")
    print(f"For a brand-new computer, download 'DOUS-Deckhand.zip' from the release page.")


if __name__ == "__main__":
    main()
