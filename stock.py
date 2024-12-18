# pages/stock.py

import streamlit as st
from database import run_query, run_insert
from helpers import refresh_data, display_dataframe
from datetime import datetime
import pandas as pd

def stock_page():
    st.title("Stock")
    st.subheader("Add a New Stock Record")

    # Load the list of products from tb_products
    product_data = st.session_state.data.get("products", [])
    product_list = [row[2] for row in product_data] if product_data else ["No products available"]

    with st.form(key='stock_form'):
        product = st.selectbox("Product", product_list)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        transaction = st.selectbox("Transaction Type", ["Entrada", "Saída"])
        submit_stock = st.form_submit_button(label="Register")

    if submit_stock:
        if product and quantity > 0:
            current_date = datetime.now()

            query = """
            INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Transação", "Data")
            VALUES (%s, %s, %s, %s);
            """
            success = run_insert(query, (product, quantity, transaction, current_date))
            if success:
                st.success("Stock record added successfully!")
                refresh_data(load_all_data=lambda: st.session_state.data.update(load_all_data()))
            else:
                st.error("Failed to add stock record.")
        else:
            st.warning("Please select a product and enter a quantity greater than 0.")

    # Display all stock records
    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        st.subheader("All Stock Records")
        columns = ["Stock ID", "Product", "Quantity", "Transaction", "Date"]
        df_stock = pd.DataFrame(stock_data, columns=columns)
        display_dataframe(df_stock)
    else:
        st.info("No stock records found.")
