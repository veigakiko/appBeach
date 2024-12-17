import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime
import pandas as pd

#####################
# Authentication Configuration
#####################
USERNAME = "admin"
PASSWORD = "admin"

#####################
# Database Utilities
#####################
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
    Executes SELECT queries and returns fetched results.
    """
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, values or ())
                return cursor.fetchall()
        except Exception as e:
            st.error(f"Query error: {e}")
            return []

def run_insert(query, values):
    """
    Executes INSERT/UPDATE queries.
    """
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, values)
            conn.commit()
            return True
        except Exception as e:
            st.error(f"Insert error: {e}")
            return False

#####################
# Data Loading
#####################
def load_all_data():
    """
    Loads all data used by the app into a dictionary.
    """
    data = {}
    try:
        data["orders"] = run_query('SELECT "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido;')
        data["products"] = run_query("SELECT supplier, product, quantity, unit_value, total_value, creation_date FROM public.tb_products;")
        data["clients"] = run_query('SELECT nome_completo FROM public.tb_clientes;')
        data["stock"] = run_query('SELECT "Produto", "Quantidade", "Valor", "Total", "Transação", "Data" FROM public.tb_estoque;')
    except Exception as e:
        st.error(f"Error loading data: {e}")
    return data

#####################
# Login Page
#####################
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

#####################
# Navigation Menu
#####################
def sidebar_navigation():
    with st.sidebar:
        st.title("Boituva Beach Club")
        selected = option_menu(
            "Menu", ["Home", "Orders", "Products", "Commands", "Stock", "Clients", "Nota Fiscal"],
            icons=["house", "file-text", "box", "list-task", "layers", "person", "file-invoice"],
            default_index=0
        )
    return selected

#####################
# Page Functions
#####################
def home_page():
    st.title("Home Page")
    st.write("🎾 Welcome to Boituva Beach Club 🎾")

def orders_page():
    st.title("Orders Management")
    st.subheader("Register a New Order")
    clients = [row[0] for row in run_query('SELECT nome_completo FROM public.tb_clientes')]
    products = [row[1] for row in run_query("SELECT product FROM public.tb_products")]
    with st.form("order_form"):
        client = st.selectbox("Select Client", clients)
        product = st.selectbox("Select Product", products)
        quantity = st.number_input("Quantity", min_value=1)
        submitted = st.form_submit_button("Submit")
        if submitted:
            if client and product and quantity > 0:
                query = """
                INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", "status")
                VALUES (%s, %s, %s, %s, %s);
                """
                success = run_insert(query, (client, product, quantity, datetime.now(), "em aberto"))
                if success:
                    st.success("Order registered successfully!")

    st.subheader("Orders List")
    orders = run_query('SELECT "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido;')
    if orders:
        st.dataframe(pd.DataFrame(orders, columns=["Client", "Product", "Quantity", "Date", "Status"]))

def products_page():
    st.title("Products Management")
    st.subheader("Add a New Product")
    with st.form("product_form"):
        supplier = st.text_input("Supplier")
        product = st.text_input("Product Name")
        quantity = st.number_input("Quantity", min_value=1)
        unit_value = st.number_input("Unit Value", min_value=0.0)
        submitted = st.form_submit_button("Add Product")
        if submitted:
            total_value = quantity * unit_value
            query = """
            INSERT INTO public.tb_products (supplier, product, quantity, unit_value, total_value, creation_date)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            success = run_insert(query, (supplier, product, quantity, unit_value, total_value, datetime.now()))
            if success:
                st.success("Product added successfully!")

    st.subheader("Products List")
    products = run_query("SELECT supplier, product, quantity, unit_value, total_value FROM public.tb_products;")
    if products:
        st.dataframe(pd.DataFrame(products, columns=["Supplier", "Product", "Quantity", "Unit Value", "Total Value"]))

def commands_page():
    st.title("Client Commands")
    clients = [row[0] for row in run_query('SELECT nome_completo FROM public.tb_clientes;')]
    selected_client = st.selectbox("Select Client", clients)
    if selected_client:
        query = """
        SELECT "Produto", "Quantidade", "Data", status
        FROM public.tb_pedido
        WHERE "Cliente" = %s;
        """
        results = run_query(query, (selected_client,))
        if results:
            st.dataframe(pd.DataFrame(results, columns=["Product", "Quantity", "Date", "Status"]))
        else:
            st.info("No orders found for this client.")

def stock_page():
    st.title("Stock Management")
    st.subheader("Stock Records")
    stock = run_query('SELECT "Produto", "Quantidade", "Valor", "Total", "Data" FROM public.tb_estoque;')
    if stock:
        st.dataframe(pd.DataFrame(stock, columns=["Product", "Quantity", "Value", "Total", "Date"]))

def clients_page():
    st.title("Clients Management")
    st.subheader("Register a New Client")
    with st.form("client_form"):
        name = st.text_input("Full Name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        submitted = st.form_submit_button("Register Client")
        if submitted:
            query = """
            INSERT INTO public.tb_clientes (nome_completo, telefone, email, data_cadastro)
            VALUES (%s, %s, %s, %s);
            """
            success = run_insert(query, (name, phone, email, datetime.now()))
            if success:
                st.success("Client registered successfully!")

    st.subheader("Clients List")
    clients = run_query("SELECT nome_completo, telefone, email FROM public.tb_clientes;")
    if clients:
        st.dataframe(pd.DataFrame(clients, columns=["Name", "Phone", "Email"]))

def invoice_page():
    st.title("Generate Nota Fiscal")
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

#####################
# Application Logic
#####################
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    selected = sidebar_navigation()
    if selected == "Home":
        home_page()
    elif selected == "Orders":
        orders_page()
    elif selected == "Products":
        products_page()
    elif selected == "Commands":
        commands_page()
    elif selected == "Stock":
        stock_page()
    elif selected == "Clients":
        clients_page()
    elif selected == "Nota Fiscal":
        invoice_page()
