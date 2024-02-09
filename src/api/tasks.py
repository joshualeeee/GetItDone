import datetime
from enum import Enum
import sqlalchemy
import re
from fastapi import APIRouter, Depends
from src.api import auth
from src import database as db
from datetime import datetime


router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    dependencies=[Depends(auth.get_api_key)],
)

def validate_date(date: str):
    try:
        date = datetime.strptime(date, '%Y-%m-%d')
        return True
    except ValueError:
        return False


@router.post("/add")
def create_task(
        user_id : int, 
        task_name : str, 
        description : str = None, 
        goal_id : int = None, 
        complete : bool = False,
        date_completed : str = None,
        time_taken : int = None,
    ): 
    """ 
        Creates a task, returns task information

        *Tasks can have identical names but must be on different days

        Parameters:
        - user_id (int): The ID of the user creating the task.
        - task_name (str): The name of the task.
        - description (str, optional): Additional description or details about the task. Defaults to None.
        - goal_id (int, optional): The ID of the goal associated with the task. Defaults to None.

        - complete (bool) : Defaults to False
        - date_completed (str, optional (required if complete)): The completion date of the task (format: YYYY-MM-DD). Defaults to None.
        - time_taken (int, optional (required if complete)): The time taken to complete the task (in minutes). Defaults to None.

        Returns error if task of same name has been created already
    """
    
    if not ((complete and time_taken and date_completed) or (not complete and not time_taken and not date_completed)):
        return {"error" : "Completed tasks require time_taken and date_completed"}
    
    if date_completed and not validate_date(date_completed):
        return { "error" : "Date_completed invalid must be (YYYY-MM-DD)" }

    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            WITH check_existing AS (
                SELECT id
                FROM tasks
                WHERE "user" = :user and task_name = :task_name and date_completed = :date_completed
            )
            INSERT INTO tasks (task_name, description, "user", goal, complete, date_completed, time_taken)
            SELECT :task_name, :description, :user, :goal_id, :complete, :date_completed, :time_taken
            WHERE NOT EXISTS (SELECT 1 FROM check_existing)
            RETURNING id;
        '''    
        )
        ,[{
            'task_name':task_name, 
            'user':user_id, 
            'description':description, 
            'goal_id':goal_id,
            'complete':complete,
            'date_completed':date_completed,
            'time_taken': time_taken
            }]).fetchone()

        if entry is None:
            return { "error" : "Task Already Created" }
        
        return  { 
                    'user' : user_id,
                    'task_id' : entry[0],
                    'task_name' : task_name,
                    'description' : description,
                    'complete':complete,
                }
    
@router.put("/complete")
def complete_task(
    user_id : int, 
    task_id : int,
    time_taken : int,
    date_completed : str = None,
    ): 
    """ 
        Completes a task, returns task information

        - user_id (int): The ID of the user completing the task.
        - task_id (int): The ID of the task to be completed.
        - time_taken (int): The time taken to complete the task (in minutes).
        - date_completed (date, optional): The completion date of the task (format: YYYY-MM-DD). Defaults to current date

        Returns error if task can't be found
    """
    if date_completed and not validate_date(date_completed):
        return { "error" : "Date_completed invalid must be (YYYY-MM-DD)" }

    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            UPDATE tasks
            SET complete = true, time_taken = :time_taken,
                date_completed = CASE WHEN :date_completed IS NOT NULL THEN :date_completed ELSE now() END
            WHERE id = :id AND "user" = :user
            RETURNING task_name;
        '''    
        )
        ,[{'id':task_id, 'user':user_id, 'time_taken':time_taken, 'date_completed': date_completed}]).fetchone()

        if date_completed:
            date_completed = validate_date(date_completed)
            if not date_completed:
                return { "error" : "Date_completed invalid must be (YYYY-MM-DD)" }

        if entry is None:
            return { "error" : "Task Not Found" }
        
        return  { 
                    'user' : user_id,
                    'task_id' : task_id,
                    'task_name' : entry.task_name,
                    'complete': True,
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

@router.delete("/delete")
def delete_task(user_id : int, task_id : int): 
    """ 
        Deletes task, returns success JSON

        Returns error if task can't be found
    """
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            DELETE FROM tasks
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
                    'status' : "successfully deleted"
                }


class search_sort_options(str, Enum):
    date_created = "date_created"
    date_completed = "date_completed"

class complete_options(str, Enum):
    incomplete = "incomplete"
    complete = "complete"
    both = "both"

class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc" 

