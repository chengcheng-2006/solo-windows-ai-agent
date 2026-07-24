"""Smoke acceptance test — runs CLI commands programmatically."""
import json
import tempfile

from click.testing import CliRunner

from solo.cli.main import cli

r = CliRunner()
all_passed = True

def check(name, ok, detail=""):
    global all_passed
    if ok:
        print(f"  [PASS] {name} {detail}")
    else:
        print(f"  [FAIL] {name} {detail}")
        all_passed = False

print("=== Solo v0.1.1 Acceptance Tests ===")
print()

# 1. Version
r1 = r.invoke(cli, ["version"])
check("Version", r1.exit_code == 0, r1.output.strip())
check("Version string", "solo-agent v0.1.1a0" in r1.output)

# 2. Doctor JSON
r2 = r.invoke(cli, ["doctor", "--json"])
data = json.loads(r2.output)
check("Doctor JSON valid", r2.exit_code == 0)
check("Doctor passes", data["summary"]["pass"] >= 4, f"{data['summary']['pass']} pass")
check("Mode detected", data["mode"] in ("lite", "core", "full"), data["mode"])

# 3. Safe Demo JSON
with tempfile.TemporaryDirectory() as tmp:
    r3 = r.invoke(cli, ["demo", "safe", "--json", "--workspace", tmp])
    check("Safe exit code", r3.exit_code == 0)
    sd = json.loads(r3.output)
    check("Safe status PASS", sd["status"] == "PASS")
    check("Safe 8 steps", len(sd["pipeline"]) == 8)
    check("Safe has word count", sd["result"]["word_count"] > 0)
    check("Safe under 2s", sd["duration_ms"] < 2000, f"{sd['duration_ms']}ms")
    states = [e["state"] for e in sd["pipeline"]]
    expected = ["RECEIVED", "TRIAGED", "PLANNING", "APPROVED",
                "DISPATCHED", "EXECUTING", "VALIDATING", "COMPLETED"]
    check("Safe state sequence", states == expected)

# 4. VETO Demo JSON
with tempfile.TemporaryDirectory() as tmp:
    r4 = r.invoke(cli, ["demo", "veto", "--json", "--workspace", tmp])
    check("VETO exit code", r4.exit_code == 0)
    vd = json.loads(r4.output)
    check("VETO status PASS", vd["status"] == "PASS")
    check("VETO vetoed True", vd["vetoed"] is True)
    check("VETO risk R3", vd["risk_level"] == "R3")
    check("VETO 4 steps", len(vd["pipeline"]) == 4)
    check("VETO under 1s", vd["duration_ms"] < 1000, f"{vd['duration_ms']}ms")
    for key, val in vd["security_guarantees"].items():
        check(f"VETO guarantee: {key}", val is True)
    v_states = [e["state"] for e in vd["pipeline"]]
    v_expected = ["RECEIVED", "TRIAGED", "REVIEW_PENDING", "REJECTED"]
    check("VETO state sequence", v_states == v_expected)

print()
if all_passed:
    print("=== ALL ACCEPTANCE TESTS PASSED ===")
else:
    print("=== SOME ACCEPTANCE TESTS FAILED ===")
    exit(1)
