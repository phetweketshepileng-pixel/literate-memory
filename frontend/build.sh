#!/bin/bash
set -e
cd "$(dirname "$0")"
API=${1:-https://backend-production-acb19.up.railway.app}
mkdir -p public
{
echo '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
echo '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
echo '<title>Ascend — AI Career Operating System</title>'
echo '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
echo '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">'
echo '<style>'; cat src/base.css src/extra.css; echo '</style></head><body>'
cat src/body.html
echo "<script>window.ASCEND_API = \"$API\";</script>"
echo '<script>'; cat src/app.js; echo '</script></body></html>'
} > public/index.html
wc -c public/index.html
