from db.connection import init_db, get_conn, release_conn
from db.queries import GET_EXPENSE_BY_GROUP_AND_TITLE, INSERT_EXPENSE, INSERT_SPLIT, DELETE_EXPENSE, \
    GET_EXPENSES_BY_GROUP, GET_EXPENSE_BY_GROUP_AND_TITLE_AND_PAYER, DELETE_EXPENSE_BY_ID, GET_EXPENSES_BY_PAYER, \
    GET_EXPENSE_SUMMARY_GIVEN_GROUP_TITLE_PAYER, GET_EXPENSE_SHARE_BY_EXPENSE_ID
from services.user_service import get_user_by_name
from psycopg2.extras import RealDictCursor


def get_expense_from_group_and_title(group_id, title):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    # check if group already exists
    cur.execute(GET_EXPENSE_BY_GROUP_AND_TITLE, (group_id, title))
    existing = cur.fetchone()
    conn.commit()
    release_conn(conn)
    if existing:
        return existing[0]
    else:
        return -1


def get_expense_from_group_and_title_and_payer(group_id, title, payer):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(GET_EXPENSE_BY_GROUP_AND_TITLE_AND_PAYER, (str(group_id), str(title), str(payer)))
    existing = cur.fetchone()
    conn.commit()
    release_conn(conn)
    if existing:
        return existing[0]
    else:
        return -1


def get_expense_summary_by_group_title_payer(group_id, title, payer):
    # Initialize DB (if needed once per app, not every query ideally)
    init_db()

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Fetch the expense summary for given group, title, and payer
            cur.execute(GET_EXPENSE_SUMMARY_GIVEN_GROUP_TITLE_PAYER, (str(group_id), str(title), str(payer)))
            existing = cur.fetchall()

        # Commit not required for SELECT, but safe in some pooled setups
        conn.commit()

        if existing:
            return dict(existing[0])  # Return first row as dict
        else:
            return -1
    except Exception as e:
        print(f"Error fetching expense summary: {e}")
        return -1
    finally:
        release_conn(conn)


def save_expense(expense_data, user_id):

    paid_by_id = get_user_by_name(expense_data[user_id]['paid_by'])

    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(INSERT_EXPENSE, (expense_data[user_id]["group"], expense_data[user_id]["title"],
                                 expense_data[user_id]["amount"], paid_by_id))
    expense_id = cur.fetchone()[0]
    conn.commit()
    release_conn(conn)
    return expense_id


def save_expense_user_id(expense_data, user_id):

    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(INSERT_EXPENSE, (expense_data[user_id]["group"], expense_data[user_id]["title"],
                                 expense_data[user_id]["amount"], expense_data[user_id]['paid_by']))
    expense_id = cur.fetchone()[0]
    conn.commit()
    release_conn(conn)
    return expense_id


def check_expense_entered(expense_data, user_id):

    total = 0
    for participant in expense_data[user_id]["participants"]:
        total += expense_data[user_id]['splits'][participant]

    if expense_data[user_id]['split_type'] == 'percentage':
        if total != 100:
            return False, 'percentage'
    elif expense_data[user_id]['split_type'] == 'amount':
        if total != expense_data[user_id]['amount']:
            return False, 'amount'

    return True, ''


def save_expense_split(expense_data, user_id, expense_id):

    for participant in expense_data[user_id]['participants']:
        participant_id = get_user_by_name(participant)
        init_db()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(INSERT_SPLIT, (expense_id, participant_id, expense_data[user_id]['splits'][participant]))
        conn.commit()
        release_conn(conn)


def save_expense_split_user_id(expense_id, user_id, share_amount):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(INSERT_SPLIT, (expense_id, user_id, share_amount))
    split_id = cur.fetchone()[0]
    conn.commit()
    release_conn(conn)
    return split_id


def delete_expense_using_id_and_title(group_id, title):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    # check if group already exists
    cur.execute(DELETE_EXPENSE, (str(group_id), str(title)))
    conn.commit()
    release_conn(conn)


def delete_expense_using_id(expense_id):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    # check if group already exists
    cur.execute(DELETE_EXPENSE_BY_ID, (str(expense_id)))
    conn.commit()
    release_conn(conn)


def get_all_expense_of_user(user_id):
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(GET_EXPENSES_BY_PAYER, (str(user_id),))
    rows = cur.fetchall()
    conn.commit()
    release_conn(conn)

    return rows


def get_expense_titles_amounts(group_id):
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(GET_EXPENSES_BY_GROUP, (group_id,))
    rows = cur.fetchall()
    conn.commit()
    release_conn(conn)

    # returns list of tuples: [(title, amount), ...]
    return rows


def get_expense_splits_by_expense_id(expense_id):
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(GET_EXPENSE_SHARE_BY_EXPENSE_ID, (str(expense_id),))
    rows = cur.fetchall()
    conn.commit()
    release_conn(conn)

    # returns list of tuples: [(user_id, share_amount), ...]
    return rows
