#!/usr/bin/env python3
"""
generate_sbom.py — Standard-library-only SBOM generator for RRE (supply-sentinel).

Produces a CycloneDX-lite JSON SBOM from the currently-installed environment
and cross-references it against requirements.txt per Rule R10 (Dependency
Provenance): anything installed but not declared, or declared but not
resolvable, is reported as a medium-severity finding.

Usage:
    python3 generate_sbom.py [--requirements requirements.txt] [--out sbom/bom.json]

Dependencies: none beyond the Python standard library (importlib.metadata
is stdlib as of Python 3.8+).
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone

try:
    from importlib import metadata as importlib_metadata
except ImportError:  # pragma: no cover - Python <3.8 fallback
    import importlib_metadata  # type: ignore


REQUIREMENT_NAME_RE = re.compile(r"^([A-Za-z0-9_.\-]+)")


def parse_requirements(path):
    names = set()
    if not os.path.exists(path):
        return names
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            m = REQUIREMENT_NAME_RE.match(line)
            if m:
                names.add(m.group(1).lower())
    return names


def build_sbom():
    components = []
    installed_names = set()
    for dist in importlib_metadata.distributions():
        name = dist.metadata.get("Name") or dist.metadata.get("Summary") or "unknown"
        version = dist.version or "unknown"
        license_ = dist.metadata.get("License") or "UNKNOWN"
        installed_names.add(name.lower())
        components.append({
            "type": "library",
            "name": name,
            "version": version,
            "licenses": [{"license": {"name": license_}}],
        })
    return components, installed_names


def cross_reference(installed_names, declared_names):
    findings = []
    undeclared = sorted(installed_names - declared_names)
    unresolved = sorted(declared_names - installed_names)

    for name in undeclared:
        findings.append({
            "id": f"prov-{len(findings) + 1:03d}",
            "category": "dependency-provenance",
            "severity": "medium",
            "location": "requirements.txt",
            "description": f"Package '{name}' is installed but not declared in requirements.txt",
            "rule_ref": "R10",
        })
    for name in unresolved:
        findings.append({
            "id": f"prov-{len(findings) + 1:03d}",
            "category": "dependency-provenance",
            "severity": "medium",
            "location": "requirements.txt",
            "description": f"Package '{name}' is declared in requirements.txt but not resolvable in the environment",
            "rule_ref": "R10",
        })
    return findings


def main():
    parser = argparse.ArgumentParser(description="Generate a CycloneDX-lite SBOM.")
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--out", default="sbom/bom.json")
    parser.add_argument("--findings-out", default="security/provenance-findings.json")
    args = parser.parse_args()

    components, installed_names = build_sbom()
    declared_names = parse_requirements(args.requirements)
    findings = cross_reference(installed_names, declared_names)

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:generated-by-rre",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [{"name": "RRE supply-sentinel", "version": "1.0"}],
        },
        "components": components,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(bom, f, indent=2)

    os.makedirs(os.path.dirname(args.findings_out) or ".", exist_ok=True)
    with open(args.findings_out, "w", encoding="utf-8") as f:
        json.dump({"subagent": "supply-sentinel", "findings": findings}, f, indent=2)

    print(f"SBOM written to {args.out} ({len(components)} components)")
    print(f"Provenance findings written to {args.findings_out} ({len(findings)} finding(s))")


if __name__ == "__main__":
    main()
