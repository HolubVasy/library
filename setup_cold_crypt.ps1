$exe = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter rclone.exe -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
$conf = "$env:USERPROFILE\.rclone_cold.conf"

function Ask([string]$prompt) {
    Write-Host $prompt
    $s = Read-Host -AsSecureString
    $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

Write-Host 'Encrypted cold backup on the VPS. You will set TWO secrets. Save both: without them the backup cannot be read.'
$p1 = Ask 'Password (input hidden):'
$p1b = Ask 'Repeat password:'
if ($p1 -ne $p1b) { Write-Host 'Passwords do not match. Run the command again.'; exit 1 }
$p2 = Ask 'Salt - a second, different secret phrase (input hidden):'
$p2b = Ask 'Repeat salt:'
if ($p2 -ne $p2b) { Write-Host 'Salts do not match. Run the command again.'; exit 1 }
if ($p1 -eq $p2) { Write-Host 'Password and salt must differ. Run the command again.'; exit 1 }

# rclone stores both secrets obscured in its config; nothing is printed here
& $exe --config $conf config create cold crypt remote=vps:/srv/cold_backup password=$p1 password2=$p2 filename_encryption=standard directory_name_encryption=true 2>&1 | Out-Null
Remove-Variable p1, p1b, p2, p2b
& $exe --config $conf mkdir cold:_check 2>&1 | Out-Null
$ok = & $exe --config $conf lsd cold: 2>&1
if ($LASTEXITCODE -eq 0) { Write-Host 'Encrypted backup storage is ready.'; $ok } else { Write-Host 'Setup failed:'; $ok | Select-Object -Last 3 }
