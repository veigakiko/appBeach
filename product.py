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
    except OperationalError:
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
    return {
        "orders": run_query('SELECT id, "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido ORDER BY "Data" DESC;')
    }

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
    Create a sidebar or horizontal menu for navigation using streamlit_option_menu.
    """
    with st.sidebar:
        st.title("Boituva Beach Club")
        return option_menu(
            "Beach Menu", ["Orders", "Nota Fiscal", "Stock", "Clients", "Products", "Commands"],
            icons=["file-text", "file-invoice", "layers", "person", "box", "list-task"],
            menu_icon="cast",
            default_index=0,
        )

#####################
# Orders Page
#####################
def orders_page():
    st.title("Orders")

    # Load Orders
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["ID", "Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        st.dataframe(df_orders, use_container_width=True)

        # Edit Section
        st.subheader("Edit an Order")
        selected_id = st.selectbox("Select an Order ID to Edit", df_orders["ID"])
        if selected_id:
            order = df_orders[df_orders["ID"] == selected_id].iloc[0]

            with st.form(key="edit_order_form"):
                cliente = st.text_input("Client", value=order["Client"])
                product = st.text_input("Product", value=order["Product"])
                quantity = st.number_input("Quantity", min_value=1, value=order["Quantity"])
                status = st.selectbox("Status", ["em aberto", "concluido"], index=["em aberto", "concluido"].index(order["Status"]))
                submit_edit = st.form_submit_button(label="Update Order")

            if submit_edit:
                update_query = '''UPDATE public.tb_pedido SET "Cliente"=%s, "Produto"=%s, "Quantidade"=%s, status=%s WHERE id=%s;'''
                success = run_insert(update_query, (cliente, product, quantity, status, selected_id))
                if success:
                    st.success("Order updated successfully!")
                    refresh_data()
    else:
        st.info("No orders found.")

#####################
# Nota Fiscal Page
#####################
def invoice_page():
    st.title("Nota Fiscal")
    st.info("Functionality not yet implemented.")

#####################
# Stock Page
#####################
def stock_page():
    st.title("Stock")
    st.info("Functionality not yet implemented.")

#####################
# Clients Page
#####################
def clients_page():
    st.title("Clients")
    st.info("Functionality not yet implemented.")

#####################
# Products Page
#####################
def products_page():
    st.title("Products")
    st.info("Functionality not yet implemented.")

#####################
# Commands Page
#####################
def commands_page():
    st.title("Commands")
    st.info("Functionality not yet implemented.")

#####################
# Initialization
#####################
if "data" not in st.session_state:
    st.session_state.data = load_all_data()

# Menu Navigation
page = sidebar_navigation()

# Page Routing
if page == "Orders":
    orders_page()
elif page == "Nota Fiscal":
    invoice_page()
elif page == "Stock":
    stock_page()
elif page == "Clients":
    clients_page()
elif page == "Products":
    products_page()
elif page == "Commands":
    commands_page()
