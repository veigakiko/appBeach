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
        st.error("Não foi possível conectar ao banco de dados. Tente novamente mais tarde.")
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
        st.error(f"Erro ao executar consulta: {e}")
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
        st.error(f"Erro ao executar inserção/atualização: {e}")
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
        data["orders"] = run_query(
            'SELECT "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido ORDER BY "Data" DESC;'
        )
        data["products"] = run_query(
            "SELECT supplier, product, quantity, unit_value, total_value, creation_date FROM public.tb_products;"
        )
        data["clients"] = run_query('SELECT DISTINCT "Cliente" FROM public.tb_pedido;')
        data["stock"] = run_query(
            'SELECT "Produto", "Quantidade", "Transação", "Data" FROM public.tb_estoque;'
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
# Menu Navigation
#####################
def sidebar_navigation():
    """
    Create a sidebar or horizontal menu for navigation using streamlit_option_menu.
    """
    with st.sidebar:
        st.title("Boituva Beach Club")
        selected = option_menu(
            "Menu Principal", ["Início", "Pedidos", "Produtos", "Estoque", "Clientes", "Nota Fiscal"],
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
# Page Functions
#####################
def home_page():
    st.title("Boituva Beach Club")
    st.write("🎾 Bem-vindo ao BeachTennis 📍Av. Do Trabalhador, 1879 🏆 5° Open BBC")
    if "data" in st.session_state:
        orders_data = st.session_state.data.get("orders", [])
        products_data = st.session_state.data.get("products", [])

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total de Pedidos", len(orders_data))
        with col2:
            st.metric("Produtos Cadastrados", len(products_data))
    st.button("Atualizar Dados", on_click=refresh_data)

def orders_page():
    st.title("Pedidos")
    st.subheader("Cadastrar Novo Pedido")

    product_data = st.session_state.data.get("products", [])
    product_list = [row[1] for row in product_data] if product_data else []

    with st.form(key='order_form'):
        clientes = run_query('SELECT nome_completo FROM public.tb_clientes')
        customer_list = [row[0] for row in clientes]

        customer_name = st.selectbox("Cliente", [""] + customer_list)
        product = st.selectbox("Produto", [""] + product_list)
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
            st.warning("Por favor, preencha todos os campos corretamente.")

def products_page():
    st.title("Produtos")
    st.subheader("Cadastrar Novo Produto")

    with st.form(key='product_form'):
        supplier = st.text_input("Fornecedor")
        product = st.text_input("Produto")
        quantity = st.number_input("Quantidade", min_value=1, step=1)
        unit_value = st.number_input("Valor Unitário", min_value=0.0, step=0.01, format="%.2f")
        creation_date = st.date_input("Data de Cadastro")
        submit_product = st.form_submit_button(label="Cadastrar Produto")

    if submit_product:
        if supplier and product and quantity > 0 and unit_value >= 0:
            query = """
            INSERT INTO public.tb_products (supplier, product, quantity, unit_value, total_value, creation_date)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            total_value = quantity * unit_value
            success = run_insert(query, (supplier, product, quantity, unit_value, total_value, creation_date))
            if success:
                st.success("Produto cadastrado com sucesso!")
                refresh_data()
        else:
            st.warning("Por favor, preencha todos os campos corretamente.")

def stock_page():
    st.title("Estoque")
    st.subheader("Gerenciamento de Estoque")
    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        columns = ["Produto", "Quantidade", "Transação", "Data"]
        df_stock = pd.DataFrame(stock_data, columns=columns)
        st.dataframe(df_stock, use_container_width=True)
    else:
        st.info("Nenhum registro de estoque encontrado.")

def clients_page():
    st.title("Clientes")
    st.subheader("Cadastrar Novo Cliente")

    with st.form(key='client_form'):
        nome_completo = st.text_input("Nome Completo")
        submit_client = st.form_submit_button(label="Cadastrar Cliente")

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
                st.success("Cliente cadastrado com sucesso!")
                refresh_data()
        else:
            st.warning("Por favor, preencha o campo Nome Completo.")

def invoice_page():
    st.title("Nota Fiscal")
    st.subheader("Gerar Nota Fiscal")
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
            st.dataframe(df)
            total_sum = df["total"].sum()
            st.subheader(f"Total Geral: R$ {total_sum:,.2f}")
            payment_options = ["Debitado", "Cartão de Crédito", "Pix"]
            payment_status = st.selectbox("Forma de Pagamento", payment_options)

            if st.button("Finalizar e Atualizar Status"):
                query = """
                UPDATE public.tb_pedido
                SET status = %s, "Data" = CURRENT_TIMESTAMP
                WHERE "Cliente" = %s AND status = 'em aberto';
                """
                success = run_insert(query, (payment_status, selected_client))
                if success:
                    st.success("Nota Fiscal atualizada e pagamento registrado com sucesso!")
                    refresh_data()
                else:
                    st.error("Erro ao atualizar a Nota Fiscal.")

#####################
# Initialization
#####################

if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

# Menu Navigation
st.session_state.page = sidebar_navigation()

# Page Routing
if st.session_state.page == "Início":
    home_page()
elif st.session_state.page == "Pedidos":
    orders_page()
elif st.session_state.page == "Produtos":
    products_page()
elif st.session_state.page == "Estoque":
    stock_page()
elif st.session_state.page == "Clientes":
    clients_page()
elif st.session_state.page == "Nota Fiscal":
    invoice_page()
