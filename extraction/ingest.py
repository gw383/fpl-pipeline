from sqlalchemy import create_engine
from urllib.parse import quote_plus
import pandas as pd
import os

from dotenv import load_dotenv
from main_endpoint import main_endpoint
from fixtures import fixtures
from event_live import event_live

from manager_profiles import manager_profiles
from manager_picks import manager_picks
from manager_transfers import manager_transfers

load_dotenv()

connection_string = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={os.getenv('FPL_DB_SERVER', 'localhost')};"
    "DATABASE=FPL;"
    f"UID={os.getenv('FPL_DB_USER')};"
    f"PWD={os.getenv('FPL_DB_PASSWORD')};"
    "TrustServerCertificate=yes;"
)

engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}"
)

def run_pipeline():

    print("\n STARTING FPL PIPELINE\n")

    main_endpoint(engine)
    fixtures(engine)

    gameweeks = list(range(1, 39))
    event_live(engine, gameweeks)

    entry_ids = [146897]

    print("\n Ingesting manager profiles...")
    manager_profiles(engine, entry_ids)

    print("\n Ingesting manager picks...")
    manager_picks(engine, entry_ids, gameweeks)

    print("\n Ingesting manager transfers...")
    manager_transfers(engine, entry_ids)

    print("\n PIPELINE COMPLETE")

if __name__ == "__main__":
    run_pipeline()
