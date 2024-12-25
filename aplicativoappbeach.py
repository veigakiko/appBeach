import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime, date
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
import altair as alt
from pathlib import Path

#####################
# Database Utilities
#####################
@st.cache_resource
def get_db_connection():
    """
    Retorna uma conexão persistente com o banco de dados usando psycopg2.
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
        st.error("Não foi possível conectar ao banco de dados. Por favor, tente novamente mais tarde.")
        return None


def run_query(query, values=None):
    """
    Executes a SELECT query and returns the data.
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
        st.error(f"Error executing the query: {e}")
        return []


def run_insert(query, values, table_name="", action_description=""):
    """
    Executes an INSERT/UPDATE/DELETE query and commits the changes.
    Also logs the action in tb_audit_logs.
    """
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values)
        conn.commit()
        # Log the audit
        log_action(
            username=st.session_state.get("username", "unknown_user"),
            action_type=_get_sql_verb(query),
            table_name=table_name,
            description=action_description
        )
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"Error executing the query: {e}")
        return False


def log_action(username, action_type, table_name, description):
    """
    Insert a log record into tb_audit_logs.
    """
    audit_query = """
        INSERT INTO public.tb_audit_logs
        (username, action_type, table_name, description)
        VALUES (%s, %s, %s, %s);
    """
    conn = get_db_connection()
    if conn is not None:
        try:
            with conn.cursor() as cursor:
                cursor.execute(audit_query, (username, action_type, table_name, description))
            conn.commit()
        except Exception as e:
            conn.rollback()
            st.error(f"Failed to log audit action: {e}")


def _get_sql_verb(query):
    """
    Tries to determine whether the query is INSERT, UPDATE, or DELETE for auditing.
    """
    first_word = query.strip().split()[0].upper()
    if first_word in ["INSERT", "UPDATE", "DELETE"]:
        return first_word
    return "OTHER"

#####################
# Data Loading
#####################
def load_all_data():
    """
    Loads all data used by the app into a dictionary and returns it.
    """
    data = {}
    try:
        data["orders"] = run_query(
            'SELECT "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido ORDER BY "Data" DESC;'
        )
        data["products"] = run_query(
            'SELECT supplier, product, quantity, unit_value, total_value, creation_date FROM public.tb_products ORDER BY creation_date DESC;'
        )
        data["clients"] = run_query(
            'SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;'
        )
        data["stock"] = run_query(
            'SELECT "Produto", "Quantidade", "Transação", "Data" FROM public.tb_estoque ORDER BY "Data" DESC;'
        )
    except Exception as e:
        st.error(f"Error loading data: {e}")
    return data


def refresh_data():
    """
    Reloads data and updates session state.
    """
    st.session_state.data = load_all_data()

#####################
# Menu Navigation
#####################
def sidebar_navigation():
    """
    Creates the main sidebar navigation menu.
    """
    with st.sidebar:
        st.title("Boituva Beach Club 🎾")
        selected = option_menu(
            "Main Menu",
            ["Home", "Orders", "Products", "Stock", "Clients", "Invoice", "Reports"],
            icons=["house", "file-text", "box", "list-task", "layers", "receipt", "bar-chart"],
            menu_icon="cast",
            default_index=0
        )
    return selected

