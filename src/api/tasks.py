import sqlalchemy
import re
from fastapi import APIRouter, Depends
from src.api import auth
from src import database as db

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    dependencies=[Depends(auth.get_api_key)],
)
 
@router.get("/add")
def create_task(task_name : str, user : int, description : str): 
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            WITH check_existing AS (
                SELECT id
                FROM tasks
                WHERE "user" = :user and task_name = :task_name
            )
            INSERT INTO tasks (task_name, description, "user")
            SELECT :task_name, :description, :user
            WHERE NOT EXISTS (SELECT 1 FROM check_existing)
            RETURNING id;
        '''    
        )
        ,[{'task_name':task_name, 'user':user, 'description':description}]).fetchone()

        if entry is None:
            return { "result" : "Task Already Created" }
        
        return  { 
                    'task_id' : entry[0],
                    'task_name' : task_name,
                    'description' : description,
                    'user' : user,
                }
    
@router.put("/complete")
def create_task(id : int): 
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            UPDATE tasks
            SET complete = true,
                date_completed = now()
            WHERE id = :id
            RETURNING task_name, "user";
        '''    
        )
        ,[{'id':id}]).fetchone()

        if entry is None:
            return { "result" : "Task Not Found" }
        
        return  { 
                    'task_id' : id,
                    'task_name' : entry.task_name,
                    'user' : entry.user,
                    'status' : "complete"
                }