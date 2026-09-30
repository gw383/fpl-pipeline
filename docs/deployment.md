# Putting the dashboard online

This takes the project from "run it on my PC" to a website anyone can open. Everything below uses free tiers.

| Piece | Where it runs | Free tier |
|---|---|---|
| Database | **Azure SQL Database** (still SQL Server, so dbt and the queries work unchanged) | Free offer: 100,000 vCore-seconds and 32 GB a month, pauses rather than charging |
| Dashboard | **Streamlit Community Cloud**, deployed from this GitHub repo | Free; sleeps after 12 hours without visitors, wakes on the next visit |
| Daily refresh | **GitHub Actions**, a scheduled job running `run_pipeline.py` | Free minutes are plenty for one run a day |

The code is already prepared for this:

- **`run_pipeline.py`** runs extract → `dbt build` → projection model in one command, on your PC or in GitHub Actions. It waits for a paused database to wake up first.
- **`extraction/db.py`** reads the `FPL_DB_*` settings for everything, including the dashboard. It supports Azure SQL and two drivers: Microsoft's ODBC driver (your PC, GitHub Actions) and `pymssql` (the hosted dashboard, which can't install the ODBC driver).
- **`transformation/profiles/profiles.yml`** is a dbt profile built from the same settings, used automatically when `FPL_DB_USER` is set.
- **`dashboard/requirements.txt`** holds the hosted dashboard's packages. Streamlit Cloud reads it instead of the full list.
- **`deploy/`** holds the scheduled GitHub Actions job and the database setup script.

---

## 1. Create the database (about 30 minutes)

