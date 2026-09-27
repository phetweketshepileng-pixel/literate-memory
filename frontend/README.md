# Ascend frontend

Live at https://web-production-382435.up.railway.app (Railway service "web").
Talks to the API at https://backend-production-acb19.up.railway.app.

- src/base.css   – design from the original Ascend prototype
- src/extra.css  – additions for the live app
- src/body.html  – screens
- src/app.js     – all API calls (no framework, no build tools needed)
- build.sh [API_URL] – assembles public/index.html
- Dockerfile + nginx.conf – how Railway serves it

To put it in GitHub: copy this `frontend/` folder into the literate-memory repo and push.
