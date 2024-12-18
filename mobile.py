import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime
import pandas as pd

# ----------------------------------------
# Authentication Configuration
# ----------------------------------------
USERNAME = "admin"
PASSWORD = "admin"

# ----------------------------------------
# Database Utilities
# ----------------------------------------
@st.cache_resource
def get_db_connection():
    """
    Establish a persistent database connection.
    """
    try:
        return psycopg2.connect(
            host="dpg-ct76kgij1k6c73b3utk0-a.oregon-postgres.render.com",
            database="beachtennis",
            user="kiko",
            password="ff15dHpkRtuoNgeF8eWjpqymWLleEM00",
            port=5432
        )
    except OperationalError as e:
        st.error("Failed to connect to the database.")
        st.stop()

def run_query(query, values=None, fetch=True):
    """
    Run SELECT or INSERT/UPDATE queries safely.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(query, values or ())
                if fetch:
                    return cursor.fetchall()
                conn.commit()
                return True
            except Exception as e:
                st.error(f"Database error: {e}")
                return [] if fetch else False

# ----------------------------------------
# Authentication Page
# ----------------------------------------
def login_page():
    st.title("Boituva Beach Club - Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == USERNAME and password == PASSWORD:
            st.session_state.logged_in = True
            st.experimental_rerun()
        else:
            st.error("Invalid credentials.")

# ----------------------------------------
# Sidebar Navigation
# ----------------------------------------
def sidebar_navigation():
    with st.sidebar:
        st.title("Boituva Beach Club")
        return option_menu(
            "Menu", ["Home", "Orders", "Products", "Commands", "Stock", "Clients", "Nota Fiscal"],
            icons=["house", "file-text", "box", "list-task", "layers", "person", "file-invoice"],
            default_index=0
        )

# ----------------------------------------
# Helper Function for Data Display
# ----------------------------------------
def display_data(title, query, columns):
    st.subheader(title)
    data = run_query(query)
    if data:
        st.dataframe(pd.DataFrame(data, columns=columns))
    else:
        st.info("No data found.")

# ----------------------------------------
# Page Functions
# ----------------------------------------
def home_page():
    st.title("🏠 Home Page")
    st.write("🎾 Welcome to Boituva Beach Club 🎾")

def orders_page():
    st.title("📦 Orders Management")
    clients = [row[0] for row in run_query('SELECT nome_completo FROM public.tb_clientes')]
    products = [row[1] for row in run_query("SELECT product FROM public.tb_products")]

    with st.form("order_form"):
        client = st.selectbox("Select Client", clients)
        product = st.selectbox("Select Product", products)
        quantity = st.number_input("Quantity", min_value=1)
        if st.form_submit_button("Submit Order"):
            if run_query("""
                INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", "status")
                VALUES (%s, %s, %s, %s, %s);
            """, (client, product, quantity, datetime.now(), "em aberto"), fetch=False):
                st.success("Order registered successfully!")

    display_data("Orders List", 
                 'SELECT "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido;', 
                 ["Client", "Product", "Quantity", "Date", "Status"])

def products_page():
    st.title("🛒 Products Management")
    with st.form("product_form"):
        supplier = st.text_input("Supplier")
        product = st.text_input("Product Name")
        quantity = st.number_input("Quantity", min_value=1)
        unit_value = st.number_input("Unit Value", min_value=0.0)
        if st.form_submit_button("Add Product"):
            total_value = quantity * unit_value
            if run_query("""
                INSERT INTO public.tb_products (supplier, product, quantity, unit_value, total_value, creation_date)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (supplier, product, quantity, unit_value, total_value, datetime.now()), fetch=False):
                st.success("Product added successfully!")

    display_data("Products List", 
                 "SELECT supplier, product, quantity, unit_value, total_value FROM public.tb_products;", 
                 ["Supplier", "Product", "Quantity", "Unit Value", "Total Value"])

def clients_page():
    st.title("👤 Clients Management")
    with st.form("client_form"):
        name = st.text_input("Full Name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        if st.form_submit_button("Register Client"):
            if run_query("""
                INSERT INTO public.tb_clientes (nome_completo, telefone, email, data_cadastro)
                VALUES (%s, %s, %s, %s);
            """, (name, phone, email, datetime.now()), fetch=False):
                st.success("Client registered successfully!")

    display_data("Clients List", 
                 "SELECT nome_completo, telefone, email FROM public.tb_clientes;", 
                 ["Name", "Phone", "Email"])

def stock_page():
    st.title("📊 Stock Management")
    display_data("Stock Records", 
                 'SELECT "Produto", "Quantidade", "Valor", "Total", "Data" FROM public.tb_estoque;', 
                 ["Product", "Quantity", "Value", "Total", "Date"])

def invoice_page():
    st.title("🧾 Generate Nota Fiscal")
    clients = [row[0] for row in run_query('SELECT DISTINCT "Cliente" FROM public.tb_pedido;')]
    selected_client = st.selectbox("Select Client", clients)
    if selected_client:
        query = """
        SELECT "Produto", "Quantidade"
        FROM public.tb_pedido
        WHERE "Cliente" = %s AND status = 'em aberto';
        """
        data = run_query(query, (selected_client,))
        if data:
            st.dataframe(pd.DataFrame(data, columns=["Product", "Quantity"]))
            st.success("Invoice generated successfully!")

# ----------------------------------------
# Application Logic
# ----------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    pages = {
        "Home": home_page,
        "Orders": orders_page,
        "Products": products_page,
        "Clients": clients_page,
        "Stock": stock_page,
        "Nota Fiscal": invoice_page
    }
    selected_page = sidebar_navigation()
    pages.get(selected_page, lambda: st.error("Page not found!"))()
