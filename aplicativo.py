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
        conn.rollback()
        st.error(f"Error executing query: {e}")
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
    except Exception as e:
        st.error(f"Error loading data: {e}")
    return data

def refresh_data():
    st.session_state.data = load_all_data()

#####################
# Orders Page
#####################
def orders_page():
    st.title("Orders")
    
    # Display existing orders
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        st.dataframe(df_orders, use_container_width=True)

        st.subheader("Edit or Delete an Existing Order")
        df_orders["unique_key"] = df_orders.apply(
            lambda row: f"{row['Client']}|{row['Product']}|{row['Date']}", axis=1
        )
        unique_keys = df_orders["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select an order to edit/delete:", [""] + unique_keys)

        if selected_key:
            matching_rows = df_orders[df_orders["unique_key"] == selected_key]
            if len(matching_rows) > 1:
                st.warning("Multiple orders found with the same key. Please refine your selection.")
            else:
                selected_row = matching_rows.iloc[0]
                original_client = selected_row["Client"]
                original_product = selected_row["Product"]
                original_quantity = selected_row["Quantity"]
                original_date = selected_row["Date"]

                with st.form(key='edit_order_form'):
                    edit_quantity = st.number_input(
                        "Quantity",
                        min_value=1,
                        step=1,
                        value=int(original_quantity)
                    )
                    edit_status = st.selectbox(
                        "Status",
                        ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix"],
                        index=["em aberto", "Received - Debited", "Received - Credit", "Received - Pix"].index(selected_row["Status"])
                    )

                    col1, col2 = st.columns(2)
                    with col1:
                        update_button = st.form_submit_button(label="Update Order")
                    with col2:
                        delete_button = st.form_submit_button(label="Delete Order")

                if update_button:
                    update_query = """
                    UPDATE public.tb_pedido
                    SET "Quantidade" = %s, status = %s
                    WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                    """
                    success = run_insert(update_query, (
                        edit_quantity, edit_status,
                        original_client, original_product, original_date
                    ))
                    if success:
                        st.success("Order updated successfully!")
                        refresh_data()
                    else:
                        st.error("Failed to update the order.")

                if delete_button:
                    delete_query = """
                    DELETE FROM public.tb_pedido
                    WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                    """
                    success = run_insert(delete_query, (
                        original_client, original_product, original_date
                    ))
                    if success:
                        st.success("Order deleted successfully!")
                        refresh_data()
                    else:
                        st.error("Failed to delete the order.")
    else:
        st.info("No orders found.")

#####################
# Initialization
#####################
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

def main():
    orders_page()

if __name__ == "__main__":
    main()
