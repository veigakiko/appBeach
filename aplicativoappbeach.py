import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime, date
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
import os

########################
# UTILIDADES GERAIS
########################
def format_currency(value: float) -> str:
    """
    Formata um valor para o formato monetário brasileiro: R$ x.xx
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
# CONEXÃO COM BANCO
########################
@st.cache_resource
def get_db_connection():
    """
    Estabelece uma conexão segura com o banco de dados usando variáveis de ambiente.
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "beachtennis"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "password"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except OperationalError as e:
        st.error("Não foi possível conectar ao banco de dados. Verifique as configurações e tente novamente.")
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
# MENU LATERAL
#####################
def sidebar_navigation():
    """
    Cria um menu lateral para navegação usando streamlit_option_menu.
    """
    with st.sidebar:
        st.title("Boituva Beach Club 🎾")
        selected = option_menu(
            "Menu Principal",
            ["Home", "Orders", "Products", "Stock", "Clients", "Nota Fiscal"],
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
# PÁGINA DE LOGIN
#####################
def login_page():
    st.title("Beach Club")
    st.write("Por favor, insira suas credenciais para acessar o aplicativo.")

    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button(label="Login")

    if submit_login:
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
# INICIALIZAÇÃO
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

    # Roteamento de Páginas
    if selected_page == "Home":
        st.title("Página Home")
    elif selected_page == "Orders":
        st.title("Página Orders")
    elif selected_page == "Products":
        st.title("Página Products")
    elif selected_page == "Stock":
        st.title("Página Stock")
    elif selected_page == "Clients":
        st.title("Página Clients")
    elif selected_page == "Nota Fiscal":
        st.title("Página Nota Fiscal")

    with st.sidebar:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.success("Desconectado com sucesso!")
            st.experimental_rerun()
