import streamlit as st
from streamlit_option_menu import option_menu
import psycopg2
from psycopg2 import OperationalError
from datetime import datetime, date
import pandas as pd
from PIL import Image
import requests
from io import BytesIO

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
# CONEXÃO COM BANCO
########################
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
# PÁGINA HOME
#####################
def home_page():
    st.title("🎾 Boituva Beach Club 🎾")
    st.write("📍 Av. Do Trabalhador, 1879 — 🏆 5° Open BBC")

    # Apenas admin vê as informações de resumo
    if st.session_state.get("username") == "admin":
        st.markdown("**Open Orders Summary**")
        open_orders_query = """
        SELECT "Cliente", SUM("total") as Total
        FROM public.vw_pedido_produto
        WHERE status = %s
        GROUP BY "Cliente"
        ORDER BY "Cliente" DESC;
        """
        open_orders_data = run_query(open_orders_query, ('em aberto',))
        if open_orders_data:
            df_open_orders = pd.DataFrame(open_orders_data, columns=["Client", "Total"])
            total_open = df_open_orders["Total"].sum()
            df_open_orders["Total_display"] = df_open_orders["Total"].apply(format_currency)
            st.table(df_open_orders[["Client", "Total_display"]])
            st.markdown(f"**Total Geral (Open Orders):** {format_currency(total_open)}")
        else:
            st.info("Nenhum pedido em aberto encontrado.")

        st.markdown("**Closed Orders Summary**")
        closed_orders_query = """
        SELECT DATE("Data") as Date, SUM("total") as Total
        FROM public.vw_pedido_produto
        WHERE status != %s
        GROUP BY DATE("Data")
        ORDER BY DATE("Data") DESC;
        """
        closed_orders_data = run_query(closed_orders_query, ('em aberto',))
        if closed_orders_data:
            df_closed_orders = pd.DataFrame(closed_orders_data, columns=["Date", "Total"])
            total_closed = df_closed_orders["Total"].sum()
            df_closed_orders["Total_display"] = df_closed_orders["Total"].apply(format_currency)
            df_closed_orders["Date"] = pd.to_datetime(df_closed_orders["Date"]).dt.strftime('%Y-%m-%d')
            st.table(df_closed_orders[["Date", "Total_display"]])
            st.markdown(f"**Total Geral (Closed Orders):** {format_currency(total_closed)}")
        else:
            st.info("Nenhum pedido fechado encontrado.")

        st.markdown("## Stock vs. Orders Summary")
        try:
            stock_vs_orders_query = """
                SELECT product, stock_quantity, orders_quantity, total_in_stock
                FROM public.vw_stock_vs_orders_summary
            """
            stock_vs_orders_data = run_query(stock_vs_orders_query)
            if stock_vs_orders_data:
                # Cria o DataFrame com as colunas nomeadas
                df_stock_vs_orders = pd.DataFrame(
                    stock_vs_orders_data, 
                    columns=["Product", "Stock_Quantity", "Orders_Quantity", "Total_in_Stock"]
                )

                # Formata a coluna "Total_in_Stock" como moeda (R$)
                df_stock_vs_orders["Total_in_Stock_display"] = df_stock_vs_orders["Total_in_Stock"].apply(format_currency)

                # Prepara apenas as colunas que serão exibidas
                df_display = df_stock_vs_orders[[
                    "Product",
                    "Stock_Quantity",
                    "Orders_Quantity",
                    "Total_in_Stock_display"
                ]]

                # Exibe como tabela (similar ao Closed Orders Summary)
                st.table(df_display)

                # Calcula e exibe o Total Geral de 'Total_in_Stock'
                total_stock_value = df_stock_vs_orders["Total_in_Stock"].sum()
                st.markdown(f"**Total Geral (Stock vs. Orders):** {format_currency(total_stock_value)}")
            else:
                st.info("Não há dados na view vw_stock_vs_orders_summary.")
        except Exception as e:
            st.error(f"Erro ao gerar o resumo Stock vs. Orders: {e}")


