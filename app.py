# app.py

import streamlit as st
from streamlit_option_menu import option_menu
from database import run_query, run_insert
from helpers import refresh_data
import pandas as pd

# Initialize session state
if 'data' not in st.session_state:
    def load_all_data():
        """
        Loads all necessary data for the application.
        """
        data = {}
        try:
            data["orders"] = run_query(
                'SELECT order_id, "Cliente", "Produto", "Quantidade", "Data", status FROM public.tb_pedido ORDER BY "Data" DESC;'
            )
            data["products"] = run_query(
                "SELECT product_id, supplier, product, quantity, unit_value, total_value, creation_date FROM public.tb_products;"
            )
            data["clients"] = run_query('SELECT client_id, "Cliente" FROM public.tb_clientes;')
            data["stock"] = run_query(
                'SELECT stock_id, "Produto", "Quantidade", "Transação", "Data" FROM public.tb_estoque;'
            )
        except Exception as e:
            st.error(f"Error loading data: {e}")
        return data

    st.session_state.data = load_all_data()

# Sidebar Navigation
def sidebar_navigation():
    """
    Creates a sidebar menu for navigation using streamlit_option_menu.
    """
    with st.sidebar:
        st.title("Boituva Beach Club")
        selected = option_menu(
            "Beach Menu", ["Home", "Orders", "Products", "Stock", "Clients", "Nota Fiscal"],
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

# Assign selected page to session state
st.session_state.page = sidebar_navigation()

# Page Routing
if st.session_state.page == "Home":
    from pages.home import home_page
    home_page()
elif st.session_state.page == "Orders":
    from pages.orders import orders_page
    orders_page()
elif st.session_state.page == "Products":
    from pages.products import products_page
    products_page()
elif st.session_state.page == "Stock":
    from pages.stock import stock_page
    stock_page()
elif st.session_state.page == "Clients":
    from pages.clients import clients_page
    clients_page()
elif st.session_state.page == "Nota Fiscal":
    from pages.invoice import invoice_page
    invoice_page()
