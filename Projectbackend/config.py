"""
Database configuration and connection management for CryptoVault
"""
import os
from dotenv import load_dotenv

# Load env vars FIRST so DB_ENGINE is available
load_dotenv()

DB_ENGINE = os.getenv('DB_ENGINE', 'mysql').lower()

if DB_ENGINE == 'postgres' or DB_ENGINE == 'postgresql':
    import psycopg2
    from psycopg2 import pool as pgpool
else:
    import mysql.connector
    from mysql.connector import pooling


class DatabaseConfig:
    """Database configuration class"""
    
    def __init__(self):
        host = os.getenv('DB_HOST', 'localhost')
        port = int(os.getenv('DB_PORT', 5432 if DB_ENGINE.startswith('post') else 3306))
        user = os.getenv('DB_USER', 'root')
        password = os.getenv('DB_PASSWORD', '')
        database = os.getenv('DB_NAME', 'cryptovault_db')

        self.pool = None
        if DB_ENGINE == 'postgres' or DB_ENGINE == 'postgresql':
            # psycopg2 connection pool config
            self.config = {
                'host': host,
                'port': port,
                'user': user,
                'password': password,
                'database': database,
                'minconn': 1,
                'maxconn': int(os.getenv('DB_POOL_SIZE', 5))
            }
        else:
            self.config = {
                'host': host,
                'port': port,
                'user': user,
                'password': password,
                'database': database,
                'charset': 'utf8mb4',
                'collation': 'utf8mb4_unicode_ci',
                'autocommit': False,
                'pool_name': 'cryptovault_pool',
                'pool_size': int(os.getenv('DB_POOL_SIZE', 5))
            }
    
    def initialize_pool(self):
        """Initialize the connection pool"""
        try:
            if DB_ENGINE == 'postgres' or DB_ENGINE == 'postgresql':
                self.pool = pgpool.SimpleConnectionPool(
                    self.config['minconn'],
                    self.config['maxconn'],
                    host=self.config['host'],
                    port=self.config['port'],
                    user=self.config['user'],
                    password=self.config['password'],
                    database=self.config['database']
                )
            else:
                self.pool = pooling.MySQLConnectionPool(**self.config)
            print("Database connection pool initialized successfully")
            return True
        except Exception as err:
            print(f"Error initializing database pool: {err}")
            return False
    
    def get_connection(self):
        """Get a connection from the pool"""
        if self.pool is None:
            self.initialize_pool()
        if DB_ENGINE == 'postgres' or DB_ENGINE == 'postgresql':
            return self.pool.getconn()
        else:
            return self.pool.get_connection()
    
    def release_connection(self, conn):
        """Release connection back to pool (for Postgres)"""
        if DB_ENGINE == 'postgres' or DB_ENGINE == 'postgresql':
            self.pool.putconn(conn)


# Global database instance
db_config = DatabaseConfig()


def get_db_connection():
    """Get a database connection"""
    return db_config.get_connection()


def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """
    Execute a database query with proper error handling
    
    Args:
        query: SQL query string
        params: Query parameters (tuple or dict)
        fetch_one: Return single result
        fetch_all: Return all results
        commit: Commit the transaction
    
    Returns:
        Query result or None
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if DB_ENGINE == 'postgres' or DB_ENGINE == 'postgresql':
            cursor = conn.cursor()
            cursor.execute(query, params)

            result = None
            if fetch_one:
                row = cursor.fetchone()
                if row and cursor.description:
                    cols = [col[0] for col in cursor.description]
                    result = dict(zip(cols, row))
            elif fetch_all:
                rows = cursor.fetchall()
                if rows and cursor.description:
                    cols = [col[0] for col in cursor.description]
                    result = [dict(zip(cols, r)) for r in rows]

            if commit:
                conn.commit()

            # For Postgres, if the caller requested fetch_one/fetch_all we already built result
            # For other cases (simple insert without RETURNING), return True to indicate success
            return result if (fetch_one or fetch_all) else True
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)

            result = None
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()

            if commit:
                conn.commit()
                result = cursor.lastrowid if cursor.lastrowid else True

            return result
    except Exception as err:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        print(f"Database error: {err}")
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                if DB_ENGINE == 'postgres' or DB_ENGINE == 'postgresql':
                    db_config.release_connection(conn)
                else:
                    conn.close()
            except Exception:
                pass


def execute_transaction(queries):
    """
    Execute multiple queries in a transaction
    
    Args:
        queries: List of tuples (query, params)
    
    Returns:
        True if successful, raises exception on failure
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if DB_ENGINE == 'postgres' or DB_ENGINE == 'postgresql':
            cursor = conn.cursor()
            for query, params in queries:
                # Ensure None params are passed as empty tuple for psycopg2
                cursor.execute(query, params or ())
            conn.commit()
            return True
        else:
            cursor = conn.cursor()
            for query, params in queries:
                cursor.execute(query, params)
            conn.commit()
            return True
    except Exception as err:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        print(f"Transaction error: {err}")
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                if DB_ENGINE == 'postgres' or DB_ENGINE == 'postgresql':
                    db_config.release_connection(conn)
                else:
                    conn.close()
            except Exception:
                pass
