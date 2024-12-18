# database.py

import streamlit as st
import psycopg2
from psycopg2 import OperationalError
import logging

# Configure logging
logging.basicConfig(
    filename='app.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

@st.cache_resource
def get_db_connection():
    """
    Establishes and returns a persistent database connection using psycopg2.
    Utilizes Streamlit's secrets management for secure credential handling.
    """
    try:
        conn = psycopg2.connect(
            host=st.secrets["postgres"]["host"],
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            port=st.secrets["postgres"]["port"]
        )
        return conn
    except OperationalError as e:
        logging.error(f"Database connection failed: {e}")
        st.error("Could not connect to the database. Please try again later.")
        return None

def run_query(query, values=None):
    """
    Executes a read-only SQL query (e.g., SELECT) and returns the fetched data.
    """
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values or ())
            data = cursor.fetchall()
            logging.info(f"Executed query: {cursor.query}")
            return data
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error executing query: {e}")
        st.error(f"Error executing query: {e}")
        return []
    finally:
        conn.close()

def run_insert(query, values):
    """
    Executes an INSERT or UPDATE SQL query.
    """
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values)
            conn.commit()
            logging.info(f"Executed insert/update: {cursor.query}")
            return True
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error executing insert/update: {e}")
        st.error(f"Error executing insert/update: {e}")
        return False
    finally:
        conn.close()