#####################
# PÁGINA ORDERS
#####################
def orders_page():
    st.title("Orders")
    st.subheader("Register a new order")

    # Criando um pequeno filtro de nome do cliente para exibição da tabela abaixo
    search_client = st.text_input("Filtrar por Nome de Cliente (na tabela abaixo):")

    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["No products available"]

    with st.form(key='order_form'):
        # Carrega lista de clientes da tb_clientes
        clientes = run_query('SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;')
        customer_list = [""] + [row[0] for row in clientes]

        col1, col2, col3 = st.columns(3)
        with col1:
            customer_name = st.selectbox("Customer Name", customer_list, index=0)
        with col2:
            product = st.selectbox("Product", product_list, index=0)
        with col3:
            quantity = st.number_input("Quantity", min_value=1, step=1)

        submit_button = st.form_submit_button(label="Register Order")

    if submit_button:
        if customer_name and product and quantity > 0:
            query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", status)
            VALUES (%s, %s, %s, %s, 'em aberto');
            """
            timestamp = datetime.now()
            success = run_insert(query, (customer_name, product, quantity, timestamp))
            if success:
                st.success("Order registered successfully!")
                refresh_data()
            else:
                st.error("Failed to register the order.")
        else:
            st.warning("Please fill in all fields correctly.")

    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)

        # Filtra a tabela se o usuário digitou algo
        if search_client:
            df_orders = df_orders[df_orders["Client"].str.contains(search_client, case=False)]

        st.dataframe(df_orders, use_container_width=True)

        # Botão para exportar CSV
        download_df_as_csv(df_orders, "orders.csv", label="Download Orders CSV")

        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Edit or Delete an Existing Order")
            df_orders["unique_key"] = df_orders.apply(
                lambda row: f"{row['Client']}|{row['Product']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
                axis=1
            )
            unique_keys = df_orders["unique_key"].unique().tolist()
            selected_key = st.selectbox("Select an order to edit/delete:", [""] + unique_keys)

            if selected_key:
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
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            edit_product = st.selectbox(
                                "Product",
                                product_list,
                                index=product_list.index(original_product) if original_product in product_list else 0
                            )
                        with col2:
                            edit_quantity = st.number_input(
                                "Quantity",
                                min_value=1,
                                step=1,
                                value=int(original_quantity)
                            )
                        with col3:
                            edit_status_list = ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix", "Received - Cash"]
                            if original_status in edit_status_list:
                                edit_status_index = edit_status_list.index(original_status)
                            else:
                                edit_status_index = 0
                            edit_status = st.selectbox("Status", edit_status_list, index=edit_status_index)

                        col_upd, col_del = st.columns(2)
                        with col_upd:
                            update_button = st.form_submit_button(label="Update Order")
                        with col_del:
                            delete_button = st.form_submit_button(label="Delete Order")

                    if delete_button:
                        delete_query = """
                        DELETE FROM public.tb_pedido
                        WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                        """
                        success = run_insert(delete_query, (original_client, original_product, original_date))
                        if success:
                            st.success("Order deleted successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to delete the order.")

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
                            st.success("Order updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the order.")
    else:
        st.info("No orders found.")


#####################
# PÁGINA PRODUCTS
#####################
def products_page():
    st.title("Products")

    st.subheader("Add a new product")
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
        submit_product = st.form_submit_button(label="Insert Product")

    if submit_product:
        if supplier and product and quantity > 0 and unit_value >= 0:
            query = """
            INSERT INTO public.tb_products (supplier, product, quantity, unit_value, total_value, creation_date)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            total_value = quantity * unit_value
            success = run_insert(query, (supplier, product, quantity, unit_value, total_value, creation_date))
            if success:
                st.success("Product added successfully!")
                refresh_data()
            else:
                st.error("Failed to add the product.")
        else:
            st.warning("Please fill in all fields correctly.")

    products_data = st.session_state.data.get("products", [])
    if products_data:
        st.subheader("All Products")
        columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
        df_products = pd.DataFrame(products_data, columns=columns)
        st.dataframe(df_products, use_container_width=True)

        # Botão para exportar CSV
        download_df_as_csv(df_products, "products.csv", label="Download Products CSV")

        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Edit or Delete an Existing Product")
            df_products["unique_key"] = df_products.apply(
                lambda row: f"{row['Supplier']}|{row['Product']}|{row['Creation Date'].strftime('%Y-%m-%d')}",
                axis=1
            )
            unique_keys = df_products["unique_key"].unique().tolist()
            selected_key = st.selectbox("Select a product to edit/delete:", [""] + unique_keys)

            if selected_key:
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
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            edit_supplier = st.text_input("Supplier", value=original_supplier, max_chars=100)
                        with col2:
                            edit_product = st.text_input("Product", value=original_product, max_chars=100)
                        with col3:
                            edit_quantity = st.number_input(
                                "Quantity",
                                min_value=1,
                                step=1,
                                value=int(original_quantity)
                            )
                        with col4:
                            edit_unit_value = st.number_input(
                                "Unit Value",
                                min_value=0.0,
                                step=0.01,
                                format="%.2f",
                                value=float(original_unit_value)
                            )

                        edit_creation_date = st.date_input("Creation Date", value=original_creation_date)

                        col_upd, col_del = st.columns(2)
                        with col_upd:
                            update_button = st.form_submit_button(label="Update Product")
                        with col_del:
                            delete_button = st.form_submit_button(label="Delete Product")

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
                            st.success("Product updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the product.")

                    if delete_button:
                        confirm = st.checkbox("Are you sure you want to delete this product?")
                        if confirm:
                            delete_query = """
                            DELETE FROM public.tb_products
                            WHERE supplier = %s AND product = %s AND creation_date = %s;
                            """
                            success = run_insert(delete_query, (original_supplier, original_product, original_creation_date))
                            if success:
                                st.success("Product deleted successfully!")
                                refresh_data()
                            else:
                                st.error("Failed to delete the product.")
    else:
        st.info("No products found.")


