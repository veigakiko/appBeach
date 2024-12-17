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
        st.error(f"Error executing insert/update: {e}")
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
        # Include id in the orders query so we can edit specific orders
        data["orders"] = run_query(
            'SELECT id, "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido ORDER BY "Data" DESC;'
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
            "Beach Menu", 
            ["Home", "Orders", "Invoice", "Stock", "Clients", "Commands"],
            icons=["house", "file-text", "file-invoice", "layers", "person", "list-task"],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"background-color": "#1b4f72"},
                "icon": {"color": "white", "font-size": "18px"},
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "0px",
                    "color": "white",
                    "--hover-color": "#145a7c",
                },
                "nav-link-selected": {"background-color": "#145a7c", "color": "white"},
            },
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
    product_list = [""] + [row[1] for row in product_data] if product_data else ["No products available"]

    # New order form
    with st.form(key='order_form'):
        customer_names = run_query('SELECT nome_completo FROM public.tb_clientes')
        customer_list = [""] + [row[0] for row in customer_names] if customer_names else [""]
        customer_name = st.selectbox("Customer Name", customer_list, index=0)
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

    # Display existing orders with edit functionality
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["ID", "Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)

        # Show the table of orders
        st.dataframe(df_orders, use_container_width=True)

        # Add edit buttons for each order
        # We'll store the selected order ID in session state when Edit is clicked
        for idx, row in df_orders.iterrows():
            col_edit, _ = st.columns([0.2, 0.8])
            if col_edit.button("Edit", key=f"edit_{row['ID']}"):
                st.session_state.edit_order_id = row["ID"]
                st.session_state.edit_cliente = row["Client"]
                st.session_state.edit_produto = row["Product"]
                st.session_state.edit_quantidade = row["Quantity"]

        # If an order is selected for editing, show edit form
        if "edit_order_id" in st.session_state and st.session_state.edit_order_id is not None:
            st.subheader("Edit Selected Order")
            with st.form(key='edit_order_form'):
                new_client = st.text_input("Client", value=st.session_state.edit_cliente)
                new_product = st.text_input("Product", value=st.session_state.edit_produto)
                new_quantity = st.number_input("Quantity", min_value=1, step=1, value=st.session_state.edit_quantidade)
                update_button = st.form_submit_button("Update Order")

            if update_button:
                update_query = """
                UPDATE public.tb_pedido
                SET "Cliente" = %s, "Produto" = %s, "Quantidade" = %s
                WHERE id = %s;
                """
                success = run_insert(update_query, (new_client, new_product, new_quantity, st.session_state.edit_order_id))
                if success:
                    st.success("Order updated successfully!")
                    # Clear editing state
                    st.session_state.edit_order_id = None
                    refresh_data()
    else:
        st.info("No orders found.")

def commands_page():
    st.title("Commands")

    clients_data = [""] + [row[0] for row in st.session_state.data.get("clients", [])]

    if clients_data:
        selected_client = st.selectbox("Select a Client", clients_data)

        if selected_client:
            query = """
            SELECT "Cliente", "Produto", "Quantidade", "Data", status, unit_value, 
                   ("Quantidade" * unit_value) AS total
            FROM vw_pedido_produto
            WHERE "Cliente" = %s;
            """
            client_orders = run_query(query, (selected_client,))

            if client_orders:
                columns = ["Client", "Product", "Quantity", "Date", "Status", "Unit Value", "Total"]
                df = pd.DataFrame(client_orders, columns=columns)
                st.divider()
                st.dataframe(df, use_container_width=True)

                total_sum = df["Total"].sum()
                st.subheader(f"Total Amount: R$ {total_sum:,.2f}")

                col1, col2, col3 = st.columns([1, 1, 1])
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
            st.info("Please select a client.")
    else:
        st.info("No clients found.")

def stock_page():
    st.title("Stock")

    st.subheader("Add a new stock record")
    with st.form(key='stock_form'):
        product = st.text_input("Product", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        value = st.number_input("Value", min_value=0.0, step=0.01, format="%.2f")
        transaction = "Entry"
        current_date = datetime.now().date()
        submit_stock = st.form_submit_button(label="Register")

    if submit_stock:
        if product and quantity > 0 and value >= 0:
            query = """
            INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Valor", "Total", "Transação", "Data")
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            total = quantity * value
            success = run_insert(query, (product, quantity, value, total, transaction, current_date))
            if success:
                st.success("Stock record added successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all fields correctly.")

    stock_data = st.session_state.data.get("stock", [])
    columns = ["Product", "Quantity", "Value", "Total", "Transaction", "Date"]
    if stock_data:
        st.subheader("All Stock Records")
        st.dataframe([dict(zip(columns, row)) for row in stock_data])
    else:
        st.info("No stock records found.")

def clients_page():
    st.title("Clients")

    st.subheader("Register a New Client")
    with st.form(key='client_form'):
        nome_completo = st.text_input("Full Name", max_chars=100)
        data_nascimento = st.date_input("Date of Birth")
        genero = st.selectbox("Sex/Gender (optional)", ["Man", "Woman"], index=0)
        telefone = st.text_input("Phone", max_chars=15)
        email = st.text_input("Email", max_chars=100)
        endereco = st.text_area("Address")
        submit_client = st.form_submit_button(label="Register New Client")

    if submit_client:
        if nome_completo and data_nascimento and telefone and email and endereco:
            query = """
            INSERT INTO public.tb_clientes (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            success = run_insert(query, (nome_completo, data_nascimento, genero, telefone, email, endereco))
            if success:
                st.success("Client registered successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all required fields.")

def invoice_page():
    st.title("Invoice")

    open_clients_query = 'SELECT DISTINCT "Cliente" FROM public.vw_pedido_produto WHERE status = %s;'
    open_clients = run_query(open_clients_query, ('em aberto',))

    client_list = [row[0] for row in open_clients] if open_clients else []

    selected_client = st.selectbox("Select a Client", [""] + client_list)

    if selected_client:
        invoice_query = (
            'SELECT "Produto", "Quantidade", "total" '
            'FROM public.vw_pedido_produto '
            'WHERE "Cliente" = %s AND status = %s;'
        )
        invoice_data = run_query(invoice_query, (selected_client, 'em aberto'))

        if invoice_data:
            df = pd.DataFrame(invoice_data, columns=["Produto", "Quantidade", "total"])
            generate_invoice_for_printer(df)

            total_sum = df["total"].sum()
            st.subheader(f"Total Geral: R$ {total_sum:,.2f}")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Debit", key="debit_button"):
                    process_payment(selected_client, "Received - Debited")

            with col2:
                if st.button("Credit", key="credit_button"):
                    process_payment(selected_client, "Received - Credit")

            with col3:
                if st.button("Pix", key="pix_button"):
                    process_payment(selected_client, "Received - Pix")
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
    success = run_insert(query, (payment_status, client))
    if success:
        st.success(f"Status updated to: {payment_status}")
        refresh_data()
    else:
        st.error("Error updating the status.")

def generate_invoice_for_printer(df):
    company = "Boituva Beach Club"
    address = "Avenida do Trabalhador 1879"
    city = "Boituva - SP 18552-100"
    cnpj = "05.365.434/0001-09"
    phone = "(13) 99154-5481"

    invoice_note = []
    invoice_note.append("==================================================")
    invoice_note.append("                         NOTA FISCAL")
    invoice_note.append("==================================================")
    invoice_note.append(f"Empresa: {company}")
    invoice_note.append(f"Endereço: {address}")
    invoice_note.append(f"Cidade: {city}")
    invoice_note.append(f"CNPJ: {cnpj}")
    invoice_note.append(f"Telefone: {phone}")
    invoice_note.append("--------------------------------------------------")
    invoice_note.append("DESCRIÇÃO             QTD     TOTAL")
    invoice_note.append("--------------------------------------------------")

    total_general = 0

    for _, row in df.iterrows():
        description = f"{row['Produto'][:20]:<20}"
        quantity = f"{row['Quantidade']:>5}"
        total = row['total']
        total_general += total
        total_formatted = f"R$ {total:,.2f}".replace('.', ',')
        invoice_note.append(f"{description} {quantity} {total_formatted}")

    formatted_general_total = f"R$ {total_general:,.2f}".replace('.', ',')
    invoice_note.append("--------------------------------------------------")
    invoice_note.append(f"TOTAL GERAL: {formatted_general_total:>28}")
    invoice_note.append("==================================================")
    invoice_note.append("OBRIGADO PELA SUA PREFERÊNCIA!")
    invoice_note.append("==================================================")

    st.text("\n".join(invoice_note))

#####################
# Initialization
#####################

if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

# Clear edit order state if the page changes
if 'page' in st.session_state:
    if st.session_state.page != "Orders":
        st.session_state.edit_order_id = None

# Menu Navigation
st.session_state.page = sidebar_navigation()

# Page Routing
if st.session_state.page == "Home":
    home_page()
elif st.session_state.page == "Orders":
    orders_page()
elif st.session_state.page == "Invoice":
    invoice_page()
elif st.session_state.page == "Stock":
    stock_page()
elif st.session_state.page == "Clients":
    clients_page()
elif st.session_state.page == "Commands":
    commands_page()
