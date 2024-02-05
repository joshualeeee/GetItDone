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

@router.post("/add")
def create_task(user_id : int, task_name : str, description : str = None): 
    """ 
        Creates a task, returns task information

        Returns error if task of same name has been created already
    """

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
        ,[{'task_name':task_name, 'user':user_id, 'description':description}]).fetchone()

        if entry is None:
            return { "error" : "Task Already Created" }
        
        return  { 
                    'user' : user_id,
                    'task_id' : entry[0],
                    'task_name' : task_name,
                    'description' : description,
                }
    
@router.put("/complete")
def complete_task(user_id : int, task_id : int): 
    """ 
        Completes a task, returns task information

        Returns error if task can't be found
    """
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            UPDATE tasks
            SET complete = true,
                date_completed = now()
            WHERE id = :id AND "user" = :user
            RETURNING task_name;
        '''    
        )
        ,[{'id':task_id, 'user':user_id}]).fetchone()

        if entry is None:
            return { "error" : "Task Not Found" }
        
        return  { 
                    'user' : user_id,
                    'task_id' : task_id,
                    'task_name' : entry.task_name,
                    'status' : "complete"
                }

@router.put("/set/goal")
def set_task_goal(user_id : int, task_id : int, goal_id : int): 
    """ 
        Sets goal of a task, returns task information

        Returns error if task can't be found
    """
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            UPDATE tasks
            SET goal = :goal_id
            WHERE id = :id AND "user" = :user
            RETURNING task_name;
        '''    
        )
        ,[{'id':task_id, 'user':user_id, 'goal_id':goal_id}]).fetchone()

        if entry is None:
            return { "error" : "Task Not Found" }
        
        return  { 
                    'user' : user_id,
                    'task_id' : task_id,
                    'task_name' : entry.task_name,
                    'status' : "complete"
                }