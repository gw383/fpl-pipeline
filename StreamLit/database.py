from sqlalchemy import create_engine
from urllib.parse import quote_plus


connection_string = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=FPL;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}"
)