1. Sign up at [portal.azure.com](https://portal.azure.com). A free account is fine.
2. Search for **SQL databases** and click **Create**. On the first tab, apply the **free offer** when the banner offers it ("Want to try Azure SQL Database for free?"). Then fill in:
   - **Resource group:** create one, e.g. `fpl`.
   - **Database name:** `fpl`.
   - **Server:** *Create new*.
     - **Server name:** e.g. `fpl-warehouse-george`. It must be globally unique and becomes `fpl-warehouse-george.database.windows.net`.
     - **Location:** UK South, or whatever is nearest.
     - **Authentication method:** *Use SQL authentication*.
     - **Server admin login / password:** choose them and **write them down**. The pipeline uses this login.
   - **Behaviour when the free limit is reached:** *Auto-pause the database until next month*. It can then never charge you.
3. On the **Networking** tab, set:
   - **Connectivity method:** *Public endpoint*.
   - **Add current client IP address:** *Yes*.
4. Click **Review + create**, then **Create**, and wait a few minutes.
5. Open the new **SQL server** (not the database), go to **Security → Networking**, and under *Firewall rules* add:
   - **Rule name:** `AllowAll`
   - **Start IP:** `0.0.0.0`
   - **End IP:** `255.255.255.255`

   GitHub Actions and Streamlit Cloud don't have fixed IP addresses, so the database has to accept connections from anywhere. Logins still need a password, and the dashboard gets a limited login in step 2.

## 2. Fill it from your PC (about 30–60 minutes, mostly waiting)

1. Keep a copy of your local settings: copy `.env` to `.env.local`.
2. Edit `.env` so the database lines read (with your values):

   ```
   FPL_DB_SERVER=fpl-warehouse-george.database.windows.net
   FPL_DB_NAME=fpl
   FPL_DB_USER=<server admin login>
   FPL_DB_PASSWORD=<server admin password>
   FPL_DB_DRIVER=odbc
   FPL_DB_TRUST_CERT=no
   ```

3. Check the connection:

   ```
   python extraction/check_connection.py
   ```

   The first attempt may take up to a minute while the database wakes up. It should end with `Connected OK.`
4. Run the whole pipeline:

   ```
   python run_pipeline.py
   ```

   The first run is the longest. It loads every gameweek, every player's previous seasons and two seasons of Premier League goal events, then builds dbt and runs the model.
5. Create the dashboard's login. In the Azure portal, open the **database** and go to **Query editor**, then sign in with the server admin login. Open `deploy/azure_setup.sql`, change the password in it (keep it for step 4), paste it into the editor and click **Run**.
6. Optional: check the local dashboard against the cloud database with `cd dashboard` then `streamlit run app.py`. Every page should load.

To go back to your local database at any time, copy `.env.local` back over `.env`.

## 3. Schedule the daily refresh (about 10 minutes)

Scheduled GitHub Actions jobs only run from the repository's default branch (`main`), so bring `main` up to date first.

1. **Merge your work into `main`.** On GitHub, open **Pull requests → New pull request**, with base `main` and compare `cleanup/portfolio`. Create it, then **Merge**.
2. **Add the workflow file.** From `C:\fpl-pipeline`:

   ```
   git checkout main
   git pull
   mkdir .github\workflows   (skip if it exists)
   copy deploy\daily-refresh.yml .github\workflows\daily-refresh.yml
   git add .github\workflows\daily-refresh.yml
   git commit -m "Schedule the daily refresh"
   git push
   ```

3. **Add the secrets.** In the GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret** and add four:

   | Secret | Value |
   |---|---|
   | `FPL_DB_SERVER` | `fpl-warehouse-george.database.windows.net` |
   | `FPL_DB_NAME` | `fpl` |
   | `FPL_DB_USER` | server admin login |
   | `FPL_DB_PASSWORD` | server admin password |

4. **Try it.** Go to **Actions → Daily refresh → Run workflow**. It takes a few minutes; each step's log is shown.

From then on it runs at 06:15 UTC every day. To change the time, edit the `cron` line in the workflow.

> If the **Extract** step fails with an HTTP 403 from `fantasy.premierleague.com`, FPL is blocking GitHub's servers. The fallback is running `python run_pipeline.py` on your PC once a day, e.g. from Windows Task Scheduler. The website works the same either way; only the refresh moves.

## 4. Put the dashboard online (about 15 minutes)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub. Allow access to the repo, including private repos if yours is private.
2. Click **Create app → Deploy a public app from GitHub** and fill in:
   - **Repository:** `gw383/fpl-pipeline`
   - **Branch:** `main`
   - **Main file path:** `dashboard/app.py`
   - **App URL:** choose a name, e.g. `fpl-analytics` → `fpl-analytics.streamlit.app`
3. Open **Advanced settings**:
   - **Python version:** 3.11
   - **Secrets:** paste the following, with your values:

     ```toml
     FPL_DB_DRIVER = "pymssql"
     FPL_DB_SERVER = "fpl-warehouse-george.database.windows.net"
     FPL_DB_NAME = "fpl"
     FPL_DB_USER = "fpl_web"
     FPL_DB_PASSWORD = "<the fpl_web password from step 2>"
     FPL_DB_TRUST_CERT = "no"
     FPL_MY_ENTRY_ID = "194625"
     ```

4. Click **Deploy**. The first build takes a few minutes. Then open the URL.

Secrets can be changed later under the app's **Settings → Secrets**. The app redeploys by itself whenever `main` changes on GitHub.

---

## Day to day

- **Nothing to do.** GitHub refreshes the data each morning and the site shows it.
- **Changing the code:** commit and push to `main` and the site updates within a minute or two.
- **After a quiet spell:** the first visitor may see Streamlit's "wake up" button, then "Waking up the database". That takes up to a minute. This is the free tiers pausing, not a fault.
- **Your PC:** `streamlit run app.py` and the launchers still work. They use whatever `.env` points at.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Login failed for user` | Wrong login/password, or (for `fpl_web`) the setup script wasn't run in the `fpl` database |
| `Cannot open server ... requested by the login` / timeouts from GitHub or Streamlit | The `AllowAll` firewall rule is missing (step 1.5) |
| Error 40613, "database not currently available" | The database is resuming; wait a minute and retry |
| Streamlit app: `pymssql` connection errors mentioning TLS/encryption | The pymssql driver couldn't negotiate encryption with Azure. Tell me the exact error; the fallback is a different driver |
| My Team lookup fails with "permission denied" | The `GRANT` lines in `deploy/azure_setup.sql` ran before the raw tables existed; run them again |
