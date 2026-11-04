"""Prepare a project-local environment once, then launch Verdant Trials."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info < (3,10):
        print('Verdant Trials requires Python 3.10 or newer.',file=sys.stderr)
        return 1
    environment = ROOT/'.venv'
    python = environment/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        print('Preparing the local game environment…',flush=True)
        subprocess.run([sys.executable,'-m','venv',str(environment)],check=True)
    requirements = ROOT/'requirements.txt'
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = environment/'.verdant-requirements.sha256'
    recorded = marker.read_text().strip() if marker.exists() else ''
    # Inspect package metadata rather than importing graphics libraries. A missing
    # system EGL driver cannot be repaired by reinstalling Python packages.
    probe = subprocess.run([str(python),'-c',
        'from importlib.metadata import version; version("PySide6-Essentials"); version("Pillow")'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if recorded != fingerprint or probe.returncode:
        print('Installing game dependencies into .venv…',flush=True)
        subprocess.run([str(python),'-m','pip','install','-r',str(requirements)],check=True)
        marker.write_text(fingerprint+'\n')
    os.execv(str(python),[str(python),str(ROOT/'main.py'),*sys.argv[1:]])


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print('Setup did not finish. Check the message above, then run ./launch again.',file=sys.stderr)
        raise SystemExit(error.returncode)
