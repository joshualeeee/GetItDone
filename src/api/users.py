import sqlalchemy
import re
from fastapi import APIRouter, Depends
from src.api import auth
from src import database as db
import bcrypt

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(auth.get_api_key)],
)

# def checkValidEmail(email):
#     regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
#     if(re.fullmatch(regex, email)):
#         return True
#     else:
#         return False

def is_valid_username(username):
    if not re.match("^[a-zA-Z0-9_]+$", username):
        return False
    if len(username) < 4 or len(username) >= 20:
        return False
    return True
    
def hash_password(password):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed_password

@router.post("/add")
def create_user(name : str, username : str, password : str):
    """
    Creates a user and returns the user id, name, and username

    Username must be unique
    """

    if is_valid_username(username) is False:
        return {  "result" : "Invalid Username : Must only contain only alphanumeric characters and underscores and be 4-20 characters (inclusive)" }


    hpassword = hash_password(password)
    
    
    with db.engine.begin() as connection:
        # check if the user already exists
        entry = connection.execute(sqlalchemy.text(
        '''
            WITH check_existing AS (
                SELECT id
                FROM users
                WHERE username = :username
            )
            INSERT INTO users (name, username, password)
            SELECT :name, :username, :password
            WHERE NOT EXISTS (SELECT 1 FROM check_existing)
            RETURNING id, password;
        '''    
        )
        ,[{'name':name, 'username':username, 'password':hpassword}]).fetchone()

        if entry is None:
            return { "result" : "Username Taken" }
        
        return  { 
                    'id' : entry.id,
                    'name' : name,
                    'username' : username,
                }
    

def verify_password(password, hashed_password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

@router.get("/validate")
def validate_user(username : str, password : str):
    """
    Validates a username and password, returns the account id
    """    
    with db.engine.begin() as connection:
        # check if the user already exists
        entry = connection.execute(sqlalchemy.text(
        '''
            SELECT id, name, password
            FROM users
            WHERE username = :username
        '''    
        )
        ,[{'username':username}]).fetchone()

        if not entry:
            return { "result" : "User not Found" }

        if verify_password(password, bytes(entry.password)) is False:
            return { "result" : "Invalid Password" }
        
        return  { 
                    'id' : entry.id,
                    'name' : entry.name,
                    'username' : username,
                }

@router.delete("/delete")
def delete_user(username : str, password : str):
    """
    Validates a username and password, deletes if valid
    """    
    with db.engine.begin() as connection:
        # check if the user already exists
        entry = connection.execute(sqlalchemy.text(
        '''
            SELECT id, password
            FROM users
            WHERE username = :username
        '''    
        )
        ,[{'username':username}]).fetchone()

        if not entry:
            return { "result" : "User not Found" }

        if verify_password(password, bytes(entry.password)) is False:
            return { "result" : "Invalid Password" }
        
        connection.execute(sqlalchemy.text(
        '''
            DELETE FROM users
            WHERE id = :user_id;
        '''    
        )
        ,[{ 'user_id' : entry.id }])

        return  { "result" : "Successfully Deleted User" }