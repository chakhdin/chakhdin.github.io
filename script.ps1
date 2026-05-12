$basePath = "C:\Astro\site\astro-gallery-cat"
Set-Location -Path $basePath

$filePath = "layouts/_default/single.html"
$content = Get-Content -Path $filePath -Raw

# Update the link from /search/?q=... to /equipment/.../
$content = $content -replace '\{\{ "/search/" \| relURL \}\}\?q=\{\{ \. \| urlize \}\}', '{{ "/equipment/" | relURL }}{{ . | urlize }}/'

Set-Content -Path $filePath -Value $content -Encoding UTF8
Write-Host "Links updated to point to the /equipment/ taxonomy!" -ForegroundColor Green