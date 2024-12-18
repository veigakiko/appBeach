# pages/products.py

import streamlit as st
from database import run_query, run_insert
from helpers import refresh_data, display_dataframe
from datetime import datetime
import pandas as pd

def products_page():
    st.title("Products")
    st.subheader("Add a New Product")

    with st.form(key='product_form'):
        supplier = st.text_input("Supplier", max_chars=100)
        product = st.text_input("Product", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        unit_value = st.number_input("Unit Value", min_value=0.0, step=0.01, format="%.2f")
        creation_date = st.date_input("Creation Date", value=datetime.now().date())
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
                refresh_data(load_all_data=lambda: st.session_state.data.update(load_all_data()))
        else:
            st.warning("Please fill in all fields correctly.")

    # Display all products
    products_data = st.session_state.data.get("products", [])
    if products_data:
        st.subheader("All Products")
        columns = ["Product ID", "Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
        df_products = pd.DataFrame(products_data, columns=columns)
        display_dataframe(df_products)

        # Editing an existing product
        st.subheader("Edit an Existing Product")
        selected_product_id = st.selectbox("Select a product to edit:", [""] + df_products["Product ID"].astype(str).tolist())

        if selected_product_id:
            selected_product = df_products[df_products["Product ID"].astype(str) == selected_product_id].iloc[0]

            with st.form(key='edit_product_form'):
                edit_supplier = st.text_input("Supplier", value=selected_product["Supplier"], max_chars=100)
                edit_product = st.text_input("Product", value=selected_product["Product"], max_chars=100)
                edit_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(selected_product["Quantity"]))
                edit_unit_value = st.number_input("Unit Value", min_value=0.0, step=0.01, format="%.2f", value=float(selected_product["Unit Value"]))
                edit_creation_date = st.date_input("Creation Date", value=selected_product["Creation Date"])
                update_button = st.form_submit_button(label="Update Product")

            if update_button:
                edit_total_value = edit_quantity * edit_unit_value
                update_query = """
                UPDATE public.tb_products
                SET supplier = %s,
                    product = %s,
                    quantity = %s,
                    unit_value = %s,
                    total_value = %s,
                    creation_date = %s
                WHERE product_id = %s;
                """
                success = run_insert(update_query, (
                    edit_supplier,
                    edit_product,
                    edit_quantity,
                    edit_unit_value,
                    edit_total_value,
                    edit_creation_date,
                    selected_product_id
                ))
                if success:
                    st.success("Product updated successfully!")
                    refresh_data(load_all_data=lambda: st.session_state.data.update(load_all_data()))
                else:
                    st.error("Failed to update the product.")
    else:
        st.info("No products found.")
