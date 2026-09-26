#!/usr/bin/env python3
"""
confidence_score.py — Standard-library-only Release Confidence Score.

Computes a transparent 0-100 score from the audit's own findings/test output
(see TRD.md section 6c for the formula). Meant to be called after all
findings are aggregated and the regression suite has run, with its output
inserted at the top of RELEASE_NOTES.md.

Usage:
    python3 confidence_score.py --findings findings.json --regression-passed true

findings.json format: {"findings": [{"severity": "critical|high|medium|low|info",
                                       "remediation_status": "unresolved|patched-verified|escalated", ...}, ...],
                        "rules_covered": ["R1","R2",...]}
"""
import argparse
import json


ALL_RULES = [f"R{i}" for i in range(1, 11)]


def compute_score(findings, regression_passed, rules_covered):
    unresolved = [f for f in findings if f.get("remediation_status") == "unresolved"]
    critical = sum(1 for f in unresolved if f["severity"] == "critical")
    high = sum(1 for f in unresolved if f["severity"] == "high")
    medium = sum(1 for f in unresolved if f["severity"] == "medium")

    score = 100
    score -= 25 if critical > 0 else 0
    score -= 15 * min(high, 3)
    score -= 5 * min(medium, 4)
    score -= 20 if not regression_passed else 0
    uncovered = [r for r in ALL_RULES if r not in rules_covered]
    score -= 10 if uncovered else 0
    score = max(score, 0)

    return {
        "score": score,
        "unresolved_critical": critical,
        "unresolved_high": high,
        "unresolved_medium": medium,
        "regression_passed": regression_passed,
        "uncovered_rules": uncovered,
        "formula": (
            "100 - 25*(critical>0) - 15*min(high,3) - 5*min(medium,4) "
            "- 20*(regression_failed) - 10*(any_rule_uncovered)"
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--findings", required=True, help="Path to a JSON file with a 'findings' list")
    parser.add_argument("--regression-passed", required=True, choices=["true", "false"])
    parser.add_argument("--rules-covered", nargs="*", default=ALL_RULES)
    args = parser.parse_args()

    with open(args.findings, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = compute_score(
        data.get("findings", []),
        args.regression_passed == "true",
        set(args.rules_covered),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
