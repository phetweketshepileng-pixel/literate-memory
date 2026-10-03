#!/bin/bash
set -e
cd "$(dirname "$0")"
API=${1:-https://backend-production-acb19.up.railway.app}
mkdir -p public
{
echo '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
echo '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
echo '<title>Ascend — AI Career Operating System</title>'
echo '<meta name="theme-color" content="#0F2A1D"><meta name="description" content="Free job search for South Africans: jobs, learnerships, government posts and a CV builder.">'
echo '<link rel="manifest" href="/manifest.webmanifest"><link rel="icon" href="/icon-192.png"><link rel="apple-touch-icon" href="/icon-192.png">'
# heading font only (one small file), and skipped entirely when the phone is in data-saver mode
echo '<script>(function(){var c=navigator.connection;if(c&&c.saveData)return;var l=document.createElement("link");l.rel="stylesheet";l.href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500..600&display=swap";document.head.appendChild(l);})();</script>'
echo '<style>'; cat src/base.css src/extra.css; echo '</style></head><body>'
cat src/body.html
echo "<script>window.ASCEND_API = \"$API\";</script>"
echo '<script>'; cat src/app.js; echo '</script>'
# installable app + offline screen (see public/sw.js)
echo '<script>if("serviceWorker" in navigator&&(location.protocol==="https:"||location.hostname==="localhost"))navigator.serviceWorker.register("/sw.js").catch(function(){});</script></body></html>'
} > public/index.html
wc -c public/index.html