@router.get("/search/")
def search_tasks(
    user_id : int,
    task_name: str = "",
    goal_id : int = None,
    complete_options: complete_options = complete_options.both,
    search_page: int = 0,
    sort_col: search_sort_options = search_sort_options.date_created,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for tasks by task_name and complete status.

    Task_name used to filter that contain the 
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return next_page >= 1 if there is a
    previous or next page of results available else it will return 0. 
    The next_page search response can be passed in the next search 
    request as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by date_created of the order
    in descending order.

    The response itself contains a start and end entry that represents 
    the 0-indexed position of results. Each
    line item contains the task_id, task_name, description,
    goal_name, date_created, completion status, date_completed, 
    time_taken. Results are paginated,  the max results you can return at any 
    time is 5 total line items.
    """

    if search_page < 0:
        return {"error" : "page out of bounds"}

    if sort_col is search_sort_options.date_completed:
        order_by = db.goals.c.date_completed
        complete_options = complete_options.complete
    elif sort_col is search_sort_options.date_created:
        order_by = db.goals.c.date_created
    else:
        assert False
    
    if sort_order == search_sort_order.desc:
        order_by = sqlalchemy.desc(order_by)
    else:
        order_by = sqlalchemy.asc(order_by)

    where_conditions = [
        db.tasks.c.task_name.ilike(f"%{task_name}%"),
        db.tasks.c.user == user_id,
    ]

    if complete_options == complete_options.complete:
        where_conditions.append((db.tasks.c.complete == True))
    elif complete_options == complete_options.incomplete:
        where_conditions.append((db.tasks.c.complete == False))

    if goal_id:
        where_conditions.append((db.tasks.c.goal == goal_id))

    joined_tables = db.tasks.outerjoin(db.goals, db.goals.c.id == db.tasks.c.goal)
    
    
    with db.engine.connect() as conn:
        stmt = (
            sqlalchemy.select(
                db.tasks.c.id,
                db.tasks.c.task_name,
                db.tasks.c.description,
                db.goals.c.goal_name,
                db.tasks.c.date_created,
                db.tasks.c.complete,
                db.tasks.c.date_completed,
                db.tasks.c.time_taken,
            ).where(
                sqlalchemy.and_(*where_conditions)
            )
            .select_from(joined_tables)
            .limit(6)
            .offset(search_page * 5)
            .order_by(order_by)
        )

        result = conn.execute(stmt).fetchall()
        next_page = -1
        if len(result) >= 6:
            next_page = search_page + 1

        res = []
        i = 0
        for row in result:
            if i < 5:
                i += 1
                res.append(
                    {
                        "tasks_id": row.id,
                        "task_name": row.task_name,
                        "description" : row.description,
                        "goal" : row.goal_name,
                        "date_created": row.date_created,
                        "complete": row.complete,
                        "date_completed": row.date_completed,
                        "time_taken": row.time_taken
                    }
                )
        
        if i == 0 and search_page > 0:
                return {"error" : "page out of bounds"}

        return  {
                    "user_id" : user_id,
                    "next_page" : next_page,
                    "start_entry" : (search_page * 5),
                    "end_entry" : (search_page * 5) + i - 1,
                    "res" : res
                }

@router.get("/count", tags=["analyze"])
def total_tasks(user_id : int): 
    """ 
        Returns the number of completed_tasks,
        incompleted_tasks, total, and percentages.

    
        Returns error if user can't be found
    """
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            SELECT
                COUNT(CASE WHEN complete THEN 1 ELSE NULL END) AS complete_tasks,
                COUNT(CASE WHEN NOT complete THEN 1 ELSE NULL END) AS incomplete_tasks,
                CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE ROUND(COUNT(CASE WHEN complete THEN 1 ELSE NULL END) * 100.0 / COUNT(*), 2)
                END AS percent_complete,
                CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE ROUND(COUNT(CASE WHEN NOT complete THEN 1 ELSE NULL END) * 100.0 / COUNT(*), 2)
                END AS percent_incomplete
            FROM tasks
            WHERE "user" = :user_id;
        '''    
        )
        ,[{'user_id':user_id}]).fetchall()

        if not entry:
            return { "error" : "No Tasks For User Found" }
            
        return  { 
                    'completed_tasks' : entry[0].complete_tasks,
                    'incompleted_tasks' : entry[0].incomplete_tasks,
                    'total' : entry[0].complete_tasks + entry[0].incomplete_tasks,
                    'percent_complete' : entry[0].percent_complete,
                    'percent_incomplete' : entry[0].percent_incomplete,
                }