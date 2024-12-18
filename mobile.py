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
        st.error("Could not connect to the database.")
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
# Login Functionality
#####################
def login_page():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == "admin" and password == "admin":
            st.session_state.authenticated = True
            st.experimental_rerun()
        else:
            st.error("Invalid username or password.")

#####################
# Main Pages
#####################
def home_page():
    st.title("Boituva Beach Club")
    st.write("🎾 Beach Tennis\n📍 Av. Do Trabalhador, 1879\n🏆 5° Open BBC")
    st.button("Refresh Data", on_click=refresh_data)

def orders_page():
    st.title("Orders")
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        df_orders = pd.DataFrame(orders_data, columns=["Client", "Product", "Quantity", "Date", "Status"])
        st.dataframe(df_orders, use_container_width=True)

        selected_order = st.selectbox("Select an order to edit or delete:", [""] + df_orders.index.astype(str).tolist())

        if selected_order:
            selected_index = int(selected_order)
            selected_row = df_orders.iloc[selected_index]
            with st.form("edit_order_form"):
                new_quantity = st.number_input("Quantity", value=selected_row["Quantity"], step=1)
                new_status = st.selectbox("Status", ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix", "Received - Cash"], index=0)
                update_button = st.form_submit_button("Update Order")

                if update_button:
                    query = """
                    UPDATE public.tb_pedido
                    SET "Quantidade" = %s, status = %s
                    WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                    """
                    run_insert(query, (new_quantity, new_status, selected_row["Client"], selected_row["Product"], selected_row["Date"]))
                    st.success("Order updated.")

            if st.button("Delete Order"):
                query = """
                DELETE FROM public.tb_pedido WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                """
                run_insert(query, (selected_row["Client"], selected_row["Product"], selected_row["Date"]))
                st.success("Order deleted.")


def products_page():
    st.title("Products")
    products_data = st.session_state.data.get("products", [])
    if products_data:
        df_products = pd.DataFrame(products_data, columns=["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"])
        st.dataframe(df_products, use_container_width=True)

        selected_product = st.selectbox("Select a product to edit or delete:", [""] + df_products.index.astype(str).tolist())

        if selected_product:
            selected_index = int(selected_product)
            selected_row = df_products.iloc[selected_index]
            with st.form("edit_product_form"):
                new_quantity = st.number_input("Quantity", value=selected_row["Quantity"], step=1)
                new_unit_value = st.number_input("Unit Value", value=selected_row["Unit Value"], step=0.01)
                update_button = st.form_submit_button("Update Product")

                if update_button:
                    query = """
                    UPDATE public.tb_products
                    SET "quantity" = %s, "unit_value" = %s
                    WHERE "product" = %s;
                    """
                    run_insert(query, (new_quantity, new_unit_value, selected_row["Product"]))
                    st.success("Product updated.")

            if st.button("Delete Product"):
                query = """
                DELETE FROM public.tb_products WHERE "product" = %s;
                """
                run_insert(query, (selected_row["Product"],))
                st.success("Product deleted.")


def invoice_page():
    st.title("Invoice")
    clients = [row[0] for row in run_query('SELECT DISTINCT "Cliente" FROM public.tb_pedido WHERE status = %s;', ('em aberto',))]
    selected_client = st.selectbox("Select a client:", [""] + clients)

    if selected_client:
        query = 'SELECT "Produto", "Quantidade", "total" FROM public.vw_pedido_produto WHERE "Cliente" = %s AND status = %s;'
        invoice_data = run_query(query, (selected_client, "em aberto"))

        if invoice_data:
            df_invoice = pd.DataFrame(invoice_data, columns=["Product", "Quantity", "Total"])
            st.dataframe(df_invoice, use_container_width=True)

            total = df_invoice["Total"].sum()
            st.subheader(f"Total: R$ {total:.2f}")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("Debit"):
                    process_payment(selected_client, "Received - Debited")
            with col2:
                if st.button("Credit"):
                    process_payment(selected_client, "Received - Credit")
            with col3:
                if st.button("Pix"):
                    process_payment(selected_client, "Received - Pix")
            with col4:
                if st.button("Cash"):
                    process_payment(selected_client, "Received - Cash")


def process_payment(client, payment_status):
    query = """
    UPDATE public.tb_pedido
    SET status = %s
    WHERE "Cliente" = %s AND status = 'em aberto';
    """
    if run_insert(query, (payment_status, client)):
        st.success(f"Payment processed: {payment_status}")

#####################
# Main Logic
#####################
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    login_page()
else:
    st.sidebar.title("Menu")
    page = option_menu("Menu", ["Home", "Orders", "Products", "Invoice"], icons=["house", "file-text", "box", "file-invoice"])

    if page == "Home":
        home_page()
    elif page == "Orders":
        orders_page()
    elif page == "Products":
        products_page()
    elif page == "Invoice":
        invoice_page()
