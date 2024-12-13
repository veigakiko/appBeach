import streamlit as st
import psycopg2
from datetime import datetime
import subprocess
import sys

# Ensure required modules are installed
def install_package(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_package("streamlit")
install_package("psycopg2")

def connect_to_db():
    return psycopg2.connect(
        host="dpg-ct76kgij1k6c73b3utk0-a.oregon-postgres.render.com",
        database="beachtennis",
        user="kiko",
        password="ff15dHpkRtuoNgeF8eWjpqymWLleEM00",
        port=5432
    )

def home_page():
    st.title("Home")
    if st.button("Orders"):
        st.session_state.page = "orders"
    if st.button("Products"):
        st.session_state.page = "products"

def orders_page():
    st.title("Orders")
    st.subheader("Register a new order")

    with st.form(key='order_form'):
        customer_name = st.text_input("Customer Name", max_chars=100)
        product = st.text_input("Product", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Register Order")

    if submit_button:
        if customer_name and product and quantity > 0:
            try:
                connection = connect_to_db()
                cursor = connection.cursor()

                query = """
                INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data")
                VALUES (%s, %s, %s, %s);
                """
                timestamp = datetime.now()
                cursor.execute(query, (customer_name, product, quantity, timestamp))

                connection.commit()

                st.success("Order registered successfully!")
            except Exception as e:
                st.error(f"An error occurred: {e}")
            finally:
                if connection:
                    cursor.close()
                    connection.close()
        else:
            st.warning("Please fill in all fields correctly.")

    if st.button("Back"):
        st.session_state.page = "home"

def products_page():
    st.title("Products")

    try:
        connection = connect_to_db()
        cursor = connection.cursor()

        cursor.execute("""
        SELECT supplier, product, quantity, unit_value, total_value, creation_date
        FROM public.tb_products;
        """)
        data = cursor.fetchall()
        columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
        st.table([dict(zip(columns, row)) for row in data])

    except Exception as e:
        st.error(f"An error occurred: {e}")
    finally:
        if connection:
            cursor.close()
            connection.close()

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
            try:
                connection = connect_to_db()
                cursor = connection.cursor()

                query = """
                INSERT INTO public.tb_products (supplier, product, quantity, unit_value, total_value, creation_date)
                VALUES (%s, %s, %s, %s, %s, %s);
                """
                total_value = quantity * unit_value
                cursor.execute(query, (supplier, product, quantity, unit_value, total_value, creation_date))

                connection.commit()

                st.success("Product added successfully!")
            except Exception as e:
                st.error(f"An error occurred: {e}")
            finally:
                if connection:
                    cursor.close()
                    connection.close()
        else:
            st.warning("Please fill in all fields correctly.")

    if st.button("Back"):
        st.session_state.page = "home"

if 'page' not in st.session_state:
    st.session_state.page = "home"

if st.session_state.page == "home":
    home_page()
elif st.session_state.page == "orders":
    orders_page()
elif st.session_state.page == "products":
    products_page()
