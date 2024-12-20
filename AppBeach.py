import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
# import plotly.express as px  # Removido, já que o gráfico foi removido da Home

####################
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
    except OperationalError as e:
        st.error("Não foi possível conectar ao banco de dados. Por favor, tente novamente mais tarde.")
        return None

def run_query(query, values=None):
    """
    Executa uma consulta de leitura (SELECT) e retorna os dados obtidos.
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
        st.error(f"Erro ao executar a consulta: {e}")
        return []

def run_insert(query, values):
    """
    Executa uma consulta de inserção, atualização ou deleção.
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
        st.error(f"Erro ao executar a consulta: {e}")
        return False

#####################
# Data Loading
#####################
def load_all_data():
    """
    Carrega todos os dados utilizados pelo aplicativo e retorna em um dicionário.
    """
    data = {}
    try:
        data["orders"] = run_query(
            'SELECT "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido ORDER BY "Data" DESC;'
        )
        data["products"] = run_query(
            'SELECT supplier, product, quantity, unit_value, total_value, creation_date FROM public.tb_products ORDER BY creation_date DESC;'
        )
        data["clients"] = run_query('SELECT DISTINCT "Cliente" FROM public.tb_pedido ORDER BY "Cliente";')
        data["stock"] = run_query(
            'SELECT "Produto", "Quantidade", "Transação", "Data" FROM public.tb_estoque ORDER BY "Data" DESC;'
        )
    except Exception as e:
        st.error(f"Erro ao carregar os dados: {e}")
    return data

def refresh_data():
    """
    Recarrega todos os dados e atualiza o estado da sessão.
    """
    st.session_state.data = load_all_data()

