import streamlit as st
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime
from streamlit_option_menu import option_menu

#####################
# Database Utilities
#####################
@st.cache_resource
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
    except OperationalError as e:
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
    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"Error executing query: {e}")
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
    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"Error executing insert: {e}")
        return False

#####################
# Data Loading
#####################
def load_all_data():
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
    st.session_state.data = load_all_data()

#####################
# Menu Navigation
#####################
def sidebar_navigation():
    with st.sidebar:
        st.title("Boituva Beach Club")
        selected = option_menu(
            "Navigation", ["Home", "Orders", "Products", "Commands", "Stock", "Clients"],
            icons=["house", "file-text", "box", "list-task", "layers", "user"],
            menu_icon="cast",
            default_index=0
        )
    return selected

#####################
# Page Functions
#####################
def orders_page():
    st.title("Orders")
    st.subheader("Register a new order")

    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["No products available"]

    with st.form(key='order_form'):
        customer_name = st.selectbox("Customer Name", [""] + [row[0] for row in run_query('SELECT nome_completo FROM public.tb_clientes')], index=0)
        product = st.selectbox("Product", product_list, index=0)
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

def commands_page():
    st.title("Commands")

    clients_data = [""] + [row[0] for row in st.session_state.data.get("clients", [])]

    selected_client = st.selectbox("Select a Client", clients_data, index=0)
    if selected_client:
        query = """
        SELECT "Cliente", "Produto", "Quantidade", "Data", status, unit_value, 
               ("Quantidade" * unit_value) AS total
        FROM vw_pedido_produto
        WHERE "Cliente" = %s;
        """
        client_orders = run_query(query, (selected_client,))

        if client_orders:
            import pandas as pd

            columns = ["Client", "Product", "Quantity", "Date", "Status", "Unit Value", "Total"]
            df = pd.DataFrame(client_orders, columns=columns)
            st.subheader("Client Orders")
            st.dataframe(df, use_container_width=True)

            total_sum = df["Total"].sum()
            st.subheader(f"Total Amount: R$ {total_sum:,.2f}")

            col1, col2, col3 = st.columns(3)
            payment_status = None

            with col1:
                if st.button("Debit"):
                    payment_status = "Received - Debited"
            with col2:
                if st.button("Credit"):
                    payment_status = "Received - Credit"
            with col3:
                if st.button("Pix"):
                    payment_status = "Received - Pix"

            if payment_status:
                update_query = """
                UPDATE public.tb_pedido
                SET status = %s, "Data" = CURRENT_TIMESTAMP
                WHERE "Cliente" = %s AND status = 'em aberto';
                """
                success = run_insert(update_query, (payment_status, selected_client))
                if success:
                    st.success(f"OK - Amount Received via {payment_status.split(' - ')[1]}")
                    refresh_data()
                else:
                    st.error("Failed to update order status.")
        else:
            st.info("No orders found for this client.")
    else:
        st.info("Select a client to view orders.")

#####################
# Initialization
#####################
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

st.session_state.page = sidebar_navigation()

if st.session_state.page == "Orders":
    orders_page()
elif st.session_state.page == "Commands":
    commands_page()
