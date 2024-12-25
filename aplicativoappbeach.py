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
    Executa uma consulta SELECT e retorna os dados.
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


def run_insert(query, values, table_name="", action_description=""):
    """
    Executa uma consulta INSERT/UPDATE/DELETE e confirma as alterações.
    Também registra a ação em tb_audit_logs.
    """
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values)
        conn.commit()
        # Registrar no log de auditoria
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
        st.error(f"Erro ao executar a consulta: {e}")
        return False


def log_action(username, action_type, table_name, description):
    """
    Insere um registro de log na tb_audit_logs.
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
            st.error(f"Falha ao registrar a ação de auditoria: {e}")


def _get_sql_verb(query):
    """
    Tenta determinar se a consulta é INSERT, UPDATE ou DELETE para auditoria.
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
    Carrega todos os dados usados pelo app em um dicionário e retorna.
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
        st.error(f"Erro ao carregar os dados: {e}")
    return data


def refresh_data():
    """
    Recarrega os dados e atualiza o estado da sessão.
    """
    st.session_state.data = load_all_data()

#####################
# Menu Navigation
#####################
def sidebar_navigation():
    """
    Cria o menu de navegação principal na barra lateral.
    """
    with st.sidebar:
        st.title("Boituva Beach Club 🎾")
        selected = option_menu(
            "Menu Principal",
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
    st.write("📍 Av. Do Trabalhador, 1879 — Bem-vindo ao 5° Open BBC")

    # Exibir resumo básico se for admin
    if st.session_state.get("username") == "admin":
        st.markdown("### Resumo de Pedidos Abertos")
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
            st.markdown(f"**Total (Pedidos Abertos):** R$ {total_open:,.2f}")
        else:
            st.info("Nenhum pedido aberto encontrado.")

        st.markdown("### Resumo de Pedidos Fechados")
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
            st.markdown(f"**Total (Pedidos Fechados):** R$ {df_closed['Total'].sum():,.2f}")
        else:
            st.info("Nenhum pedido fechado encontrado.")
    else:
        st.info("Bem-vindo ao Boituva Beach Club!")

#####################
# Orders Page (with basic Search/Filters)
#####################
def orders_page():
    st.title("Orders")

    st.subheader("Buscar Pedidos / Filtrar")
    # Filtros básicos
    clients_data = st.session_state.data.get("clients", [])
    client_names = ["All"] + [r[0] for r in clients_data]
    selected_client = st.selectbox("Filtrar por Cliente", client_names, index=0)

    start_date = st.date_input("Data de Início", value=date(2023, 1, 1))
    end_date = st.date_input("Data de Término", value=date.today())

    if st.button("Aplicar Filtros"):
        # Construir consulta dinâmica
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
            df_orders_filtered = pd.DataFrame(filtered_data, columns=["Client", "Product", "Quantity", "Date", "Status"])
            st.dataframe(df_orders_filtered, use_container_width=True)
        else:
            st.info("Nenhum pedido encontrado para os filtros selecionados.")

    st.subheader("Registrar um Novo Pedido")
    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["Sem produtos disponíveis"]

    with st.form(key='order_form'):
        clientes = st.session_state.data.get("clients", [])
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
            success = run_insert(
                query,
                (customer_name, product, quantity, timestamp),
                table_name="tb_pedido",
                action_description=f"Novo pedido para {customer_name}, produto={product}"
            )
            if success:
                st.success("Pedido registrado com sucesso!")
                refresh_data()
        else:
            st.warning("Por favor, preencha todos os campos corretamente.")

    # Exibir todos os pedidos
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("Todos os Pedidos")
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        st.dataframe(df_orders, use_container_width=True)

        # Edição/exclusão para admin
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
                        edit_quantity = st.number_input("Quantidade", min_value=1, step=1, value=int(original_quantity))
                        edit_status_list = ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix", "Received - Cash"]
                        edit_status_index = edit_status_list.index(original_status) if original_status in edit_status_list else 0
                        edit_status = st.selectbox("Status", edit_status_list, index=edit_status_index)

                        col_edit, col_delete = st.columns(2)
                        with col_edit:
                            update_button = st.form_submit_button(label="Atualizar Pedido")
                        with col_delete:
                            delete_button = st.form_submit_button(label="Excluir Pedido")

                    if delete_button:
                        delete_query = """
                        DELETE FROM public.tb_pedido
                        WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                        """
                        success = run_insert(
                            delete_query,
                            (original_client, original_product, original_date),
                            table_name="tb_pedido",
                            action_description=f"Excluindo pedido para {original_client}"
                        )
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
                        success = run_insert(
                            update_query,
                            (edit_product, edit_quantity, edit_status,
                             original_client, original_product, original_date),
                            table_name="tb_pedido",
                            action_description=f"Atualizando pedido para {original_client}"
                        )
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
        creation_date = st.date_input("Data de Criação", value=date.today())
        submit_product = st.form_submit_button(label="Inserir Produto")

    if submit_product:
        if supplier and product and quantity > 0 and unit_value >= 0:
            total_value = quantity * unit_value
            query = """
            INSERT INTO public.tb_products (supplier, product, quantity, unit_value, total_value, creation_date)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            success = run_insert(
                query,
                (supplier, product, quantity, unit_value, total_value, creation_date),
                table_name="tb_products",
                action_description=f"Novo produto: {product}"
            )
            if success:
                st.success("Produto adicionado com sucesso!")
                refresh_data()
        else:
            st.warning("Por favor, preencha todos os campos corretamente.")

    products_data = st.session_state.data.get("products", [])
    if products_data:
        st.subheader("Todos os Produtos")
        columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
        df_products = pd.DataFrame(products_data, columns=columns)
        st.dataframe(df_products, use_container_width=True)

        # Edição/exclusão para admin
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
                            "Quantidade", min_value=1, step=1, value=int(original_quantity)
                        )
                        edit_unit_value = st.number_input(
                            "Valor Unitário",
                            min_value=0.0,
                            step=0.01,
                            format="%.2f",
                            value=float(original_unit_value)
                        )
                        edit_creation_date = st.date_input("Data de Criação", value=original_creation_date)

                        col_update, col_delete = st.columns(2)
                        with col_update:
                            update_button = st.form_submit_button(label="Atualizar Produto")
                        with col_delete:
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
                            action_description=f"Atualizando produto: {original_product}"
                        )
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
                            success = run_insert(
                                delete_query,
                                (original_supplier, original_product, original_creation_date),
                                table_name="tb_products",
                                action_description=f"Excluindo produto: {original_product}"
                            )
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

    st.subheader("Registrar uma Nova Entrada de Estoque")
    st.write(
        """
        Esta página é destinada a registrar **apenas entradas (Entrada)** no estoque.  
        Se precisar rastrear saídas ou devoluções, você também pode adicionar a transação 'Saída'.
        """
    )

    product_data = run_query("SELECT product FROM public.tb_products ORDER BY product;")
    product_list = [row[0] for row in product_data] if product_data else ["Sem produtos disponíveis"]

    with st.form(key='stock_form'):
        product = st.selectbox("Produto", product_list)
        quantity = st.number_input("Quantidade", min_value=1, step=1)
        transaction = st.selectbox("Tipo de Transação", ["Entrada", "Saída"])
        picked_date = st.date_input("Data", value=datetime.now().date())
        submit_stock = st.form_submit_button(label="Registrar")

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
                action_description=f"Estoque {transaction} para o produto {product}"
            )
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
        st.dataframe(df_stock, use_container_width=True)

        # Edição/exclusão para admin
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
                            index=["Entrada", "Saída"].index(original_transaction)
                            if original_transaction in ["Entrada", "Saída"] else 0
                        )
                        edit_date = st.date_input("Data", value=original_date.date())

                        col_update, col_delete = st.columns(2)
                        with col_update:
                            update_button = st.form_submit_button(label="Atualizar Registro de Estoque")
                        with col_delete:
                            delete_button = st.form_submit_button(label="Excluir Registro de Estoque")

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
                            action_description=f"Atualizando registro de estoque para o produto {original_product}"
                        )
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
                            success = run_insert(
                                delete_query,
                                (original_product, original_transaction, original_date),
                                table_name="tb_estoque",
                                action_description=f"Excluindo registro de estoque para o produto {original_product}"
                            )
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
        full_name = st.text_input("Nome Completo", max_chars=100)
        submit_client = st.form_submit_button(label="Registrar Novo Cliente")

    if submit_client:
        if full_name:
            # Para simplicidade, inserimos valores padrão/placeholder para outros campos
            data_nascimento = datetime(2000, 1, 1).date()
            genero = "Man"
            telefone = "0000-0000"
            unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
            email = f"{full_name.replace(' ', '_').lower()}_{unique_id}@example.com"
            endereco = "Endereço Padrão"

            query = """
            INSERT INTO public.tb_clientes 
            (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            success = run_insert(
                query,
                (full_name, data_nascimento, genero, telefone, email, endereco),
                table_name="tb_clientes",
                action_description=f"Novo cliente: {full_name}"
            )
            if success:
                st.success("Cliente registrado com sucesso!")
                refresh_data()
        else:
            st.warning("Por favor, insira o Nome Completo.")

    # Exibir todos os clientes
    clients_data = run_query(
        """
        SELECT nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro
        FROM public.tb_clientes
        ORDER BY data_cadastro DESC;
        """
    )
    if clients_data:
        st.subheader("Todos os Clientes")
        columns = ["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"]
        df_clients = pd.DataFrame(clients_data, columns=columns)
        st.dataframe(df_clients, use_container_width=True)

        # Edição/exclusão para admin
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
                        success = run_insert(
                            update_query,
                            (edit_name, selected_email),
                            table_name="tb_clientes",
                            action_description=f"Atualizando cliente: {selected_email}"
                        )
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
                        success = run_insert(
                            delete_query,
                            (selected_email,),
                            table_name="tb_clientes",
                            action_description=f"Excluindo cliente: {selected_email}"
                        )
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
    st.title("Invoice")

    open_clients_query = """
        SELECT DISTINCT "Cliente"
        FROM public.vw_pedido_produto
        WHERE status = 'em aberto';
    """
    open_clients = run_query(open_clients_query)
    client_list = [row[0] for row in open_clients] if open_clients else []

    selected_client = st.selectbox("Selecione um Cliente", [""] + client_list)

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

            # Botões de pagamento
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("Débito"):
                    process_payment(selected_client, "Received - Debited")
            with col2:
                if st.button("Crédito"):
                    process_payment(selected_client, "Received - Credit")
            with col3:
                if st.button("Pix"):
                    process_payment(selected_client, "Received - Pix")
            with col4:
                if st.button("Dinheiro"):
                    process_payment(selected_client, "Received - Cash")
        else:
            st.info("Nenhum pedido aberto para o cliente selecionado.")
    else:
        st.warning("Por favor, selecione um cliente.")

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
        action_description=f"Atualizando status de pagamento para {client} para {payment_status}"
    )
    if success:
        st.success(f"Status atualizado para: {payment_status}")
        refresh_data()
    else:
        st.error("Falha ao atualizar o status.")

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
        description = f"{row['Product'][:20]:<20}"  # limitar a 20 caracteres
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

    # Exemplo: Exibir total vendido por produto (da view existente vw_total_sold)
    total_sold_query = """
        SELECT "Produto", total_sold
        FROM public.vw_total_sold
        ORDER BY total_sold DESC;
    """
    total_sold_data = run_query(total_sold_query)
    if total_sold_data:
        df_sold = pd.DataFrame(total_sold_data, columns=["Product", "Total_Sold"])
        st.subheader("Total Vendido por Produto")
        st.dataframe(df_sold)

        # Criar um gráfico de barras simples usando Altair
        chart = alt.Chart(df_sold).mark_bar().encode(
            x=alt.X("Product", sort=None),
            y="Total_Sold"
        ).properties(width=600, height=400)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Nenhum dado vendido encontrado na vw_total_sold.")

    # Exemplo: Distribuição por tipo de pagamento
    payment_type_query = """
        SELECT payment_type, total_sold
        FROM public.vw_total_por_tipo_pagamento;
    """
    payment_type_data = run_query(payment_type_query)
    if payment_type_data:
        df_payment = pd.DataFrame(payment_type_data, columns=["Payment_Type", "Total_Sold"])
        st.subheader("Total Vendido por Tipo de Pagamento")
        st.dataframe(df_payment)

        pie_chart = alt.Chart(df_payment).mark_arc(innerRadius=50).encode(
            theta="Total_Sold",
            color="Payment_Type",
            tooltip=["Payment_Type", "Total_Sold"]
        )
        st.altair_chart(pie_chart, use_container_width=True)
    else:
        st.info("Nenhum dado encontrado na vw_total_por_tipo_pagamento.")

# URL para o vídeo de fundo
video_url = (
    "https://github.com/veigakiko/appBeach/raw/refs/heads/main/"
    "20241224_0437_Vibrant%20Beach%20Tennis_remix_01jfvsjewve73t9bq6sb9hcc2q.mp4"
)

def login_page():
    """
    Renderiza a página de login com um vídeo de fundo que roda automaticamente e em loop.
    """
    # CSS personalizado para o vídeo de fundo e o formulário de login
    st.markdown(
        f"""
        <style>
        /* Estilos para remover margens e padding */
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            overflow: hidden;
        }}

        /* Container do vídeo de fundo */
        .background {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }}

        /* Estilos para o vídeo */
        video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        /* Estilos para o container do formulário de login */
        .login-container {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(255, 255, 255, 0.85);
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            max-width: 400px;
            width: 90%;
        }}

        /* Estilos para os títulos */
        .login-container h1 {{
            text-align: center;
            margin-bottom: 20px;
        }}
        </style>
        <div class="background">
            <video autoplay muted loop>
                <source src="{video_url}" type="video/mp4">
                Seu navegador não suporta HTML5 video.
            </video>
        </div>
        <div class="login-container">
        """,
        unsafe_allow_html=True,
    )

    # Formulário de login dentro do container
    with st.form(key="login_form"):
        st.markdown("<h1>Beach Club</h1>", unsafe_allow_html=True)
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button(label="Login")

    if submit_login:
        if username == "admin" and password == "adminbeach":
            st.session_state.logged_in = True
            st.session_state.username = "admin"
            st.success("Login realizado com sucesso!")
            st.experimental_rerun()
        elif username == "caixa" and password == "caixabeach":
            st.session_state.logged_in = True
            st.session_state.username = "caixa"
            st.success("Login realizado com sucesso!")
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha incorretos.")

    # Fechar o div do container
    st.markdown("</div>", unsafe_allow_html=True)

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
        # Remover quaisquer variáveis de sessão, se necessário
        keys_to_reset = ['home_page_initialized']
        for key in keys_to_reset:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.logged_in = False
        st.success("Logout realizado com sucesso!")
        st.experimental_rerun()
