import os
import dotenv
from sqlalchemy import create_engine
import sqlalchemy

def database_connection_url():
    dotenv.load_dotenv()
    return os.environ.get("POSTGRES_URI")

# postgres://postgres.bckutmfiybslsueyjnsu:ZhZ_mbQF?h/p75Y@aws-0-us-west-1.pooler.supabase.com:5432/postgres

engine = create_engine(database_connection_url(), pool_pre_ping=True)