#####################
# Home Page
#####################
def home_page():
    st.title("🎾 Boituva Beach Club 🎾")
    st.write("📍 Av. Do Trabalhador, 1879 — Welcome to 5° Open BBC")

    # Display basic summary if admin
    if st.session_state.get("username") == "admin":
        st.markdown("### Open Orders Summary")
        open_orders_query = """
        SELECT "Cliente", SUM("total") as Total
        FROM public.vw_pedido_produto
        WHERE status = 'em aberto'
        GROUP BY "Cliente"
        ORDER BY "Cliente";
        """
        open_orders_data = run_query(open_orders_query)
        if open_orders_data:
            df_open = pd.DataFrame(open_orders_data, columns=["Client", "Total"])
            df_open["Total_display"] = df_open["Total"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            st.table(df_open[["Client", "Total_display"]])
            total_open = df_open["Total"].sum()
            st.markdown(f"**Total (Open Orders):** R$ {total_open:,.2f}")
        else:
            st.info("No open orders found.")

        st.markdown("### Closed Orders Summary")
        closed_orders_query = """
        SELECT DATE("Data") as Date, SUM("total") as Total
        FROM public.vw_pedido_produto
        WHERE status != 'em aberto'
        GROUP BY DATE("Data")
        ORDER BY DATE("Data") DESC;
        """
        closed_orders_data = run_query(closed_orders_query)
        if closed_orders_data:
            df_closed = pd.DataFrame(closed_orders_data, columns=["Date", "Total"])
            st.table(df_closed)
            st.markdown(f"**Total (Closed Orders):** R$ {df_closed['Total'].sum():,.2f}")
        else:
            st.info("No closed orders found.")
    else:
        st.info("Welcome to Boituva Beach Club!")

#####################
# Orders Page (with basic Search/Filters)
#####################
def orders_page():
    st.title("Orders")

    st.subheader("Search Orders / Filter")
    clients_data = st.session_state.data.get("clients", [])
    client_names = ["All"] + [r[0] for r in clients_data]
    selected_client = st.selectbox("Filter by Client", client_names, index=0)

    start_date = st.date_input("Start Date", value=date(2023, 1, 1))
    end_date = st.date_input("End Date", value=date.today())

    if st.button("Apply Filters"):
        # Build dynamic query
        query_filters = []
        values = []

        base_query = """
        SELECT "Cliente", "Produto", "Quantidade", "Data", status
        FROM public.tb_pedido
        WHERE 1=1
        """

        if selected_client != "All":
            query_filters.append('"Cliente" = %s')
            values.append(selected_client)

        if start_date and end_date:
            query_filters.append('"Data" BETWEEN %s AND %s')
            values.append(datetime.combine(start_date, datetime.min.time()))
            values.append(datetime.combine(end_date, datetime.max.time()))

        if query_filters:
            base_query += " AND " + " AND ".join(query_filters)

        base_query += ' ORDER BY "Data" DESC'

        filtered_data = run_query(base_query, tuple(values))
        if filtered_data:
            df_orders_filtered = pd.DataFrame(
                filtered_data,
                columns=["Client", "Product", "Quantity", "Date", "Status"]
            )
            st.dataframe(df_orders_filtered, use_container_width=True)
        else:
            st.info("No orders found for the selected filters.")

    st.subheader("Register a New Order")
    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["No products available"]

    with st.form(key='order_form'):
        clientes = st.session_state.data.get("clients", [])
        customer_list = [""] + [row[0] for row in clientes]
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
            success = run_insert(
                query,
                (customer_name, product, quantity, timestamp),
                table_name="tb_pedido",
                action_description=f"New order for {customer_name}, product={product}"
            )
            if success:
                st.success("Order registered successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all fields correctly.")

    # Show all orders
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        st.dataframe(df_orders, use_container_width=True)

        # Admin edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Edit or Delete an Existing Order")
            df_orders["unique_key"] = df_orders.apply(
                lambda row: f"{row['Client']}|{row['Product']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
                axis=1
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
                    original_status = selected_row["Status"]

                    with st.form(key='edit_order_form'):
                        edit_product = st.selectbox(
                            "Product",
                            product_list,
                            index=product_list.index(original_product) if original_product in product_list else 0
                        )
                        edit_quantity = st.number_input(
                            "Quantity", min_value=1, step=1, value=int(original_quantity)
                        )
                        edit_status_list = [
                            "em aberto",
                            "Received - Debited",
                            "Received - Credit",
                            "Received - Pix",
                            "Received - Cash"
                        ]
                        edit_status_index = (
                            edit_status_list.index(original_status)
                            if original_status in edit_status_list
                            else 0
                        )
                        edit_status = st.selectbox("Status", edit_status_list, index=edit_status_index)

                        col_edit, col_delete = st.columns(2)
                        with col_edit:
                            update_button = st.form_submit_button(label="Update Order")
                        with col_delete:
                            delete_button = st.form_submit_button(label="Delete Order")

                    if delete_button:
                        delete_query = """
                        DELETE FROM public.tb_pedido
                        WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                        """
                        success = run_insert(
                            delete_query,
                            (original_client, original_product, original_date),
                            table_name="tb_pedido",
                            action_description=f"Deleting order for {original_client}"
                        )
                        if success:
                            st.success("Order deleted successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to delete the order.")

                    if update_button:
                        update_query = """
                        UPDATE public.tb_pedido
                        SET "Produto" = %s, "Quantidade" = %s, status = %s
                        WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                        """
                        success = run_insert(
                            update_query,
                            (
                                edit_product,
                                edit_quantity,
                                edit_status,
                                original_client,
                                original_product,
                                original_date
                            ),
                            table_name="tb_pedido",
                            action_description=f"Updating order for {original_client}"
                        )
                        if success:
                            st.success("Order updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the order.")
    else:
        st.info("No orders found.")

#####################
# Products Page
#####################
def products_page():
    st.title("Products")

    st.subheader("Add a New Product")
    with st.form(key='product_form'):
        supplier = st.text_input("Supplier", max_chars=100)
        product = st.text_input("Product", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        unit_value = st.number_input("Unit Value", min_value=0.0, step=0.01, format="%.2f")
        creation_date = st.date_input("Creation Date", value=date.today())
        submit_product = st.form_submit_button(label="Insert Product")

    if submit_product:
        if supplier and product and quantity > 0 and unit_value >= 0:
            total_value = quantity * unit_value
            query = """
            INSERT INTO public.tb_products 
            (supplier, product, quantity, unit_value, total_value, creation_date)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            success = run_insert(
                query,
                (supplier, product, quantity, unit_value, total_value, creation_date),
                table_name="tb_products",
                action_description=f"New product: {product}"
            )
            if success:
                st.success("Product added successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all fields correctly.")

    products_data = st.session_state.data.get("products", [])
    if products_data:
        st.subheader("All Products")
        columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
        df_products = pd.DataFrame(products_data, columns=columns)
        st.dataframe(df_products, use_container_width=True)

        # Admin edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Edit or Delete an Existing Product")
            df_products["unique_key"] = df_products.apply(
                lambda row: f"{row['Supplier']}|{row['Product']}|{row['Creation Date'].strftime('%Y-%m-%d')}",
                axis=1
            )
            unique_keys = df_products["unique_key"].unique().tolist()
            selected_key = st.selectbox("Select a product to edit/delete:", [""] + unique_keys)

            if selected_key:
                matching_rows = df_products[df_products["unique_key"] == selected_key]
                if len(matching_rows) > 1:
                    st.warning("Multiple products found with the same key. Please refine your selection.")
                else:
                    selected_row = matching_rows.iloc[0]
                    original_supplier = selected_row["Supplier"]
                    original_product = selected_row["Product"]
                    original_quantity = selected_row["Quantity"]
                    original_unit_value = selected_row["Unit Value"]
                    original_creation_date = selected_row["Creation Date"]

                    with st.form(key='edit_product_form'):
                        edit_supplier = st.text_input("Supplier", value=original_supplier, max_chars=100)
                        edit_product = st.text_input("Product", value=original_product, max_chars=100)
                        edit_quantity = st.number_input(
                            "Quantity", min_value=1, step=1, value=int(original_quantity)
                        )
                        edit_unit_value = st.number_input(
                            "Unit Value",
                            min_value=0.0,
                            step=0.01,
                            format="%.2f",
                            value=float(original_unit_value)
                        )
                        edit_creation_date = st.date_input("Creation Date", value=original_creation_date)

                        col_update, col_delete = st.columns(2)
                        with col_update:
                            update_button = st.form_submit_button(label="Update Product")
                        with col_delete:
                            delete_button = st.form_submit_button(label="Delete Product")

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
                        WHERE supplier = %s AND product = %s AND creation_date = %s;
                        """
                        success = run_insert(
                            update_query,
                            (
                                edit_supplier,
                                edit_product,
                                edit_quantity,
                                edit_unit_value,
                                edit_total_value,
                                edit_creation_date,
                                original_supplier,
                                original_product,
                                original_creation_date
                            ),
                            table_name="tb_products",
                            action_description=f"Updating product: {original_product}"
                        )
                        if success:
                            st.success("Product updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the product.")

                    if delete_button:
                        confirm = st.checkbox("Are you sure you want to delete this product?")
                        if confirm:
                            delete_query = """
                            DELETE FROM public.tb_products
                            WHERE supplier = %s AND product = %s AND creation_date = %s;
                            """
                            success = run_insert(
                                delete_query,
                                (original_supplier, original_product, original_creation_date),
                                table_name="tb_products",
                                action_description=f"Deleting product: {original_product}"
                            )
                            if success:
                                st.success("Product deleted successfully!")
                                refresh_data()
                            else:
                                st.error("Failed to delete the product.")
    else:
        st.info("No products found.")

#####################
# Stock Page
#####################
def stock_page():
    st.title("Stock")

    st.subheader("Register a New Stock Entry")
    st.write(
        """
        This page is designed to log **only product arrivals (Entrada)** into stock.  
        If you need to track removals or returns, you can add the 'Saída' transaction as well.
        """
    )

    product_data = run_query("SELECT product FROM public.tb_products ORDER BY product;")
    product_list = [row[0] for row in product_data] if product_data else ["No products available"]

    with st.form(key='stock_form'):
        product = st.selectbox("Product", product_list)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        transaction = st.selectbox("Transaction Type", ["Entrada", "Saída"])
        picked_date = st.date_input("Date", value=datetime.now().date())
        submit_stock = st.form_submit_button(label="Register")

    if submit_stock:
        if product and quantity > 0:
            current_datetime = datetime.combine(picked_date, datetime.min.time())
            query = """
            INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Transação", "Data")
            VALUES (%s, %s, %s, %s);
            """
            success = run_insert(
                query,
                (product, quantity, transaction, current_datetime),
                table_name="tb_estoque",
                action_description=f"Stock {transaction} for product {product}"
            )
            if success:
                st.success("Stock record added successfully!")
                refresh_data()
        else:
            st.warning("Please select a product and enter a quantity greater than 0.")

    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        st.subheader("All Stock Records")
        columns = ["Product", "Quantity", "Transaction", "Date"]
        df_stock = pd.DataFrame(stock_data, columns=columns)
        st.dataframe(df_stock, use_container_width=True)

        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Edit or Delete an Existing Stock Record")
            df_stock["unique_key"] = df_stock.apply(
                lambda row: f"{row['Product']}|{row['Transaction']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
                axis=1
            )
            unique_keys = df_stock["unique_key"].unique().tolist()
            selected_key = st.selectbox("Select a stock record to edit/delete:", [""] + unique_keys)

            if selected_key:
                matching_rows = df_stock[df_stock["unique_key"] == selected_key]
                if len(matching_rows) > 1:
                    st.warning("Multiple stock records found with the same key. Please refine your selection.")
                else:
                    selected_row = matching_rows.iloc[0]
                    original_product = selected_row["Product"]
                    original_quantity = selected_row["Quantity"]
                    original_transaction = selected_row["Transaction"]
                    original_date = selected_row["Date"]

                    with st.form(key='edit_stock_form'):
                        edit_product = st.selectbox(
                            "Product",
                            product_list,
                            index=product_list.index(original_product) if original_product in product_list else 0
                        )
                        edit_quantity = st.number_input(
                            "Quantity", min_value=1, step=1, value=int(original_quantity)
                        )
                        edit_transaction = st.selectbox(
                            "Transaction Type",
                            ["Entrada", "Saída"],
                            index=["Entrada", "Saída"].index(original_transaction)
                            if original_transaction in ["Entrada", "Saída"] else 0
                        )
                        edit_date = st.date_input("Date", value=original_date.date())

                        col_update, col_delete = st.columns(2)
                        with col_update:
                            update_button = st.form_submit_button(label="Update Stock Record")
                        with col_delete:
                            delete_button = st.form_submit_button(label="Delete Stock Record")

                    if update_button:
                        edit_datetime = datetime.combine(edit_date, datetime.min.time())
                        update_query = """
                        UPDATE public.tb_estoque
                        SET "Produto" = %s, "Quantidade" = %s, "Transação" = %s, "Data" = %s
                        WHERE "Produto" = %s AND "Transação" = %s AND "Data" = %s;
                        """
                        success = run_insert(
                            update_query,
                            (
                                edit_product,
                                edit_quantity,
                                edit_transaction,
                                edit_datetime,
                                original_product,
                                original_transaction,
                                original_date
                            ),
                            table_name="tb_estoque",
                            action_description=f"Updating stock record for product {original_product}"
                        )
                        if success:
                            st.success("Stock record updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the stock record.")

                    if delete_button:
                        confirm = st.checkbox("Are you sure you want to delete this stock record?")
                        if confirm:
                            delete_query = """
                            DELETE FROM public.tb_estoque
                            WHERE "Produto" = %s AND "Transação" = %s AND "Data" = %s;
                            """
                            success = run_insert(
                                delete_query,
                                (original_product, original_transaction, original_date),
                                table_name="tb_estoque",
                                action_description=f"Deleting stock record for product {original_product}"
                            )
                            if success:
                                st.success("Stock record deleted successfully!")
                                refresh_data()
                            else:
                                st.error("Failed to delete the stock record.")
    else:
        st.info("No stock records found.")

#####################
# Clients Page
#####################
def clients_page():
    st.title("Clients")
    st.subheader("Register a New Client")

    with st.form(key='client_form'):
        full_name = st.text_input("Full Name", max_chars=100)
        submit_client = st.form_submit_button(label="Register New Client")

    if submit_client:
        if full_name:
            # Para simplicidade, inserimos valores padrão/placeholder para outros campos
            data_nascimento = datetime(2000, 1, 1).date()
            genero = "Man"
            telefone = "0000-0000"
            unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
            email = f"{full_name.replace(' ', '_').lower()}_{unique_id}@example.com"
            endereco = "Default Address"

            query = """
            INSERT INTO public.tb_clientes 
            (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            success = run_insert(
                query,
                (full_name, data_nascimento, genero, telefone, email, endereco),
                table_name="tb_clientes",
                action_description=f"New client: {full_name}"
            )
            if success:
                st.success("Client registered successfully!")
                refresh_data()
        else:
            st.warning("Please enter the Full Name.")

    # Exibe todos os clientes
    clients_data = run_query(
        """
        SELECT nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro
        FROM public.tb_clientes
        ORDER BY data_cadastro DESC;
        """
    )
    if clients_data:
        st.subheader("All Clients")
        columns = ["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"]
        df_clients = pd.DataFrame(clients_data, columns=columns)
        st.dataframe(df_clients, use_container_width=True)

        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Edit or Delete an Existing Client")
            client_emails = df_clients["Email"].unique().tolist()
            selected_email = st.selectbox("Select a client by Email:", [""] + client_emails)

            if selected_email:
                selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
                original_name = selected_client_row["Full Name"]

                with st.form(key='edit_client_form'):
                    edit_name = st.text_input("Full Name", value=original_name, max_chars=100)
                    col1, col2 = st.columns(2)
                    with col1:
                        update_button = st.form_submit_button(label="Update Client")
                    with col2:
                        delete_button = st.form_submit_button(label="Delete Client")

                if update_button:
                    if edit_name:
                        update_query = """
                        UPDATE public.tb_clientes
                        SET nome_completo = %s
                        WHERE email = %s;
                        """
                        success = run_insert(
                            update_query,
                            (edit_name, selected_email),
                            table_name="tb_clientes",
                            action_description=f"Updating client: {selected_email}"
                        )
                        if success:
                            st.success("Client updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the client.")
                    else:
                        st.warning("Please fill in the Full Name field.")

                if delete_button:
                    confirm = st.checkbox("Are you sure you want to delete this client?")
                    if confirm:
                        delete_query = "DELETE FROM public.tb_clientes WHERE email = %s;"
                        success = run_insert(
                            delete_query,
                            (selected_email,),
                            table_name="tb_clientes",
                            action_description=f"Deleting client: {selected_email}"
                        )
                        if success:
                            st.success("Client deleted successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to delete the client.")
    else:
        st.info("No clients found.")

#####################
# Invoice Page
#####################
def invoice_page():
    st.title("Invoice")

    open_clients_query = """
        SELECT DISTINCT "Cliente"
        FROM public.vw_pedido_produto
        WHERE status = 'em aberto';
    """
    open_clients = run_query(open_clients_query)
    client_list = [row[0] for row in open_clients] if open_clients else []

    selected_client = st.selectbox("Select a Client", [""] + client_list)

    if selected_client:
        invoice_query = """
            SELECT "Produto", "Quantidade", "total"
            FROM public.vw_pedido_produto
            WHERE "Cliente" = %s AND status = 'em aberto';
        """
        invoice_data = run_query(invoice_query, (selected_client,))
        if invoice_data:
            df = pd.DataFrame(invoice_data, columns=["Product", "Quantity", "total"])
            generate_invoice_for_printer(df)

            # Payment buttons
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
        else:
            st.info("No open orders for the selected client.")
    else:
        st.warning("Please select a client.")


def process_payment(client, payment_status):
    query = """
    UPDATE public.tb_pedido
    SET status = %s, "Data" = CURRENT_TIMESTAMP
    WHERE "Cliente" = %s AND status = 'em aberto';
    """
    success = run_insert(
        query,
        (payment_status, client),
        table_name="tb_pedido",
        action_description=f"Updating payment status for {client} to {payment_status}"
    )
    if success:
        st.success(f"Status updated to: {payment_status}")
        refresh_data()
    else:
        st.error("Failed to update status.")


def generate_invoice_for_printer(df):
    company = "Boituva Beach Club"
    address = "Avenida do Trabalhador 1879"
    city = "Boituva - SP 18552-100"
    cnpj = "05.365.434/0001-09"
    phone = "(13) 99154-5481"

    invoice_note = [
        "==================================================",
        "                      INVOICE                     ",
        "==================================================",
        f"Company:  {company}",
        f"Address:  {address}",
        f"City:     {city}",
        f"CNPJ:     {cnpj}",
        f"Phone:    {phone}",
        "--------------------------------------------------",
        "DESCRIPTION           QTY       TOTAL",
        "--------------------------------------------------",
    ]

    grouped_df = df.groupby('Product').agg({'Quantity': 'sum', 'total': 'sum'}).reset_index()
    total_general = 0

    for _, row in grouped_df.iterrows():
        description = f"{row['Product'][:20]:<20}"  # limit to 20 chars
        quantity = f"{int(row['Quantity']):>5}"
        total = row['total']
        total_general += total
        total_formatted = f"R$ {total:,.2f}".replace('.', ',')
        invoice_note.append(f"{description} {quantity}  {total_formatted}")

    invoice_note.append("--------------------------------------------------")
    invoice_note.append(f"{'TOTAL:':>30} R$ {total_general:,.2f}")
    invoice_note.append("==================================================")
    invoice_note.append("Thank You for Your Preference!")
    invoice_note.append("==================================================")

    st.text("\n".join(invoice_note))

#####################
# Reports Page (Charts / Visualization)
#####################
def reports_page():
    st.title("Reports & Visualization")

    # Example: Display total sold by product (from existing view vw_total_sold)
    total_sold_query = """
        SELECT "Produto", total_sold
        FROM public.vw_total_sold
        ORDER BY total_sold DESC;
    """
    total_sold_data = run_query(total_sold_query)
    if total_sold_data:
        df_sold = pd.DataFrame(total_sold_data, columns=["Product", "Total_Sold"])
        st.subheader("Total Sold by Product")
        st.dataframe(df_sold)

        # Create a simple bar chart using Altair
        chart = alt.Chart(df_sold).mark_bar().encode(
            x=alt.X("Product", sort=None),
            y="Total_Sold"
        ).properties(width=600, height=400)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No sold data found in vw_total_sold.")

    # Example: Payment type distribution
    payment_type_query = """
        SELECT payment_type, total_sold
        FROM public.vw_total_por_tipo_pagamento;
    """
    payment_type_data = run_query(payment_type_query)
    if payment_type_data:
        df_payment = pd.DataFrame(payment_type_data, columns=["Payment_Type", "Total_Sold"])
        st.subheader("Total Sold by Payment Type")
        st.dataframe(df_payment)

        pie_chart = alt.Chart(df_payment).mark_arc(innerRadius=50).encode(
            theta="Total_Sold",
            color="Payment_Type",
            tooltip=["Payment_Type", "Total_Sold"]
        )
        st.altair_chart(pie_chart, use_container_width=True)
    else:
        st.info("No data found in vw_total_por_tipo_pagamento.")

# URL para o vídeo de fundo
video_url = (
    "https://github.com/veigakiko/appBeach/raw/refs/heads/main/"
    "20241224_0437_Vibrant%20Beach%20Tennis_remix_01jfvsjewve73t9bq6sb9hcc2q.mp4"
)

def login_page():
    """
    Renders the login page with a video background and updated title.
    """
    # Set custom CSS for the video background
    st.markdown(
        f"""
        <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            overflow: hidden;
        }}
        .background {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }}
        .block-container {{
            background: rgba(255, 255, 255, 0.8);
            padding: 40px;
            border-radius: 10px;
            max-width: 400px;
            margin: 100px auto;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        </style>
        <div class="background">
            <video autoplay muted loop>
                <source src="{video_url}" type="video/mp4">
                Your browser does not support HTML5 video.
            </video>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Login form
    st.title("Beach Club")
    st.write("Please enter your credentials to access the application.")

    with st.form(key="login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button(label="Login")

    if submit_login:
        if username == "admin" and password == "adminbeach":
            st.session_state.logged_in = True
            st.session_state.username = "admin"
            st.success("Login successful!")
        elif username == "caixa" and password == "caixabeach":
            st.session_state.logged_in = True
            st.session_state.username = "caixa"
            st.success("Login successful!")
        else:
            st.error("Incorrect username or password.")

#####################
# APP MAIN SECTION
#####################
# 1) Inicialização das variáveis de sessão
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "data" not in st.session_state:
    st.session_state.data = load_all_data()

# 2) Fluxo de login
if not st.session_state.logged_in:
    login_page()
    st.stop()  # impede que o resto do script seja executado sem login

# Se chegou aqui, significa que o usuário está logado
selected_page = sidebar_navigation()

if 'current_page' not in st.session_state:
    st.session_state.current_page = selected_page
elif selected_page != st.session_state.current_page:
    refresh_data()
    st.session_state.current_page = selected_page

# 3) Roteamento de páginas
if selected_page == "Home":
    home_page()
elif selected_page == "Orders":
    orders_page()
elif selected_page == "Products":
    products_page()
elif selected_page == "Stock":
    stock_page()
elif selected_page == "Clients":
    clients_page()
elif selected_page == "Invoice":
    invoice_page()
elif selected_page == "Reports":
    reports_page()

# 4) Botão de Logout
with st.sidebar:
    if st.button("Logout"):
        # Se quiser remover quaisquer variáveis de sessão, faça aqui
        keys_to_reset = ['home_page_initialized']
        for key in keys_to_reset:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.logged_in = False
        st.success("Logged out successfully!")
        st.experimental_rerun()
