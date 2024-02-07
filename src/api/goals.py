import sqlalchemy
import re
from fastapi import APIRouter, Depends
from src.api import auth
from src import database as db
from enum import Enum

router = APIRouter(
    prefix="/goals",
    tags=["goals"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/add")
def create_goal(user_id : int, goal_name : str): 
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
            return { "result" : "Task Already Created" }
        
        return  { 
                    'user' : user_id,
                    'goal_id' : entry[0],
                    'goal_name' : goal_name,
                }
    
@router.put("/complete")
def complete_goal(user_id : int, goal_id : int): 
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
            return { "result" : "Goal Not Found" }
        
        return  { 
                    'user' : user_id,
                    'goal_id' : goal_id,
                    'goal_name' : entry.goal_name,
                    'status' : "complete"
                }

@router.delete("/delete")
def delete_goal(user_id : int, goal_id : int): 
    """ 
        Deletes goal, returns success JSON

        Returns error if task can't be found
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
            return { "error" : "Task Not Found" }
        
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
def search_orders(
    user_id : int,
    goal_name: str = "",
    complete_options: complete_options = complete_options.incomplete,
    search_page: int = 0,
    sort_col: search_sort_options = search_sort_options.date_created,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for goals by goal_name and complete status.

    Goal_name used to filter that contain the 
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
    line item contains the goal_id, goal_name, date_created, 
    completeness, and date_completed. Results are paginated, 
    the max results you can return at any time is 5 total line items.
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
                res.append(
                    {
                        "goal_id": row.id,
                        "goal_name": row.goal_name,
                        "date_created": row.date_created,
                        "complete": row.complete,
                        "date_completed": row.date_completed,
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