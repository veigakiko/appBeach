import streamlit as st
from psycopg import connect
from datetime import datetime
from contextlib import closing

#####################
# Database Utilities
#####################
@st.cache_resource
def get_db_connection():
    """Return a persistent database connection using psycopg (psycopg3)."""
    # Utilize uma string de conexão completa:
    return connect(
        "postgresql://kiko:ff15dHpkRtuoNgeF8eWjpqymWLleEM00@dpg-ct76kgij1k6c73b3utk0-a.oregon-postgres.render.com:5432/beachtennis"
    )

def run_query(query, values=None):
    """
    Runs a read-only query (SELECT) and returns the fetched data.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            if values:
                cursor.execute(query, values)
            else:
                cursor.execute(query)
            return cursor.fetchall()

def run_insert(query, values):
    """
    Runs an insert or update query.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, values)
        conn.commit()

#####################
# Data Loading & Caching
#####################
@st.cache_data
def load_all_data():
    """
    Load all data used by the application and return it as a dictionary.
    This function is cached to avoid re-querying the database unnecessarily.
    """
    data = {}
    # Load orders data with the newest first
    data["orders"] = run_query(
        'SELECT "Cliente", "Produto", "Quantidade", "Data" FROM public.tb_pedido ORDER BY "Data" DESC;'
    )
    # Load products data
    data["products"] = run_query(
        "SELECT supplier, product, quantity, unit_value, total_value, creation_date FROM public.tb_products;"
    )
    # Load distinct clients for commands page
    data["clients"] = run_query('SELECT DISTINCT "Cliente" FROM public.tb_pedido;')
    # Load stock data
    data["stock"] = run_query(
        'SELECT "Produto", "Quantidade", "Valor", "Total", "Transação", "Data" FROM public.tb_estoque;'
    )
    return data

def refresh_data():
    """
    Force a data refresh by clearing the cache and reloading everything.
    """
    load_all_data.clear()
    st.session_state.data = load_all_data()

#####################
# Sidebar Navigation
#####################
def sidebar_navigation():
    """
    Create a sidebar with navigation buttons. When a button is clicked,
    update the session state and rerun the app to show the selected page.
    """
    st.sidebar.title("Menu")
    if st.sidebar.button("Boituva Beach Club"):
        st.session_state.page = "home"
        st.experimental_rerun()
    if st.sidebar.button("Orders"):
        st.session_state.page = "orders"
        st.experimental_rerun()
    if st.sidebar.button("Products"):
        st.session_state.page = "products"
        st.experimental_rerun()
    if st.sidebar.button("Commands"):
        st.session_state.page = "commands"
        st.experimental_rerun()
    if st.sidebar.button("Stock"):
        st.session_state.page = "stock"
        st.experimental_rerun()

#####################
# Page Functions
#####################
def home_page():
    st.title("Boituva Beach Club")
    st.write("Welcome! Please choose an option:")

    # Refresh data button (optional)
    if st.button("Refresh Data"):
        refresh_data()
        st.success("Data refreshed!")

def orders_page():
    st.title("Orders")
    st.subheader("Register a new order")

    # Get product names from loaded product data
    product_data = st.session_state.data.get("products", [])
    product_list = [row[1] for row in product_data]  # 'product' is the second column in the SELECT
    if not product_list:
        product_list = ["No products available"]

    with st.form(key='order_form'):
        customer_name = st.text_input("Customer Name", max_chars=100)
        product = st.selectbox("Product", product_list)  # Using selectbox instead of text_input
        quantity = st.number_input("Quantity", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Register Order")

    if submit_button:
        if customer_name and product and quantity > 0:
            insert_query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data")
            VALUES (%s, %s, %s, %s);
            """
            timestamp = datetime.now()
            try:
                run_insert(insert_query, (customer_name, product, quantity, timestamp))
                st.success("Order registered successfully!")
                refresh_data()
            except Exception as e:
                st.error(f"An error occurred: {e}")
        else:
            st.warning("Please fill in all fields correctly.")

    # Show all orders (cached and sorted by date desc from the query)
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        columns = ["Client", "Product", "Quantity", "Date"]
        st.subheader("All Orders")
        st.table([dict(zip(columns, row)) for row in orders_data])
    else:
        st.info("No orders found.")

def products_page():
    st.title("Products")

    # Display existing products (cached)
    products_data = st.session_state.data.get("products", [])
    columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
    if products_data:
        st.table([dict(zip(columns, row)) for row in products_data])
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
            insert_query = """
            INSERT INTO public.tb_products (supplier, product, quantity, unit_value, total_value, creation_date)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            total_value = quantity * unit_value
            try:
                run_insert(insert_query, (supplier, product, quantity, unit_value, total_value, creation_date))
                st.success("Product added successfully!")
                refresh_data()
            except Exception as e:
                st.error(f"An error occurred: {e}")
        else:
            st.warning("Please fill in all fields correctly.")

def commands_page():
    st.title("Commands")

    # Fetch distinct clients (cached)
    clients_data = [row[0] for row in st.session_state.data.get("clients", [])]

    if clients_data:
        selected_client = st.selectbox("Select a Client", clients_data)
        if st.button("Open Command"):
            # Filtered from cached orders data
            orders_data = st.session_state.data.get("orders", [])
            client_orders = [o for o in orders_data if o[0] == selected_client]

            columns = ["Client", "Product", "Quantity", "Date"]
            if client_orders:
                st.table([dict(zip(columns, row)) for row in client_orders])
            else:
                st.info("No orders found for this client.")
    else:
        st.info("No clients found.")

def stock_page():
    st.title("Stock")

    # Display stock data (cached)
    stock_data = st.session_state.data.get("stock", [])
    columns = ["Product", "Quantity", "Value", "Total", "Transaction", "Date"]
    if stock_data:
        st.table([dict(zip(columns, row)) for row in stock_data])
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
            insert_query = """
            INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Valor", "Total", "Transação", "Data")
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            total = quantity * value
            try:
                run_insert(insert_query, (product, quantity, value, total, transaction, current_date))
                st.success("Stock record added successfully!")
                refresh_data()
            except Exception as e:
                st.error(f"An error occurred: {e}")
        else:
            st.warning("Please fill in all fields correctly.")

#####################
# Initialization
#####################
if 'page' not in st.session_state:
    st.session_state.page = "home"

# Load all data if not already loaded
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

# Render Sidebar Navigation on every page
sidebar_navigation()

#####################
# Page Routing
#####################
if st.session_state.page == "home":
    home_page()
elif st.session_state.page == "orders":
    orders_page()
elif st.session_state.page == "products":
    products_page()
elif st.session_state.page == "commands":
    commands_page()
elif st.session_state.page == "stock":
    stock_page()
