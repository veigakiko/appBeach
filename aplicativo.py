# app.py
import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
import plotly.express as px
from database import run_query, run_insert, load_all_data, refresh_data
from auth import authenticate_user
import os

#####################
# Helper Functions
#####################

def format_currency(value):
    """
    Formats a number into Brazilian Real currency format.
    """
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def generate_unique_key(row, keys):
    """
    Generates a unique key for a given row based on specified keys.
    """
    return "|".join([str(row[key]) for key in keys])

def load_logo(url):
    """
    Loads and returns an image from a given URL.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        logo = Image.open(BytesIO(response.content))
        return logo
    except requests.exceptions.RequestException as e:
        st.error("Falha ao carregar o logotipo.")
        return None

#####################
# UI Components
#####################

def sidebar_navigation():
    """
    Creates a sidebar menu for navigation.
    """
    with st.sidebar:
        st.title("Boituva Beach Club 🎾")
        selected = option_menu(
            "Menu Principal",
            ["Home", "Orders", "Products", "Stock", "Clients", "Nota Fiscal"],
            icons=["house", "file-text", "box", "list-task", "layers", "file-invoice"],
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
# Pages
#####################

def home_page():
    st.title("Boituva Beach Club 🎾")
    st.write("📍 Av. Do Trabalhador, 1879 🏆 5° Open BBC")

    ############################
    # Display Open Orders Summary
    ############################

    st.subheader("Open Orders Summary")
    open_orders_query = """
    SELECT "Cliente", SUM("total") as Total
    FROM public.vw_pedido_produto
    WHERE status = %s
    GROUP BY "Cliente"
    ORDER BY "Cliente" DESC;
    """
    open_orders_data = run_query(open_orders_query, ('em aberto',))

    if open_orders_data:
        df_open_orders_display = pd.DataFrame(open_orders_data, columns=["Client", "Total"])
        total_open = df_open_orders_display["Total"].sum()
        df_open_orders_display["Total"] = df_open_orders_display["Total"].apply(format_currency)
        df_open_orders_display = df_open_orders_display.reset_index(drop=True)[["Client", "Total"]]
        st.table(df_open_orders_display)
        st.markdown(f"**Total Geral (Open Orders):** {format_currency(total_open)}")
    else:
        st.info("Nenhum pedido em aberto encontrado.")

    ############################
    # Display Closed Orders Summary
    ############################

    st.subheader("Closed Orders Summary")
    closed_orders_query = """
    SELECT DATE("Data") as Date, SUM("total") as Total
    FROM public.vw_pedido_produto
    WHERE status != %s
    GROUP BY DATE("Data")
    ORDER BY DATE("Data") DESC;
    """
    closed_orders_data = run_query(closed_orders_query, ('em aberto',))

    if closed_orders_data:
        df_closed_orders_plot = pd.DataFrame(closed_orders_data, columns=["Date", "Total"])
        df_closed_orders_display = df_closed_orders_plot.copy()
        df_closed_orders_display["Date"] = pd.to_datetime(df_closed_orders_display["Date"]).dt.strftime('%Y-%m-%d')
        df_closed_orders_display["Total"] = df_closed_orders_display["Total"].apply(format_currency)
        total_closed = df_closed_orders_plot["Total"].sum()
        st.table(df_closed_orders_display)
        fig = px.area(
            df_closed_orders_plot,
            x='Date',
            y='Total',
            title='Total Vendido por Dia',
            labels={'Date': 'Data', 'Total': 'Total Vendido (R$)'},
            template='plotly_white'
        )
        fig.update_layout(
            autosize=False,
            width=700,
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(f"**Total Geral (Closed Orders):** {format_currency(total_closed)}")
    else:
        st.info("Nenhum pedido fechado encontrado.")

def orders_page():
    st.title("Orders")
    st.subheader("Register a New Order")

    # Fetch products and clients
    product_data = run_query('SELECT product FROM public.tb_products ORDER BY product;')
    product_list = [row[0] for row in product_data] if product_data else ["No products available"]

    client_data = run_query('SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;')
    client_list = [row[0] for row in client_data] if client_data else ["No clients available"]

    # Order Registration Form
    with st.form(key='order_form'):
        customer_name = st.selectbox("Customer Name", client_list, index=0)
        product = st.selectbox("Product", product_list, index=0)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Register Order")

    if submit_button:
        if customer_name and product and quantity > 0:
            query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", status, total)
            VALUES (%s, %s, %s, %s, 'em aberto', (SELECT unit_value FROM public.tb_products WHERE product = %s) * %s);
            """
            timestamp = datetime.now()
            unit_value_query = 'SELECT unit_value FROM public.tb_products WHERE product = %s;'
            unit_value = run_query(unit_value_query, (product,))
            if unit_value:
                total_value = unit_value[0][0] * quantity
                success = run_insert(query, (customer_name, product, quantity, timestamp, product, quantity))
                if success:
                    st.success("Order registered successfully!")
                    refresh_data()
                else:
                    st.error("Failed to register the order.")
            else:
                st.error("Failed to retrieve unit value for the selected product.")
        else:
            st.warning("Please fill in all fields correctly.")

    # Display All Orders with Search and Filter
    st.subheader("All Orders")
    search_term = st.text_input("Search by Client or Product")
    status_filter = st.selectbox("Filter by Status", ["All", "em aberto", "Received - Debited", "Received - Credit", "Received - Pix"])

    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        df_orders = pd.DataFrame(orders_data, columns=["Client", "Product", "Quantity", "Date", "Status", "Total"])

        if search_term:
            df_orders = df_orders[
                df_orders["Client"].str.contains(search_term, case=False) | 
                df_orders["Product"].str.contains(search_term, case=False)
            ]

        if status_filter != "All":
            df_orders = df_orders[df_orders["Status"] == status_filter]

        st.dataframe(df_orders, use_container_width=True)

        st.subheader("Edit or Delete an Existing Order")
        # Generate unique keys based on Client, Product, and Date
        df_orders["unique_key"] = df_orders.apply(
            lambda row: generate_unique_key(row, ["Client", "Product", "Date"]),
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

                # Edit/Delete Form
                with st.form(key='edit_order_form'):
                    edit_product = st.selectbox(
                        "Product",
                        product_list,
                        index=product_list.index(original_product) if original_product in product_list else 0
                    )
                    edit_quantity = st.number_input(
                        "Quantity",
                        min_value=1,
                        step=1,
                        value=int(original_quantity)
                    )
                    edit_status_list = ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix"]
                    edit_status_index = edit_status_list.index(original_status) if original_status in edit_status_list else 0
                    edit_status = st.selectbox("Status", edit_status_list, index=edit_status_index)

                    update_button = st.form_submit_button(label="Update Order")
                    delete_button = st.form_submit_button(label="Delete Order")

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

                if update_button:
                    update_query = """
                    UPDATE public.tb_pedido
                    SET "Produto" = %s, "Quantidade" = %s, status = %s, total = (SELECT unit_value FROM public.tb_products WHERE product = %s) * %s
                    WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                    """
                    success = run_insert(update_query, (
                        edit_product, edit_quantity, edit_status, edit_product, edit_quantity,
                        original_client, original_product, original_date
                    ))
                    if success:
                        st.success("Order updated successfully!")
                        refresh_data()
                    else:
                        st.error("Failed to update the order.")
    else:
        st.info("No orders found.")

def products_page():
    st.title("Products")

    st.subheader("Add a New Product")
    with st.form(key='product_form'):
        supplier = st.text_input("Supplier", max_chars=100)
        product = st.text_input("Product", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        unit_value = st.number_input("Unit Value", min_value=0.0, step=0.01, format="%.2f")
        creation_date = st.date_input("Creation Date")
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
                refresh_data()
            else:
                st.error("Failed to add the product.")
        else:
            st.warning("Please fill in all fields correctly.")

    # Display All Products with Search and Filter
    st.subheader("All Products")
    search_term = st.text_input("Search by Supplier or Product")
    date_filter = st.date_input("Filter by Creation Date", value=None)

    products_data = st.session_state.data.get("products", [])
    if products_data:
        df_products = pd.DataFrame(products_data, columns=["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"])

        if search_term:
            df_products = df_products[
                df_products["Supplier"].str.contains(search_term, case=False) | 
                df_products["Product"].str.contains(search_term, case=False)
            ]

        if date_filter:
            df_products = df_products[df_products["Creation Date"] == date_filter]

        st.dataframe(df_products, use_container_width=True)

        st.subheader("Edit or Delete an Existing Product")
        # Generate unique keys based on Supplier, Product, and Creation Date
        df_products["unique_key"] = df_products.apply(
            lambda row: generate_unique_key(row, ["Supplier", "Product", "Creation Date"]),
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

                # Edit/Delete Form
                with st.form(key='edit_product_form'):
                    edit_supplier = st.text_input("Supplier", value=original_supplier, max_chars=100)
                    edit_product = st.text_input("Product", value=original_product, max_chars=100)
                    edit_quantity = st.number_input(
                        "Quantity",
                        min_value=1,
                        step=1,
                        value=int(original_quantity)
                    )
                    edit_unit_value = st.number_input(
                        "Unit Value",
                        min_value=0.0,
                        step=0.01,
                        format="%.2f",
                        value=float(original_unit_value)
                    )
                    edit_creation_date = st.date_input("Creation Date", value=original_creation_date)

                    update_button = st.form_submit_button(label="Update Product")
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
                    success = run_insert(update_query, (
                        edit_supplier, edit_product, edit_quantity, edit_unit_value, edit_total_value, edit_creation_date,
                        original_supplier, original_product, original_creation_date
                    ))
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
                        success = run_insert(delete_query, (original_supplier, original_product, original_creation_date))
                        if success:
                            st.success("Product deleted successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to delete the product.")
    else:
        st.info("No products found.")

def stock_page():
    st.title("Stock")

    st.subheader("Add a New Stock Record")

    # Load product list
    product_data = run_query("SELECT product FROM public.tb_products ORDER BY product;")
    product_list = [row[0] for row in product_data] if product_data else ["No products available"]

    with st.form(key='stock_form'):
        product = st.selectbox("Product", product_list)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        transaction = st.selectbox("Transaction Type", ["Entrada", "Saída"])
        date = st.date_input("Date", value=datetime.now().date())
        submit_stock = st.form_submit_button(label="Register")

    if submit_stock:
        if product and quantity > 0:
            current_datetime = datetime.combine(date, datetime.min.time())
            query = """
            INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Transação", "Data")
            VALUES (%s, %s, %s, %s);
            """
            success = run_insert(query, (product, quantity, transaction, current_datetime))
            if success:
                st.success("Stock record added successfully!")
                refresh_data()
            else:
                st.error("Failed to add stock record.")
        else:
            st.warning("Please select a product and enter a quantity greater than 0.")

    # Display All Stock Records with Search and Filter
    st.subheader("All Stock Records")
    search_term = st.text_input("Search by Product or Transaction Type")
    date_filter = st.date_input("Filter by Date", value=None)

    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        df_stock = pd.DataFrame(stock_data, columns=["Product", "Quantity", "Transaction", "Date"])

        if search_term:
            df_stock = df_stock[
                df_stock["Product"].str.contains(search_term, case=False) | 
                df_stock["Transaction"].str.contains(search_term, case=False)
            ]

        if date_filter:
            df_stock = df_stock[df_stock["Date"] == date_filter]

        st.dataframe(df_stock, use_container_width=True)

        st.subheader("Edit or Delete an Existing Stock Record")
        # Generate unique keys based on Product, Transaction, and Date
        df_stock["unique_key"] = df_stock.apply(
            lambda row: generate_unique_key(row, ["Product", "Transaction", "Date"]),
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

                # Edit/Delete Form
                with st.form(key='edit_stock_form'):
                    edit_product = st.selectbox(
                        "Product",
                        product_list,
                        index=product_list.index(original_product) if original_product in product_list else 0
                    )
                    edit_quantity = st.number_input(
                        "Quantity",
                        min_value=1,
                        step=1,
                        value=int(original_quantity)
                    )
                    edit_transaction = st.selectbox(
                        "Transaction Type",
                        ["Entrada", "Saída"],
                        index=["Entrada", "Saída"].index(original_transaction) if original_transaction in ["Entrada", "Saída"] else 0
                    )
                    edit_date = st.date_input("Date", value=original_date.date())

                    update_button = st.form_submit_button(label="Update Stock Record")
                    delete_button = st.form_submit_button(label="Delete Stock Record")

                if update_button:
                    edit_datetime = datetime.combine(edit_date, datetime.min.time())
                    update_query = """
                    UPDATE public.tb_estoque
                    SET "Produto" = %s, "Quantidade" = %s, "Transação" = %s, "Data" = %s
                    WHERE "Produto" = %s AND "Transação" = %s AND "Data" = %s;
                    """
                    success = run_insert(update_query, (
                        edit_product, edit_quantity, edit_transaction, edit_datetime,
                        original_product, original_transaction, original_date
                    ))
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
                        success = run_insert(delete_query, (
                            original_product, original_transaction, original_date
                        ))
                        if success:
                            st.success("Stock record deleted successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to delete the stock record.")
    else:
        st.info("No stock records found.")

def clients_page():
    st.title("Clients")

    st.subheader("Register a New Client")

    with st.form(key='client_form'):
        nome_completo = st.text_input("Full Name", max_chars=100)
        submit_client = st.form_submit_button(label="Register New Client")

    if submit_client:
        if nome_completo:
            # Default values
            data_nascimento = datetime(2000, 1, 1).date()
            genero = "Man"
            telefone = "0000-0000"
            endereco = "Endereço padrão"

            # Generate a unique email
            unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
            email = f"{nome_completo.replace(' ', '_').lower()}_{unique_id}@example.com"

            query = """
            INSERT INTO public.tb_clientes (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            success = run_insert(query, (nome_completo, data_nascimento, genero, telefone, email, endereco))
            if success:
                st.success("Client registered successfully!")
                refresh_data()
            else:
                st.error("Failed to register the client.")
        else:
            st.warning("Please fill in the Full Name field.")

    # Display All Clients with Search and Filter
    st.subheader("All Clients")
    search_term = st.text_input("Search by Full Name or Email")
    date_filter = st.date_input("Filter by Registration Date", value=None)

    clients_data = run_query("SELECT nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro FROM public.tb_clientes ORDER BY data_cadastro DESC;")
    if clients_data:
        df_clients = pd.DataFrame(clients_data, columns=["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"])

        if search_term:
            df_clients = df_clients[
                df_clients["Full Name"].str.contains(search_term, case=False) | 
                df_clients["Email"].str.contains(search_term, case=False)
            ]

        if date_filter:
            df_clients = df_clients[df_clients["Register Date"].dt.date == date_filter]

        st.dataframe(df_clients, use_container_width=True)

        st.subheader("Edit or Delete an Existing Client")
        # Select client by Email
        client_emails = df_clients["Email"].unique().tolist()
        selected_email = st.selectbox("Select a client by Email:", [""] + client_emails)

        if selected_email:
            selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
            original_name = selected_client_row["Full Name"]
            original_birth_date = selected_client_row["Birth Date"]
            original_gender = selected_client_row["Gender"]
            original_phone = selected_client_row["Phone"]
            original_address = selected_client_row["Address"]

            # Edit/Delete Form
            with st.form(key='edit_client_form'):
                edit_name = st.text_input("Full Name", value=original_name, max_chars=100)
                edit_birth_date = st.date_input("Birth Date", value=original_birth_date)
                edit_gender = st.selectbox("Gender", ["Man", "Woman", "Other"], index=["Man", "Woman", "Other"].index(original_gender) if original_gender in ["Man", "Woman", "Other"] else 0)
                edit_phone = st.text_input("Phone", value=original_phone)
                edit_address = st.text_input("Address", value=original_address, max_chars=200)

                update_button = st.form_submit_button(label="Update Client")
                delete_button = st.form_submit_button(label="Delete Client")

            if update_button:
                if edit_name and edit_phone and edit_address:
                    update_query = """
                    UPDATE public.tb_clientes
                    SET nome_completo = %s,
                        data_nascimento = %s,
                        genero = %s,
                        telefone = %s,
                        endereco = %s
                    WHERE email = %s;
                    """
                    success = run_insert(update_query, (
                        edit_name, edit_birth_date, edit_gender, edit_phone, edit_address, selected_email
                    ))
                    if success:
                        st.success("Client updated successfully!")
                        refresh_data()
                    else:
                        st.error("Failed to update the client.")
                else:
                    st.warning("Please fill in all fields correctly.")

            if delete_button:
                confirm = st.checkbox("Are you sure you want to delete this client?")
                if confirm:
                    delete_query = "DELETE FROM public.tb_clientes WHERE email = %s;"
                    success = run_insert(delete_query, (selected_email,))
                    if success:
                        st.success("Client deleted successfully!")
                        refresh_data()
                    else:
                        st.error("Failed to delete the client.")
    else:
        st.info("No clients found.")

def invoice_page():
    st.title("Nota Fiscal")

    open_clients_query = 'SELECT DISTINCT "Cliente" FROM public.vw_pedido_produto WHERE status = %s;'
    open_clients = run_query(open_clients_query, ('em aberto',))

    client_list = [row[0] for row in open_clients] if open_clients else []

    selected_client = st.selectbox("Selecione um Cliente", [""] + client_list)

    if selected_client:
        invoice_query = (
            'SELECT "Produto", "Quantidade", "total" '
            'FROM public.vw_pedido_produto '
            'WHERE "Cliente" = %s AND status = %s;'
        )
        invoice_data = run_query(invoice_query, (selected_client, 'em aberto'))

        if invoice_data:
            df = pd.DataFrame(invoice_data, columns=["Produto", "Quantidade", "total"])
            generate_invoice_pdf(df)

            total_sum = df["total"].sum()
            st.markdown(f"**Total Geral: {format_currency(total_sum)}**")

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
            st.info("Não há pedidos em aberto para o cliente selecionado.")
    else:
        st.warning("Por favor, selecione um cliente.")

def process_payment(client, payment_status):
    query = """
    UPDATE public.tb_pedido
    SET status = %s, "Data" = CURRENT_TIMESTAMP
    WHERE "Cliente" = %s AND status = 'em aberto';
    """
    success = run_insert(query, (payment_status, client))
    if success:
        st.success(f"Status atualizado para: {payment_status}")
        refresh_data()
    else:
        st.error("Erro ao atualizar o status.")

def generate_invoice_pdf(df):
    """
    Generates a PDF invoice and provides a download link.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm

    company = "Boituva Beach Club"
    address = "Avenida do Trabalhador 1879"
    city = "Boituva - SP 18552-100"
    cnpj = "05.365.434/0001-09"
    phone = "(13) 99154-5481"

    invoice_filename = f"invoice_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"

    c = canvas.Canvas(invoice_filename, pagesize=A4)
    width, height = A4

    # Company Details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 50, company)
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 65, address)
    c.drawString(50, height - 80, city)
    c.drawString(50, height - 95, f"CNPJ: {cnpj}")
    c.drawString(50, height - 110, f"Telefone: {phone}")

    # Invoice Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(200, height - 150, "NOTA FISCAL")

    # Table Headers
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 180, "DESCRIÇÃO")
    c.drawString(300, height - 180, "QTD")
    c.drawString(400, height - 180, "TOTAL")

    # Table Content
    c.setFont("Helvetica", 12)
    y = height - 200
    for _, row in df.iterrows():
        description = f"{row['Produto'][:20]:<20}"
        quantity = f"{row['Quantidade']}"
        total = format_currency(row['total'])
        c.drawString(50, y, description)
        c.drawString(300, y, quantity)
        c.drawString(400, y, total)
        y -= 20

    # Total
    total_sum = df["total"].sum()
    c.setFont("Helvetica-Bold", 12)
    c.drawString(300, y - 20, "TOTAL GERAL:")
    c.drawString(400, y - 20, format_currency(total_sum))

    # Thank You Note
    c.setFont("Helvetica", 12)
    c.drawString(200, y - 60, "OBRIGADO PELA SUA PREFERÊNCIA!")

    c.save()

    # Provide download link
    with open(invoice_filename, "rb") as pdf_file:
        PDFbyte = pdf_file.read()
        st.download_button(
            label="Download Invoice",
            data=PDFbyte,
            file_name=invoice_filename,
            mime="application/pdf"
        )

#####################
# Initialization
#####################

def main():
    # Initialize session state
    if 'data' not in st.session_state:
        st.session_state.data = load_all_data()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    # Authentication
    if not st.session_state.logged_in:
        if authenticate_user():
            st.session_state.logged_in = True
            refresh_data()
    else:
        # Sidebar Navigation
        selected_page = sidebar_navigation()

        # Page Routing
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
        elif selected_page == "Nota Fiscal":
            invoice_page()

        # Logout Button
        with st.sidebar:
            if st.button("Logout"):
                st.session_state.logged_in = False
                st.experimental_rerun()

if __name__ == "__main__":
    main()
