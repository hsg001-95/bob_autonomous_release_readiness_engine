#!/usr/bin/env python3
"""
secrets_sentinel.py — Standard-library-only secrets scanner for RRE.

Scans a repository tree for literal credentials via:
  1. High-confidence pattern matches (known key formats).
  2. Shannon-entropy analysis on suspiciously-named string assignments.

Usage:
    python3 secrets_sentinel.py <repo_root> [--allowlist path] [--out path]

Exit code: 0 if no findings, 1 if any finding (for CI gating).
Dependencies: none beyond the Python standard library.
"""
import argparse
import json
import math
import os
import re
import sys

# --- Pattern pass -----------------------------------------------------

PATTERNS = {
    "aws-access-key-id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "generic-api-key-assignment": re.compile(
        r"""(?i)\b(api[_-]?key|secret[_-]?key)\b\s*[:=]\s*['"][A-Za-z0-9_\-]{20,}['"]"""
    ),
    "private-key-block": re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"),
    "db-connection-string-with-password": re.compile(
        r"""(?i)(postgres|mysql|mongodb)(\+\w+)?://[^:\s]+:[^@\s]+@"""
    ),
}

# --- Entropy pass -------------------------------------------------------

ASSIGNMENT_RE = re.compile(
    r"""(?i)\b(\w*(?:key|secret|token|password|pwd|credential)\w*)\s*[:=]\s*['"]([^'"]{16,})['"]"""
)
PLACEHOLDER_VALUES = {
    "changeme", "xxx", "your-key-here", "your_key_here", "replace-me",
    "example", "dummy", "test", "placeholder",
}
ENTROPY_THRESHOLD_BITS_PER_CHAR = 4.0


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in freq.values())


def load_allowlist(path):
    if not path or not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return {line.strip() for line in f if line.strip() and not line.startswith("#")}


def load_bobignore(repo_root):
    ignore_path = os.path.join(repo_root, ".bobignore")
    patterns = []
    if os.path.exists(ignore_path):
        with open(ignore_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line.rstrip("/"))
    return patterns


def is_ignored(rel_path, ignore_patterns):
    parts = rel_path.split(os.sep)
    for pat in ignore_patterns:
        clean = pat.strip("*").strip("/")
        if clean and clean in parts:
            return True
        if pat.startswith("*.") and rel_path.endswith(pat[1:]):
            return True
    return False


TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".md", ".txt",
    ".env", ".cfg", ".ini", ".toml", ".sh",
}


def scan_repo(repo_root, allowlist):
    ignore_patterns = load_bobignore(repo_root)
    findings = []

    for dirpath, dirnames, filenames in os.walk(repo_root):
        rel_dir = os.path.relpath(dirpath, repo_root)
        dirnames[:] = [
            d for d in dirnames
            if not is_ignored(os.path.join(rel_dir, d), ignore_patterns)
        ]
        for fname in filenames:
            rel_path = os.path.normpath(os.path.join(rel_dir, fname))
            if is_ignored(rel_path, ignore_patterns):
                continue
            ext = os.path.splitext(fname)[1]
            if ext and ext not in TEXT_EXTENSIONS:
                continue

            full_path = os.path.join(dirpath, fname)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except OSError:
                continue

            for lineno, line in enumerate(lines, start=1):
                # Check allowlist before matching patterns
                if any(allowed in line for allowed in allowlist):
                    continue

                # Pattern pass
                for rule_id, pattern in PATTERNS.items():
                    if pattern.search(line):
                        findings.append({
                            "id": f"secret-{len(findings) + 1:03d}",
                            "category": "secret",
                            "severity": "critical",
                            "location": f"{rel_path}:{lineno}",
                            "description": f"Matched pattern '{rule_id}'",
                            "rule_ref": "R9",
                        })

                # Entropy pass
                for m in ASSIGNMENT_RE.finditer(line):
                    var_name, value = m.group(1), m.group(2)
                    if value.lower() in PLACEHOLDER_VALUES or value in allowlist:
                        continue
                    entropy = shannon_entropy(value)
                    if entropy >= ENTROPY_THRESHOLD_BITS_PER_CHAR:
                        findings.append({
                            "id": f"secret-{len(findings) + 1:03d}",
                            "category": "secret",
                            "severity": "critical",
                            "location": f"{rel_path}:{lineno}",
                            "description": (
                                f"High-entropy value ({entropy:.2f} bits/char) assigned "
                                f"to '{var_name}' — looks like a credential"
                            ),
                            "rule_ref": "R9",
                        })
    return findings


def main():
    parser = argparse.ArgumentParser(description="Scan a repo for literal secrets.")
    parser.add_argument("repo_root")
    parser.add_argument("--allowlist", default="security/secrets-allowlist.txt")
    parser.add_argument("--out", default="security/secrets-findings.json")
    args = parser.parse_args()

    allowlist = load_allowlist(args.allowlist)
    findings = scan_repo(args.repo_root, allowlist)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"subagent": "secrets-sentinel", "findings": findings}, f, indent=2)

    print(f"secrets-sentinel: {len(findings)} finding(s) written to {args.out}")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
