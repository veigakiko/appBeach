# pages/orders.py

import streamlit as st
from database import run_query, run_insert
from helpers import refresh_data, generate_unique_key, display_dataframe
from datetime import datetime
import pandas as pd

def orders_page():
    st.title("Orders")
    st.subheader("Register a New Order")

    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[2] for row in product_data] if product_data else ["No products available"]

    # Form to insert a new order
    with st.form(key='order_form'):
        # Loading list of clients for the new order
        clients = st.session_state.data.get("clients", [])
        customer_list = [""] + [row[1] for row in clients] if clients else ["No clients available"]

        customer_name = st.selectbox("Customer Name", customer_list, index=0)
        product = st.selectbox("Product", product_list, index=0)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Register Order")

    if submit_button:
        if customer_name and product and quantity > 0:
            query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", status)
            VALUES (%s, %s, %s, %s, 'em aberto');
            """
            timestamp = datetime.now()
            success = run_insert(query, (customer_name, product, quantity, timestamp))
            if success:
                st.success("Order registered successfully!")
                refresh_data(load_all_data=lambda: st.session_state.data.update(load_all_data()))
        else:
            st.warning("Please fill in all fields correctly.")

    # Display all orders
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["Order ID", "Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        display_dataframe(df_orders)

        # Editing an existing order
        st.subheader("Edit an Existing Order")
        selected_order_id = st.selectbox("Select an order to edit:", [""] + df_orders["Order ID"].astype(str).tolist())

        if selected_order_id:
            selected_order = df_orders[df_orders["Order ID"].astype(str) == selected_order_id].iloc[0]

            with st.form(key='edit_order_form'):
                edit_product = st.selectbox("Product", product_list, index=product_list.index(selected_order["Product"]) if selected_order["Product"] in product_list else 0)
                edit_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(selected_order["Quantity"]))
                edit_status_list = ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix"]
                edit_status = st.selectbox("Status", edit_status_list, index=edit_status_list.index(selected_order["Status"]) if selected_order["Status"] in edit_status_list else 0)

                update_button = st.form_submit_button(label="Update Order")

            if update_button:
                update_query = """
                UPDATE public.tb_pedido
                SET "Produto" = %s, "Quantidade" = %s, status = %s
                WHERE order_id = %s;
                """
                success = run_insert(update_query, (edit_product, edit_quantity, edit_status, selected_order_id))
                if success:
                    st.success("Order updated successfully!")
                    refresh_data(load_all_data=lambda: st.session_state.data.update(load_all_data()))
                else:
                    st.error("Failed to update the order.")
    else:
        st.info("No orders found.")