#####################
# PÁGINA STOCK
#####################
def stock_page():
    st.title("Stock")
    st.subheader("Add a new stock record")
    st.write("""
Esta página foi projetada para registrar **apenas entradas de produtos no estoque** de forma prática e organizada.  
Com este sistema, você poderá monitorar todas as adições ao estoque com maior controle e rastreabilidade.  
""")

    product_data = run_query("SELECT product FROM public.tb_products ORDER BY product;")
    product_list = [row[0] for row in product_data] if product_data else ["No products available"]

    with st.form(key='stock_form'):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            product = st.selectbox("Product", product_list)
        with col2:
            quantity = st.number_input("Quantity", min_value=1, step=1)
        with col3:
            transaction = st.selectbox("Transaction Type", ["Entrada"])
        with col4:
            date_input = st.date_input("Date", value=datetime.now().date())

        submit_stock = st.form_submit_button(label="Register")

    if submit_stock:
        if product and quantity > 0:
            current_datetime = datetime.combine(date_input, datetime.min.time())
            query = """
            INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Transação", "Data")
            VALUES (%s, %s, %s, %s);
            """
            success = run_insert(query, (product, quantity, transaction, current_datetime))
            if success:
                st.success("Stock record added successfully!")
                refresh_data()
            else:
                st.error("Failed to add stock record.")
        else:
            st.warning("Please select a product and enter a quantity greater than 0.")

    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        st.subheader("All Stock Records")
        columns = ["Product", "Quantity", "Transaction", "Date"]
        df_stock = pd.DataFrame(stock_data, columns=columns)
        st.dataframe(df_stock, use_container_width=True)

        # Botão para exportar CSV
        download_df_as_csv(df_stock, "stock.csv", label="Download Stock CSV")

        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Edit or Delete an Existing Stock Record")
            df_stock["unique_key"] = df_stock.apply(
                lambda row: f"{row['Product']}|{row['Transaction']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
                axis=1
            )
            unique_keys = df_stock["unique_key"].unique().tolist()
            selected_key = st.selectbox("Select a stock record to edit/delete:", [""] + unique_keys)

            if selected_key:
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
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            edit_product = st.selectbox(
                                "Product",
                                product_list,
                                index=product_list.index(original_product) if original_product in product_list else 0
                            )
                        with col2:
                            edit_quantity = st.number_input(
                                "Quantity",
                                min_value=1,
                                step=1,
                                value=int(original_quantity)
                            )
                        with col3:
                            # Permitindo alterar para 'Saída', se quiser
                            edit_transaction = st.selectbox(
                                "Transaction Type",
                                ["Entrada", "Saída"],
                                index=["Entrada", "Saída"].index(original_transaction) if original_transaction in ["Entrada", "Saída"] else 0
                            )
                        with col4:
                            edit_date = st.date_input("Date", value=original_date.date())

                        col_upd, col_del = st.columns(2)
                        with col_upd:
                            update_button = st.form_submit_button(label="Update Stock Record")
                        with col_del:
                            delete_button = st.form_submit_button(label="Delete Stock Record")

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
                            st.success("Stock record updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the stock record.")

                    if delete_button:
                        confirm = st.checkbox("Are you sure you want to delete this stock record?")
                        if confirm:
                            delete_query = """
                            DELETE FROM public.tb_estoque
                            WHERE "Produto" = %s AND "Transação" = %s AND "Data" = %s;
                            """
                            success = run_insert(delete_query, (
                                original_product, original_transaction, original_date
                            ))
                            if success:
                                st.success("Stock record deleted successfully!")
                                refresh_data()
                            else:
                                st.error("Failed to delete the stock record.")
    else:
        st.info("No stock records found.")


