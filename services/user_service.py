from db.connection import get_conn, release_conn, init_db
from db.queries import GET_USER_BY_PHONE, INSERT_USER, GET_USER_BY_NAME, GET_USER_BY_ID


def get_user_by_phone(phone_number, display_name=None):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(GET_USER_BY_PHONE, (phone_number,))
    user = cur.fetchone()
    release_conn(conn)

    if user:
        user_id, name = user
        return user_id, name

    return -1, display_name


def get_user_by_name(name):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(GET_USER_BY_NAME, (name,))
    user = cur.fetchone()
    release_conn(conn)
    if user:
        return user[0]

    return -1


def get_user_by_id(user_id):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(GET_USER_BY_ID, (str(user_id),))
    user = cur.fetchone()
    release_conn(conn)
    if user:
        return user[0]

    return -1


def create_user_in_db(user_id, phone_number, display_name):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(INSERT_USER, (str(user_id), phone_number, display_name))
    user_id = cur.fetchone()[0]
    conn.commit()

    release_conn(conn)
    return user_id, display_name
