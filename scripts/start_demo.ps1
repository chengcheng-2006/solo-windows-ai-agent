# Solo Safe Demo — Run a local task to demonstrate the orchestration pipeline
# No API keys required. Uses basic file operations.

$ErrorActionPreference = 'Stop'
$script:SoloRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Write-Step { Write-Host "`n[STEP] $_" -ForegroundColor Cyan }
function Write-Info { Write-Host "  $_" }

# Create temp demo workspace
$demoDir = Join-Path $env:TEMP "solo-demo-$([System.Guid]::NewGuid().ToString().Substring(0,8))"
New-Item -ItemType Directory -Path $demoDir -Force | Out-Null
Write-Host "===== Solo Safe Demo =====" -ForegroundColor Green
Write-Host "Demo workspace: $demoDir"

# Step 1: Create a test task file
Write-Step "Creating test task"
$taskFile = Join-Path $demoDir "task.json"
@{
    task_id = "demo-001"
    description = "Count words in a test file"
    status = "created"
    created_at = (Get-Date -Format 'o')
} | ConvertTo-Json | Out-File $taskFile
Write-Info "Task created: task_id=demo-001"
Get-Content $taskFile | Write-Info

# Step 2: Generate a plan
Write-Step "Generating plan"
$planFile = Join-Path $demoDir "plan.json"
@{
    task_id = "demo-001"
    steps = @(
        @{ step = 1; action = "Create test text file"; agent = "local" }
        @{ step = 2; action = "Count words"; agent = "local" }
        @{ step = 3; action = "Write result to audit log"; agent = "local" }
    )
    risk_level = "R0"
    status = "planned"
} | ConvertTo-Json | Out-File $planFile
Write-Info "Plan generated: 3 steps, risk level R0"
Get-Content $planFile | ConvertFrom-Json | ForEach-Object { $_.steps | ForEach-Object { Write-Info "  Step $($_.step): $($_.action) ($($_.agent))" } }

# Step 3: Review (auto-approve R0)
Write-Step "Auto-reviewing plan"
$reviewFile = Join-Path $demoDir "review.json"
@{
    task_id = "demo-001"
    verdict = "APPROVED"
    reviewer = "demo-reviewer"
    notes = "R0 task, auto-approved"
    reviewed_at = (Get-Date -Format 'o')
} | ConvertTo-Json | Out-File $reviewFile
Write-Info "Verdict: APPROVED (R0 — safe operation)"
Write-Info "Reviewer: demo-reviewer"

# Step 4: Execute safe action (word count)
Write-Step "Executing task"
$testFile = Join-Path $demoDir "sample_text.txt"
@"
Solo is a Windows-first personal AI agent system.
It processes chat requests through a multi-agent pipeline:
planning, review, approval, execution, and verification.
This demo demonstrates the orchestration pipeline.
"@ | Out-File $testFile
$wordCount = (Get-Content $testFile | Out-String | Measure-Object -Word).Words
Write-Info "Sample text: 4 lines, ${wordCount} words"

# Step 5: Validate result
Write-Step "Validating result"
$resultFile = Join-Path $demoDir "result.json"
@{
    task_id = "demo-001"
    status = "completed"
    action = "word_count"
    input_file = "sample_text.txt"
    result = @{ word_count = $wordCount }
    completed_at = (Get-Date -Format 'o')
} | ConvertTo-Json | Out-File $resultFile
Write-Info "Validated: word_count = $wordCount"

# Step 6: Write audit record
Write-Step "Writing audit trail"
$auditFile = Join-Path $demoDir "audit.json"
@{
    task_id = "demo-001"
    events = @(
        @{ timestamp = (Get-Date -Format 'o'); event = "task_created"; actor = "user" }
        @{ timestamp = (Get-Date -Format 'o'); event = "plan_generated"; actor = "planner" }
        @{ timestamp = (Get-Date -Format 'o'); event = "plan_reviewed"; actor = "reviewer"; verdict = "APPROVED" }
        @{ timestamp = (Get-Date -Format 'o'); event = "task_executed"; actor = "executor"; result = "${wordCount} words" }
        @{ timestamp = (Get-Date -Format 'o'); event = "result_validated"; actor = "validator"; status = "PASS" }
    )
} | ConvertTo-Json | Out-File $auditFile
Write-Info "Audit trail written: 5 events logged"

# Final summary
Write-Step "Demo complete"
Write-Host "All files:" -ForegroundColor Cyan
Get-ChildItem $demoDir | ForEach-Object { Write-Info "  $($_.Name) ($($_.Length) bytes)" }
Write-Host ""
Write-Host "===== Demo SUCCESS =====" -ForegroundColor Green
Write-Host "Pipeline demonstrated: Create → Plan → Review → Execute → Validate → Audit"
Write-Host "Clean up with: .\scripts\stop_demo.ps1"
exit 0
