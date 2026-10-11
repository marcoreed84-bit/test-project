<#
.SYNOPSIS
    Sorts through PhotoRec output and finds files that could be Quattro Pro notebooks.

.DESCRIPTION
    Looks at every file under the PhotoRec output folder (recup_dir.1, recup_dir.2, ...).
    Quattro Pro .wb3/.qpw notebooks use the same "OLE" container as old Office files,
    so the script:
      1. keeps only files that start with the OLE signature (D0 CF 11 E0 A1 B1 1A E1),
      2. reads the names of the streams inside each one,
      3. labels each file: Likely Quattro Pro / Possible / Word / Excel / PowerPoint / etc.
    "Likely" and "Possible" files are COPIED (never moved) into an output folder with a
    .wb3 extension so you can try opening them in Quattro Pro. A CSV report of every
    OLE file found is written there too. Nothing in the PhotoRec folders is changed.

.PARAMETER Path
    Folder that contains the recup_dir.* folders. Defaults to the current folder.

.PARAMETER OutDir
    Where to copy candidates and write the report. Defaults to <Path>\QuattroCandidates.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Find-QuattroFiles.ps1 -Path "E:\Recovered"
#>
param(
    [string]$Path = (Get-Location).Path,
    [string]$OutDir
)

if (-not $OutDir) { $OutDir = Join-Path $Path 'QuattroCandidates' }

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

public static class OleScan
{
    static readonly byte[] Sig = { 0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1 };

    public static bool IsOle(string path)
    {
        try
        {
            using (FileStream fs = File.OpenRead(path))
            {
                byte[] head = new byte[8];
                if (fs.Read(head, 0, 8) < 8) return false;
                for (int i = 0; i < 8; i++) if (head[i] != Sig[i]) return false;
                return true;
            }
        }
        catch { return false; }
    }

    // Finds directory entries by shape rather than by following the FAT, so it still
    // works on recovered files whose sector chains are damaged.
    public static string[] EntryNames(byte[] d)
    {
        List<string> names = new List<string>();
        for (int o = 512; o + 128 <= d.Length; o += 128)
        {
            int len = d[o + 64] | (d[o + 65] << 8);
            byte type = d[o + 66];
            byte color = d[o + 67];
            if (len < 4 || len > 64 || (len & 1) != 0) continue;
            if (type != 1 && type != 2 && type != 5) continue;
            if (color > 1) continue;
            int chars = len / 2 - 1;
            if (d[o + chars * 2] != 0 || d[o + chars * 2 + 1] != 0) continue;
            bool ok = true;
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < chars; i++)
            {
                int c = d[o + i * 2] | (d[o + i * 2 + 1] << 8);
                if (c == 0 || (c >= 0xD800 && c <= 0xDFFF)) { ok = false; break; }
                sb.Append(c < 0x20 ? '#' : (char)c);
            }
            if (ok && !names.Contains(sb.ToString())) names.Add(sb.ToString());
        }
        return names.ToArray();
    }

    public static bool Contains(byte[] d, string text)
    {
        return IndexOf(d, Encoding.ASCII.GetBytes(text)) >= 0
            || IndexOf(d, Encoding.Unicode.GetBytes(text)) >= 0;
    }

    static int IndexOf(byte[] d, byte[] p)
    {
        for (int i = 0; i <= d.Length - p.Length; i++)
        {
            if (d[i] != p[0]) continue;
            int j = 1;
            while (j < p.Length && d[i + j] == p[j]) j++;
            if (j == p.Length) return i;
        }
        return -1;
    }
}
'@

