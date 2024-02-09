import sqlalchemy
import re
from fastapi import APIRouter, Depends, HTTPException, status
from src.api import auth
from src import database as db
from enum import Enum
from datetime import datetime

router = APIRouter(
    prefix="/goals",
    tags=["goals"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/add")
def create_goal(user_id : int, goal_name : str): 
    """ 
    Creates a new goal for a user.

    Args:
        user_id (int): The ID of the user for whom the goal is created.
        goal_name (str): The name of the goal.

    Returns:
        dict: A dictionary containing information about the created goal or an error message.
    """
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            WITH check_existing AS (
                SELECT id
                FROM goals
                WHERE "user" = :user and goal_name = :goal_name
            )
            INSERT INTO goals (goal_name, "user")
            SELECT :goal_name, :user
            WHERE NOT EXISTS (SELECT 1 FROM check_existing)
            RETURNING id;
        '''    
        )
        ,[{'goal_name':goal_name, 'user':user_id}]).fetchone()

        if entry is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task Already Created")
        
        return  { 
                    'user' : user_id,
                    'goal_id' : entry[0],
                    'goal_name' : goal_name,
                }
    
@router.put("/complete")
def complete_goal(user_id : int, goal_id : int): 
    """ 
    Marks a goal as complete.
    Goals already complete can be set completed again to update complete_date.

    Args:
        user_id (int): The ID of the user who owns the goal.
        goal_id (int): The ID of the goal to mark as complete.

    Returns:
        dict: A dictionary containing information about the completed goal or an error message.
    """
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            UPDATE goals
            SET complete = true,
                date_completed = now()
            WHERE id = :id AND "user" = :user
            RETURNING goal_name;
        '''    
        )
        ,[{'id':goal_id, 'user':user_id}]).fetchone()

        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal Not Found")
        
        return  { 
                    'user' : user_id,
                    'goal_id' : goal_id,
                    'goal_name' : entry.goal_name,
                    'status' : "complete"
                }

