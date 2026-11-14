# Deploy on Render Free with temporary SQLite

This setup creates only a Python web service. No separate database, disk, or Docker setup is needed. Games and seats disappear when Render sleeps, restarts, or redeploys. Startup migrations automatically recreate tables.

## 1. Upload to GitHub

Create an empty private GitHub repository named `family-thirty-one` (no README, license, or gitignore). In PowerShell:

```powershell
Set-Location 'C:\Users\conno\OneDrive\Desktop\31 Web Game'
git init
git add .
git commit -m "Add family 31 game and Render configuration"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/family-thirty-one.git
git push -u origin main
```

Replace YOUR-USERNAME with your GitHub username. Authenticate if prompted. If Git requests identity, set `git config user.name "Your Name"` and `git config user.email "YOUR-GITHUB-EMAIL"`, then rerun the commit and subsequent commands. GitHub's private noreply email also works. `.gitignore` excludes local databases, virtual environments, collected static files, and `.env`. Migration files in `game/migrations` must be uploaded.

## 2. Create the web service

Sign into https://dashboard.render.com, choose **New → Web Service**, connect GitHub, and select the repository. Grant Render access to this repository. Set:

| Setting | Value |
| --- | --- |
| Name | Any available name, such as `family-thirty-one` |
| Language / Runtime | **Python 3**, even if Render detects the Dockerfile |
| Branch | `main` |
| Root Directory | Leave empty |
| Region | A nearby region |
| Instance Type | **Free** |
| Health Check Path | `/` |

Build Command:

```sh
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

Start Command:

```sh
python manage.py migrate --noinput && waitress-serve --listen=0.0.0.0:$PORT thirtyone.wsgi:application
```

These are Render Linux shell commands. Paste them directly into the dashboard, not local PowerShell. Migrations belong in startup so a new SQLite database works after every restart, not only after builds.

## 3. Environment variables

Before creating the service, add:

| Key | Value |
| --- | --- |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_SECRET_KEY` | Use Render's Generate option for a random secret |

If Generate is unavailable, run ` .\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(64))"` locally and paste its output into the secret field. Do not put the secret in GitHub. Keep it unchanged across restarts.

Leave `DATABASE_PATH`, `DATABASE_URL`, and `PYTHON_VERSION` unset. The app uses its default local SQLite path and `.python-version` selects Python 3.12. Render automatically supplies `PORT` and `RENDER_EXTERNAL_HOSTNAME`; the app uses the latter for allowed hosts and trusted HTTPS form origins. No need to set them manually. No superuser account is required.

## 4. Deploy and play

Click **Create Web Service**. Watch deployment logs until live, then open the assigned **HTTPS** `.onrender.com` link. It should show the home page with styles. Create a table with your name; this also checks that database migrations, cookies, and forms work. Copy the invite link and open it in a different browser/private window or another device. Join as another player, then deal, draw, and discard to confirm both screens update. Regular tabs share a seat; use different browsers or devices for different players.

For the family game, open the main URL, create a fresh table, and share its invite. Wait for everyone to join before dealing; new players cannot join once play starts. Keep the host's browser available to deal later rounds. Your computer does not need to remain on after deployment; Render runs the app.

## 5. Later updates and resets

To publish local changes:

```powershell
git add .
git commit -m "Update family game"
git push
```

Render normally deploys pushes to the linked branch automatically. Avoid pushing during a game because deployment resets temporary rooms. Free services sleep after 15 minutes without inbound traffic; waking takes around a minute. Open the site shortly before inviting family. Close game tabs when finished because they poll for updates. Render may also restart unexpectedly; if a room disappears, return to `/`, create a new table, and share a fresh invite. Manual setup is never needed after a reset. Usage quotas still apply to free services.

## Troubleshooting

- **Docker fields instead of Python commands:** select Python 3 as the runtime.
- **Missing DJANGO_SECRET_KEY:** add it under Environment, then redeploy.
- **400 / DisallowedHost:** verify the service has `RENDER_EXTERNAL_HOSTNAME`; the updated settings must be pushed. Do not use `*` as allowed hosts.
- **403 / CSRF verification failed:** use the assigned HTTPS URL and ensure the updated settings were deployed. Refresh the home page and retry. Keep CSRF protection enabled.
- **no such table:** check that Start Command runs `migrate` before Waitress.
- **No open ports:** use exactly `0.0.0.0:$PORT` in the Render Start Command.
- **Missing styles:** check build logs for successful `collectstatic`; hard refresh the browser.
- **Room not found after inactivity/deploy:** expected with temporary SQLite. Create a fresh table.

References: https://render.com/docs/web-services, https://render.com/docs/free, https://render.com/docs/python-version, https://render.com/docs/environment-variables.
