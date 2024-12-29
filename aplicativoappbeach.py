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

# Carrega variáveis de ambiente do arquivo .env (local)
load_dotenv()

########################
# UTILIDADES GERAIS
########################
def format_currency(value: float) -> str:
    """
    Formata um valor para o formato monetário brasileiro: R$ x.xx
    Exemplo:
       1234.56 -> "R$ 1.234,56"
    """
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def download_df_as_csv(df: pd.DataFrame, filename: str, label: str = "Baixar CSV"):
    """
    Exibe um botão de download de um DataFrame como CSV.
    """
    csv_data = df.to_csv(index=False)
    st.download_button(
        label=label,
        data=csv_data,
        file_name=filename,
        mime="text/csv",
    )

########################
# VALIDAÇÃO DE VARIÁVEIS DE AMBIENTE
########################
def validate_env_vars():
    """
    Verifica se as variáveis de ambiente necessárias para conexão ao banco estão setadas.
    """
    required_vars = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_PORT"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        st.error(f"As seguintes variáveis de ambiente estão ausentes: {', '.join(missing_vars)}")
        return False
    return True

########################
# CONEXÃO COM BANCO
########################
@st.cache_resource
def get_db_connection():
    """
    Estabelece uma conexão segura com o banco de dados usando variáveis de ambiente (dotenv).
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", "5432")  # Porta padrão 5432
        )
        return conn
    except OperationalError as e:
        st.error(f"Não foi possível conectar ao banco de dados: {e}")
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
    finally:
        conn.close()


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
    finally:
        conn.close()

#####################
# CARREGAMENTO DE DADOS
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
# PÁGINAS (FUNÇÕES)
#####################

def home_page():
    """
    Página Home: Mostra informações básicas ou resumo.
    """
    st.title("🎾 Boituva Beach Club 🎾")
    st.write("📍 Av. do Trabalhador, 1879 — Boituva/SP")
    
    # Exemplo: poderíamos exibir algum resumo de pedidos
    st.markdown("## Seja bem-vindo(a) à página inicial!")
    st.write("Navegue pelo menu ao lado para gerenciar Pedidos, Produtos, Estoque, Clientes e Nota Fiscal.")

def orders_page():
    """
    Página Orders: Cadastro e listagem de pedidos.
    """
    st.title("Orders")
    st.subheader("Registrar novo pedido")

    # Exemplo de um pequeno filtro para mostrar a tabela depois
    search_client = st.text_input("Filtrar por Nome de Cliente (na tabela abaixo):")

    # Carrega lista de produtos
    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["No products available"]

    with st.form(key='order_form'):
        # Carrega lista de clientes (tb_clientes) - caso exista
        clientes = run_query('SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;')
        customer_list = [""] + [row[0] for row in clientes]

        col1, col2, col3 = st.columns(3)
        with col1:
            customer_name = st.selectbox("Customer Name", customer_list, index=0)
        with col2:
            product = st.selectbox("Product", product_list, index=0)
        with col3:
            quantity = st.number_input("Quantity", min_value=1, step=1)

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
            st.warning("Preencha todos os campos corretamente.")

    # Tabela de todos os pedidos
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("Todos os Pedidos")
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)

        # Filtro de cliente
        if search_client:
            df_orders = df_orders[df_orders["Client"].str.contains(search_client, case=False)]

        st.dataframe(df_orders, use_container_width=True)
        
        # Download CSV
        download_df_as_csv(df_orders, "orders.csv", label="Download Orders CSV")

        # Edição/Exclusão apenas se user == admin
        if st.session_state.get("username") == "admin":
            st.subheader("Editar ou Excluir Pedido Existente")
            # Cria uma "chave única" para cada pedido (combinando client, product, date)
            df_orders["unique_key"] = df_orders.apply(
                lambda row: f"{row['Client']}|{row['Product']}|{row['Date']}",
                axis=1
            )
            unique_keys = df_orders["unique_key"].unique().tolist()
            selected_key = st.selectbox("Selecione um pedido para editar/excluir:", [""] + unique_keys)

            if selected_key:
                matching_rows = df_orders[df_orders["unique_key"] == selected_key]
                if len(matching_rows) > 1:
                    st.warning("Múltiplos pedidos encontrados com a mesma key. Selecione outro.")
                else:
                    selected_row = matching_rows.iloc[0]
                    original_client = selected_row["Client"]
                    original_product = selected_row["Product"]
                    original_quantity = selected_row["Quantity"]
                    original_date = selected_row["Date"]
                    original_status = selected_row["Status"]

                    with st.form(key='edit_order_form'):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            edit_product = st.selectbox("Product", product_list, index=product_list.index(original_product) if original_product in product_list else 0)
                        with col2:
                            edit_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(original_quantity))
                        with col3:
                            edit_status_list = ["em aberto", "Recebido - Débito", "Recebido - Crédito", "Recebido - Pix", "Recebido - Dinheiro"]
                            if original_status in edit_status_list:
                                edit_status_index = edit_status_list.index(original_status)
                            else:
                                edit_status_index = 0
                            edit_status = st.selectbox("Status", edit_status_list, index=edit_status_index)

                        col_upd, col_del = st.columns(2)
                        with col_upd:
                            update_button = st.form_submit_button(label="Atualizar Pedido")
                        with col_del:
                            delete_button = st.form_submit_button(label="Excluir Pedido")

                    if delete_button:
                        delete_query = """
                            DELETE FROM public.tb_pedido
                            WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                        """
                        success = run_insert(delete_query, (original_client, original_product, original_date))
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

def products_page():
    """
    Página Products: Cadastro e listagem de produtos.
    """
    st.title("Products")

    st.subheader("Adicionar novo produto")
    with st.form(key='product_form'):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            supplier = st.text_input("Supplier", max_chars=100)
        with col2:
            product = st.text_input("Product", max_chars=100)
        with col3:
            quantity = st.number_input("Quantity", min_value=1, step=1)
        with col4:
            unit_value = st.number_input("Unit Value", min_value=0.0, step=0.01, format="%.2f")

        creation_date = st.date_input("Creation Date", value=date.today())
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
            st.warning("Preencha todos os campos corretamente.")

    products_data = st.session_state.data.get("products", [])
    if products_data:
        st.subheader("Todos os Produtos")
        columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
        df_products = pd.DataFrame(products_data, columns=columns)
        st.dataframe(df_products, use_container_width=True)

        # Download CSV
        download_df_as_csv(df_products, "products.csv", label="Download Products CSV")

        if st.session_state.get("username") == "admin":
            st.subheader("Editar ou Excluir Produto Existente")
            df_products["unique_key"] = df_products.apply(
                lambda row: f"{row['Supplier']}|{row['Product']}|{row['Creation Date']}",
                axis=1
            )
            unique_keys = df_products["unique_key"].unique().tolist()
            selected_key = st.selectbox("Selecione um produto para editar/excluir:", [""] + unique_keys)

            if selected_key:
                matching_rows = df_products[df_products["unique_key"] == selected_key]
                if len(matching_rows) > 1:
                    st.warning("Múltiplos produtos encontrados com a mesma key. Selecione outro.")
                else:
                    selected_row = matching_rows.iloc[0]
                    original_supplier = selected_row["Supplier"]
                    original_product = selected_row["Product"]
                    original_quantity = selected_row["Quantity"]
                    original_unit_value = selected_row["Unit Value"]
                    original_creation_date = selected_row["Creation Date"]

                    with st.form(key='edit_product_form'):
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            edit_supplier = st.text_input("Supplier", value=original_supplier, max_chars=100)
                        with col2:
                            edit_product = st.text_input("Product", value=original_product, max_chars=100)
                        with col3:
                            edit_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(original_quantity))
                        with col4:
                            edit_unit_value = st.number_input("Unit Value", min_value=0.0, step=0.01, format="%.2f", value=float(original_unit_value))

                        edit_creation_date = st.date_input("Creation Date", value=original_creation_date)

                        col_upd, col_del = st.columns(2)
                        with col_upd:
                            update_button = st.form_submit_button(label="Atualizar Produto")
                        with col_del:
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
                        confirm = st.checkbox("Tem certeza que deseja excluir este produto?")
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

def stock_page():
    """
    Página Stock: Registro de entradas/saídas de estoque.
    """
    st.title("Stock")
    st.subheader("Registrar entrada de estoque")

    product_data = run_query("SELECT product FROM public.tb_products ORDER BY product;")
    product_list = [row[0] for row in product_data] if product_data else ["No products available"]

    with st.form(key='stock_form'):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            product = st.selectbox("Product", product_list)
        with col2:
            quantity = st.number_input("Quantity", min_value=1, step=1)
        with col3:
            transaction = st.selectbox("Transaction Type", ["Entrada", "Saída"])
        with col4:
            date_input = st.date_input("Date", value=datetime.now().date())

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
                st.error("Falha ao adicionar registro de estoque.")
        else:
            st.warning("Selecione um produto e uma quantidade maior que 0.")

    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        st.subheader("Todos os Registros de Estoque")
        columns = ["Product", "Quantity", "Transaction", "Date"]
        df_stock = pd.DataFrame(stock_data, columns=columns)
        st.dataframe(df_stock, use_container_width=True)

        download_df_as_csv(df_stock, "stock.csv", label="Download Stock CSV")

        if st.session_state.get("username") == "admin":
            st.subheader("Editar ou Excluir Registro de Estoque")
            df_stock["unique_key"] = df_stock.apply(
                lambda row: f"{row['Product']}|{row['Transaction']}|{row['Date']}",
                axis=1
            )
            unique_keys = df_stock["unique_key"].unique().tolist()
            selected_key = st.selectbox("Selecione um registro para editar/excluir:", [""] + unique_keys)

            if selected_key:
                matching_rows = df_stock[df_stock["unique_key"] == selected_key]
                if len(matching_rows) > 1:
                    st.warning("Múltiplos registros encontrados com a mesma key.")
                else:
                    selected_row = matching_rows.iloc[0]
                    original_product = selected_row["Product"]
                    original_quantity = selected_row["Quantity"]
                    original_transaction = selected_row["Transaction"]
                    original_date = selected_row["Date"]

                    with st.form(key='edit_stock_form'):
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            edit_product = st.selectbox("Product", product_list, index=product_list.index(original_product) if original_product in product_list else 0)
                        with col2:
                            edit_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(original_quantity))
                        with col3:
                            edit_transaction = st.selectbox("Transaction Type", ["Entrada", "Saída"], index=["Entrada", "Saída"].index(original_transaction) if original_transaction in ["Entrada", "Saída"] else 0)
                        with col4:
                            edit_date = st.date_input("Date", value=pd.to_datetime(original_date).date())

                        col_upd, col_del = st.columns(2)
                        with col_upd:
                            update_button = st.form_submit_button(label="Atualizar Registro")
                        with col_del:
                            delete_button = st.form_submit_button(label="Excluir Registro")

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
                        confirm = st.checkbox("Tem certeza que deseja excluir este registro?")
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

def clients_page():
    """
    Página Clients: Cadastro e listagem de clientes.
    """
    st.title("Clients")
    st.subheader("Registrar Novo Cliente")

    with st.form(key='client_form'):
        nome_completo = st.text_input("Full Name", max_chars=100)
        submit_client = st.form_submit_button(label="Registrar Novo Cliente")

    if submit_client:
        if nome_completo:
            data_nascimento = datetime(2000, 1, 1).date()
            genero = "Man"
            telefone = "0000-0000"
            unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
            email = f"{nome_completo.replace(' ', '_').lower()}_{unique_id}@example.com"
            endereco = "Endereço padrão"

            query = """
                INSERT INTO public.tb_clientes (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            success = run_insert(query, (nome_completo, data_nascimento, genero, telefone, email, endereco))
            if success:
                st.success("Cliente registrado com sucesso!")
                refresh_data()
        else:
            st.warning("Preencha o campo de Nome Completo.")

    # Exibe todos os clientes
    clients_data = run_query(
        """SELECT nome_completo, data_nascimento, genero,
                  telefone, email, endereco, data_cadastro
           FROM public.tb_clientes
           ORDER BY data_cadastro DESC;"""
    )
    if clients_data:
        st.subheader("Todos os Clientes")
        columns = ["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"]
        df_clients = pd.DataFrame(clients_data, columns=columns)
        st.dataframe(df_clients, use_container_width=True)

        download_df_as_csv(df_clients, "clients.csv", label="Download Clients CSV")

        if st.session_state.get("username") == "admin":
            st.subheader("Editar ou Excluir Cliente Existente")
            client_emails = df_clients["Email"].unique().tolist()
            selected_email = st.selectbox("Selecione um cliente pelo Email:", [""] + client_emails)

            if selected_email:
                selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
                original_name = selected_client_row["Full Name"]

                with st.form(key='edit_client_form'):
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_name = st.text_input("Full Name", value=original_name, max_chars=100)
                    with col2:
                        st.write("")
                    col_upd, col_del = st.columns(2)
                    with col_upd:
                        update_button = st.form_submit_button(label="Atualizar Cliente")
                    with col_del:
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
                        st.warning("Preencha o campo de Nome Completo.")

                if delete_button:
                    confirm = st.checkbox("Tem certeza que deseja excluir este cliente?")
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

def invoice_page():
    """
    Página Nota Fiscal: Exibe e processa pedidos em aberto.
    """
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
                if st.button("Débito"):
                    process_payment(selected_client, "Recebido - Débito")
            with col2:
                if st.button("Crédito"):
                    process_payment(selected_client, "Recebido - Crédito")
            with col3:
                if st.button("Pix"):
                    process_payment(selected_client, "Recebido - Pix")
            with col4:
                if st.button("Dinheiro"):
                    process_payment(selected_client, "Recebido - Dinheiro")
        else:
            st.info("Não há pedidos em aberto para o cliente selecionado.")
    else:
        st.warning("Por favor, selecione um cliente.")

def process_payment(client, payment_status):
    """
    Atualiza o status dos pedidos em aberto para o status de pagamento escolhido.
    """
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

def generate_invoice_for_printer(df: pd.DataFrame):
    """
    Exibe em tela uma 'nota fiscal' para impressão, calculando total.
    """
    company = "Boituva Beach Club"
    address = "Avenida do Trabalhador, 1879 - Boituva/SP"
    cnpj = "05.365.434/0001-09"
    phone = "(13) 99154-5481"

    invoice_note = []
    invoice_note.append("==================================================")
    invoice_note.append("                NOTA FISCAL / RECIBO             ")
    invoice_note.append("==================================================")
    invoice_note.append(f"Empresa: {company}")
    invoice_note.append(f"Endereço: {address}")
    invoice_note.append(f"CNPJ: {cnpj}")
    invoice_note.append(f"Telefone: {phone}")
    invoice_note.append("--------------------------------------------------")
    invoice_note.append("DESCRIÇÃO             QTD     TOTAL")
    invoice_note.append("--------------------------------------------------")

    grouped_df = df.groupby('Produto').agg({'Quantidade': 'sum', 'total': 'sum'}).reset_index()
    total_general = 0

    for _, row in grouped_df.iterrows():
        description = f"{row['Produto'][:20]:<20}"  # limitando a 20 chars
        quantity = f"{int(row['Quantidade']):>5}"
        total_item = row['total']
        total_general += total_item
        total_formatted = format_currency(total_item)
        invoice_note.append(f"{description} {quantity} {total_formatted}")

    invoice_note.append("--------------------------------------------------")
    invoice_note.append(f"{'TOTAL GERAL:':>30} {format_currency(total_general):>10}")
    invoice_note.append("==================================================")
    invoice_note.append("OBRIGADO PELA PREFERÊNCIA!")
    invoice_note.append("==================================================")

    st.text("\n".join(invoice_note))

#####################
# TESTE DE CONEXÃO
#####################
def test_db_connection():
    """
    Testa a conexão ao banco antes de carregar dados,
    exibindo uma mensagem de sucesso ou de erro detalhada.
    """
    if not validate_env_vars():
        # Se variáveis de ambiente estão faltando, interrompe.
        st.stop()

    conn = get_db_connection()
    if conn is not None:
        st.success("Teste de conexão ao banco de dados: OK!")
        conn.close()
    else:
        st.stop()

#####################
# PÁGINA DE LOGIN
#####################
def login_page():
    """
    Página de Login.
    """
    st.title("Beach Club")
    st.write("Por favor, insira suas credenciais para acessar o aplicativo.")

    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button(label="Login")

    if submit_login:
        # Poderia usar variáveis de ambiente aqui, se desejado
        # ex: admin_user = os.getenv("ADMIN_USERNAME", "admin")
        #     admin_pass = os.getenv("ADMIN_PASSWORD", "adminbeach")
        if username == "admin" and password == "adminbeach":
            st.session_state.logged_in = True
            st.session_state.username = "admin"
            st.success("Login bem-sucedido!")
        elif username == "caixa" and password == "caixabeach":
            st.session_state.logged_in = True
            st.session_state.username = "caixa"
            st.success("Login bem-sucedido!")
        else:
            st.error("Nome de usuário ou senha incorretos.")


#####################
# INICIALIZAÇÃO / MAIN
#####################
def main():
    # 1. Testa a conexão de imediato (apenas uma vez)
    if "db_tested" not in st.session_state:
        test_db_connection()
        st.session_state.db_tested = True

    # 2. Carrega dados
    if 'data' not in st.session_state:
        st.session_state.data = load_all_data()

    # 3. Flag de login
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    # 4. Verifica login
    if not st.session_state.logged_in:
        login_page()
    else:
        # Menu lateral
        with st.sidebar:
            st.title("Boituva Beach Club 🎾")
        selected_page = option_menu(
            "Menu Principal",
            ["Home", "Orders", "Products", "Stock", "Clients", "Nota Fiscal", "Logout"],
            icons=["house", "file-text", "box", "list-task", "users", "receipt", "arrow-left-circle"],
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
        elif selected_page == "Logout":
            st.session_state.logged_in = False
            st.experimental_rerun()

if __name__ == "__main__":
    main()
