# Digital Course — server deployment checklist

Reusable steps for one machine serving **FastAPI** (teacher + API) and the **student SPA** under one domain (example paths match `bujiuhong6.top` layout: code in `/www/wwwroot/digital-course`, SPA build in `student-dist/`, API on `127.0.0.1:8000`). Replace domain and paths if yours differ.

## 1. Server preparation

- Install **Python 3** (version per project README), **Nginx**, and (if used) panel TLS certs.
- Open firewall **80** and **443** to the world; keep **8000** bound to loopback only.
- Create deploy user or use **root** only if your runbook requires it; the sample **systemd** unit runs as `root` to match the parent plan.

## 2. Upload application code and data

- Clone or upload the repo to **`/www/wwwroot/digital-course`** (or your chosen root).
- On the server, in `services/api/`, copy your local **`.env`** to the server and edit it there. **Never commit `.env` or paste real secrets into the repo.**
- For this migration, keep `STUDENT_PASSWORD_KEY` exactly aligned with the local database. If the local `.env` has this line commented out, keep it commented out on the server so existing student passwords continue to decrypt.
- Create a virtualenv at `services/api/.venv` and install dependencies (see project `README` / lockfiles for the exact `pip` command).
- **Database:** copy your preserved `teach.db` to `services/api/data/teach.db`, then align the schema before starting the API:
  ```bash
  cd /www/wwwroot/digital-course/services/api
  .venv/bin/python -m alembic upgrade head
  ```
- Do not run `scripts/initialize_content_db.py` during this migration; it is for initialization workflows and can clear runtime data such as students and roster entries.

## 3. Student SPA (`/student/`)

- On a build machine (or CI), run the student app production build with base URL **`/student/`** as required by the frontend docs.
- Upload the build output to **`/www/wwwroot/digital-course/student-dist/`** (sync/rsync/scp). Keep a dated copy of the previous `student-dist` before overwriting (rollback).

## 4. systemd API service

- Copy `deploy/systemd/digital-course-api.service` to `/etc/systemd/system/digital-course-api.service`.
- Ensure **`ExecStart`** points at the real **`.venv` Python** under `services/api` (systemd needs an absolute path to the interpreter).
- `systemctl daemon-reload`
- `systemctl enable --now digital-course-api`
- Check: `systemctl status digital-course-api` and `curl -sS http://127.0.0.1:8000/health`

## 5. Nginx + HTTPS

- Install or issue TLS certificates (example panel paths in `deploy/nginx/digital-course.conf`: `fullchain.pem` / `privkey.pem` under `.../cert/<your-domain>/`).
- Include or symlink `deploy/nginx/digital-course.conf` into your Nginx `sites-enabled` (or paste its `server` blocks into the panel site config).
- `nginx -t` then `systemctl reload nginx`
- In a browser: HTTPS home redirects to **`/student/`**, teacher works under **`/teacher`**, API under **`/v1/...`**.

**Note:** FastAPI’s default **`/docs`** and **`/openapi.json`** are not matched by the sample proxy regex. Add a `location` for them if you need Swagger on production.

## 6. Rollback and backup

- **API:** `systemctl stop digital-course-api`, restore previous code or venv, restore `.env` from a secure backup, `systemctl start digital-course-api`.
- **Frontend:** restore the previous `student-dist` directory from your dated backup, reload Nginx if needed.
- **Database:** restore from your file or dump backup; test on a copy first when possible.