#####################
# Menu Navigation
#####################
def sidebar_navigation():
    """
    Cria um menu lateral para navegação usando streamlit_option_menu.
    """
    with st.sidebar:
        st.title("Boituva Beach Club 🎾")
        selected = option_menu(
            "Menu Principal", ["Home", "Orders", "Products", "Stock", "Clients", "Nota Fiscal"],
            icons=["house", "file-text", "box", "list-task", "layers", "receipt"],  # Alterado "file-invoice" para "receipt"
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
# Home Page
#####################
def home_page():
    # Título ajustado com emoji no início
    st.title("🎾Boituva Beach Club 🎾")
    # Descrição com tamanho de fonte normal
    st.write("📍 Av. Do Trabalhador, 1879 🏆 5° Open BBC")
    
    ############################
    # Display Open Orders Summary
    ############################

    st.markdown("**Open Orders Summary**")
    # Consulta para obter pedidos em aberto agrupados por Cliente com a soma total
    open_orders_query = """
    SELECT "Cliente", SUM("total") as Total
    FROM public.vw_pedido_produto
    WHERE status = %s
    GROUP BY "Cliente"
    ORDER BY "Cliente" DESC;
    """
    open_orders_data = run_query(open_orders_query, ('em aberto',))

    if open_orders_data:
        # Criar DataFrame para exibição
        df_open_orders_display = pd.DataFrame(open_orders_data, columns=["Client", "Total"])
        
        # Calcular a soma total dos pedidos em aberto
        total_open = df_open_orders_display["Total"].sum()
        
        # Formatar a coluna 'Total_display' para moeda brasileira
        df_open_orders_display["Total_display"] = df_open_orders_display["Total"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        
        # Selecionar apenas as colunas para exibição
        df_display = df_open_orders_display[["Client", "Total_display"]]
        
        # Exibir a tabela sem índice e com largura otimizada para a coluna
        st.table(df_display)
        
        # Formatar o total geral para moeda brasileira
        formatted_total_open = f"R$ {total_open:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        st.markdown(f"**Total Geral (Open Orders):** {formatted_total_open}")
    else:
        st.info("Nenhum pedido em aberto encontrado.")

    ############################
    # Display Closed Orders Summary
    ############################

    st.markdown("**Closed Orders Summary**")
    # Consulta para obter pedidos fechados agrupados por Data (somente dia) com a soma total
    closed_orders_query = """
    SELECT DATE("Data") as Date, SUM("total") as Total
    FROM public.vw_pedido_produto
    WHERE status != %s
    GROUP BY DATE("Data")
    ORDER BY DATE("Data") DESC;
    """
    closed_orders_data = run_query(closed_orders_query, ('em aberto',))

    if closed_orders_data:
        # Criar DataFrame para exibição com formatação
        df_closed_orders_display = pd.DataFrame(closed_orders_data, columns=["Date", "Total"])
        
        # Calcular a soma total dos pedidos fechados antes da formatação
        total_closed = df_closed_orders_display["Total"].sum()
        
        # Formatar a coluna 'Total_display' para moeda brasileira
        df_closed_orders_display["Total_display"] = df_closed_orders_display["Total"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        
        # Formatar a coluna 'Date' para exibição amigável (somente dia)
        df_closed_orders_display["Date"] = pd.to_datetime(df_closed_orders_display["Date"]).dt.strftime('%Y-%m-%d')
        
        # Selecionar apenas as colunas para exibição
        df_display = df_closed_orders_display[["Date", "Total_display"]]
        
        # Exibir a tabela de Closed Orders Summary
        st.table(df_display)
        
        # Formatar o total geral para moeda brasileira
        formatted_total_closed = f"R$ {total_closed:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        st.markdown(f"**Total Geral (Closed Orders):** {formatted_total_closed}")
    else:
        st.info("Nenhum pedido fechado encontrado.")

#####################
# Orders Page
#####################
def orders_page():
    st.title("Orders")
    st.subheader("Register a new order")

    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["No products available"]

    # Formulário para inserir novo pedido
    with st.form(key='order_form'):
        # Carregando lista de clientes para o novo pedido
        clientes = run_query('SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;')
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
            success = run_insert(query, (customer_name, product, quantity, timestamp))
            if success:
                st.success("Order registered successfully!")
                refresh_data()
            else:
                st.error("Failed to register the order.")
        else:
            st.warning("Please fill in all fields correctly.")

    # Exibir todos os pedidos
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        
        # Exibir a tabela de pedidos
        st.dataframe(df_orders, use_container_width=True)

        st.subheader("Edit or Delete an Existing Order")
        # Criar uma chave única para identificar cada pedido
        df_orders["unique_key"] = df_orders.apply(
            lambda row: f"{row['Client']}|{row['Product']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
            axis=1
        )
        unique_keys = df_orders["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select an order to edit/delete:", [""] + unique_keys)

        if selected_key:
            # Verificar quantos registros correspondem à chave única
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

                # Formulário para editar o pedido
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

                # Deletar Ordem imediatamente após clicar no botão, sem confirmação
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
                    # Atualiza o pedido no banco usando a combinação de campos como filtro
                    update_query = """
                    UPDATE public.tb_pedido
                    SET "Produto" = %s, "Quantidade" = %s, status = %s
                    WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                    """
                    success = run_insert(update_query, (
                        edit_product, edit_quantity, edit_status,
                        original_client, original_product, original_date
                    ))
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

    # Exibir todos os produtos
    products_data = st.session_state.data.get("products", [])
    if products_data:
        st.subheader("All Products")
        columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
        df_products = pd.DataFrame(products_data, columns=columns)
        
        # Depuração: Exibir nomes das colunas
        st.write("Columns in df_products:", df_products.columns.tolist())

        st.dataframe(df_products, use_container_width=True)

        st.subheader("Edit or Delete an Existing Product")
        # Criar uma chave única para identificar cada produto
        df_products["unique_key"] = df_products.apply(
            lambda row: f"{row['Supplier']}|{row['Product']}|{row['Creation Date'].strftime('%Y-%m-%d')}",
            axis=1
        )
        unique_keys = df_products["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select a product to edit/delete:", [""] + unique_keys)

        if selected_key:
            # Verificar quantos registros correspondem à chave única
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

                # Formulário para editar o produto
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
                    # Recalcular total_value se quantity ou unit_value foram alterados
                    edit_total_value = edit_quantity * edit_unit_value

                    # Atualiza o produto no banco usando a combinação de campos como filtro
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
                    # Confirmação antes de deletar
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

#####################
# Stock Page
#####################
def stock_page():
    st.title("Stock")
    st.subheader("Add a new stock record")
    st.write("Esta página foi projetada para registrar apenas entradas de produtos no estoque de forma prática e organizada.")

    # Carregar a lista de produtos da tabela tb_products
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

    # Exibir todos os registros de estoque
    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        st.subheader("All Stock Records")
        columns = ["Product", "Quantity", "Transaction", "Date"]
        df_stock = pd.DataFrame(stock_data, columns=columns)
        
        # Depuração: Exibir nomes das colunas
        st.write("Columns in df_stock:", df_stock.columns.tolist())

        st.dataframe(df_stock, use_container_width=True)

        st.subheader("Edit or Delete an Existing Stock Record")
        # Criar uma chave única para identificar cada registro de estoque
        df_stock["unique_key"] = df_stock.apply(
            lambda row: f"{row['Product']}|{row['Transaction']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
            axis=1
        )
        unique_keys = df_stock["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select a stock record to edit/delete:", [""] + unique_keys)

        if selected_key:
            # Verificar quantos registros correspondem à chave única
            matching_rows = df_stock[df_stock["unique_key"] == selected_key]
            if len(matching_rows) > 1:
                st.warning("Multiple stock records found with the same key. Please refine your selection.")
            else:
                selected_row = matching_rows.iloc[0]
                original_product = selected_row["Product"]
                original_quantity = selected_row["Quantity"]
                original_transaction = selected_row["Transaction"]
                original_date = selected_row["Date"]  # Isso é um objeto datetime

                # Formulário para editar o registro de estoque
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

                    # Atualiza o registro de estoque no banco usando a combinação de campos como filtro
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
                    # Confirmação antes de deletar
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

#####################
# Clients Page
#####################
def clients_page():
    st.title("Clients")

    st.subheader("Register a New Client")

    # Formulário com apenas o campo Full Name
    with st.form(key='client_form'):
        nome_completo = st.text_input("Full Name", max_chars=100)
        submit_client = st.form_submit_button(label="Register New Client")

    if submit_client:
        if nome_completo:
            # Outros valores padrões
            data_nascimento = datetime(2000, 1, 1).date()
            genero = "Man"
            telefone = "0000-0000"
            
            # Gera um email único para evitar conflito de chave única
            unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
            email = f"{nome_completo.replace(' ', '_').lower()}_{unique_id}@example.com"

            endereco = "Endereço padrão"

            query = """
            INSERT INTO public.tb_clientes (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            success = run_insert(query, (nome_completo, data_nascimento, genero, telefone, email, endereco))
            if success:
                st.success("Client registered successfully!")
                refresh_data()
        else:
            st.warning("Please fill in the Full Name field.")

    # Mostrar a tabela de clientes cadastrados
    clients_data = run_query("SELECT nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro FROM public.tb_clientes ORDER BY data_cadastro DESC;")

    if clients_data:
        st.subheader("All Clients")
        columns = ["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"]
        df_clients = pd.DataFrame(clients_data, columns=columns)
        st.dataframe(df_clients, use_container_width=True)

        st.subheader("Edit or Delete an Existing Client")
        # Selecionar um cliente para edição
        client_emails = df_clients["Email"].unique().tolist()
        selected_email = st.selectbox("Select a client by Email:", [""] + client_emails)

        if selected_email:
            # Obtém dados do cliente selecionado
            selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
            original_name = selected_client_row["Full Name"]

            # Formulário para editar o nome
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
                    success = run_insert(update_query, (edit_name, selected_email))
                    if success:
                        st.success("Client updated successfully!")
                        refresh_data()
                    else:
                        st.error("Failed to update the client.")
                else:
                    st.warning("Please fill in the Full Name field.")

            if delete_button:
                # Confirmação antes de deletar
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

#####################
# Invoice Page
#####################
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
            generate_invoice_for_printer(df)

            # Calcular o total geral antes da formatação
            total_sum = df["total"].sum()
            # Formatar para moeda brasileira
            formatted_total_sum = f"R$ {total_sum:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            # **Remova ou comente esta linha para evitar duplicação**
            # st.markdown(f"**Total Geral: {formatted_total_sum}**")
            
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

def generate_invoice_for_printer(df):
    company = "Boituva Beach Club"
    address = "Avenida do Trabalhador 1879"
    city = "Boituva - SP 18552-100"
    cnpj = "05.365.434/0001-09"
    phone = "(13) 99154-5481"

    invoice_note = []
    invoice_note.append("==================================================")
    invoice_note.append("                      NOTA FISCAL                ")
    invoice_note.append("==================================================")
    invoice_note.append(f"Empresa: {company}")
    invoice_note.append(f"Endereço: {address}")
    invoice_note.append(f"Cidade: {city}")
    invoice_note.append(f"CNPJ: {cnpj}")
    invoice_note.append(f"Telefone: {phone}")
    invoice_note.append("--------------------------------------------------")
    invoice_note.append("DESCRIÇÃO             QTD     TOTAL")
    invoice_note.append("--------------------------------------------------")

    # Agrupar os dados por 'Produto', somando 'Quantidade' e 'total'
    grouped_df = df.groupby('Produto').agg({'Quantidade': 'sum', 'total': 'sum'}).reset_index()

    total_general = 0

    for _, row in grouped_df.iterrows():
        description = f"{row['Produto'][:20]:<20}"  # Limitar a descrição a 20 caracteres
        quantity = f"{int(row['Quantidade']):>5}"   # Garantir que a quantidade seja um inteiro
        total = row['total']
        total_general += total
        total_formatted = f"R$ {total:,.2f}".replace('.', ',')  # Formatar para moeda brasileira
        invoice_note.append(f"{description} {quantity} {total_formatted}")

    invoice_note.append("--------------------------------------------------")
    # Alinhar o texto 'TOTAL GERAL:' à direita e o valor total também à direita
    formatted_general_total = f"R$ {total_general:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    invoice_note.append(f"{'TOTAL GERAL:':>30} {formatted_general_total:>10}")
    invoice_note.append("==================================================")
    invoice_note.append("OBRIGADO PELA SUA PREFERÊNCIA!")
    invoice_note.append("==================================================")

    # Exibir a Nota Fiscal como texto
    st.text("\n".join(invoice_note))

#####################
# Login Page
#####################
def login_page():
    # CSS para alterar a cor de fundo da página de login para branco
    st.markdown(
        """
        <style>
        /* Define a cor de fundo para branco */
        body {
            background-color: white;
        }
        /* Opcional: Centralizar o conteúdo do login */
        .block-container {
            padding-top: 100px;
            padding-bottom: 100px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Carregar e exibir o logotipo
    logo_url = "https://res.cloudinary.com/lptennis/image/upload/v1657233475/kyz4k7fcptxt7x7mu9qu.jpg"
    try:
        response = requests.get(logo_url)
        response.raise_for_status()
        logo = Image.open(BytesIO(response.content))
        st.image(logo, use_column_width=False)  # Exibe em tamanho original
    except requests.exceptions.RequestException as e:
        st.error("Falha ao carregar o logotipo.")

    st.title("Beach Club")
    st.write("Por favor, insira suas credenciais para acessar o aplicativo.")

    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button(label="Login")

    if submit_login:
        if username == "admin" and password == "adminbeach":
            st.session_state.logged_in = True
            st.success("Login bem-sucedido!")
        else:
            st.error("Nome de usuário ou senha incorretos.")

#####################
# Initialization
#####################

# Inicializar o estado da sessão para dados e login
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# Verificar se o usuário está logado
if not st.session_state.logged_in:
    login_page()
else:
    # Menu Navigation
    selected_page = sidebar_navigation()

    # Detectar mudança de página e atualizar os dados se necessário
    if 'current_page' not in st.session_state:
        st.session_state.current_page = selected_page
        # Inicialmente, os dados já estão carregados
    elif selected_page != st.session_state.current_page:
        # Página mudou, recarregar os dados
        refresh_data()
        st.session_state.current_page = selected_page
        # Reset home page initialization flag quando navegar para Home
        if selected_page == "Home":
            st.session_state.home_page_initialized = False
            # As tabelas serão exibidas por padrão na home_page()

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

    # Adicionar opção de logout no sidebar
    with st.sidebar:
        if st.button("Logout"):
            # Reset all home page related session state variables
            keys_to_reset = [
                'home_page_initialized'
            ]
            for key in keys_to_reset:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.logged_in = False
            st.success("Desconectado com sucesso!")
            st.experimental_rerun()
