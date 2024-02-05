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
 
def checkValidEmail(email):
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    if(re.fullmatch(regex, email)):
        return True
    else:
        return False

@router.post("/add")
def create_user(name : str, email : str):
    if not checkValidEmail(email):
        return {"error": "INVALID EMAIL" }
    
    with db.engine.begin() as connection:
        # check if the user already exists
        entry = connection.execute(sqlalchemy.text(
        '''
            WITH check_existing AS (
                SELECT id
                FROM users
                WHERE email = :email
            )
            INSERT INTO users (name, email)
            SELECT :name, :email
            WHERE NOT EXISTS (SELECT 1 FROM check_existing)
            RETURNING id;
        '''    
        )
        ,[{'name':name, 'email':email}]).fetchone()

        if entry is None:
            return { "result" : "Email Already in Use" }
        
        return  { 
                    'name' : name,
                    'email' : email,
                }