import psycopg2
from psycopg2 import pool

db_pool = None

def init_db():
    global db_pool
    db_pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dbname="splitpay",
        user="sneha",
        password="",
        host="localhost",
        port="5432"
    )
    if not db_pool:
        raise Exception("Database connection pool could not be created.")

def get_conn():
    return db_pool.getconn()

def release_conn(conn):
    db_pool.putconn(conn)
