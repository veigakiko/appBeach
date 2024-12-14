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
        if conn:
            conn.rollback()
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
        if conn:
            conn.rollback()
        st.error(f"Error executing insert: {e}")
        return False

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
    st.sidebar.radio("Navigate to:", ["Home", "Orders", "Products", "Commands", "Stock", "Clients"], key="page")

#####################
# Page Functions
#####################
def home_page():
    st.title("Boituva Beach Club")
    st.write("🎾 BeachTennis📍Av. Do Trabalhador, 1879🏆 5° Open BBC")
    
    st.button("Refresh Data", on_click=refresh_data)


def orders_page():
    st.title("Orders")
    st.subheader("Register a new order")

    # Load product data
    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else [""]

    # Order form with empty default values
    with st.form(key='order_form'):
        customer_name = st.text_input("Customer Name", value="", max_chars=100)
        product = st.selectbox("Product", product_list, index=0)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Register Order")

    # Handle form submission
    if submit_button:
        if customer_name.strip() and product.strip() and quantity > 0:
            query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data")
            VALUES (%s, %s, %s, %s);
            """
            timestamp = datetime.now()
            success = run_insert(query, (customer_name.strip(), product.strip(), quantity, timestamp))
            if success:
                st.success("Order registered successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all fields correctly.")

    # Display all orders
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["Client", "Product", "Quantity", "Date"]
        st.dataframe([dict(zip(columns, row)) for row in orders_data])
    else:
        st.info("No orders found.")

def commands_page():
    st.title("Commands")

    # Load client data
    clients_data = [""] + [row[0] for row in st.session_state.data.get("clients", [])]

    # Command form with empty default value
    selected_client = st.selectbox("Select a Client", clients_data, index=0)
    if st.button("Open Command") and selected_client.strip():
        orders_data = st.session_state.data.get("orders", [])
        client_orders = [o for o in orders_data if o[0] == selected_client]

        # Display client orders below buttons
        columns = ["Client", "Product", "Quantity", "Date"]
        if client_orders:
            st.write("---")
            st.subheader("Client Orders")
            st.dataframe([dict(zip(columns, row)) for row in client_orders])
        else:
            st.info("No orders found for this client.")
    elif not selected_client.strip():
        st.warning("Please select a client.")

def stock_page():
    st.title("Stock")

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

    stock_data = st.session_state.data.get("stock", [])
    columns = ["Product", "Quantity", "Value", "Total", "Transaction", "Date"]
    if stock_data:
        st.subheader("All Stock Records")
        st.dataframe([dict(zip(columns, row)) for row in stock_data])
    else:
        st.info("No stock records found.")

def clients_page():
    st.title("Clients")

    st.subheader("Register a New Client")
    with st.form(key='client_form'):
        nome_completo = st.text_input("Full Name", max_chars=100)
        data_nascimento = st.date_input("Date of Birth")
        genero = st.text_input("Sex/Gender (optional)", max_chars=50)
        telefone = st.text_input("Phone", max_chars=15)
        email = st.text_input("Email", max_chars=100)
        endereco = st.text_area("Address")
        submit_client = st.form_submit_button(label="Register New Client")

    if submit_client:
        if nome_completo and data_nascimento and telefone and email and endereco:
            query = """
            INSERT INTO public.tb_clientes (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            success = run_insert(query, (nome_completo, data_nascimento, genero, telefone, email, endereco))
            if success:
                st.success("Client registered successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all required fields.")

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
elif st.session_state.page == "Clients":
    clients_page()
