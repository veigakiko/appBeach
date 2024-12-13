import streamlit as st
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime

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
        st.error("Could not connect to the database. Please try again later.")
        return None

def run_query(query, values=None):
    """
    Runs a read-only query (SELECT) and returns the fetched data.
    """
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values or ())
            return cursor.fetchall()
    except Exception as e:
        st.error(f"Error executing query: {e}")
        return []

def run_insert(query, values):
    """
    Runs an insert or update query.
    """
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error executing insert: {e}")
        return False

# Função para fechar a conexão ao finalizar o app
def close_db_connection():
    """
    Close the database connection if it exists.
    """
    conn = get_db_connection()
    if conn:
        conn.close()

# Configuração para fechar a conexão ao sair
st.on_event("shutdown", close_db_connection)

#####################
# Data Loading
#####################
def load_all_data():
    """
    Load all data used by the application and return it as a dictionary.
    """
    data = {}
    try:
        data["orders"] = run_query(
            'SELECT "Cliente", "Produto", "Quantidade", "Data" FROM public.tb_pedido ORDER BY "Data" DESC;'
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

#####################
# Sidebar Navigation
#####################
def sidebar_navigation():
    """
    Create a sidebar for navigation.
    """
    st.sidebar.title("Menu")
    st.sidebar.radio("Navigate to:", ["Home", "Orders", "Products", "Commands", "Stock"], key="page")

#####################
# Page Functions
#####################
def home_page():
    st.title("Boituva Beach Club")
    st.write("Welcome! Use the sidebar to navigate.")

    st.button("Refresh Data", on_click=refresh_data)

def orders_page():
    st.title("Orders")
    st.subheader("Register a new order")

    product_data = st.session_state.data.get("products", [])
    product_list = [row[1] for row in product_data] if product_data else ["No products available"]

    with st.form(key='order_form'):
        customer_name = st.text_input("Customer Name", max_chars=100)
        product = st.selectbox("Product", product_list)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Register Order")

    if submit_button:
        if customer_name and product and quantity > 0:
            query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data")
            VALUES (%s, %s, %s, %s);
            """
            timestamp = datetime.now()
            success = run_insert(query, (customer_name, product, quantity, timestamp))
            if success:
                st.success("Order registered successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all fields correctly.")

    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["Client", "Product", "Quantity", "Date"]
        st.dataframe([dict(zip(columns, row)) for row in orders_data])
    else:
        st.info("No orders found.")

def products_page():
    st.title("Products")

    products_data = st.session_state.data.get("products", [])
    columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
    if products_data:
        st.dataframe([dict(zip(columns, row)) for row in products_data])
    else:
        st.info("No products found.")

    st.subheader("Add a new product")
    with st.form(key='product_form'):
        supplier = st.text_input("Supplier", max_chars=100)
        product = st.text_input("Product", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        unit_value = st.number_input("Unit Value", min_value=0.0, step=0.01, format="%.2f")
        creation_date = st.date_input("Creation Date")
        submit_product = st.form_submit_button(label="Insert Product")

    if submit_product:
        if supplier and product and quantity > 0 and unit_value >= 0:
            query = """
            INSERT INTO public.tb_products (supplier, product, quantity, unit_value, total_value, creation_date)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            total_value = quantity * unit_value
            success = run_insert(query, (supplier, product, quantity, unit_value, total_value, creation_date))
            if success:
                st.success("Product added successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all fields correctly.")

def commands_page():
    st.title("Commands")

    clients_data = [row[0] for row in st.session_state.data.get("clients", [])]

    if clients_data:
        selected_client = st.selectbox("Select a Client", clients_data)
        if st.button("Open Command"):
            orders_data = st.session_state.data.get("orders", [])
            client_orders = [o for o in orders_data if o[0] == selected_client]

            columns = ["Client", "Product", "Quantity", "Date"]
            if client_orders:
                st.dataframe([dict(zip(columns, row)) for row in client_orders])
            else:
                st.info("No orders found for this client.")
    else:
        st.info("No clients found.")

def stock_page():
    st.title("Stock")

    stock_data = st.session_state.data.get("stock", [])
    columns = ["Product", "Quantity", "Value", "Total", "Transaction", "Date"]
    if stock_data:
        st.dataframe([dict(zip(columns, row)) for row in stock_data])
    else:
        st.info("No stock records found.")

    st.subheader("Add a new stock record")
    with st.form(key='stock_form'):
        product = st.text_input("Product", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        value = st.number_input("Value", min_value=0.0, step=0.01, format="%.2f")
        transaction = "Entry"
        current_date = datetime.now().date()
        submit_stock = st.form_submit_button(label="Register")

    if submit_stock:
        if product and quantity > 0 and value >= 0:
            query = """
            INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Valor", "Total", "Transação", "Data")
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            total = quantity * value
            success = run_insert(query, (product, quantity, value, total, transaction, current_date))
            if success:
                st.success("Stock record added successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all fields correctly.")

#####################
# Initialization
#####################
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

# Sidebar Navigation
sidebar_navigation()

# Page Routing
if st.session_state.page == "Home":
    home_page()
elif st.session_state.page == "Orders":
    orders_page()
elif st.session_state.page == "Products":
    products_page()
elif st.session_state.page == "Commands":
    commands_page()
elif st.session_state.page == "Stock":
    stock_page()
