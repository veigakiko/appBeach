import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime, date
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
from dotenv import load_dotenv
import os

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

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
    Executa uma consulta de inserção, atualização ou deleção (INSERT, UPDATE ou DELETE).
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
            icons=["house", "file-text", "box", "list-task", "layers", "receipt"],
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
    st.title("🎾 Boituva Beach Club 🎾")
    st.write("📍 Av. Do Trabalhador, 1879 🏆 5° Open BBC")
    
    # Só exibe estes resumos se o user for admin
    if st.session_state.get("username") == "admin":
        ############################
        # Display Open Orders Summary
        ############################
        st.markdown("**Resumo de Pedidos Abertos**")
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
            df_open_orders_display["Total_display"] = df_open_orders_display["Total"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            df_display_open = df_open_orders_display[["Client", "Total_display"]]
            st.table(df_display_open)
            formatted_total_open = f"R$ {total_open:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            st.markdown(f"**Total Geral (Pedidos Abertos):** {formatted_total_open}")
        else:
            st.info("Nenhum pedido em aberto encontrado.")

        ############################
        # Display Closed Orders Summary
        ############################
        st.markdown("**Resumo de Pedidos Fechados**")
        closed_orders_query = """
        SELECT DATE("Data") as Date, SUM("total") as Total
        FROM public.vw_pedido_produto
        WHERE status != %s
        GROUP BY DATE("Data")
        ORDER BY DATE("Data") DESC;
        """
        closed_orders_data = run_query(closed_orders_query, ('em aberto',))
        if closed_orders_data:
            df_closed_orders_display = pd.DataFrame(closed_orders_data, columns=["Date", "Total"])
            total_closed = df_closed_orders_display["Total"].sum()
            df_closed_orders_display["Total_display"] = df_closed_orders_display["Total"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            df_closed_orders_display["Date"] = pd.to_datetime(df_closed_orders_display["Date"]).dt.strftime('%Y-%m-%d')
            df_display_closed = df_closed_orders_display[["Date", "Total_display"]]
            st.table(df_display_closed)
            formatted_total_closed = f"R$ {total_closed:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            st.markdown(f"**Total Geral (Pedidos Fechados):** {formatted_total_closed}")
        else:
            st.info("Nenhum pedido fechado encontrado.")

        # EXEMPLO ADICIONAL: Resumo Estoque vs Pedidos (se aplicável)
        st.markdown("## Resumo Estoque vs Pedidos")
        try:
            stock_vs_orders_query = """
                SELECT product, stock_quantity, orders_quantity, total_in_stock
                FROM public.vw_stock_vs_orders_summary
            """
            stock_vs_orders_data = run_query(stock_vs_orders_query)
            if stock_vs_orders_data:
                df_stock_vs_orders = pd.DataFrame(
                    stock_vs_orders_data, 
                    columns=["Product", "Stock_Quantity", "Orders_Quantity", "Total_in_STOCK"]
                )
                st.dataframe(df_stock_vs_orders)
            else:
                st.info("Não há dados na view vw_stock_vs_orders_summary.")
        except Exception as e:
            st.error(f"Erro ao gerar o resumo Estoque vs Pedidos: {e}")

#####################
# Orders Page
#####################
def orders_page():
    st.title("Orders")
    st.subheader("Registrar um Novo Pedido")

    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["Sem produtos disponíveis"]

    with st.form(key='order_form'):
        clientes = run_query('SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;')
        customer_list = [""] + [row[0] for row in clientes]
        customer_name = st.selectbox("Nome do Cliente", customer_list, index=0)
        product = st.selectbox("Produto", product_list, index=0)
        quantity = st.number_input("Quantidade", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Registrar Pedido")

    if submit_button:
        if customer_name and product and quantity > 0:
            query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", status)
            VALUES (%s, %s, %s, %s, 'em aberto');
            """
            timestamp = datetime.now()
            success = run_insert(query, (customer_name, product, quantity, timestamp))
            if success:
                st.success("Pedido registrado com sucesso!")
                refresh_data()
            else:
                st.error("Falha ao registrar o pedido.")
        else:
            st.warning("Por favor, preencha todos os campos corretamente.")

    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("Todos os Pedidos")
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        st.dataframe(df_orders, use_container_width=True)

        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Editar ou Excluir um Pedido Existente")
            df_orders["unique_key"] = df_orders.apply(
                lambda row: f"{row['Client']}|{row['Product']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
                axis=1
            )
            unique_keys = df_orders["unique_key"].unique().tolist()
            selected_key = st.selectbox("Selecione um pedido para editar/excluir:", [""] + unique_keys)

            if selected_key:
                matching_rows = df_orders[df_orders["unique_key"] == selected_key]
                if len(matching_rows) > 1:
                    st.warning("Vários pedidos encontrados com a mesma chave. Por favor, refine sua seleção.")
                else:
                    selected_row = matching_rows.iloc[0]
                    original_client = selected_row["Client"]
                    original_product = selected_row["Product"]
                    original_quantity = selected_row["Quantity"]
                    original_date = selected_row["Date"]
                    original_status = selected_row["Status"]

                    with st.form(key='edit_order_form'):
                        edit_product = st.selectbox(
                            "Produto",
                            product_list,
                            index=product_list.index(original_product) if original_product in product_list else 0
                        )
                        edit_quantity = st.number_input(
                            "Quantidade",
                            min_value=1,
                            step=1,
                            value=int(original_quantity)
                        )
                        edit_status_list = ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix", "Received - Cash"]
                        if original_status in edit_status_list:
                            edit_status_index = edit_status_list.index(original_status)
                        else:
                            edit_status_index = 0
                        edit_status = st.selectbox("Status", edit_status_list, index=edit_status_index)

                        update_button = st.form_submit_button(label="Atualizar Pedido")
                        delete_button = st.form_submit_button(label="Excluir Pedido")

                    if delete_button:
                        delete_query = """
                        DELETE FROM public.tb_pedido
                        WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                        """
                        success = run_insert(delete_query, (
                            original_client, original_product, original_date
                        ))
                        if success:
                            st.success("Pedido excluído com sucesso!")
                            refresh_data()
                        else:
                            st.error("Falha ao excluir o pedido.")

                    if update_button:
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
                            st.success("Pedido atualizado com sucesso!")
                            refresh_data()
                        else:
                            st.error("Falha ao atualizar o pedido.")
    else:
        st.info("Nenhum pedido encontrado.")

#####################
# Products Page
#####################
def products_page():
    st.title("Products")

    st.subheader("Adicionar um Novo Produto")
    with st.form(key='product_form'):
        supplier = st.text_input("Fornecedor", max_chars=100)
        product = st.text_input("Produto", max_chars=100)
        quantity = st.number_input("Quantidade", min_value=1, step=1)
        unit_value = st.number_input("Valor Unitário", min_value=0.0, step=0.01, format="%.2f")
        creation_date = st.date_input("Data de Criação")
        submit_product = st.form_submit_button(label="Inserir Produto")

    if submit_product:
        if supplier and product and quantity > 0 and unit_value >= 0:
            query = """
            INSERT INTO public.tb_products (supplier, product, quantity, unit_value, total_value, creation_date)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            total_value = quantity * unit_value
            success = run_insert(query, (supplier, product, quantity, unit_value, total_value, creation_date))
            if success:
                st.success("Produto adicionado com sucesso!")
                refresh_data()
            else:
                st.error("Falha ao adicionar o produto.")
        else:
            st.warning("Por favor, preencha todos os campos corretamente.")

    products_data = st.session_state.data.get("products", [])
    if products_data:
        st.subheader("Todos os Produtos")
        columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
        df_products = pd.DataFrame(products_data, columns=columns)

        st.write("Colunas em df_products:", df_products.columns.tolist())
        st.dataframe(df_products, use_container_width=True)

        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Editar ou Excluir um Produto Existente")
            df_products["unique_key"] = df_products.apply(
                lambda row: f"{row['Supplier']}|{row['Product']}|{row['Creation Date'].strftime('%Y-%m-%d')}",
                axis=1
            )
            unique_keys = df_products["unique_key"].unique().tolist()
            selected_key = st.selectbox("Selecione um produto para editar/excluir:", [""] + unique_keys)

            if selected_key:
                matching_rows = df_products[df_products["unique_key"] == selected_key]
                if len(matching_rows) > 1:
                    st.warning("Vários produtos encontrados com a mesma chave. Por favor, refine sua seleção.")
                else:
                    selected_row = matching_rows.iloc[0]
                    original_supplier = selected_row["Supplier"]
                    original_product = selected_row["Product"]
                    original_quantity = selected_row["Quantity"]
                    original_unit_value = selected_row["Unit Value"]
                    original_creation_date = selected_row["Creation Date"]

                    with st.form(key='edit_product_form'):
                        edit_supplier = st.text_input("Fornecedor", value=original_supplier, max_chars=100)
                        edit_product = st.text_input("Produto", value=original_product, max_chars=100)
                        edit_quantity = st.number_input(
                            "Quantidade",
                            min_value=1,
                            step=1,
                            value=int(original_quantity)
                        )
                        edit_unit_value = st.number_input(
                            "Valor Unitário",
                            min_value=0.0,
                            step=0.01,
                            format="%.2f",
                            value=float(original_unit_value)
                        )
                        edit_creation_date = st.date_input("Data de Criação", value=original_creation_date)

                        update_button = st.form_submit_button(label="Atualizar Produto")
                        delete_button = st.form_submit_button(label="Excluir Produto")

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
                            st.success("Produto atualizado com sucesso!")
                            refresh_data()
                        else:
                            st.error("Falha ao atualizar o produto.")

                    if delete_button:
                        confirm = st.checkbox("Tem certeza de que deseja excluir este produto?")
                        if confirm:
                            delete_query = """
                            DELETE FROM public.tb_products
                            WHERE supplier = %s AND product = %s AND creation_date = %s;
                            """
                            success = run_insert(delete_query, (original_supplier, original_product, original_creation_date))
                            if success:
                                st.success("Produto excluído com sucesso!")
                                refresh_data()
                            else:
                                st.error("Falha ao excluir o produto.")
    else:
        st.info("Nenhum produto encontrado.")

#####################
# Stock Page
#####################
def stock_page():
    st.title("Stock")
    st.subheader("Adicionar um Novo Registro de Estoque")
    st.write("""
    Esta página foi projetada para registrar **apenas entradas de produtos no estoque** de forma prática e organizada.  
    Com este sistema, você poderá monitorar todas as adições ao estoque com maior controle e rastreabilidade.  
    O registro exclusivo de entradas permite garantir uma gestão eficiente, evitando inconsistências e oferecendo um histórico claro de movimentações no estoque.  
    """)

    product_data = run_query("SELECT product FROM public.tb_products ORDER BY product;")
    product_list = [row[0] for row in product_data] if product_data else ["Sem produtos disponíveis"]

    with st.form(key='stock_form'):
        product = st.selectbox("Produto", product_list)
        quantity = st.number_input("Quantidade", min_value=1, step=1)
        transaction = st.selectbox("Tipo de Transação", ["Entrada"])
        date_input = st.date_input("Data", value=datetime.now().date())
        submit_stock = st.form_submit_button(label="Registrar")

    if submit_stock:
        if product and quantity > 0:
            current_datetime = datetime.combine(date_input, datetime.min.time())
            query = """
            INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Transação", "Data")
            VALUES (%s, %s, %s, %s);
            """
            success = run_insert(query, (product, quantity, transaction, current_datetime))
            if success:
                st.success("Registro de estoque adicionado com sucesso!")
                refresh_data()
            else:
                st.error("Falha ao adicionar o registro de estoque.")
        else:
            st.warning("Por favor, selecione um produto e insira uma quantidade maior que 0.")

    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        st.subheader("Todos os Registros de Estoque")
        columns = ["Product", "Quantity", "Transaction", "Date"]
        df_stock = pd.DataFrame(stock_data, columns=columns)
        st.write("Colunas em df_stock:", df_stock.columns.tolist())
        st.dataframe(df_stock, use_container_width=True)

        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Editar ou Excluir um Registro de Estoque Existente")
            df_stock["unique_key"] = df_stock.apply(
                lambda row: f"{row['Product']}|{row['Transaction']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
                axis=1
            )
            unique_keys = df_stock["unique_key"].unique().tolist()
            selected_key = st.selectbox("Selecione um registro de estoque para editar/excluir:", [""] + unique_keys)

            if selected_key:
                matching_rows = df_stock[df_stock["unique_key"] == selected_key]
                if len(matching_rows) > 1:
                    st.warning("Vários registros de estoque encontrados com a mesma chave. Por favor, refine sua seleção.")
                else:
                    selected_row = matching_rows.iloc[0]
                    original_product = selected_row["Product"]
                    original_quantity = selected_row["Quantity"]
                    original_transaction = selected_row["Transaction"]
                    original_date = selected_row["Date"]

                    with st.form(key='edit_stock_form'):
                        edit_product = st.selectbox(
                            "Produto",
                            product_list,
                            index=product_list.index(original_product) if original_product in product_list else 0
                        )
                        edit_quantity = st.number_input(
                            "Quantidade", min_value=1, step=1, value=int(original_quantity)
                        )
                        edit_transaction = st.selectbox(
                            "Tipo de Transação",
                            ["Entrada", "Saída"],
                            index=["Entrada", "Saída"].index(original_transaction) if original_transaction in ["Entrada", "Saída"] else 0
                        )
                        edit_date = st.date_input("Data", value=original_date.date())

                        update_button = st.form_submit_button(label="Atualizar Registro de Estoque")
                        delete_button = st.form_submit_button(label="Excluir Registro de Estoque")

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
                            st.success("Registro de estoque atualizado com sucesso!")
                            refresh_data()
                        else:
                            st.error("Falha ao atualizar o registro de estoque.")

                    if delete_button:
                        confirm = st.checkbox("Tem certeza de que deseja excluir este registro de estoque?")
                        if confirm:
                            delete_query = """
                            DELETE FROM public.tb_estoque
                            WHERE "Produto" = %s AND "Transação" = %s AND "Data" = %s;
                            """
                            success = run_insert(delete_query, (
                                original_product, original_transaction, original_date
                            ))
                            if success:
                                st.success("Registro de estoque excluído com sucesso!")
                                refresh_data()
                            else:
                                st.error("Falha ao excluir o registro de estoque.")
    else:
        st.info("Nenhum registro de estoque encontrado.")

#####################
# Clients Page
#####################
def clients_page():
    st.title("Clients")
    st.subheader("Registrar um Novo Cliente")

    with st.form(key='client_form'):
        nome_completo = st.text_input("Nome Completo", max_chars=100)
        submit_client = st.form_submit_button(label="Registrar Novo Cliente")

    if submit_client:
        if nome_completo:
            data_nascimento = datetime(2000, 1, 1).date()  # Placeholder
            genero = "Man"  # Placeholder
            telefone = "0000-0000"  # Placeholder
            unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
            email = f"{nome_completo.replace(' ', '_').lower()}_{unique_id}@example.com"
            endereco = "Endereço Padrão"

            query = """
            INSERT INTO public.tb_clientes 
            (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            success = run_insert(query, (nome_completo, data_nascimento, genero, telefone, email, endereco))
            if success:
                st.success("Cliente registrado com sucesso!")
                refresh_data()
        else:
            st.warning("Por favor, insira o Nome Completo.")

    # Exibir todos os clientes
    clients_data = run_query(
        "SELECT nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro FROM public.tb_clientes ORDER BY data_cadastro DESC;"
    )
    if clients_data:
        st.subheader("Todos os Clientes")
        columns = ["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"]
        df_clients = pd.DataFrame(clients_data, columns=columns)
        st.dataframe(df_clients, use_container_width=True)

        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Editar ou Excluir um Cliente Existente")
            client_emails = df_clients["Email"].unique().tolist()
            selected_email = st.selectbox("Selecione um cliente pelo Email:", [""] + client_emails)

            if selected_email:
                selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
                original_name = selected_client_row["Full Name"]

                with st.form(key='edit_client_form'):
                    edit_name = st.text_input("Nome Completo", value=original_name, max_chars=100)
                    col1, col2 = st.columns(2)
                    with col1:
                        update_button = st.form_submit_button(label="Atualizar Cliente")
                    with col2:
                        delete_button = st.form_submit_button(label="Excluir Cliente")

                if update_button:
                    if edit_name:
                        update_query = """
                        UPDATE public.tb_clientes
                        SET nome_completo = %s
                        WHERE email = %s;
                        """
                        success = run_insert(update_query, (edit_name, selected_email))
                        if success:
                            st.success("Cliente atualizado com sucesso!")
                            refresh_data()
                        else:
                            st.error("Falha ao atualizar o cliente.")
                    else:
                        st.warning("Por favor, preencha o campo Nome Completo.")

                if delete_button:
                    confirm = st.checkbox("Tem certeza de que deseja excluir este cliente?")
                    if confirm:
                        delete_query = "DELETE FROM public.tb_clientes WHERE email = %s;"
                        success = run_insert(delete_query, (selected_email,))
                        if success:
                            st.success("Cliente excluído com sucesso!")
                            refresh_data()
                        else:
                            st.error("Falha ao excluir o cliente.")
    else:
        st.info("Nenhum cliente encontrado.")

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

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("Débito", key="debit_button"):
                    process_payment(selected_client, "Received - Debited")
            with col2:
                if st.button("Crédito", key="credit_button"):
                    process_payment(selected_client, "Received - Credit")
            with col3:
                if st.button("Pix", key="pix_button"):
                    process_payment(selected_client, "Received - Pix")
            with col4:
                if st.button("Dinheiro", key="cash_button"):
                    process_payment(selected_client, "Received - Cash")
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

    grouped_df = df.groupby('Produto').agg({'Quantidade': 'sum', 'total': 'sum'}).reset_index()
    total_general = 0

    for _, row in grouped_df.iterrows():
        description = f"{row['Produto'][:20]:<20}"  # limitar a 20 caracteres
        quantity = f"{int(row['Quantidade']):>5}"
        total = row['total']
        total_general += total
        total_formatted = f"R$ {total:,.2f}".replace('.', ',')
        invoice_note.append(f"{description} {quantity} {total_formatted}")

    invoice_note.append("--------------------------------------------------")
    formatted_general_total = f"R$ {total_general:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    invoice_note.append(f"{'TOTAL GERAL:':>30} {formatted_general_total:>10}")
    invoice_note.append("==================================================")
    invoice_note.append("OBRIGADO PELA SUA PREFERÊNCIA!")
    invoice_note.append("==================================================")

    st.text("\n".join(invoice_note))

#####################
# Login Page
#####################
def login_page():
    # Link direto do vídeo hospedado no Streamable
    video_url = "https://cdn.streamable.com/video/mp4/96jd85.mp4"  # Substitua pelo link direto obtido

    # CSS personalizado para posicionar o vídeo de fundo e estilizar o formulário de login
    page_bg_video = f"""
    <style>
    /* Estilos para o vídeo de fundo */
    .background-video {{
        position: fixed;
        right: 0;
        bottom: 0;
        min-width: 100%; 
        min-height: 100%;
        z-index: -1;
        object-fit: cover; /* Garante que o vídeo cubra todo o fundo sem distorção */
    }}
    /* Container do formulário de login */
    .login-container {{
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(255, 255, 255, 0.85); /* Fundo semi-transparente para melhor legibilidade */
        padding: 40px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        max-width: 400px;
        width: 90%;
    }}
    /* Estilos para os títulos */
    .login-container h1 {{
        text-align: center;
        margin-bottom: 20px;
        color: #1b4f72;
    }}
    /* Estilos para os campos de entrada */
    .login-container input {{
        width: 100%;
        padding: 10px;
        margin: 10px 0;
        border: 1px solid #ccc;
        border-radius: 5px;
    }}
    /* Estilos para o botão de login */
    .login-container button {{
        width: 100%;
        padding: 10px;
        background-color: #1b4f72;
        color: white;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        font-size: 16px;
    }}
    .login-container button:hover {{
        background-color: #145a7c;
    }}
    </style>
    
    <!-- Vídeo de fundo -->
    <video autoplay muted loop class="background-video">
        <source src="{video_url}" type="video/mp4">
        Seu navegador não suporta o elemento de vídeo.
    </video>
    
    <!-- Container do formulário de login -->
    <div class="login-container">
    """

    # Adiciona o CSS e o vídeo de fundo ao Streamlit
    st.markdown(page_bg_video, unsafe_allow_html=True)

    # Conteúdo do formulário de login dentro do container
    with st.form(key='login_form'):
        st.markdown("<h1>Beach Club</h1>", unsafe_allow_html=True)
        username = st.text_input("Nome de Usuário")
        password = st.text_input("Senha", type="password")
        submit_login = st.form_submit_button(label="Login")

    if submit_login:
        admin_username = os.getenv("ADMIN_USERNAME")
        admin_password = os.getenv("ADMIN_PASSWORD")
        caixa_username = os.getenv("CAIXA_USERNAME")
        caixa_password = os.getenv("CAIXA_PASSWORD")
        
        if username == admin and password == admin:
            st.session_state.logged_in = True
            st.session_state.username = "admin"
            st.success("Login bem-sucedido como Admin!")
            st.experimental_rerun()
        elif username == caixa_username and password == caixa_password:
            st.session_state.logged_in = True
            st.session_state.username = "caixa"
            st.success("Login bem-sucedido como Caixa!")
            st.experimental_rerun()
        else:
            st.error("Nome de usuário ou senha incorretos.")

    # Fecha o div do container do formulário
    st.markdown("</div>", unsafe_allow_html=True)

#####################
# Initialization
#####################
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    selected_page = sidebar_navigation()

    if 'current_page' not in st.session_state:
        st.session_state.current_page = selected_page
    elif selected_page != st.session_state.current_page:
        refresh_data()
        st.session_state.current_page = selected_page
        if selected_page == "Home":
            st.session_state.home_page_initialized = False

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

    with st.sidebar:
        if st.button("Logout"):
            keys_to_reset = ['home_page_initialized']
            for key in keys_to_reset:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.logged_in = False
            st.success("Desconectado com sucesso!")
            st.experimental_rerun()