function Get-Category([string[]]$names, [byte[]]$bytes) {
    $joined = $names -join '|'
    if ($joined -match 'NativeContent|Quattro|PerfectOffice|QPW' -or
        [OleScan]::Contains($bytes, 'Quattro') -or [OleScan]::Contains($bytes, 'QUATTRO')) {
        return 'Likely Quattro Pro'
    }
    if ($names -contains 'WordDocument')                       { return 'Word document' }
    if ($names -contains 'Workbook' -or $names -contains 'Book') { return 'Excel workbook' }
    if ($names -contains 'PowerPoint Document')                { return 'PowerPoint' }
    if ($names -contains 'VisioDocument')                      { return 'Visio' }
    if ($joined -match '__substg1\.0_|__properties_version1\.0') { return 'Outlook email' }
    if ($names -contains 'Catalog')                            { return 'Thumbnail cache' }
    if ($joined -match '[\u3800-\u4840]')                      { return 'Windows installer' }
    if ($names.Count -eq 0)                                    { return 'Possible (damaged, no readable contents list)' }
    return 'Possible (unknown OLE type)'
}

$files = Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "$OutDir*" }
Write-Host "Checking $($files.Count) files under $Path ..."

$results = New-Object System.Collections.Generic.List[object]
$i = 0
foreach ($f in $files) {
    $i++
    if ($i % 200 -eq 0) {
        Write-Progress -Activity 'Scanning recovered files' -Status $f.Name -PercentComplete ($i * 100 / $files.Count)
    }
    if (-not [OleScan]::IsOle($f.FullName)) { continue }
    if ($f.Length -gt 200MB) {
        $results.Add([pscustomobject]@{ Category = 'Skipped (over 200 MB)'; SizeKB = [math]::Round($f.Length / 1KB); File = $f.FullName; Streams = '' })
        continue
    }
    try { $bytes = [System.IO.File]::ReadAllBytes($f.FullName) } catch { continue }
    $names = [OleScan]::EntryNames($bytes)
    $results.Add([pscustomobject]@{
        Category = Get-Category $names $bytes
        SizeKB   = [math]::Round($f.Length / 1KB)
        File     = $f.FullName
        Streams  = ($names | Where-Object { $_ -ne 'Root Entry' }) -join ', '
    })
}
Write-Progress -Activity 'Scanning recovered files' -Completed

if ($results.Count -eq 0) {
    Write-Host 'No OLE files found. Check that -Path points at the folder holding recup_dir.1, recup_dir.2, ...' -ForegroundColor Yellow
    return
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$rank = @{ e = { if ($_.Category -like 'Likely*') { 0 } elseif ($_.Category -like 'Possible*') { 1 } else { 2 } } }
$results | Sort-Object $rank, @{ e = 'SizeKB'; Descending = $true } |
    Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $OutDir 'report.csv')

$candidates = $results | Where-Object { $_.Category -like 'Likely*' -or $_.Category -like 'Possible*' }
foreach ($c in $candidates) {
    $prefix = if ($c.Category -like 'Likely*') { 'LIKELY_' } else { 'possible_' }
    $name = $prefix + [System.IO.Path]::GetFileNameWithoutExtension($c.File) + '.wb3'
    Copy-Item -LiteralPath $c.File -Destination (Join-Path $OutDir $name) -Force
}

Write-Host ''
Write-Host 'Summary of OLE files found:' -ForegroundColor Cyan
$results | Group-Object Category | Sort-Object Count -Descending |
    Format-Table @{ n = 'Type'; e = { $_.Name } }, Count -AutoSize | Out-Host

if ($candidates) {
    Write-Host 'Candidates (largest first):' -ForegroundColor Cyan
    $candidates | Sort-Object $rank, @{ e = 'SizeKB'; Descending = $true } |
        Format-Table Category, SizeKB, @{ n = 'File'; e = { Split-Path $_.File -Leaf } }, Streams -AutoSize -Wrap | Out-Host
    Write-Host "Copied $(@($candidates).Count) candidate(s) to $OutDir as .wb3 files. Try opening the LIKELY_ ones first." -ForegroundColor Green
} else {
    Write-Host 'No Quattro Pro candidates found among the OLE files.' -ForegroundColor Yellow
}
Write-Host "Full report: $(Join-Path $OutDir 'report.csv')"
