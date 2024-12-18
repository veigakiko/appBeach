import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime
import pandas as pd
import hashlib

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
    Runs an insert, update, or delete query.
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
        st.error(f"Error executing query: {e}")
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
            'SELECT supplier, product, quantity, unit_value, total_value, creation_date FROM public.tb_products ORDER BY creation_date DESC;'
        )
        data["clients"] = run_query('SELECT DISTINCT "Cliente" FROM public.tb_pedido ORDER BY "Cliente";')
        data["stock"] = run_query(
            'SELECT "Produto", "Quantidade", "Transação", "Data" FROM public.tb_estoque ORDER BY "Data" DESC;'
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
            "Beach Menu", ["Home", "Orders", "Products", "Stock", "Clients", "Nota Fiscal"],
            icons=["house", "file-text", "box", "list-task", "layers", "person", "file-invoice"],
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

def home_page():
    st.title("Boituva Beach Club")
    st.write("🎾 BeachTennis 📍 Av. Do Trabalhador, 1879 🏆 5° Open BBC")
    st.info("Os dados são atualizados automaticamente ao navegar entre as páginas.")
    
    ############################
    # Botões para exibir as tabelas
    ############################

    # Criar colunas para botões alinhados horizontalmente
    col1, col2, col3, col4, col5 = st.columns(5)

    # Botão para mostrar pedidos em aberto
    with col1:
        if st.button("Mostrar Pedidos em Aberto"):
            st.session_state.show_open_orders = True
        else:
            st.session_state.show_open_orders = False
    
    # Botão para mostrar pedidos fechados
    with col2:
        if st.button("Mostrar Pedidos Fechados"):
            st.session_state.show_closed_orders = True
        else:
            st.session_state.show_closed_orders = False
    
    # Botão para mostrar resumo por status
    with col3:
        if st.button("Mostrar Resumo por Status"):
            st.session_state.show_status_summary = True
        else:
            st.session_state.show_status_summary = False
    
    # Botão para mostrar resumo por produto
    with col4:
        if st.button("Mostrar Resumo por Produto"):
            st.session_state.show_product_summary = True
        else:
            st.session_state.show_product_summary = False
    
    # Botão para mostrar resumo combinado de produto e estoque
    with col5:
        if st.button("Mostrar Resumo Combinado de Produto e Estoque"):
            st.session_state.show_combined_summary = True
        else:
            st.session_state.show_combined_summary = False

    # Exibir as tabelas fora das colunas, dependendo do que o usuário selecionou
    if st.session_state.get('show_open_orders', False):
        st.subheader("Open Orders Summary")
        # Consulta para obter pedidos em aberto agrupados por Cliente e Data (somente dia) com a soma total
        open_orders_query = """
        SELECT "Cliente", DATE("Data") as Date, SUM("total") as Total
        FROM public.vw_pedido_produto
        WHERE status = %s
        GROUP BY "Cliente", DATE("Data")
        ORDER BY "Cliente", DATE("Data") DESC;
        """
        open_orders_data = run_query(open_orders_query, ('em aberto',))

        if open_orders_data:
            # Criar DataFrame
            df_open_orders = pd.DataFrame(open_orders_data, columns=["Client", "Date", "Total"])
            
            # Calcular a soma total dos pedidos em aberto
            total_open = df_open_orders["Total"].sum()
            
            # Formatar a coluna 'Date' para exibição amigável
            df_open_orders["Date"] = pd.to_datetime(df_open_orders["Date"]).dt.strftime('%Y-%m-%d')
            
            # Formatar a coluna 'Total' para moeda brasileira
            df_open_orders["Total"] = df_open_orders["Total"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            
            # Remover o índice e selecionar apenas as colunas desejadas
            df_open_orders = df_open_orders.reset_index(drop=True)[["Client", "Date", "Total"]]
            
            # Exibir a tabela sem índice e com largura otimizada para a coluna
            st.dataframe(df_open_orders, use_container_width=True)
            
            # Exibir a soma total abaixo da tabela
            st.markdown(f"**Total Geral (Open Orders):** R$ {total_open:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        else:
            st.info("Nenhum pedido em aberto encontrado.")
    
    if st.session_state.get('show_closed_orders', False):
        st.subheader("Closed Orders Summary")
        closed_orders_query = """
        SELECT "Cliente", DATE("Data") as Date, SUM("total") as Total
        FROM public.vw_pedido_produto
        WHERE status != %s
        GROUP BY "Cliente", DATE("Data")
        ORDER BY "Cliente", DATE("Data") DESC;
        """
        closed_orders_data = run_query(closed_orders_query, ('em aberto',))

        if closed_orders_data:
            df_closed_orders = pd.DataFrame(closed_orders_data, columns=["Client", "Date", "Total"])
            
            total_closed = df_closed_orders["Total"].sum()
            df_closed_orders["Date"] = pd.to_datetime(df_closed_orders["Date"]).dt.strftime('%Y-%m-%d')
            df_closed_orders["Total"] = df_closed_orders["Total"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            df_closed_orders = df_closed_orders.reset_index(drop=True)[["Client", "Date", "Total"]]
            
            st.dataframe(df_closed_orders, use_container_width=True)
            st.markdown(f"**Total Geral (Closed Orders):** R$ {total_closed:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        else:
            st.info("Nenhum pedido fechado encontrado.")
    
    if st.session_state.get('show_status_summary', False):
        st.subheader("Status Summary")
        status_summary_query = """
        SELECT status, SUM("total") as Total
        FROM public.vw_pedido_produto
        GROUP BY status
        ORDER BY status;
        """
        status_summary_data = run_query(status_summary_query)

        if status_summary_data:
            df_status_summary = pd.DataFrame(status_summary_data, columns=["Status", "Total"])

            df_status_summary["Total"] = df_status_summary["Total"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            
            df_status_summary = df_status_summary.reset_index(drop=True)[["Status", "Total"]]
            st.dataframe(df_status_summary, use_container_width=True)
        else:
            st.info("Nenhum pedido encontrado para resumo por status.")
    
    # You can continue with the other page handling similarly...

#####################
# Login Page
#####################
def login_page():
    st.title("Beach Club")
    st.write("Por favor, insira suas credenciais para acessar o aplicativo.")

    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button(label="Login")

    if submit_login:
        # Example hardcoded check. Replace with real check
        if username == "admin" and hash_password(password) == hash_password("admin123"):
            st.session_state.logged_in = True
            st.success("Login bem-sucedido!")
        else:
            st.error("Nome de usuário ou senha incorretos.")

def hash_password(password):
    """
    Simple password hashing for security. You should use a stronger method like bcrypt in real applications.
    """
    return hashlib.sha256(password.encode()).hexdigest()

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

    # Page Routing
    if selected_page == "Home":
        home_page()
    # Implement other pages as needed...