#####################
# PÁGINA CLIENTS
#####################
def clients_page():
    st.title("Clients")
    st.subheader("Register a New Client")

    with st.form(key='client_form'):
        nome_completo = st.text_input("Full Name", max_chars=100)
        submit_client = st.form_submit_button(label="Register New Client")

    if submit_client:
        if nome_completo:
            # Exemplos de valores default
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
                st.success("Client registered successfully!")
                refresh_data()
        else:
            st.warning("Please fill in the Full Name field.")

    # Display all clients
    clients_data = run_query(
        """SELECT nome_completo, data_nascimento, genero,
                  telefone, email, endereco, data_cadastro
           FROM public.tb_clientes
           ORDER BY data_cadastro DESC;"""
    )
    if clients_data:
        st.subheader("All Clients")
        columns = ["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"]
        df_clients = pd.DataFrame(clients_data, columns=columns)
        st.dataframe(df_clients, use_container_width=True)

        # Botão de download
        download_df_as_csv(df_clients, "clients.csv", label="Download Clients CSV")

        # Admin-only edit/delete
        if st.session_state.get("username") == "admin":
            st.subheader("Edit or Delete an Existing Client")
            client_emails = df_clients["Email"].unique().tolist()
            selected_email = st.selectbox("Select a client by Email:", [""] + client_emails)

            if selected_email:
                selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
                original_name = selected_client_row["Full Name"]

                with st.form(key='edit_client_form'):
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_name = st.text_input("Full Name", value=original_name, max_chars=100)
                    with col2:
                        st.write("")  # Espaço para layout
                    col_upd, col_del = st.columns(2)
                    with col_upd:
                        update_button = st.form_submit_button(label="Update Client")
                    with col_del:
                        delete_button = st.form_submit_button(label="Delete Client")

                if update_button:
                    if edit_name:
                        update_query = """
                        UPDATE public.tb_clientes
                        SET nome_completo = %s
                        WHERE email = %s;
                        """
                        success = run_insert(update_query, (edit_name, selected_email))
                        if success:
                            st.success("Client updated successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to update the client.")
                    else:
                        st.warning("Please fill in the Full Name field.")

                if delete_button:
                    confirm = st.checkbox("Are you sure you want to delete this client?")
                    if confirm:
                        delete_query = "DELETE FROM public.tb_clientes WHERE email = %s;"
                        success = run_insert(delete_query, (selected_email,))
                        if success:
                            st.success("Client deleted successfully!")
                            refresh_data()
                        else:
                            st.error("Failed to delete the client.")
    else:
        st.info("No clients found.")


#####################
# PÁGINA NOTA FISCAL
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
                if st.button("Debit", key="debit_button"):
                    process_payment(selected_client, "Received - Debited")
            with col2:
                if st.button("Credit", key="credit_button"):
                    process_payment(selected_client, "Received - Credit")
            with col3:
                if st.button("Pix", key="pix_button"):
                    process_payment(selected_client, "Received - Pix")
            with col4:
                if st.button("Cash", key="cash_button"):
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


def generate_invoice_for_printer(df: pd.DataFrame):
    """
    Exibe em tela uma 'nota fiscal' para impressão.
    """
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
        description = f"{row['Produto'][:20]:<20}"  # limitando a 20 chars
        quantity = f"{int(row['Quantidade']):>5}"
        total = row['total']
        total_general += total
        total_formatted = format_currency(total)
        invoice_note.append(f"{description} {quantity} {total_formatted}")

    invoice_note.append("--------------------------------------------------")
    invoice_note.append(f"{'TOTAL GERAL:':>30} {format_currency(total_general):>10}")
    invoice_note.append("==================================================")
    invoice_note.append("OBRIGADO PELA SUA PREFERÊNCIA!")
    invoice_note.append("==================================================")

    st.text("\n".join(invoice_note))


#####################
# PÁGINA DE LOGIN
#####################
def login_page():
    st.markdown(
        """
        <style>
        body {
            background-color: white;
        }
        .block-container {
            padding-top: 100px;
            padding-bottom: 100px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    logo_url = "https://res.cloudinary.com/lptennis/image/upload/v1657233475/kyz4k7fcptxt7x7mu9qu.jpg"
    try:
        response = requests.get(logo_url)
        response.raise_for_status()
        logo = Image.open(BytesIO(response.content))
        st.image(logo, use_column_width=False)
    except requests.exceptions.RequestException as e:
        st.error("Falha ao carregar o logotipo.")

    st.title("Beach Club")
    st.write("Por favor, insira suas credenciais para acessar o aplicativo.")

    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button(label="Login")

    if submit_login:
        # Dois usuários possíveis: admin / caixa
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
        if selected_page == "Home":
            st.session_state.home_page_initialized = False

    # Roteamento de Páginas
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
            # Opcional: limpar dados de página
            keys_to_reset = ['home_page_initialized']
            for key in keys_to_reset:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.logged_in = False
            st.success("Desconectado com sucesso!")
            st.experimental_rerun()
