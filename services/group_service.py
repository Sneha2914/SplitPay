from db.connection import get_conn, release_conn, init_db
from db.queries import INSERT_GROUP, ADD_PARTICIPANT, GET_PARTICIPANTS, GET_GROUP_BY_NAME, UPDATE_GROUP_NAME, GET_GROUP_BY_ID


def check_group_in_db(group_name):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    # check if group already exists
    cur.execute(GET_GROUP_BY_NAME, (group_name,))
    existing = cur.fetchone()

    release_conn(conn)
    if existing:
        return existing[0]
    else:
        return -1


def check_group_in_db_using_id(group_id):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    # check if group already exists
    cur.execute(GET_GROUP_BY_ID, (str(group_id),))
    existing = cur.fetchone()

    release_conn(conn)
    if existing:
        return existing[0]
    else:
        return -1


def create_group_in_db(group_id, group_name, created_by_user_id):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    # create new group
    cur.execute(INSERT_GROUP, (str(group_id), group_name, str(created_by_user_id)))
    group_id = cur.fetchone()[0]
    conn.commit()

    release_conn(conn)
    return group_id


def update_group_name(group_id, old_group_name, new_group_name):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    # create new group
    cur.execute(UPDATE_GROUP_NAME, (new_group_name, str(group_id), old_group_name))
    group_id = cur.fetchone()[0]
    conn.commit()

    release_conn(conn)
    return group_id


def add_participant(group_id, user_id):
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(ADD_PARTICIPANT, (str(group_id), str(user_id)))
    conn.commit()
    release_conn(conn)


def get_group_participants(group_id):
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(GET_PARTICIPANTS, (str(group_id),))
    participants = cur.fetchall()
    release_conn(conn)

    # returns list of tuples: [(user_id, display_name), ...]
    return participants