@router.delete("/delete")
def delete_goal(user_id : int, goal_id : int): 
    """ 
    Returns the number of completed and incomplete goals, along with percentages.

    Args:
        user_id (int): The ID of the user for which to retrieve goal statistics.

    Returns:
        dict: A dictionary containing goal statistics or an error message.
    """
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            DELETE FROM goals
            WHERE id = :id AND "user" = :user
            RETURNING goal_name;
        '''    
        )
        ,[{'id':goal_id, 'user':user_id}]).fetchone()

        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal Not Found")
        
        return  { 
                    'user' : user_id,
                    'goal_id' : goal_id,
                    'goal_name' : entry.goal_name,
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
def search_goals(
    user_id : int,
    goal_name: str = "",
    complete_options: complete_options = complete_options.both,
    search_page: int = 0,
    sort_col: search_sort_options = search_sort_options.date_created,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Searches for goals by name and completion status.

    Search page is a cursor for pagination. The response to this
    search endpoint will return next_page >= 1 if there is a
    previous or next page of results available else it will return -1. 
    The next_page search response can be passed in the next search 
    request as search page to get that page of results.


    Args:
        user_id (int): The ID of the user searching for goals.
        goal_name (str, optional): The name of the goal to search for (case-insensitive). Defaults to "".
        complete_options (complete_options, optional): Filter goals by completion status. Defaults to complete_options.both.
        search_page (int, optional): The page number for pagination. Defaults to 0.
        sort_col (search_sort_options, optional): The column to sort by. Defaults to search_sort_options.date_created.
        sort_order (search_sort_order, optional): The sort order. Defaults to search_sort_order.desc.

    Returns:
        dict: A dictionary containing the search results or an error message.
    """

    if search_page < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page out of bounds")

    if sort_col is search_sort_options.date_completed:
        order_by = db.goals.c.date_completed
        complete_options = complete_options.complete
    elif sort_col is search_sort_options.date_created:
        order_by = db.goals.c.date_created
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sort column")
    
    if sort_order == search_sort_order.desc:
        order_by = sqlalchemy.desc(order_by)
    else:
        order_by = sqlalchemy.asc(order_by)

    where_conditions = [
        db.goals.c.goal_name.ilike(f"%{goal_name}%"),
        db.goals.c.user == user_id
    ]
    if complete_options == complete_options.complete:
        where_conditions.append(db.goals.c.complete == True)
    elif complete_options == complete_options.incomplete:
        where_conditions.append(db.goals.c.complete == False)
        

    with db.engine.connect() as conn:
        stmt = (
            sqlalchemy.select(
                db.goals.c.id,
                db.goals.c.goal_name,
                db.goals.c.date_created,
                db.goals.c.complete,
                db.goals.c.date_completed,
            ).where(
                sqlalchemy.and_(*where_conditions)
            )
            .select_from(db.goals)
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
                        "goal_id": row.id,
                        "goal_name": row.goal_name,
                        "complete": row.complete,
                        "date_completed": date_completed,
                    }
                )
        
        if i == 0 and search_page > 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page out of bounds")

        return  {
                    "user_id" : user_id,
                    "next_page" : next_page,
                    "start_entry" : (search_page * 5),
                    "end_entry" : (search_page * 5) + i - 1,
                    "res" : res
                }
    
@router.get("/count", tags=["analyze"])
def total_goals(user_id : int): 
    """ 
    Returns progress information for a specific goal.

    Args:
        user_id (int): The ID of the user who owns the goal.
        goal_id (int): The ID of the goal to retrieve progress information for.

    Returns:
        dict: A dictionary containing progress information for the goal or an error message.
    """
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            SELECT
                COUNT(CASE WHEN complete THEN 1 ELSE NULL END) AS complete_goals,
                COUNT(CASE WHEN NOT complete THEN 1 ELSE NULL END) AS incomplete_goals,
                CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE ROUND(COUNT(CASE WHEN complete THEN 1 ELSE NULL END) * 100.0 / COUNT(*), 2)
                END AS percent_complete,
                CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE ROUND(COUNT(CASE WHEN NOT complete THEN 1 ELSE NULL END) * 100.0 / COUNT(*), 2)
                END AS percent_incomplete
            FROM goals
            WHERE "user" = :user_id;
        '''    
        )
        ,[{'user_id':user_id}]).fetchall()

        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Tasks For User Found")
            
        return  { 
                    'completed_goals' : entry[0].complete_goals,
                    'incompleted_goals' : entry[0].incomplete_goals,
                    'total' : entry[0].complete_goals + entry[0].incomplete_goals,
                    'percent_complete' : entry[0].percent_complete,
                    'percent_incomplete' : entry[0].percent_incomplete,
                }

@router.get("/progress", tags=["analyze"])
def goal_progress(user_id : int, goal_id : int): 
    """ 
        Returns the number of completed_goals,
        incompleted_goals, total, and percentages.

    
        Returns error if user can't be found
    """
    with db.engine.begin() as connection:
        entry = connection.execute(sqlalchemy.text(
        '''
            SELECT
                g.goal_name,
                g.complete,
                SUM(t.time_taken) AS minutes_spent,
                COUNT(CASE WHEN t.complete THEN 1 ELSE NULL END) AS complete_tasks,
                COUNT(CASE WHEN NOT t.complete THEN 1 ELSE NULL END) AS incomplete_tasks,
                CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE ROUND(COUNT(CASE WHEN t.complete THEN 1 ELSE NULL END) * 100.0 / COUNT(*), 2)
                END AS percent_complete,
                CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE ROUND(COUNT(CASE WHEN NOT t.complete THEN 1 ELSE NULL END) * 100.0 / COUNT(*), 2)
                END AS percent_incomplete
            FROM
                goals as g
            LEFT JOIN
                tasks as t ON g.id = t.goal
            WHERE
                g.id = :goal_id and g.user = :user_id
            GROUP BY
                g.id, g.goal_name;
        '''    
        )
        ,[{'user_id':user_id, "goal_id" : goal_id}]).fetchall()

        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal Not Found For User")
            
        return  { 
                    'user_id' : user_id,
                    'goal_id' : goal_id,
                    'goal_name' : entry[0].goal_name,
                    'complete' : entry[0].complete,
                    'minutes_spent' : entry[0].minutes_spent,
                    'complete_tasks' : entry[0].complete_tasks,
                    'incomplete_tasks' : entry[0].incomplete_tasks,
                    'percent_complete' : entry[0].percent_complete,
                    'percent_incomplete' : entry[0].percent_incomplete,
                }
