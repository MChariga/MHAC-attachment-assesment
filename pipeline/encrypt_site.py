#!/usr/bin/env python3
"""
Build the PUBLIC copy of the dashboard with all data encrypted.

  dashboard/  (plaintext data written by kobo_pipeline.py)  ->  site/  (safe to publish)

In site/data/ only entries.enc.json remains: AES-256-GCM, key derived from the passphrase with
PBKDF2-SHA256 (600,000 rounds), random salt and nonce on every run. The plaintext entries.json,
entries.js and entries_flat.csv are removed. The dashboard decrypts in the browser after the
viewer types the passphrase, so the passphrase is never sent anywhere.

Needs the DASHBOARD_PASSPHRASE environment variable (a GitHub secret in the workflow).
Use a long random passphrase: the encrypted file is public, so people can guess offline.
"""
import base64, hashlib, json, os, shutil, sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    sys.exit("Missing dependency. Run: pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
SRC, DST = ROOT / "dashboard", ROOT / "site"
ITER = 600_000
MIN_LEN = 16


def main():
    pw = os.environ.get("DASHBOARD_PASSPHRASE", "")
    if len(pw) < MIN_LEN:
        sys.exit(f"DASHBOARD_PASSPHRASE is missing or shorter than {MIN_LEN} characters. "
                 "Set it as a GitHub secret (use 5+ random words).")
    plain = SRC / "data" / "entries.json"
    if not plain.exists():
        sys.exit("dashboard/data/entries.json not found. Run kobo_pipeline.py first.")

    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    salt, nonce = os.urandom(16), os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, ITER, dklen=32)
    ct = AESGCM(key).encrypt(nonce, plain.read_bytes(), None)  # ciphertext || 16-byte tag
    pkg = {"v": 1, "kdf": "PBKDF2-SHA256", "iter": ITER,
           "salt": base64.b64encode(salt).decode(), "iv": base64.b64encode(nonce).decode(),
           "ct": base64.b64encode(ct).decode()}

    data = DST / "data"
    for name in ("entries.json", "entries.js", "entries_flat.csv"):
        (data / name).unlink(missing_ok=True)
    (data / "entries.enc.json").write_text(json.dumps(pkg), encoding="utf-8")
    (data / "entries.js").write_text("window.ASSESSMENT_DATA = null;\n", encoding="utf-8")  # no plaintext
    print(f"Encrypted site written to {DST}")


if __name__ == "__main__":
    main()
