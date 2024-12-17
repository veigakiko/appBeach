import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime
import pandas as pd

# ===========================
# Authentication Variables
# ===========================
USERNAME = "admin"
PASSWORD = "admin"

# ===========================
# Database Utilities
# ===========================
@st.cache_resource
def get_db_connection():
    """
    Return a persistent database connection using psycopg2.
    """
    try:
        conn = psycopg2.connect(
            host="dpg-ct76kgij1k6c73b3utk0-a.oregon-postgres.render.com",
            database="beachtennis",
            user="kiko",
            password="ff15dHpkRtuoNgeF8eWjpqymWLleEM00",
            port=5432
        )
        return conn
    except OperationalError as e:
        st.error("Could not connect to the database.")
        return None

def run_query(query, values=None):
    """
    Run a query and return fetched results.
    """
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cursor:
            cursor.execute(query, values or ())
            return cursor.fetchall()

def run_insert(query, values):
    """
    Execute an insert or update query.
    """
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, values)
            conn.commit()
            return True
        except Exception as e:
            st.error(f"Error executing insert: {e}")
            return False

# ===========================
# Login Page
# ===========================
def login_page():
    st.title("Boituva Beach Club - Login")
    st.subheader("Please enter your credentials to access the system.")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_button = st.button("Login")
    
    if login_button:
        if username == USERNAME and password == PASSWORD:
            st.session_state.logged_in = True
            st.success("Login Successful!")
            st.experimental_rerun()
        else:
            st.error("Invalid Username or Password")

# ===========================
# Navigation Menu
# ===========================
def sidebar_navigation():
    with st.sidebar:
        st.title("Boituva Beach Club")
        selected = option_menu(
            "Beach Menu", ["Home", "Orders", "Products", "Commands", "Stock", "Clients", "Nota Fiscal"],
            icons=["house", "file-text", "box", "list-task", "layers", "person", "file-invoice"],
            default_index=0
        )
    return selected

# ===========================
# Page Functions
# ===========================
def home_page():
    st.title("Boituva Beach Club")
    st.write("🎾 Beach Tennis 📍 Avenida Do Trabalhador, 1879 🏆 5° Open BBC")
    st.button("Refresh Data", on_click=lambda: st.session_state.update(data=load_all_data()))

def orders_page():
    st.title("Orders")
    st.write("Manage Orders Here")

def products_page():
    st.title("Products")
    st.write("Manage Products Here")

def commands_page():
    st.title("Commands")
    st.write("View Client Commands Here")

def stock_page():
    st.title("Stock")
    st.write("Manage Stock Here")

def clients_page():
    st.title("Clients")
    st.write("Register and View Clients Here")

def invoice_page():
    st.title("Nota Fiscal")
    st.write("Generate Client Invoices")

# ===========================
# Data Loading
# ===========================
def load_all_data():
    """
    Load all data used by the application and return it as a dictionary.
    """
    data = {}
    try:
        data["orders"] = run_query(
            'SELECT "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido ORDER BY "Data" DESC;'
        )
        data["products"] = run_query(
            "SELECT supplier, product, quantity, unit_value, total_value, creation_date FROM public.tb_products;"
        )
        data["clients"] = run_query('SELECT DISTINCT "Cliente" FROM public.tb_pedido;')
        data["stock"] = run_query(
            'SELECT "Produto", "Quantidade", "Valor", "Total", "Transação", "Data" FROM public.tb_estoque;'
        )
    except Exception as e:
        st.error(f"Error loading data: {e}")
    return data

def refresh_data():
    """
    Reload all data and update the session state.
    """
    st.session_state.data = load_all_data()

# ===========================
# Application Initialization
# ===========================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "data" not in st.session_state:
    st.session_state.data = load_all_data()

# ===========================
# Main Streamlit App
# ===========================
if not st.session_state.logged_in:
    login_page()
else:
    selected_page = sidebar_navigation()

    # Page Routing
    if selected_page == "Home":
        home_page()
    elif selected_page == "Orders":
        orders_page()
    elif selected_page == "Products":
        products_page()
    elif selected_page == "Commands":
        commands_page()
    elif selected_page == "Stock":
        stock_page()
    elif selected_page == "Clients":
        clients_page()
    elif selected_page == "Nota Fiscal":
        invoice_page()
