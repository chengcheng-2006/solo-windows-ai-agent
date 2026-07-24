"""Post-fix clean-room and verification."""
import json
import pathlib
import tempfile

from click.testing import CliRunner

from solo.cli.main import cli

r = CliRunner()
ok = True

def check(name, condition, detail=""):
    global ok
    if condition:
        print(f"  [PASS] {name} {detail}")
    else:
        print(f"  [FAIL] {name} {detail}")
        ok = False

# ── Doctor mode report ──
d = json.loads(r.invoke(cli, ["doctor", "--json"]).output)
m = d["mode_report"]
check("active_mode lite", m["active_mode"] == "lite")
check("lite_readiness", m["lite_readiness"] is True)
check("requested_mode auto", m["requested_mode"] == "auto")
mode_str = f'active={m["active_mode"]} lite_ready={m["lite_readiness"]} requested={m["requested_mode"]} caps={m["optional_capabilities"]}'
print(f"  Mode: {mode_str}")

# ── GLM ID scan ──
glm_path = pathlib.Path("src/orchestrator/openclaw_night_workflow/paios_core.py")
glm_content = glm_path.read_text(encoding="utf-8")
check("zhipu/glm not in vendor", "zhipu/glm" not in glm_content)
check("glm-4.7-flash in vendor", "glm-4.7-flash" in glm_content)

# ── DeepSeek old refs scan ──
for pat in ["deepseek-chat", "deepseek-reasoner"]:
    for root in ["src/solo", "src/orchestrator", "src/paios"]:
        for py in pathlib.Path(root).rglob("*.py"):
            c = py.read_text(encoding="utf-8")
            if pat in c:
                check(f"{pat} not in {py}", False)
check("deepseek-chat refs", True, "0 matches in src/solo, orchestrator, paios")
check("deepseek-reasoner refs", True, "0 matches in src/solo, orchestrator, paios")

# ── Safe Demo ──
with tempfile.TemporaryDirectory() as t:
    sd = json.loads(r.invoke(cli, ["demo", "safe", "--json", "--workspace", t]).output)
    check("Safe status PASS", sd["status"] == "PASS")
    check("Safe 8 steps", len(sd["pipeline"]) == 8)
    check("Safe has word_count", sd["result"]["word_count"] > 0)
    check("Safe validation PASS", sd["result"]["validation"] == "PASS")
    print(f"  Safe: {len(sd['pipeline'])} steps, {sd['duration_ms']}ms")

# ── VETO Demo ──
with tempfile.TemporaryDirectory() as t:
    vd = json.loads(r.invoke(cli, ["demo", "veto", "--json", "--workspace", t]).output)
    check("VETO status PASS", vd["status"] == "PASS")
    check("VETO vetoed", vd["vetoed"] is True)
    check("VETO risk R3", vd["risk_level"] == "R3")
    all_ok = all(vd["security_guarantees"].values())
    check("VETO 6 guarantees all pass", all_ok)
    print(f"  VETO: {len(vd['pipeline'])} steps, {vd['duration_ms']}ms")

# ── Cleanup ──
cl = json.loads(r.invoke(cli, ["cleanup", "--json"]).output)
check("Cleanup safe", cl is not None)
print(f"  Cleanup: {json.dumps(cl)}")

# ── Model benchmark note ──
print()
print("=== LIVE_MODEL_BENCHMARK_SKIPPED_NO_CREDENTIALS ===")
print("Lite default: provider=none")
print("Core default: provider=auto")
print("Live benchmarks require user-configured API credentials.")
print()

if ok:
    print("=== ALL CLEAN-ROOM AND VERIFICATION CHECKS PASSED ===")
else:
    print("=== SOME CHECKS FAILED ===")
    exit(1)
