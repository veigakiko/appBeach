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
            host=st.secrets["DB_HOST"],       # Utilize st.secrets para segurança
            database=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            port=st.secrets["DB_PORT"]
        )
        return conn
    except OperationalError as e:
        st.error("Não foi possível conectar ao banco de dados. Por favor, tente novamente mais tarde.")
        return None

def run_query(query, values=None):
    """
    Executes a read-only query (SELECT) and returns the fetched data.
    """
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values or ())
            return cursor.fetchall()
    except (Exception, psycopg2.DatabaseError) as e:
        st.error(f"Erro ao executar a consulta: {e}")
        return []
    finally:
        if conn:
            conn.close()

def run_insert(query, values):
    """
    Executes an insert or update query.
    """
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, values)
        conn.commit()
        return True
    except (Exception, psycopg2.DatabaseError) as e:
        if conn:
            conn.rollback()
        st.error(f"Erro ao executar a operação: {e}")
        return False
    finally:
        if conn:
            conn.close()

#####################
# Data Loading
#####################

@st.cache_data(ttl=600)
def load_all_data():
    """
    Load all data used by the application and return it as a dictionary.
    """
    data = {}
    try:
        # Carrega todos os pedidos
        data["orders"] = run_query(
            'SELECT "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido ORDER BY "Data" DESC;'
        )
        # Carrega todos os produtos
        data["products"] = run_query(
            "SELECT supplier, product, quantity, unit_value, total_value, creation_date FROM public.tb_products ORDER BY creation_date DESC;"
        )
        # Carrega todos os clientes
        data["clients"] = run_query('SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;')
        # Carrega todos os registros de estoque
        data["stock"] = run_query(
            'SELECT "Produto", "Quantidade", "Transação", "Data" FROM public.tb_estoque ORDER BY "Data" DESC;'
        )
    except Exception as e:
        st.error(f"Erro ao carregar os dados: {e}")
    return data

def refresh_data():
    """
    Reload all data and update the session state.
    """
    st.session_state.data = load_all_data()

#####################
# Login Functionality
#####################

def login():
    """
    Display a login form and handle authentication.
    """
    st.title("Login")
    with st.form(key='login_form'):
        username = st.text_input("Nome de Usuário")
        password = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar")
    
    if submit:
        if username == "admin" and password == "admin":  # Substitua por um método de autenticação mais robusto
            st.session_state.logged_in = True
            st.success("Login realizado com sucesso!")
            refresh_data()
        else:
            st.error("Nome de usuário ou senha inválidos.")

#####################
# Menu Navigation
#####################

