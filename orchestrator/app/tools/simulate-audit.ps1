# simulate-audit.ps1 - runs the same checks as project_audit.py
# using PowerShell (since neither Python nor Node is on PATH here).
# NOT a replacement for the real audit; exists only to give runtime
# evidence that the audit's expectations match the repo.

$REPO = 'c:\Users\Administrator\Downloads\videoAI'

function Test-Path2($p) { return (Test-Path $p) }
function Get-Text($p) {
    if (Test-Path $p) { return (Get-Content $p -Raw -Encoding UTF8) } else { return '' }
}

$dims = New-Object System.Collections.Generic.List[object]

# 1. docs presence
$REQUIRED = @(
    'PROJECT_CONTEXT.md','PROJECT_STATE.md','ARCHITECTURE.md',
    'ARCHITECTURE_DECISIONS.md','SYSTEM_MAP.md','DATA_CONTRACTS.md',
    'API_CONTRACTS.md','PROVIDER_REGISTRY.md','PIPELINE_REGISTRY.md',
    'DEPENDENCY_GRAPH.md','FEATURE_MATRIX.md','TECHNICAL_DEBT.md',
    'KNOWN_LIMITATIONS.md','CHANGELOG_INTERNAL.md','TEST_STATUS.md',
    'SAFE_CHANGE_RULES.md'
)
$missing = New-Object System.Collections.Generic.List[string]
foreach ($n in $REQUIRED) {
    $full = Join-Path $REPO ("docs\" + $n)
    if (-not (Test-Path2 $full)) { $missing.Add($n) }
}
$dims.Add([pscustomobject]@{
    name='docs presence'
    status = if ($missing.Count -eq 0) { 'PASS' } else { 'FAIL' }
    summary = if ($missing.Count -eq 0) { "all $($REQUIRED.Count) required docs present" } else { "$($missing.Count) required doc(s) missing" }
    details = $missing.ToArray()
})

# 2. pipeline registry
$runner = Join-Path $REPO 'orchestrator\app\pipeline\runner.py'
$rsrc = Get-Text $runner
if ($rsrc -eq '') {
    $dims.Add([pscustomobject]@{ name='pipeline registry'; status='FAIL'; summary='runner.py missing'; details=@($runner) })
} else {
    $m = [regex]::Match($rsrc, 'STAGES\s*=\s*\[([^\]]+)\]')
    $stageNames = New-Object System.Collections.Generic.List[string]
    if ($m.Success) {
        foreach ($mm in [regex]::Matches($m.Groups[1].Value, '(\w+)\(\)')) {
            $stageNames.Add($mm.Groups[1].Value)
        }
    }
    $miss = New-Object System.Collections.Generic.List[string]
    $mm2 = New-Object System.Collections.Generic.List[string]
    foreach ($cls in $stageNames) {
        if ($cls -notmatch '^s\d+_(.+)$') { continue }
        $modPath = Join-Path $REPO ("orchestrator\app\pipeline\stages\" + $cls + ".py")
        if (-not (Test-Path2 $modPath)) { $miss.Add($modPath); continue }
        $text = Get-Text $modPath
        $parts = $cls.Split('_') | Select-Object -Skip 1
        $titleParts = @()
        foreach ($p in $parts) { $titleParts += ($p.Substring(0,1).ToUpper() + $p.Substring(1)) }
        $expectedClass = ($titleParts -join '') + 'Stage'
        if ($text -notmatch ("^class\s+$expectedClass\b")) {
            $mm2.Add("$cls.py missing class $expectedClass")
        }
    }
    $dims.Add([pscustomobject]@{
        name='pipeline registry'
        status = if ($miss.Count -eq 0 -and $mm2.Count -eq 0) { 'PASS' } else { 'FAIL' }
        summary = if ($miss.Count -eq 0 -and $mm2.Count -eq 0) { "all $($stageNames.Count) runner.STAGES have matching files and classes" } else { "$($miss.Count) missing, $($mm2.Count) mismatch" }
        details = @($miss.ToArray() + $mm2.ToArray())
    })
}

# 3. api routes
$apiRoot = Join-Path $REPO 'orchestrator\app\api'
$main = Join-Path $REPO 'orchestrator\app\main.py'
$routeCount = 0
$files = New-Object System.Collections.Generic.List[string]
if (Test-Path2 $apiRoot) {
    foreach ($f in (Get-ChildItem $apiRoot -Filter '*.py')) { $files.Add($f.FullName) }
}
$files.Add($main)
foreach ($f in $files) {
    $t = Get-Text $f
    $routeCount += ([regex]::Matches($t, '@router\.(get|post|put|delete|patch)\(')).Count
    $routeCount += ([regex]::Matches($t, '@app\.(get|post|put|delete|patch)\(')).Count
}
$dims.Add([pscustomobject]@{
    name='api routes'
    status = if ($routeCount -ge 5) { 'PASS' } else { 'FAIL' }
    summary = if ($routeCount -ge 5) { "$routeCount HTTP routes registered" } else { "only $routeCount routes" }
    details = @()
})

# 4. provider ABCs
$expected = @('LLMProvider','TTSProvider','ImageProvider','SearchProvider','ContentFetchProvider')
$provRoot = Join-Path $REPO 'orchestrator\app\providers'
$impls = @{}
foreach ($ab in $expected) { $impls[$ab] = New-Object System.Collections.Generic.List[string] }
if (Test-Path2 $provRoot) {
    foreach ($f in (Get-ChildItem $provRoot -Filter '*.py')) {
        if ($f.Name -eq 'base.py' -or $f.Name -eq '__init__.py') { continue }
        $t = Get-Text $f.FullName
        $clsMatch = [regex]::Match($t, '^class\s+(\w+)', [System.Text.RegularExpressions.RegexOptions]::Multiline)
        if (-not $clsMatch.Success) { continue }
        $clsName = $clsMatch.Groups[1].Value
        foreach ($ab in $expected) {
            if ($t -match "\b$ab\b") {
                if (-not $impls[$ab].Contains($clsName)) {
                    $impls[$ab].Add($clsName)
                }
            }
        }
    }
}
$abmiss = New-Object System.Collections.Generic.List[string]
foreach ($ab in $expected) {
    if ($impls[$ab].Count -eq 0) { $abmiss.Add($ab) }
}
$details4 = New-Object System.Collections.Generic.List[string]
foreach ($m in $abmiss) { $details4.Add("$m`: no impl found") }
$dims.Add([pscustomobject]@{
    name='provider ABCs'
    status = if ($abmiss.Count -eq 0) { 'PASS' } else { 'WARN' }
    summary = if ($abmiss.Count -eq 0) { "all $($expected.Count) provider ABCs have >=1 concrete impl" } else { "$($abmiss.Count) ABC(s) have no concrete impl" }
    details = $details4.ToArray()
})

# 5. schemas exported
$expectedSchemas = @('job.py','script.py','research.py','research_package.py','scene_definition.py')
$schemasDir = Join-Path $REPO 'orchestrator\app\schemas'
$actualSchemas = @()
if (Test-Path2 $schemasDir) {
    $actualSchemas = @(Get-ChildItem $schemasDir -Filter '*.py' | ForEach-Object { $_.Name })
}
$smiss = New-Object System.Collections.Generic.List[string]
foreach ($e in $expectedSchemas) {
    if ($actualSchemas -notcontains $e) { $smiss.Add($e) }
}
$details5 = New-Object System.Collections.Generic.List[string]
foreach ($m in $smiss) { $details5.Add("schemas/$m") }
$dims.Add([pscustomobject]@{
    name='schemas exported'
    status = if ($smiss.Count -eq 0) { 'PASS' } else { 'FAIL' }
    summary = if ($smiss.Count -eq 0) { "all $($expectedSchemas.Count) schema files present" } else { "$($smiss.Count) missing" }
    details = $details5.ToArray()
})

# 6. test files
$testsRoot = Join-Path $REPO 'orchestrator\tests'
if (-not (Test-Path2 $testsRoot)) {
    $dims.Add([pscustomobject]@{ name='test files'; status='FAIL'; summary='tests/ directory missing'; details=@() })
} else {
    $tests = @(Get-ChildItem $testsRoot -Filter 'test_*.py' | ForEach-Object { "tests/$($_.Name)" })
    $dims.Add([pscustomobject]@{
        name='test files'
        status='PASS'
        summary="$(@($tests).Count) Python test file(s) present; runtime BLOCKED on this host (no Python)"
        details = @($tests)
    })
}

# 7. research engine steps
$engine = Join-Path $REPO 'orchestrator\app\research\engine.py'
$et = Get-Text $engine
$stepNames = @('decompose_questions','search_sources','fetch_and_score_sources','deduplicate_sources','extract_claims','build_claim_source_graph','detect_contradictions','model_uncertainty','build_timeline','extract_visual_opportunities','extract_story_opportunities','synthesize','score_quality')
$present = New-Object System.Collections.Generic.List[string]
foreach ($s in $stepNames) {
    if ($et -match "\b$s\b") { $present.Add($s) }
}
$dims.Add([pscustomobject]@{
    name='research engine steps'
    status = if ($present.Count -ge 10) { 'PASS' } else { 'FAIL' }
    summary = if ($present.Count -ge 10) { "$($present.Count) engine step method(s) detected" } else { "only $($present.Count)" }
    details = @($present.ToArray())
})

# 8. secrets scan
$patterns = @(
    @{ rx='sk-[A-Za-z0-9]{20,}'; label='OpenAI-style key' },
    @{ rx='AKIA[0-9A-Z]{16}'; label='AWS access key' },
    @{ rx='ghp_[A-Za-z0-9]{20,}'; label='GitHub personal token' },
    @{ rx='xoxb-[A-Za-z0-9-]{20,}'; label='Slack token' }
)
$findings = New-Object System.Collections.Generic.List[string]
if (Test-Path2 (Join-Path $REPO 'orchestrator')) {
    foreach ($f in (Get-ChildItem (Join-Path $REPO 'orchestrator') -Recurse -Filter '*.py')) {
        $t = Get-Text $f.FullName
        foreach ($p in $patterns) {
            if ($t -match $p.rx) {
                $rel = $f.FullName.Substring($REPO.Length + 1)
                $findings.Add("$($p.label): $rel")
                break
            }
        }
    }
}
$dims.Add([pscustomobject]@{
    name='secrets scan'
    status = if ($findings.Count -eq 0) { 'PASS' } else { 'FAIL' }
    summary = if ($findings.Count -eq 0) { 'no accidental secret patterns detected' } else { "$($findings.Count) potential secret(s) detected" }
    details = @($findings.ToArray())
})

# 9. docker-compose usage
$compose = Join-Path $REPO 'docker-compose.yml'
$csrc = Get-Text $compose
$reqsFile = Join-Path $REPO 'orchestrator\requirements.txt'
$reqsText = (Get-Text $reqsFile).ToLower()
if ($csrc -eq '') {
    $dims.Add([pscustomobject]@{ name='docker-compose'; status='WARN'; summary='docker-compose.yml not present'; details=@() })
} else {
    $declared = New-Object System.Collections.Generic.List[string]
    if ($csrc -match '(?m)^\s*redis:') { $declared.Add('redis') }
    if ($csrc -match '(?m)^\s*postgres:') { $declared.Add('postgres') }
    $unused = New-Object System.Collections.Generic.List[string]
    $intentOnly = New-Object System.Collections.Generic.List[string]
    foreach ($svc in $declared) {
        $hits = New-Object System.Collections.Generic.List[object]
        if ($svc -eq 'redis') {
            foreach ($f in (Get-ChildItem (Join-Path $REPO 'orchestrator') -Recurse -Filter '*.py')) {
                # Skip the audit tooling itself so we don't match our own source.
                if ($f.FullName -like '*\app\tools\*') { continue }
                $t = Get-Text $f.FullName
                if ($t -match '\b(redis|aioredis)\b') { $hits.Add($f); break }
            }
            $dep = $reqsText.Contains('redis')
        } else {
            foreach ($f in (Get-ChildItem (Join-Path $REPO 'orchestrator') -Recurse -Filter '*.py')) {
                if ($f.FullName -like '*\app\tools\*') { continue }
                $t = Get-Text $f.FullName
                if ($t -match '\b(sqlalchemy|psycopg|asyncpg)\b') { $hits.Add($f); break }
            }
            $dep = $reqsText.Contains('sqlalchemy')
        }
        if ($hits.Count -eq 0 -and -not $dep) {
            $unused.Add($svc)
        } elseif ($hits.Count -eq 0 -and $dep) {
            $intentOnly.Add($svc)
        }
    }
    $details9 = New-Object System.Collections.Generic.List[string]
    foreach ($u in $unused) { $details9.Add("$u`: declared in compose but no Python usage or dep") }
    foreach ($i in $intentOnly) { $details9.Add("$i`: declared in compose + requirements.txt but never imported") }
    if ($unused.Count -gt 0) {
        $dims.Add([pscustomobject]@{
            name='docker-compose'
            status='WARN'
            summary="$($unused.Count) service(s) declared but not used by code"
            details = $details9.ToArray()
        })
    } elseif ($intentOnly.Count -gt 0) {
        $dims.Add([pscustomobject]@{
            name='docker-compose'
            status='WARN'
            summary="$($intentOnly.Count) service(s) declared but only as future-intent dep"
            details = $details9.ToArray()
        })
    } else {
        $dims.Add([pscustomobject]@{
            name='docker-compose'
            status='PASS'
            summary='all declared services are used'
            details = @()
        })
    }
}

# 10. git repo
$gitDir = Join-Path $REPO '.git'
$gitOk = (Test-Path2 $gitDir) -and ((Get-Item $gitDir).PSIsContainer)
$dims.Add([pscustomobject]@{
    name='git repository'
    status = if ($gitOk) { 'PASS' } else { 'WARN' }
    summary = if ($gitOk) { '.git/ present' } else { 'no .git/ directory; no commit history' }
    details = if ($gitOk) { @() } else { @('run `git init` only with user approval (TECHNICAL_DEBT C-008)') }
})

# Aggregate and render
$hasFail = $false
$hasWarn = $false
foreach ($d in $dims) {
    if ($d.status -eq 'FAIL') { $hasFail = $true }
    if ($d.status -eq 'WARN') { $hasWarn = $true }
}
$overall = if ($hasFail) { 'FAIL' } elseif ($hasWarn) { 'WARN' } else { 'PASS' }

Write-Output ('=' * 72)
Write-Output 'videoAI Project Audit (PROMPT 0.5) - PowerShell simulation'
Write-Output "repo root: $REPO"
Write-Output ('=' * 72)
Write-Output ''
foreach ($d in $dims) {
    Write-Output ("[{0}] {1}: {2}" -f $d.status, $d.name, $d.summary)
    foreach ($x in @($d.details)) { Write-Output ("    - {0}" -f $x) }
    Write-Output ''
}
Write-Output ('-' * 72)
Write-Output "OVERALL: $overall"
Write-Output ('-' * 72)
switch ($overall) {
    'PASS' { Write-Output 'No HIGH/CRITICAL conflicts detected.' }
    'WARN' {
        Write-Output 'WARN: known HIGH conflicts recorded in docs/TECHNICAL_DEBT.md'
        Write-Output '(C-001, C-002, C-003, C-008). These are NOT fixed by design.'
    }
    default { Write-Output 'FAIL: at least one dimension failed.' }
}
