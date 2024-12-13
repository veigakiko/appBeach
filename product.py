import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime
import pandas as pd

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

#####################
# Menu Navigation
#####################
def sidebar_navigation():
    """
    Create a sidebar or horizontal menu for navigation using streamlit_option_menu.
    """
    with st.sidebar:
        st.title("Boituva Beach Club")
        selected = option_menu(
            "Navigation", ["Home", "Orders", "Products", "Commands", "Stock", "Clients", "Checkout"],
            icons=["house", "file-text", "box", "list-task", "layers", "user", "cart"],
            menu_icon="cast",
            default_index=0
        )
    return selected

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

    product_data = st.session_state.data.get("products", [])
    product_list = [row[1] for row in product_data] if product_data else ["No products available"]

    with st.form(key='order_form'):
        customer_name = st.selectbox("Customer Name", [row[0] for row in run_query('SELECT nome_completo FROM public.tb_clientes')])
        product = st.selectbox("Product", product_list)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Register Order")

    if submit_button:
        if customer_name and product and quantity > 0:
            query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", "status")
            VALUES (%s, %s, %s, %s, 'em aberto');
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
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        st.dataframe([dict(zip(columns, row)) for row in orders_data], use_container_width=True)
    else:
        st.info("No orders found.")

def checkout_page():
    st.title("Checkout")

    # Retrieve orders with status "open" and "received"
    open_orders_query = """
    SELECT "Cliente", "Produto", "Quantidade", "Data", status
    FROM public.tb_pedido
    WHERE status = 'em aberto';
    """
    received_orders_query = """
    SELECT "Cliente", "Produto", "Quantidade", "Data", status
    FROM public.tb_pedido
    WHERE status LIKE 'Received%';
    """

    # Fetch data for open and received orders
    open_orders = run_query(open_orders_query)
    received_orders = run_query(received_orders_query)

    # Check if the data is not empty and handle missing columns
    if open_orders:
        open_orders_df = pd.DataFrame(open_orders, columns=["Client", "Product", "Quantity", "Date", "Status"])
    else:
        open_orders_df = pd.DataFrame(columns=["Client", "Product", "Quantity", "Date", "Status"])

    if received_orders:
        received_orders_df = pd.DataFrame(received_orders, columns=["Client", "Product", "Quantity", "Date", "Status"])
    else:
        received_orders_df = pd.DataFrame(columns=["Client", "Product", "Quantity", "Date", "Status"])

    # Display the tables side by side
    st.markdown("### Orders Overview")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Open Orders")
        if open_orders_df.empty:
            st.info("No open orders.")
        else:
            st.dataframe(open_orders_df, use_container_width=True)

    with col2:
        st.subheader("Received Orders")
        if received_orders_df.empty:
            st.info("No received orders.")
        else:
            st.dataframe(received_orders_df, use_container_width=True)

#####################
# Initialization
#####################
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

st.session_state.page = sidebar_navigation()

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
elif st.session_state.page == "Checkout":
    checkout_page()
