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
        minutes_taken : int = None,
    ): 
    """ 
    Creates a task and returns task information.

    Tasks can have identical names but must be on different days.
    Completed tasks must inlude date_completed and minutes_taken

    Args:
        user_id (int): The ID of the user creating the task.
        task_name (str): The name of the task.
        description (str, optional): Additional description or details about the task. Defaults to None.
        goal_id (int, optional): The ID of the goal associated with the task. Defaults to None.
        complete (bool): Indicates whether the task is complete. Defaults to False.
        date_completed (str, optional): The completion date of the task (format: YYYY-MM-DD). Defaults to None.
        minutes_taken (int, optional): The time taken to complete the task (in minutes). Defaults to None.

    Returns:
        dict: A dictionary containing the task information or an error message.
    """
    
    if complete is True and minutes_taken and date_completed:
        pass
    elif complete is False and not minutes_taken and not date_completed:
        pass
    else:
        return {"error" : "Completed tasks require minutes_taken and date_completed"}
    
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
            SELECT :task_name, :description, :user, :goal_id, :complete, :date_completed, :minutes_taken
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
            'minutes_taken': minutes_taken
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
    minutes_taken : int,
    date_completed : str = None,
    ): 
    """ 
    Completes a task and returns task information.
    Tasks already complete can be set completed again to update complete_date.

    Args:
        user_id (int): The ID of the user completing the task.
        task_id (int): The ID of the task to be completed.
        minutes_taken (int): The time taken to complete the task (in minutes).
        date_completed (str, optional): The completion date of the task (format: YYYY-MM-DD). Defaults to current date.

    Returns:
        dict: A dictionary containing the task information or an error message.
    """
    if date_completed and not validate_date(date_completed):
        return { "error" : "Date_completed invalid must be (YYYY-MM-DD)" }

    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            UPDATE tasks
            SET complete = true, time_taken = :minutes_taken,
                date_completed = CASE WHEN :date_completed IS NOT NULL THEN :date_completed ELSE now() END
            WHERE id = :id AND "user" = :user
            RETURNING task_name;
        '''    
        )
        ,[{'id':task_id, 'user':user_id, 'minutes_taken':minutes_taken, 'date_completed': date_completed}]).fetchone()

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
    Sets the goal of a task and returns task information.

    Args:
        user_id (int): The ID of the user setting the goal.
        task_id (int): The ID of the task for which the goal is being set.
        goal_id (int): The ID of the goal to be set for the task.

    Returns:
        dict: A dictionary containing the task information or an error message.
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
    Deletes a task and returns success JSON.

    Args:
        user_id (int): The ID of the user deleting the task.
        task_id (int): The ID of the task to be deleted.

    Returns:
        dict: A dictionary containing the result of the deletion operation or an error message.
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
     
    Search, filter, and sort for tasks by task_name and other factors.

    Search page is a cursor for pagination. The response to this
    search endpoint will return next_page >= 1 if there is a
    previous or next page of results available else it will return -1. 
    The next_page search response can be passed in the next search 
    request as search page to get that page of results.

    Args:
        user_id (int): The ID of the user searching for tasks.
        task_name (str, optional): The name of the task to search for (case-insensitive). Defaults to "".
        goal_id (int, optional): The ID of the goal associated with the task. Defaults to None.
        complete_options (complete_options, optional): Filter tasks by completion status. Defaults to complete_options.both.
        search_page (int, optional): The page number for pagination. Defaults to 0.
        sort_col (search_sort_options, optional): The column to sort by. Defaults to search_sort_options.date_created.
        sort_order (search_sort_order, optional): The sort order. Defaults to search_sort_order.desc.

    Returns:
        dict: A dictionary containing the search results or an error message.
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
                db.tasks.c.goal,
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

                date_completed = datetime.strftime(row.date_completed, '%Y-%m-%d') if row.date_completed else None

                res.append(
                    {
                        "tasks_id": row.id,
                        "task_name": row.task_name,
                        "description" : row.description,
                        "goal_id" : row.goal,
                        "goal" : row.goal_name,
                        "complete": row.complete,
                        "date_completed": date_completed,
                        "minutes_taken": row.time_taken
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
    Returns the number of completed_tasks, incompleted_tasks, total, and percentages.

    Args:
        user_id (int): The ID of the user for which to retrieve task statistics.

    Returns:
        dict: A dictionary containing task statistics or an error message.
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

@router.get("/days", tags=["analyze"])
def evaluate_days(user_id : int, goal_id : int = None): 
    """ 
    Returns the number of completed tasks on every day.

    Args:
        user_id (int): The ID of the user for which to evaluate task completion by day.
        goal_id (int, optional): The ID of the goal to filter tasks by. Defaults to None.

    Returns:
        dict: A dictionary containing the number of completed tasks for each day of the week or an error message.
    """
    with db.engine.begin() as connection:
        query = '''
            WITH week_dates AS (
                SELECT
                    generate_series(date_trunc
                        ('week', current_date), date_trunc('week', current_date) + interval '6 days', interval '1 day') AS day
            )
            SELECT
                to_char(week_dates.day, 'Day') AS day_of_week,
                COUNT(t.id) AS tasks_completed
            FROM
                week_dates
            LEFT JOIN
                tasks AS t ON to_char(t.date_completed, 'Day') = to_char(week_dates.day, 'Day') 
                    AND t.complete = true 
                    AND t.user = :user_id
                    {goal_filter}
            GROUP BY
                day_of_week
            ORDER BY
                MIN(week_dates.day);
        '''

        goal_filter = ''
        if goal_id is not None:
            goal_filter = 'AND t.goal = :goal_id'

        entry = connection.execute(sqlalchemy.text(query.format(goal_filter=goal_filter)), {'user_id': user_id, 'goal_id': goal_id}).fetchall()

        if not entry:
            return { "error" : "User not Found" }

        res = {row[0]: row[1] for row in entry}
            
        return res