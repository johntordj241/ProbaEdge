<#
.SYNOPSIS
    Apply the local Supabase schema files with a single command.

.DESCRIPTION
    This script wraps the psql CLI so you can safely run both schema.sql and
    supabase_additional_tables.sql without retyping the connection flags.
    Provide a Supabase password when prompted; it is stored only in memory for
    the duration of the command and cleared before exit.

.EXAMPLE
    pwsh scripts/apply_supabase_schema.ps1 `
        -Host 'aws-1-eu-west-1.pooler.supabase.com' `
        -User 'postgres.heiqjkdxevoajczggco'

    Prompts for the Supabase password, then executes both SQL files against the
    given instance via psql (default path: C:\Program Files\PostgreSQL\17\bin\psql.exe).
#>
param(
    [string]$PsqlPath = "C:\Program Files\PostgreSQL\17\bin\psql.exe",
    [string]$Host = "aws-1-eu-west-1.pooler.supabase.com",
    [int]$Port = 6543,
    [string]$Database = "postgres",
    [string]$User = "",
    [string[]]$SqlFiles = @("schema.sql", "supabase_additional_tables.sql")
)

function Resolve-SqlFile {
    param([string]$Path)

    if (-not (Test-Path -Path $Path)) {
        throw "SQL file '$Path' not found. Run the script from the repo root or pass fully-qualified paths."
    }

    return (Resolve-Path -Path $Path).Path
}

if (-not (Test-Path -Path $PsqlPath)) {
    throw "psql not found at '$PsqlPath'. Update -PsqlPath to match your local installation."
}

if ([string]::IsNullOrWhiteSpace($User)) {
    throw "Supabase user is empty. Pass -User 'postgres.<project>' as shown in the Supabase dashboard."
}

$resolvedFiles = @()
foreach ($file in $SqlFiles) {
    $resolvedFiles += (Resolve-SqlFile -Path $file)
}

$securePassword = Read-Host -Prompt "Supabase password (input hidden)" -AsSecureString
if (-not $securePassword) {
    throw "Password is required to connect to Supabase."
}

$passwordPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPtr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr)
}

$previousPassword = $env:PGPASSWORD
$previousSslMode = $env:PGSSLMODE
$env:PGPASSWORD = $plainPassword
$env:PGSSLMODE = "require"

try {
    foreach ($sqlFile in $resolvedFiles) {
        Write-Host "→ Applying $sqlFile..." -ForegroundColor Cyan
        & $PsqlPath -h $Host -p $Port -d $Database -U $User -f $sqlFile
        if ($LASTEXITCODE -ne 0) {
            throw "psql exited with code $LASTEXITCODE while running '$sqlFile'."
        }
    }

    Write-Host "✓ All Supabase schema files applied successfully." -ForegroundColor Green
}
finally {
    $env:PGPASSWORD = $previousPassword
    $env:PGSSLMODE = $previousSslMode
    $plainPassword = $null
    [System.GC]::Collect()
}
