# Putting the dashboard online

This takes the project from "run it on my PC" to a website anyone can open. Everything below uses free tiers.

| Piece | Where it runs | Free tier |
|---|---|---|
| Database | **Azure SQL Database** (still SQL Server, so dbt and the pipeline work unchanged) | Free offer: 100,000 vCore-seconds and 32 GB a month, pauses rather than charging |
| Dashboard | **Streamlit Community Cloud**, deployed from this GitHub repo | Free; sleeps after 12 hours without visitors, wakes on the next visit |
| Daily refresh | **GitHub Actions**, a scheduled job running `run_pipeline.py --publish` | Free minutes are plenty for one run a day |
| Dashboard data | A file on this repository's **`data` branch**, replaced by each refresh | Free |

The dashboard doesn't query the database when someone opens a page. The pipeline's last step exports the tables the dashboard reads into one SQLite file and publishes it to the `data` branch; the dashboard downloads that file and queries it locally. So pages are fast however far away or fast asleep the database is, and the database only uses its free allowance while the pipeline runs. The one exception is the My Team page looking up a manager who isn't in the file yet.

The code is already prepared for this:

- **`run_pipeline.py`** runs extract → `dbt build` → projection model → data file in one command, on your PC or in GitHub Actions. It waits for a paused database to wake up first. `--publish` also publishes the data file.
- **`serving/`** exports the data file (`export_data.py`) and publishes it (`publish_data.py`).
- **`extraction/db.py`** reads the `FPL_DB_*` settings for everything. It supports Azure SQL and two drivers: Microsoft's ODBC driver (your PC, GitHub Actions) and `pymssql` (the hosted dashboard, which can't install the ODBC driver).
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
4. Run the whole pipeline, and publish the dashboard's data file at the end:

   ```
   python run_pipeline.py --publish
   ```

   The first run is the longest. It loads every gameweek, every player's previous seasons and two seasons of Premier League goal events, then builds dbt, runs the model and exports the data file. `--publish` pushes that file to the repository's `data` branch with your own git login (the same one `git push` uses), which is where the hosted dashboard gets it. The hosted dashboard shows "no data to show yet" until this has been done once.
5. Create the dashboard's login. In the Azure portal, open the **database** and go to **Query editor**, then sign in with the server admin login. Open `deploy/azure_setup.sql`, change the password in it (keep it for step 4), paste it into the editor and click **Run**.
6. Optional: check the local dashboard with `cd dashboard` then `streamlit run app.py`. Every page should load, and the footer says when the data was refreshed.

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

From then on it runs at 06:15 UTC every day and publishes the new data file when it finishes. To change the time, edit the `cron` line in the workflow.

The workflow publishes with the job's own token, which is what the `permissions: contents: write` line in it is for. If the publish step is refused, check **Settings → Actions → General → Workflow permissions** allows read and write.

> If the **Extract** step fails with an HTTP 403 from `fantasy.premierleague.com`, FPL is blocking GitHub's servers. The fallback is running `python run_pipeline.py --publish` on your PC once a day, e.g. from Windows Task Scheduler. The website works the same either way; only the refresh moves.

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

The pages themselves need none of those secrets: they read the published data file. The database login is only for the My Team page, to look up a manager who isn't in the file yet. Without it, the site still works for saved managers.

Secrets can be changed later under the app's **Settings → Secrets**. The app redeploys by itself whenever `main` changes on GitHub. A new data file doesn't need a redeploy: the app checks for one every 15 minutes.

### A test version

A second app deployed from another branch (e.g. `dev`, with the same secrets) is a place to try changes before they reach the live site. Both read the same published data file, so the test app only reads the live site's data. The exception is a new manager looked up on My Team: either app saves them to the same database, and the next refresh adds them to the file.

---

## Day to day

- **Nothing to do.** GitHub refreshes the data each morning and the site shows it. The footer of every page says when the data was last refreshed.
- **Changing the code:** commit and push to `main` and the site updates within a minute or two.
- **Changing what the dashboard reads:** a page that needs a new table or column needs it in the data file too. New tables go in `TABLES` in `serving/data_file.py`; then run the pipeline (or `python serving/export_data.py --publish`) before the dashboard change goes live.
- **After a quiet spell:** the first visitor may see Streamlit's "wake up" button. That is the free hosting pausing, not a fault. The pages no longer wait for the database.
- **Looking up a new manager** on My Team can take up to a minute, while the database wakes up.
- **Your PC:** `streamlit run app.py` and the launchers still work. They read the data file your last local pipeline run wrote (`serving/data/`), or the published one if there isn't one.
- **The database allowance:** the database is now only awake for the daily refresh and the odd manager lookup. To use even less, set its auto-pause delay to the minimum (the database's **Compute + storage** page in the Azure portal).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| The site says "The dashboard has no data to show yet" with HTTP 404 | Nothing has been published to the `data` branch yet. Run `python run_pipeline.py --publish` (or `python serving/export_data.py --publish`) once |
| The footer's "data refreshed" time is days old | The daily refresh is failing or not publishing. Check the latest run under **Actions → Daily refresh** |
| The publish step fails with "Permission denied" or 403 in GitHub Actions | The workflow file lacks `permissions: contents: write`, or the repository's workflow permissions are read-only |
| `Login failed for user` | Wrong login/password, or (for `fpl_web`) the setup script wasn't run in the `fpl` database |
| `Cannot open server ... requested by the login` / timeouts from GitHub or Streamlit | The `AllowAll` firewall rule is missing (step 1.5) |
| Error 40613, "database not currently available" (pipeline, or a My Team lookup) | The database is resuming; wait a minute and retry |
| Streamlit app: `pymssql` connection errors mentioning TLS/encryption | The pymssql driver couldn't negotiate encryption with Azure. Tell me the exact error; the fallback is a different driver |
| My Team lookup fails with "permission denied" | The `GRANT` lines in `deploy/azure_setup.sql` ran before the raw tables existed; run them again |
