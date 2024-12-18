import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime
import pandas as pd

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="dpg-ct76kgij1k6c73b3utk0-a.oregon-postgres.render.com",
            database="beachtennis",
            user="kiko",
            password="ff15dHpkRtuoNgeF8eWjpqymWLleEM00",
            port=5432
        )
        return conn
    except OperationalError:
        st.error("Could not connect to the database. Please try again later.")
        return None

def run_query(query, values=None):
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values or ())
            return cursor.fetchall()
    except Exception:
        if conn:
            conn.rollback()
        st.error("Error executing query.")
        return []

def run_insert(query, values):
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values)
        conn.commit()
        return True
    except Exception:
        if conn:
            conn.rollback()
        st.error("Error executing query.")
        return False

def load_all_data():
    data = {}
    try:
        data["orders"] = run_query(
            'SELECT "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido ORDER BY "Data" DESC;'
        )
        data["products"] = run_query(
            'SELECT supplier, product, quantity, unit_value, total_value, creation_date FROM public.tb_products ORDER BY creation_date DESC;'
        )
        data["clients"] = run_query('SELECT DISTINCT "Cliente" FROM public.tb_pedido ORDER BY "Cliente";')
        data["stock"] = run_query(
            'SELECT "Produto", "Quantidade", "Transação", "Data" FROM public.tb_estoque ORDER BY "Data" DESC;'
        )
    except Exception:
        st.error("Error loading data.")
    return data

def refresh_data():
    st.session_state.data = load_all_data()

def sidebar_navigation():
    with st.sidebar:
        st.title("Boituva Beach Club")
        selected = option_menu(
            "Beach Menu", ["Home", "Orders", "Products", "Stock", "Clients", "Nota Fiscal"],
            icons=["house", "file-text", "box", "list-task", "layers", "person", "file-invoice"],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"background-color": "#1b4f72"},
                "icon": {"color": "white", "font-size": "18px"},
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "0px",
                    "color": "white",
                    "--hover-color": "#145a7c",
                },
                "nav-link-selected": {"background-color": "#145a7c", "color": "white"},
            },
        )
    return selected

def home_page():
    st.title("Boituva Beach Club")
    st.write("🎾 BeachTennis 📍 Av. Do Trabalhador, 1879 🏆 5° Open BBC")
    st.info("Os dados são atualizados automaticamente ao navegar entre as páginas.")

def orders_page():
    st.title("Orders")

def products_page():
    st.title("Products")

def stock_page():
    st.title("Stock")

def clients_page():
    st.title("Clients")

def invoice_page():
    st.title("Nota Fiscal")

def login_page():
    st.title("Beach Club")
    st.write("Por favor, insira suas credenciais para acessar o aplicativo.")
    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button(label="Login")
    if submit_login:
        if username == "" and password == "":
            st.session_state.logged_in = True
            st.success("Login bem-sucedido!")
        else:
            st.error("Nome de usuário ou senha incorretos.")
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if not st.session_state.logged_in:
    login_page()
else:
    selected_page = sidebar_navigation()
    if 'current_page' not in st.session_state:
        st.session_state.current_page = selected_page
    elif selected_page != st.session_state.current_page:
        refresh_data()
        st.session_state.current_page = selected_page
    if selected_page == "Home":
        home_page()
    elif selected_page == "Orders":
        orders_page()
    elif selected_page == "Products":
        products_page()
    elif selected_page == "Stock":
        stock_page()
    elif selected_page == "Clients":
        clients_page()
    elif selected_page == "Nota Fiscal":
        invoice_page()
    with st.sidebar:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.success("Desconectado com sucesso!")
            st.experimental_rerun()
