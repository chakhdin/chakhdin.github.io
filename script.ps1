$basePath = "C:\Astro\site\astro-gallery-cat"
Set-Location -Path $basePath

$indexPath = "layouts/index.html"

# 1. Check if the file exists
if (-Not (Test-Path $indexPath)) {
    Write-Host "Warning: layouts/index.html not found!" -ForegroundColor Yellow
    Write-Host "It looks like your homepage is being loaded directly from your theme folder."
    Write-Host "To fix this, copy the index.html file from your themes/[your-theme-name]/layouts/ folder into your main layouts/ folder, then run this script again."
    exit
}

$content = Get-Content -Path $indexPath -Raw

# 2. Prevent duplicate injections
if ($content -match "") {
    Write-Host "The Latest Images section is already in your index.html!" -ForegroundColor Cyan
    exit
}

# 3. Define the exact HTML block to inject
$newSection = @'
    <div class="mt-16 px-4 max-w-7xl mx-auto">
        <h2 class="text-3xl font-extrabold text-white mb-8 border-b border-gray-800 pb-4">
            {{ if eq .Site.Language.Lang "it" }}Ultimi Arrivi
            {{ else if eq .Site.Language.Lang "ru" }}Последние Добавления
            {{ else }}Latest Additions{{ end }}
        </h2>
        
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {{ $pages := where .Site.RegularPages "Params.featured_image" "!=" nil }}
            {{ $latest := $pages.ByDate.Reverse | first 6 }}
            
            {{ range $latest }}
                <a href="{{ .RelPermalink }}" class="block group bg-gray-900 rounded-xl overflow-hidden border border-gray-800 hover:border-gray-500 transition shadow-lg">
                    <div class="aspect-video overflow-hidden bg-black relative">
                        {{ $image := .Resources.GetMatch .Params.featured_image }}
                        {{ if $image }}
                            <img src="{{ $image.RelPermalink }}" alt="{{ .Title }}" class="w-full h-full object-cover group-hover:scale-105 transition duration-700 ease-out">
                        {{ end }}
                    </div>
                    <div class="p-4">
                        <h3 class="text-lg font-bold text-gray-200 group-hover:text-blue-400 transition truncate">{{ .Title }}</h3>
                        <div class="text-xs text-gray-500 mt-2">{{ .Date.Format "2006-01-02" }}</div>
                    </div>
                </a>
            {{ end }}
        </div>
        
        <div class="mt-12 mb-8 text-center">
            <a href="{{ .Site.BaseURL }}{{ if ne .Site.Language.Lang "en" }}{{ .Site.Language.Lang }}/{{ end }}latest/" class="inline-block bg-blue-900/50 hover:bg-blue-800 text-blue-200 border border-blue-700 px-6 py-3 rounded-lg font-semibold transition shadow-md">
                {{ if eq .Site.Language.Lang "it" }}Vedi Tutta la Galleria
                {{ else if eq .Site.Language.Lang "ru" }}Смотреть Всю Галерею
                {{ else }}View Full Gallery{{ end }} &rarr;
            </a>
        </div>
    </div>
'@

# 4. Use Regex to find the absolute last {{ end }} tag and insert our code right above it
$updatedContent = $content -replace '(?s)(.*)\{\{\s*end\s*\}\}(.*)$', "`$1`r`n$newSection`r`n{{ end }}`$2"

# 5. Save the updated file
if ($updatedContent -cne $content) {
    Set-Content -Path $indexPath -Value $updatedContent -Encoding UTF8
    Write-Host "Success! The Latest Images section has been automatically added to your homepage." -ForegroundColor Green
} else {
    Write-Host "Error: Could not locate the closing {{ end }} tag in your index.html. You may need to paste the code manually." -ForegroundColor Red
}