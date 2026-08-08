# Support Ticketing — Databricks App

A Streamlit app that reads from and writes to Lakebase (`ticketing_system.tickets`
and `ticketing_system.ticket_messages`). No hard-coded data — every view, create,
and update hits Lakebase directly.

## Files

- `app.py` — Streamlit UI (list tickets, view a ticket's messages, create a
  ticket, add a message, update status)
- `lakebase.py` — Lakebase connection + all SQL (SELECT/INSERT/UPDATE). Fetches the
  Postgres connection URL from a Databricks secret rather than an env var.
- `setup_secrets.py` — one-time script that creates the secret scope, stores
  the Lakebase URL, and grants the app's identity read access to it. Run this
  once, before deploying, from a machine with the Databricks CLI configured.
- `requirements.txt` — `streamlit`, `psycopg2-binary`, `databricks-sdk`,
  `sqlalchemy`
- `app.yaml` — Databricks Apps runtime config (env vars)

## One-time setup

1. **Store the Lakebase credential as a secret.** Open `setup_secrets.py`,
   set `APP_PRINCIPAL` to the service principal or group the app runs as,
   then run:
   ```bash
   python setup_secrets.py
   ```
   It will prompt for your Lakebase connection URL
   (`postgresql://role:password@host:5432/databricks_postgres?sslmode=require`)
   and store it under scope `database`, key `lakebase-url`, readable only by
   `APP_PRINCIPAL`.
2. **`app.yaml` env vars** (`LAKEBASE_SECRET_SCOPE`, `LAKEBASE_SECRET_KEY`)
   already point at that scope/key by default — only change them if you used
   different names in step 1.
3. Tables must already exist (from your earlier `CREATE TABLE` statements) in
   the `ticketing_system` schema of that Lakebase database.

## Deploy as a Databricks App

```bash
databricks apps create ticketing-app
databricks sync . /Workspace/Users/<you>/ticketing-app
databricks apps deploy ticketing-app --source-code-path /Workspace/Users/<you>/ticketing-app
```

## Run locally against Lakebase (optional, for testing)

```bash
pip install -r requirements.txt
databricks auth login   # sets up local Databricks auth used by databricks-sdk
python setup_secrets.py # one-time, if you haven't already
streamlit run app.py
```

## How auth to Lakebase works

`lakebase.py` does not read the Postgres password from an env var. On each new
connection it calls `WorkspaceClient().secrets.get_secret(scope, key)` to
fetch the Lakebase connection URL (host, role, and password together) that
`setup_secrets.py` stored, base64-decodes it, and connects with it directly.
The password itself is static and does not expire — access control comes
from who is allowed to *read the secret* (governed by the ACL `setup_secrets.py`
grants), not from short-lived tokens. Rotate the password by re-running
`setup_secrets.py` with a new URL.

