#!/usr/bin/env python3
"""Install pinned recorder WASM assets with SHA-256 verification."""
import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.10.22-rc.20250304'
ASSETS = {'vision_wasm_nosimd_internal.wasm': '3821ea9b1f7fb8c549ef2a064ef5c85750bf375c545a49fd6eea0df44a95f1f4', 'vision_wasm_internal.wasm': 'f00ec4731faa23b3e714d00e88d4d10e2df5c0a427d3a2b4ae6e3526fdd14ef7'}

def prepare():
    directory = ROOT / 'public/vendor/wasm'
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in ASSETS.items():
        target = directory / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            print('Verified:', name)
            continue
        url = f'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@{VERSION}/wasm/{name}'
        temporary = None
        try:
            digest = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=60) as response:
                with tempfile.NamedTemporaryFile(dir=directory, delete=False) as output:
                    temporary = Path(output.name)
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                        digest.update(chunk)
            if digest.hexdigest() != expected:
                raise RuntimeError('Asset integrity check failed: ' + name)
            temporary.chmod(0o644)
            os.replace(temporary, target)
            print('Installed:', name)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

if __name__ == '__main__':
    prepare()
