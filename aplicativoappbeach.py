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
# VERIFICAÇÃO DAS VARIÁVEIS DE AMBIENTE
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
    Estabelece uma conexão segura com o banco de dados usando variáveis de ambiente.
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
        # Exibe a mensagem de erro completa para diagnóstico
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
        # Aqui você pode usar variáveis de ambiente ou st.secrets se quiser:
        # admin_user = os.getenv("ADMIN_USERNAME", "admin")
        # admin_pass = os.getenv("ADMIN_PASSWORD", "adminbeach")
        # caixa_user = os.getenv("CAIXA_USERNAME", "caixa")
        # caixa_pass = os.getenv("CAIXA_PASSWORD", "caixabeach")
        
        # Por ora, mantendo fixo:
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
# TESTE DE CONEXÃO
#####################
def test_db_connection():
    """
    Testa a conexão ao banco antes de carregar dados,
    exibindo uma mensagem de sucesso ou de erro detalhada.
    """
    if not validate_env_vars():
        # Se variáveis de ambiente estão faltando, interrompe a execução.
        st.stop()

    # Testa conexão simples
    conn = get_db_connection()
    if conn is not None:
        st.success("Teste de conexão ao banco de dados: OK!")
        conn.close()
    else:
        st.stop()  # Interrompe a execução se a conexão falhar


#####################
# INICIALIZAÇÃO
#####################
# 1. Testa a conexão imediatamente (opcional, mas útil para diagnóstico)
if "db_tested" not in st.session_state:
    test_db_connection()
    st.session_state.db_tested = True

# 2. Carrega dados na sessão
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

# 3. Flag de login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# 4. Se não estiver logado, mostra a página de login
if not st.session_state.logged_in:
    login_page()
else:
    # Exibe o menu lateral
    selected_page = sidebar_navigation()

    if 'current_page' not in st.session_state:
        st.session_state.current_page = selected_page
    elif selected_page != st.session_state.current_page:
        refresh_data()
        st.session_state.current_page = selected_page

    # Roteamento de páginas
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

    # Botão de Logout na sidebar
    with st.sidebar:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.success("Desconectado com sucesso!")
            st.experimental_rerun()
