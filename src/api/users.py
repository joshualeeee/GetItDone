import sqlalchemy
import re
from fastapi import APIRouter, Depends
from src.api import auth
from src import database as db

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(auth.get_api_key)],
)
# email = [A-Za-z]+@email\.com
@router.post("/add")
def create_user(username : str, email : str):
    if not username and not email:
        return {"result": "EMPTY USERNAME/EMAIL" }
    calpoly = re.compile('[A-Za-z0-9]+@calpoly\.edu')
    gmail = re.compile('[A-Za-z0-9]+@gmail\.com')

    if calpoly.match(email) is None and gmail.match(email) is None:
        return {"result": "MUST USE CALPOLY OR GMAIL EMAIL ADDRESS" }
    
    with db.engine.begin() as connection:
        # check if the user already exists
        entry = connection.execute(sqlalchemy.text(
        '''
            WITH check_existing AS (
                SELECT id
                FROM users
                WHERE username = :username OR email = :email
            )
            INSERT INTO users (username, email)
            SELECT :username, :email
            WHERE NOT EXISTS (SELECT 1 FROM check_existing)
            RETURNING id;
        '''    
        )
        ,[{'username':username,'email':email}]).scalar()

        if entry is None:
            return { "result" : "Username or Email already in use" }
        
        return { 'user_id' : entry }