-- Run once in the Azure portal's Query editor, connected to your FPL
-- database (not master) as the server admin.
--
-- Creates the login the hosted dashboard uses: it can read everything, and
-- write only the raw schema's manager tables (the My Team page fetches
-- managers on demand). The pipeline itself uses the server admin login.
-- Replace the password (at least 8 characters, mixing upper/lower case,
-- numbers and symbols) and keep it for the Streamlit secrets.

CREATE USER fpl_web WITH PASSWORD = 'CHANGE-ME-to-a-long-password-1!';
ALTER ROLE db_datareader ADD MEMBER fpl_web;
GO

-- After the pipeline's first run has created the raw tables:
GRANT SELECT, INSERT, DELETE ON raw.raw_manager_profiles TO fpl_web;
GRANT SELECT, INSERT, DELETE ON raw.raw_manager_picks TO fpl_web;
GRANT SELECT, INSERT, DELETE ON raw.raw_manager_gameweek_history TO fpl_web;
GRANT SELECT, INSERT, DELETE ON raw.raw_manager_transfers TO fpl_web;
GO
