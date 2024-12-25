import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
import bcrypt
from dotenv import load_dotenv
import os

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

####################
# Configurações
####################
# Configurar página
st.set_page_config(
    page_title="Boituva Beach Club",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

def run_query(query, values=None, fetch=True):
    """
    Executa uma consulta de leitura (SELECT) e retorna os dados obtidos.
    """
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values or ())
            if fetch:
                return cursor.fetchall()
            else:
                conn.commit()
                return None
    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"Erro ao executar a consulta: {e}")
        return []
    finally:
        if conn:
            conn.close()

def run_insert(query, values):
    """
    Executa uma consulta de inserção, atualização ou deleção (INSERT, UPDATE ou DELETE).
    """
    return run_query(query, values, fetch=False)

#####################
# Funções Auxiliares
#####################
def format_currency(value):
    """
    Formata um número como moeda brasileira (R$).
    """
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def display_table(data, columns, title):
    """
    Exibe uma tabela formatada no Streamlit.
    """
    if data:
        df = pd.DataFrame(data, columns=columns)
        st.table(df)
    else:
        st.info(f"Nenhum dado encontrado para {title}.")

def load_image(url):
    """
    Carrega uma imagem a partir de uma URL.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except requests.exceptions.RequestException:
        st.error("Falha ao carregar o logotipo.")
        return None

#####################
# Data Loading
#####################
@st.cache_data
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
            menu_title="Menu Principal",
            options=["Home", "Orders", "Products", "Stock", "Clients", "Nota Fiscal"],
            icons=["house", "file-text", "box", "list-task", "people", "receipt"],
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
        st.markdown("---")
        if st.session_state.get("logged_in"):
            if st.button("Logout"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.success("Desconectado com sucesso!")
                st.experimental_rerun()
    return selected

#####################
# Home Page
#####################
def home_page():
    st.title("🎾 Boituva Beach Club 🎾")
    st.write("📍 Av. Do Trabalhador, 1879 🏆 5° Open BBC")
    
    # Somente usuários admin podem ver os resumos
    if st.session_state.get("username") == "admin":
        # 1. Open Orders Summary
        st.header("📊 Open Orders Summary")
        open_orders_query = """
            SELECT "Cliente", SUM("total") as Total
            FROM public.vw_pedido_produto
            WHERE status = %s
            GROUP BY "Cliente"
            ORDER BY SUM("total") DESC;
        """
        open_orders_data = run_query(open_orders_query, ('em aberto',))
        if open_orders_data:
            df_open_orders = pd.DataFrame(open_orders_data, columns=["Client", "Total"])
            df_open_orders["Total_display"] = df_open_orders["Total"].apply(format_currency)
            st.table(df_open_orders[["Client", "Total_display"]])
            total_open = df_open_orders["Total"].sum()
            st.markdown(f"**Total Geral (Open Orders):** {format_currency(total_open)}")
        else:
            st.info("Nenhum pedido em aberto encontrado.")
        
        st.markdown("---")
        
        # 2. Closed Orders Summary
        st.header("📊 Closed Orders Summary")
        closed_orders_query = """
            SELECT DATE("Data") as Date, SUM("total") as Total
            FROM public.vw_pedido_produto
            WHERE status != %s
            GROUP BY DATE("Data")
            ORDER BY SUM("total") DESC;
        """
        closed_orders_data = run_query(closed_orders_query, ('em aberto',))
        if closed_orders_data:
            df_closed_orders = pd.DataFrame(closed_orders_data, columns=["Date", "Total"])
            df_closed_orders["Total_display"] = df_closed_orders["Total"].apply(format_currency)
            df_closed_orders["Date"] = pd.to_datetime(df_closed_orders["Date"]).dt.strftime('%Y-%m-%d')
            st.table(df_closed_orders[["Date", "Total_display"]])
            total_closed = df_closed_orders["Total"].sum()
            st.markdown(f"**Total Geral (Closed Orders):** {format_currency(total_closed)}")
        else:
            st.info("Nenhum pedido fechado encontrado.")
        
        st.markdown("---")
        
        # 3. Stock vs. Orders Summary
        st.header("📦 Stock vs. Orders Summary")
        stock_vs_orders_query = """
            SELECT product, stock_quantity, orders_quantity, total_in_stock
            FROM public.vw_stock_vs_orders_summary
        """
        stock_vs_orders_data = run_query(stock_vs_orders_query)
        if stock_vs_orders_data:
            df_stock_vs_orders = pd.DataFrame(
                stock_vs_orders_data, 
                columns=["Product", "Stock Quantity", "Orders Quantity", "Total in Stock"]
            )
            st.dataframe(df_stock_vs_orders)
        else:
            st.info("Não há dados na view vw_stock_vs_orders_summary.")
        
        st.markdown("---")
        
        # 4. Total Sold by Product
        st.header("📈 Total Sold by Product")
        total_sold_query = """
            SELECT "Produto", total_sold
            FROM public.vw_total_sold
            ORDER BY total_sold DESC;
        """
        total_sold_data = run_query(total_sold_query)
        if total_sold_data:
            df_total_sold = pd.DataFrame(total_sold_data, columns=["Product", "Total Sold"])
            st.table(df_total_sold)
        else:
            st.info("Nenhum produto vendido encontrado.")
        
        st.markdown("---")
        
        # 5. Sum by Client
        st.header("👥 Sum by Client")
        client_sum_query = """
            SELECT "Cliente", total_geral
            FROM public.vw_cliente_sum_total;
        """
        client_sum_data = run_query(client_sum_query)
        if client_sum_data:
            df_client_sum = pd.DataFrame(client_sum_data, columns=["Client", "Total Geral"])
            st.table(df_client_sum)
        else:
            st.info("Nenhum dado encontrado na vw_cliente_sum_total.")
        
        st.markdown("---")
        
        # 6. Sum by Payment Type
        st.header("💳 Sum by Payment Type")
        payment_type_query = """
            SELECT payment_type, total_sold
            FROM public.vw_total_por_tipo_pagamento;
        """
        payment_type_data = run_query(payment_type_query)
        if payment_type_data:
            df_payment_type = pd.DataFrame(payment_type_data, columns=["Payment Type", "Total Sold"])
            st.table(df_payment_type)
        else:
            st.info("Nenhum dado encontrado na vw_total_por_tipo_pagamento.")
    else:
        st.info("Bem-vindo(a) ao Boituva Beach Club!")

#####################
# Orders Page
#####################
def orders_page():
    st.title("📋 Orders")
    st.subheader("Register a New Order")
    
    product_data = st.session_state.data.get("products", [])
    product_list = ["Selecione um produto"] + [row[1] for row in product_data] if product_data else ["No products available"]
    
    with st.form(key='order_form'):
        clients = run_query('SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;')
        customer_list = ["Selecione um cliente"] + [row[0] for row in clients] if clients else ["No clients available"]
        customer_name = st.selectbox("Customer Name", customer_list, index=0)
        product = st.selectbox("Product", product_list, index=0)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Register Order")
    
    if submit_button:
        if customer_name != "Selecione um cliente" and product != "Selecione um produto" and quantity > 0:
            insert_order_query = """
                INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", status)
                VALUES (%s, %s, %s, %s, 'em aberto');
            """
            timestamp = datetime.now()
            success = run_insert(insert_order_query, (customer_name, product, quantity, timestamp))
            if success:
                st.success("Order registered successfully!")
                refresh_data()
            else:
                st.error("Failed to register the order.")
        else:
            st.warning("Please fill in all fields correctly.")
    
    # Exibir todas as ordens
    st.header("🗂️ All Orders")
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        df_orders = pd.DataFrame(orders_data, columns=["Client", "Product", "Quantity", "Date", "Status"])
        st.dataframe(df_orders, use_container_width=True)
        
        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("🔄 Edit or Delete an Existing Order")
            df_orders["unique_key"] = df_orders.apply(
                lambda row: f"{row['Client']}|{row['Product']}|{row['Date']}",
                axis=1
            )
            unique_keys = df_orders["unique_key"].unique().tolist()
            selected_key = st.selectbox("Select an order to edit/delete:", [""] + unique_keys)
    
            if selected_key and selected_key != "":
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
                            "Quantity",
                            min_value=1,
                            step=1,
                            value=int(original_quantity)
                        )
                        status_options = ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix", "Received - Cash"]
                        edit_status = st.selectbox("Status", status_options, index=status_options.index(original_status) if original_status in status_options else 0)
    
                        update_button = st.form_submit_button(label="Update Order")
                        delete_button = st.form_submit_button(label="Delete Order")
    
                    if delete_button:
                        delete_order_query = """
                            DELETE FROM public.tb_pedido
                            WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                        """
                        success = run_insert(delete_order_query, (original_client, original_product, original_date))
                        if success:
                            st.success("Order deleted successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to delete the order.")
    
                    if update_button:
                        update_order_query = """
                            UPDATE public.tb_pedido
                            SET "Produto" = %s, "Quantidade" = %s, status = %s
                            WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                        """
                        success = run_insert(update_order_query, (
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
    st.title("📦 Products")
    st.subheader("Add a New Product")
    
    with st.form(key='product_form'):
        supplier = st.text_input("Supplier", max_chars=100)
        product = st.text_input("Product", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        unit_value = st.number_input("Unit Value (R$)", min_value=0.0, step=0.01, format="%.2f")
        creation_date = st.date_input("Creation Date", value=datetime.now().date())
        submit_product = st.form_submit_button(label="Insert Product")
    
    if submit_product:
        if supplier and product and quantity > 0 and unit_value >= 0:
            insert_product_query = """
                INSERT INTO public.tb_products (supplier, product, quantity, unit_value, total_value, creation_date)
                VALUES (%s, %s, %s, %s, %s, %s);
            """
            total_value = quantity * unit_value
            success = run_insert(insert_product_query, (supplier, product, quantity, unit_value, total_value, creation_date))
            if success:
                st.success("Product added successfully!")
                refresh_data()
            else:
                st.error("Failed to add the product.")
        else:
            st.warning("Please fill in all fields correctly.")
    
    # Exibir todos os produtos
    st.header("🗂️ All Products")
    products_data = st.session_state.data.get("products", [])
    if products_data:
        df_products = pd.DataFrame(products_data, columns=["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"])
        st.dataframe(df_products, use_container_width=True)
        
        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("🔄 Edit or Delete an Existing Product")
            df_products["unique_key"] = df_products.apply(
                lambda row: f"{row['Supplier']}|{row['Product']}|{row['Creation Date']}",
                axis=1
            )
            unique_keys = df_products["unique_key"].unique().tolist()
            selected_key = st.selectbox("Select a product to edit/delete:", [""] + unique_keys)
    
            if selected_key and selected_key != "":
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
                        edit_product_name = st.text_input("Product", value=original_product, max_chars=100)
                        edit_quantity = st.number_input(
                            "Quantity",
                            min_value=1,
                            step=1,
                            value=int(original_quantity)
                        )
                        edit_unit_value = st.number_input(
                            "Unit Value (R$)",
                            min_value=0.0,
                            step=0.01,
                            format="%.2f",
                            value=float(original_unit_value)
                        )
                        edit_creation_date = st.date_input("Creation Date", value=original_creation_date)
    
                        update_button = st.form_submit_button(label="Update Product")
                        delete_button = st.form_submit_button(label="Delete Product")
    
                    if delete_button:
                        delete_product_query = """
                            DELETE FROM public.tb_products
                            WHERE supplier = %s AND product = %s AND creation_date = %s;
                        """
                        success = run_insert(delete_product_query, (original_supplier, original_product, original_creation_date))
                        if success:
                            st.success("Product deleted successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to delete the product.")
    
                    if update_button:
                        update_product_query = """
                            UPDATE public.tb_products
                            SET supplier = %s,
                                product = %s,
                                quantity = %s,
                                unit_value = %s,
                                total_value = %s,
                                creation_date = %s
                            WHERE supplier = %s AND product = %s AND creation_date = %s;
                        """
                        new_total_value = edit_quantity * edit_unit_value
                        success = run_insert(update_product_query, (
                            edit_supplier, edit_product_name, edit_quantity, edit_unit_value, new_total_value, edit_creation_date,
                            original_supplier, original_product, original_creation_date
                        ))
                        if success:
                            st.success("Product updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the product.")
    else:
        st.info("No products found.")

#####################
# Stock Page
#####################
def stock_page():
    st.title("📦 Stock")
    st.subheader("Add a New Stock Record")
    st.write("""
    Esta página foi projetada para registrar **apenas entradas de produtos no estoque** de forma prática e organizada.  
    Com este sistema, você poderá monitorar todas as adições ao estoque com maior controle e rastreabilidade.  
    O registro exclusivo de entradas permite garantir uma gestão eficiente, evitando inconsistências e oferecendo um histórico claro de movimentações no estoque.  
    """)
    
    product_data = run_query("SELECT product FROM public.tb_products ORDER BY product;")
    product_list = ["Selecione um produto"] + [row[0] for row in product_data] if product_data else ["No products available"]
    
    with st.form(key='stock_form'):
        product = st.selectbox("Product", product_list, index=0)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        transaction = st.selectbox("Transaction Type", ["Entrada"])
        date = st.date_input("Date", value=datetime.now().date())
        submit_stock = st.form_submit_button(label="Register")
    
    if submit_stock:
        if product != "Selecione um produto" and quantity > 0:
            insert_stock_query = """
                INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Transação", "Data")
                VALUES (%s, %s, %s, %s);
            """
            current_datetime = datetime.combine(date, datetime.min.time())
            success = run_insert(insert_stock_query, (product, quantity, transaction, current_datetime))
            if success:
                st.success("Stock record added successfully!")
                refresh_data()
            else:
                st.error("Failed to add stock record.")
        else:
            st.warning("Please select a product and enter a quantity greater than 0.")
    
    # Exibir todos os registros de estoque
    st.header("🗂️ All Stock Records")
    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        df_stock = pd.DataFrame(stock_data, columns=["Product", "Quantity", "Transaction", "Date"])
        st.dataframe(df_stock, use_container_width=True)
        
        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("🔄 Edit or Delete an Existing Stock Record")
            df_stock["unique_key"] = df_stock.apply(
                lambda row: f"{row['Product']}|{row['Transaction']}|{row['Date']}",
                axis=1
            )
            unique_keys = df_stock["unique_key"].unique().tolist()
            selected_key = st.selectbox("Select a stock record to edit/delete:", [""] + unique_keys)
    
            if selected_key and selected_key != "":
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
                        edit_date = st.date_input("Date", value=datetime.strptime(original_date, '%Y-%m-%d').date())
    
                        update_button = st.form_submit_button(label="Update Stock Record")
                        delete_button = st.form_submit_button(label="Delete Stock Record")
    
                    if delete_button:
                        delete_stock_query = """
                            DELETE FROM public.tb_estoque
                            WHERE "Produto" = %s AND "Transação" = %s AND "Data" = %s;
                        """
                        success = run_insert(delete_stock_query, (original_product, original_transaction, original_date))
                        if success:
                            st.success("Stock record deleted successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to delete the stock record.")
    
                    if update_button:
                        update_stock_query = """
                            UPDATE public.tb_estoque
                            SET "Produto" = %s, "Quantidade" = %s, "Transação" = %s, "Data" = %s
                            WHERE "Produto" = %s AND "Transação" = %s AND "Data" = %s;
                        """
                        new_date = datetime.combine(edit_date, datetime.min.time())
                        success = run_insert(update_stock_query, (
                            edit_product, edit_quantity, edit_transaction, new_date,
                            original_product, original_transaction, original_date
                        ))
                        if success:
                            st.success("Stock record updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the stock record.")
    else:
        st.info("No stock records found.")

#####################
# Clients Page
#####################
def clients_page():
    st.title("👥 Clients")
    st.subheader("Register a New Client")
    
    with st.form(key='client_form'):
        full_name = st.text_input("Full Name", max_chars=100)
        birth_date = st.date_input("Birth Date", value=datetime(2000, 1, 1).date())
        gender = st.selectbox("Gender", ["Man", "Woman", "Other"])
        phone = st.text_input("Phone", max_chars=15)
        email = st.text_input("Email", max_chars=100)
        address = st.text_area("Address", height=100)
        submit_client = st.form_submit_button(label="Register New Client")
    
    if submit_client:
        if full_name and email and phone and address:
            # Verificar se o email já está cadastrado
            check_email_query = """
                SELECT email FROM public.tb_clientes WHERE email = %s;
            """
            existing_email = run_query(check_email_query, (email,))
            if existing_email:
                st.error("Email já cadastrado. Por favor, use outro.")
            else:
                insert_client_query = """
                    INSERT INTO public.tb_clientes (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
                """
                success = run_insert(insert_client_query, (
                    full_name, birth_date, gender, phone, email, address
                ))
                if success:
                    st.success("Client registered successfully!")
                    refresh_data()
                else:
                    st.error("Failed to register the client.")
        else:
            st.warning("Please fill in all required fields (Full Name, Email, Phone, Address).")
    
    # Exibir todos os clientes
    st.header("🗂️ All Clients")
    clients_data = run_query("""
        SELECT nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro
        FROM public.tb_clientes
        ORDER BY data_cadastro DESC;
    """)
    if clients_data:
        df_clients = pd.DataFrame(clients_data, columns=["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"])
        st.dataframe(df_clients, use_container_width=True)
        
        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("🔄 Edit or Delete an Existing Client")
            client_emails = df_clients["Email"].unique().tolist()
            selected_email = st.selectbox("Select a client by Email:", [""] + client_emails)
    
            if selected_email and selected_email != "":
                selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
                original_name = selected_client_row["Full Name"]
                original_birth_date = selected_client_row["Birth Date"]
                original_gender = selected_client_row["Gender"]
                original_phone = selected_client_row["Phone"]
                original_address = selected_client_row["Address"]
    
                with st.form(key='edit_client_form'):
                    edit_name = st.text_input("Full Name", value=original_name, max_chars=100)
                    edit_birth_date = st.date_input("Birth Date", value=original_birth_date)
                    edit_gender = st.selectbox("Gender", ["Man", "Woman", "Other"], index=["Man", "Woman", "Other"].index(original_gender) if original_gender in ["Man", "Woman", "Other"] else 0)
                    edit_phone = st.text_input("Phone", value=original_phone, max_chars=15)
                    edit_address = st.text_area("Address", value=original_address, height=100)
    
                    update_button = st.form_submit_button(label="Update Client")
                    delete_button = st.form_submit_button(label="Delete Client")
    
                if delete_button:
                    delete_client_query = """
                        DELETE FROM public.tb_clientes
                        WHERE email = %s;
                    """
                    success = run_insert(delete_client_query, (selected_email,))
                    if success:
                        st.success("Client deleted successfully!")
                        refresh_data()
                    else:
                        st.error("Failed to delete the client.")
    
                if update_button:
                    if edit_name and edit_phone and edit_address:
                        update_client_query = """
                            UPDATE public.tb_clientes
                            SET nome_completo = %s,
                                data_nascimento = %s,
                                genero = %s,
                                telefone = %s,
                                endereco = %s
                            WHERE email = %s;
                        """
                        success = run_insert(update_client_query, (
                            edit_name, edit_birth_date, edit_gender, edit_phone, edit_address, selected_email
                        ))
                        if success:
                            st.success("Client updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the client.")
                    else:
                        st.warning("Please fill in all required fields (Full Name, Phone, Address).")
    else:
        st.info("No clients found.")

#####################
# Invoice Page
#####################
def invoice_page():
    st.title("🧾 Nota Fiscal")
    
    open_clients_query = 'SELECT DISTINCT "Cliente" FROM public.vw_pedido_produto WHERE status = %s;'
    open_clients = run_query(open_clients_query, ('em aberto',))
    client_list = [row[0] for row in open_clients] if open_clients else []
    
    selected_client = st.selectbox("Selecione um Cliente", [""] + client_list)
    
    if selected_client:
        invoice_query = """
            SELECT "Produto", "Quantidade", "total"
            FROM public.vw_pedido_produto
            WHERE "Cliente" = %s AND status = %s;
        """
        invoice_data = run_query(invoice_query, (selected_client, 'em aberto'))
        
        if invoice_data:
            df_invoice = pd.DataFrame(invoice_data, columns=["Produto", "Quantidade", "Total"])
            st.subheader("🧾 Invoice Preview")
            generate_invoice(df_invoice, selected_client)
            
            st.subheader("💳 Process Payment")
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
            st.info("Não há pedidos em aberto para o cliente selecionado.")
    else:
        st.warning("Por favor, selecione um cliente.")

def process_payment(client, payment_status):
    update_payment_query = """
        UPDATE public.tb_pedido
        SET status = %s, "Data" = CURRENT_TIMESTAMP
        WHERE "Cliente" = %s AND status = 'em aberto';
    """
    success = run_insert(update_payment_query, (payment_status, client))
    if success:
        st.success(f"Status atualizado para: {payment_status}")
        refresh_data()
    else:
        st.error("Erro ao atualizar o status.")

def generate_invoice(df, client):
    company = "Boituva Beach Club"
    address = "Avenida do Trabalhador, 1879"
    city = "Boituva - SP 18552-100"
    cnpj = "05.365.434/0001-09"
    phone = "(13) 99154-5481"
    
    invoice = []
    invoice.append("==================================================")
    invoice.append("                      NOTA FISCAL                ")
    invoice.append("==================================================")
    invoice.append(f"Empresa: {company}")
    invoice.append(f"Endereço: {address}")
    invoice.append(f"Cidade: {city}")
    invoice.append(f"CNPJ: {cnpj}")
    invoice.append(f"Telefone: {phone}")
    invoice.append("--------------------------------------------------")
    invoice.append(f"Cliente: {client}")
    invoice.append("--------------------------------------------------")
    invoice.append("DESCRIÇÃO             QTD     TOTAL")
    invoice.append("--------------------------------------------------")
    
    grouped_df = df.groupby('Produto').agg({'Quantidade': 'sum', 'Total': 'sum'}).reset_index()
    total_general = grouped_df['Total'].sum()
    
    for _, row in grouped_df.iterrows():
        description = f"{row['Produto'][:20]:<20}"  # Limita a 20 caracteres
        quantity = f"{int(row['Quantidade']):>5}"
        total = format_currency(row['Total'])
        invoice.append(f"{description} {quantity} {total}")
    
    invoice.append("--------------------------------------------------")
    formatted_total = format_currency(total_general)
    invoice.append(f"{'TOTAL GERAL:':>30} {formatted_total:>10}")
    invoice.append("==================================================")
    invoice.append("OBRIGADO PELA SUA PREFERÊNCIA!")
    invoice.append("==================================================")
    
    st.text("\n".join(invoice))

#####################
# Login Page
#####################
def login_page():
    st.markdown(
        """
        <style>
        body {
            background-color: white;
        }
        .block-container {
            padding-top: 50px;
            padding-bottom: 50px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # Carregar e exibir o logotipo
    logo_url = "https://res.cloudinary.com/lptennis/image/upload/v1657233475/kyz4k7fcptxt7x7mu9qu.jpg"
    logo = load_image(logo_url)
    if logo:
        st.image(logo, width=200)
    
    st.title("🔒 Login")
    st.write("Por favor, insira suas credenciais para acessar o aplicativo.")
    
    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button(label="Login")
    
    if submit_login:
        if username and password:
            login_query = """
                SELECT "password" FROM public.username_login
                WHERE username = %s;
            """
            login_data = run_query(login_query, (username,))
            if login_data:
                stored_hashed_password = login_data[0][0]
                if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password.encode('utf-8')):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success("Login bem-sucedido!")
                    st.experimental_rerun()
                else:
                    st.error("Nome de usuário ou senha incorretos.")
            else:
                st.error("Nome de usuário ou senha incorretos.")
        else:
            st.warning("Por favor, preencha ambos os campos.")

    st.markdown("---")
    
    st.subheader("Registrar um Novo Usuário")
    with st.form(key='register_form'):
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        new_email = st.text_input("Email")
        submit_register = st.form_submit_button(label="Register")
    
    if submit_register:
        if new_username and new_password and new_email:
            # Verificar se o usuário já existe
            check_user_query = """
                SELECT username FROM public.username_login WHERE username = %s;
            """
            existing_user = run_query(check_user_query, (new_username,))
            if existing_user:
                st.error("Username já existe. Por favor, escolha outro.")
            else:
                # Hash da senha
                hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                # Inserir no banco de dados
                register_query = """
                    INSERT INTO public.username_login (username, "password", email)
                    VALUES (%s, %s, %s);
                """
                success = run_insert(register_query, (new_username, hashed_password, new_email))
                if success:
                    st.success("Usuário registrado com sucesso! Você pode agora fazer login.")
                else:
                    st.error("Falha ao registrar o usuário. Por favor, tente novamente.")
        else:
            st.warning("Por favor, preencha todos os campos.")

#####################
# Initialization
#####################
def initialize_session_state():
    """
    Inicializa o estado da sessão para evitar erros.
    """
    if 'data' not in st.session_state:
        st.session_state.data = load_all_data()
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""

# Inicializar estado da sessão
initialize_session_state()

#####################
# Main
#####################
def main():
    if not st.session_state.logged_in:
        login_page()
    else:
        selected_page = sidebar_navigation()
        
        # Atualizar dados quando a página selecionada muda
        if 'current_page' not in st.session_state:
            st.session_state.current_page = selected_page
        elif selected_page != st.session_state.current_page:
            refresh_data()
            st.session_state.current_page = selected_page
        
        # Rotas das páginas
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

# Executar o aplicativo
if __name__ == "__main__":
    main()