def sidebar_navigation():
    """
    Create a sidebar menu for navigation using streamlit_option_menu.
    """
    with st.sidebar:
        st.title("Boituva Beach Club")
        selected = option_menu(
            "Menu Principal", ["Home", "Pedidos", "Produtos", "Estoque", "Clientes", "Nota Fiscal", "Sair"],
            icons=["house", "file-text", "box", "list-task", "people", "file-invoice", "box-arrow-right"],
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
    st.write("🎾 BeachTennis 📍 Av. Do Trabalhador, 1879 🏆 5° Open BBC")
    if st.button("Atualizar Dados"):
        refresh_data()

def orders_page():
    st.title("Pedidos")
    st.subheader("Registrar um Novo Pedido")

    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["Nenhum produto disponível"]

    # Formulário para inserir novo pedido
    with st.form(key='order_form'):
        # Carregando lista de clientes para o novo pedido
        clientes = run_query('SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;')
        customer_list = [""] + [row[0] for row in clientes] if clientes else ["Nenhum cliente disponível"]

        customer_name = st.selectbox("Nome do Cliente", customer_list, index=0)
        product = st.selectbox("Produto", product_list, index=0)
        quantity = st.number_input("Quantidade", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Registrar Pedido")

    if submit_button:
        if customer_name and product and quantity > 0:
            query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", "status")
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

    # Exibir todos os pedidos
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("Todos os Pedidos")
        columns = ["Cliente", "Produto", "Quantidade", "Data", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        st.dataframe(df_orders, use_container_width=True)

        # Cria identificadores únicos com base em Cliente, Produto e Data
        # Convertendo Data para string, caso esteja em datetime, para exibição
        df_orders["unique_key"] = df_orders.apply(lambda row: f"{row['Cliente']}|{row['Produto']}|{row['Data']}", axis=1)

        st.subheader("Editar ou Excluir um Pedido Existente")
        unique_keys = df_orders["unique_key"].unique().tolist()
        selected_key = st.selectbox("Selecione um pedido para editar ou excluir:", [""] + unique_keys)

        if selected_key:
            # Extrair valores originais do pedido selecionado
            selected_row = df_orders[df_orders["unique_key"] == selected_key].iloc[0]

            original_client = selected_row["Cliente"]
            original_product = selected_row["Produto"]
            original_date = selected_row["Data"]  # datetime
            original_quantity = selected_row["Quantidade"]
            original_status = selected_row["Status"]

            # Prepara o formulário de edição
            product_index = product_list.index(original_product) if original_product in product_list else 0

            st.markdown("### Editar Detalhes do Pedido")
            with st.form(key='edit_order_form'):
                edit_product = st.selectbox("Produto", product_list, index=product_index)
                edit_quantity = st.number_input("Quantidade", min_value=1, step=1, value=int(original_quantity))
                edit_status_list = ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix", "Received - Cash"]
                edit_status_index = edit_status_list.index(original_status) if original_status in edit_status_list else 0
                edit_status = st.selectbox("Status", edit_status_list, index=edit_status_index)

                update_button = st.form_submit_button(label="Atualizar Pedido")

            if update_button:
                if edit_product and edit_quantity > 0 and edit_status:
                    update_query = """
                    UPDATE public.tb_pedido
                    SET "Produto" = %s, "Quantidade" = %s, status = %s, "Data" = %s
                    WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                    """
                    new_timestamp = datetime.now()
                    success = run_insert(update_query, (edit_product, edit_quantity, edit_status, new_timestamp, original_client, original_product, original_date))
                    if success:
                        st.success("Pedido atualizado com sucesso!")
                        refresh_data()
                    else:
                        st.error("Falha ao atualizar o pedido.")
                else:
                    st.warning("Por favor, preencha todos os campos corretamente.")

            st.markdown("### Excluir Pedido")
            with st.form(key='delete_order_form'):
                st.warning("Tem certeza de que deseja excluir este pedido?")
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
    else:
        st.info("Nenhum pedido encontrado.")

def products_page():
    st.title("Produtos")

    st.subheader("Adicionar um Novo Produto")
    with st.form(key='product_form'):
        supplier = st.text_input("Fornecedor", max_chars=100)
        product = st.text_input("Produto", max_chars=100)
        quantity = st.number_input("Quantidade", min_value=1, step=1)
        unit_value = st.number_input("Valor Unitário", min_value=0.0, step=0.01, format="%.2f")
        creation_date = st.date_input("Data de Criação", value=datetime.today())
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

    # Exibir todos os produtos
    products_data = st.session_state.data.get("products", [])
    columns = ["Fornecedor", "Produto", "Quantidade", "Valor Unitário", "Valor Total", "Data de Criação"]
    if products_data:
        st.subheader("Todos os Produtos")
        df_products = pd.DataFrame(products_data, columns=columns)
        st.dataframe(df_products, use_container_width=True)

        # Criar uma chave única a partir de Fornecedor, Produto e Data de Criação
        df_products["unique_key"] = df_products.apply(
            lambda row: f"{row['Fornecedor']}|{row['Produto']}|{row['Data de Criação']}", axis=1
        )

        st.subheader("Editar ou Excluir um Produto Existente")
        unique_keys = df_products["unique_key"].unique().tolist()
        selected_key = st.selectbox("Selecione um produto para editar ou excluir:", [""] + unique_keys)

        if selected_key:
            selected_row = df_products[df_products["unique_key"] == selected_key].iloc[0]

            original_supplier = selected_row["Fornecedor"]
            original_product = selected_row["Produto"]
            original_quantity = selected_row["Quantidade"]
            original_unit_value = selected_row["Valor Unitário"]
            original_total_value = selected_row["Valor Total"]
            original_creation_date = selected_row["Data de Criação"]

            # Formulário para editar o produto
            st.markdown("### Editar Detalhes do Produto")
            with st.form(key='edit_product_form'):
                edit_supplier = st.text_input("Fornecedor", value=original_supplier, max_chars=100)
                edit_product = st.text_input("Produto", value=original_product, max_chars=100)
                edit_quantity = st.number_input("Quantidade", min_value=1, step=1, value=int(original_quantity))
                edit_unit_value = st.number_input("Valor Unitário", min_value=0.0, step=0.01, format="%.2f", value=float(original_unit_value))
                edit_creation_date = st.date_input("Data de Criação", value=original_creation_date)

                update_button = st.form_submit_button(label="Atualizar Produto")

            if update_button:
                if edit_supplier and edit_product and edit_quantity > 0 and edit_unit_value >= 0:
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
                else:
                    st.warning("Por favor, preencha todos os campos corretamente.")

            st.markdown("### Excluir Produto")
            with st.form(key='delete_product_form'):
                st.warning("Tem certeza de que deseja excluir este produto?")
                delete_button = st.form_submit_button(label="Excluir Produto")

            if delete_button:
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
    st.title("Estoque")

    st.subheader("Adicionar um Novo Registro de Estoque")

    # Carregar a lista de produtos da tabela tb_products
    product_data = run_query("SELECT product FROM public.tb_products ORDER BY product;")
    product_list = [row[0] for row in product_data] if product_data else ["Nenhum produto disponível"]

    with st.form(key='stock_form'):
        product = st.selectbox("Produto", product_list)
        quantity = st.number_input("Quantidade", min_value=1, step=1)
        transaction_type = st.selectbox("Tipo de Transação", ["Entrada", "Saída"])
        submit_stock = st.form_submit_button(label="Registrar")

    if submit_stock:
        if product and quantity > 0:
            transaction = transaction_type
            current_date = datetime.now()

            query = """
            INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Transação", "Data")
            VALUES (%s, %s, %s, %s);
            """
            success = run_insert(query, (product, quantity, transaction, current_date))
            if success:
                st.success("Registro de estoque adicionado com sucesso!")
                refresh_data()
            else:
                st.error("Falha ao adicionar o registro de estoque.")
        else:
            st.warning("Por favor, selecione um produto e insira uma quantidade maior que 0.")

    # Carregar os registros de estoque atualizados
    stock_data = st.session_state.data.get("stock", [])
    columns = ["Produto", "Quantidade", "Transação", "Data"]

    if stock_data:
        st.subheader("Todos os Registros de Estoque")
        try:
            df_stock = pd.DataFrame(stock_data, columns=columns)
            st.dataframe(df_stock, use_container_width=True)
        except ValueError as ve:
            st.error(f"Falha na criação do DataFrame: {ve}")
            st.write("Colunas Esperadas:", columns)
            st.write("Número de elementos por linha:", [len(row) for row in stock_data])
            st.write("Exemplo de Linha:", stock_data[0] if stock_data else "Sem dados")
    else:
        st.info("Nenhum registro de estoque encontrado.")

def clients_page():
    st.title("Clientes")

    st.subheader("Registrar um Novo Cliente")

    # Formulário com apenas o campo Nome Completo
    with st.form(key='client_form'):
        nome_completo = st.text_input("Nome Completo", max_chars=100)
        submit_client = st.form_submit_button(label="Registrar Novo Cliente")

    if submit_client:
        if nome_completo:
            # Outros valores padrões
            data_nascimento = datetime(2000, 1, 1).date()
            genero = "Masculino"
            telefone = "0000-0000"
            
            # Gera um email único para evitar conflito de chave única
            unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
            email = f"{nome_completo.replace(' ', '_').lower()}_{unique_id}@exemplo.com"

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
                st.error("Falha ao registrar o cliente.")
        else:
            st.warning("Por favor, preencha o campo Nome Completo.")

    # Mostrar a tabela de clientes cadastrados
    clients_data = run_query("SELECT nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro FROM public.tb_clientes ORDER BY data_cadastro DESC;")

    if clients_data:
        st.subheader("Todos os Clientes")
        columns = ["Nome Completo", "Data de Nascimento", "Gênero", "Telefone", "Email", "Endereço", "Data de Cadastro"]
        df_clients = pd.DataFrame(clients_data, columns=columns)
        st.dataframe(df_clients, use_container_width=True)

        # Selecionar um cliente para edição ou exclusão
        st.subheader("Editar ou Excluir um Cliente Existente")
        client_emails = df_clients["Email"].unique().tolist()
        selected_email = st.selectbox("Selecione um cliente pelo Email:", [""] + client_emails)

        if selected_email:
            # Obter dados do cliente selecionado
            selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
            original_name = selected_client_row["Nome Completo"]

            # Formulário para editar o nome
            st.markdown("### Editar Detalhes do Cliente")
            with st.form(key='edit_client_form'):
                edit_name = st.text_input("Nome Completo", value=original_name, max_chars=100)
                update_button = st.form_submit_button(label="Atualizar Cliente")

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

            # Formulário separado para excluir o cliente
            st.markdown("### Excluir Cliente")
            with st.form(key='delete_client_form'):
                st.warning("Tem certeza de que deseja excluir este cliente?")
                delete_button = st.form_submit_button(label="Excluir Cliente")

            if delete_button:
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
    st.title("Nota Fiscal")

    # Selecionar um cliente com pedidos em aberto
    open_clients_query = """
    SELECT DISTINCT c.nome_completo
    FROM public.tb_clientes c
    JOIN public.tb_pedido p ON c.nome_completo = p."Cliente"
    WHERE p.status = %s
    ORDER BY c.nome_completo;
    """
    open_clients = run_query(open_clients_query, ('em aberto',))

    client_list = [row[0] for row in open_clients] if open_clients else []

    selected_client = st.selectbox("Selecione um Cliente", [""] + client_list)

    if selected_client:
        # Recuperar os pedidos em aberto do cliente selecionado, junto com unit_value
        invoice_query = """
        SELECT p."Produto", p."Quantidade", p."Data", pr.unit_value
        FROM public.tb_pedido p
        JOIN public.tb_products pr ON p."Produto" = pr.product
        WHERE p."Cliente" = %s AND p.status = %s
        ORDER BY p."Data" ASC;
        """
        invoice_data = run_query(invoice_query, (selected_client, 'em aberto'))

        if invoice_data:
            # Criar DataFrame com os dados dos pedidos
            df = pd.DataFrame(invoice_data, columns=["Produto", "Quantidade", "Data", "unit_value"])
            st.subheader("Detalhes da Nota Fiscal")
            st.dataframe(df.drop(columns=["unit_value"]), use_container_width=True)

            # Calcular o total de cada pedido
            df['Total'] = df["Quantidade"].astype(float) * df["unit_value"].astype(float)
            total_sum = df["Total"].sum()

            # Coletar os identificadores únicos (Cliente|Produto|Data)
            invoice_data_keys = df.apply(lambda row: f"{selected_client}|{row['Produto']}|{row['Data']}", axis=1).tolist()

            # Exibir a nota fiscal para impressão
            generate_invoice_for_printer(df)

            # Exibir o total geral
            st.subheader(f"Total Geral: R$ {total_sum:,.2f}")

            # Botões para escolher o método de pagamento
            st.markdown("### Escolha o Método de Pagamento")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("Débito", key="debit_button"):
                    process_payment(invoice_data_keys, "Received - Debited")
            with col2:
                if st.button("Crédito", key="credit_button"):
                    process_payment(invoice_data_keys, "Received - Credit")
            with col3:
                if st.button("Pix", key="pix_button"):
                    process_payment(invoice_data_keys, "Received - Pix")
            with col4:
                if st.button("Dinheiro", key="cash_button"):
                    process_payment(invoice_data_keys, "Received - Cash")
        else:
            st.info("Não há pedidos em aberto para o cliente selecionado.")
    else:
        st.warning("Por favor, selecione um cliente.")

def process_payment(invoice_keys, payment_status):
    """
    Atualiza o status dos pedidos específicos para o status de pagamento selecionado.
    
    Parameters:
    - invoice_keys (list): Lista de identificadores únicos dos pedidos (Cliente|Produto|Data).
    - payment_status (str): Novo status a ser atribuído.
    """
    if not invoice_keys:
        st.warning("Nenhum pedido para atualizar.")
        return

    # Construir a consulta com cláusulas WHERE para cada identificador único
    # Cada identificador único é uma combinação de "Cliente|Produto|Data"
    # Vamos dividir isso para obter os campos necessários
    conditions = []
    params = []
    for key in invoice_keys:
        try:
            cliente, produto, data = key.split('|')
            # Converter 'data' para datetime se necessário
            if isinstance(data, str):
                # Dependendo do formato da data, ajuste aqui. Exemplo assume ISO format.
                data = datetime.fromisoformat(data)
            conditions.append('( "Cliente" = %s AND "Produto" = %s AND "Data" = %s )')
            params.extend([cliente, produto, data])
        except ValueError:
            st.error(f"Identificador único inválido: {key}")
            return

    where_clause = " OR ".join(conditions)
    query = f"""
    UPDATE public.tb_pedido
    SET status = %s, "Data" = %s
    WHERE ({where_clause}) AND status = 'em aberto';
    """
    # Adicionar o payment_status e o novo timestamp
    params = [payment_status, datetime.now()] + params

    success = run_insert(query, tuple(params))
    if success:
        st.success(f"Status atualizado para: {payment_status}")
        refresh_data()
    else:
        st.error("Erro ao atualizar o status.")

def generate_invoice_for_printer(df):
    """
    Gera uma nota fiscal formatada para impressão.
    """
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
        quantity = f"{int(row['Quantidade']):>5}"
        total = row['Total']
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
# Logout Functionality
#####################

def logout():
    """
    Handles user logout.
    """
    st.session_state.logged_in = False
    st.session_state.page = "Home"
    st.success("Logout realizado com sucesso!")

#####################
# Initialization
#####################

# Inicializar variáveis de estado da sessão
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# Verificação de Autenticação
if not st.session_state.logged_in:
    login()
    st.stop()

if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

# Menu de Navegação
selected_page = sidebar_navigation()

# Tratar Logout
if selected_page == "Sair":
    logout()
    st.stop()

# Page Routing
if selected_page == "Home":
    home_page()
elif selected_page == "Pedidos":
    orders_page()
elif selected_page == "Produtos":
    products_page()
elif selected_page == "Estoque":
    stock_page()
elif selected_page == "Clientes":
    clients_page()
elif selected_page == "Nota Fiscal":
    invoice_page()
