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

    # Botão para mostrar resumo por status
    with col3:
        if st.button("Mostrar Resumo por Status"):
            st.session_state.show_status_summary = True
        else:
            st.session_state.show_status_summary = False
    
    # Exibir as tabelas fora das colunas, dependendo do que o usuário selecionou
    if st.session_state.get('show_status_summary', False):
        st.subheader("Status Summary")
        # Consulta para obter soma total agrupada por Status
        status_summary_query = """
        SELECT status, SUM("total") as Total
        FROM public.vw_pedido_produto
        GROUP BY status
        ORDER BY status;
        """
        status_summary_data = run_query(status_summary_query)

        if status_summary_data:
            # Criar DataFrame
            df_status_summary = pd.DataFrame(status_summary_data, columns=["Status", "Total"])

            # Formatar a coluna 'Total' para moeda brasileira
            df_status_summary["Total"] = df_status_summary["Total"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            
            # Remover o índice e selecionar apenas as colunas desejadas
            df_status_summary = df_status_summary.reset_index(drop=True)[["Status", "Total"]]
            
            # Exibir a tabela sem índice e com largura otimizada para a coluna
            st.dataframe(df_status_summary, use_container_width=True)

            ##############################
            # Criando o gráfico com os dados da tabela Status Summary
            ##############################

            # Preparando os dados para o gráfico
            status_labels = df_status_summary["Status"]
            status_totals = df_status_summary["Total"].apply(
                lambda x: float(x.replace("R$ ", "").replace(".", "").replace(",", "."))  # Convertendo o valor de volta para float
            )
            
            # Criando o gráfico de barras horizontais
            fig, ax = plt.subplots(figsize=(8, 4))  # Definir o tamanho do gráfico para garantir boa visibilidade
            y_pos = np.arange(len(status_labels))
            ax.barh(y_pos, status_totals, align='center', color='skyblue')
            ax.set_yticks(y_pos, labels=status_labels)
            ax.invert_yaxis()  # Inverte o eixo Y para rótulos de cima para baixo
            ax.set_xlabel('Total')
            ax.set_title('Total por Status')

            # Exibindo o gráfico no Streamlit
            st.pyplot(fig)
        else:
            st.info("Nenhum pedido encontrado para resumo por status.")

def products_page():
    st.title("Products")

    st.subheader("Add a new product")
    with st.form(key='product_form'):
        supplier = st.text_input("Supplier", max_chars=100)
        product = st.text_input("Product", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        unit_value = st.number_input("Unit Value", min_value=0.0, step=0.01, format="%.2f")
        creation_date = st.date_input("Creation Date")
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

    # Exibir todos os produtos
    products_data = st.session_state.data.get("products", [])
    if products_data:
        st.subheader("All Products")
        columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
        df_products = pd.DataFrame(products_data, columns=columns)
        
        # Depuração: Exibir nomes das colunas
        st.write("Columns in df_products:", df_products.columns.tolist())

        st.dataframe(df_products, use_container_width=True)

        st.subheader("Edit or Delete an Existing Product")
        # Criar uma chave única para identificar cada produto
        df_products["unique_key"] = df_products.apply(
            lambda row: f"{row['Supplier']}|{row['Product']}|{row['Creation Date'].strftime('%Y-%m-%d')}",
            axis=1
        )
        unique_keys = df_products["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select a product to edit/delete:", [""] + unique_keys)

        if selected_key:
            # Verificar quantos registros correspondem à chave única
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

                # Formulário para editar o produto
                with st.form(key='edit_product_form'):
                    edit_supplier = st.text_input("Supplier", value=original_supplier, max_chars=100)
                    edit_product = st.text_input("Product", value=original_product, max_chars=100)
                    edit_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(original_quantity))
                    edit_unit_value = st.number_input("Unit Value", min_value=0.0, step=0.01, format="%.2f", value=float(original_unit_value))
                    edit_creation_date = st.date_input("Creation Date", value=original_creation_date)

                    update_button = st.form_submit_button(label="Update Product")
                    delete_button = st.form_submit_button(label="Delete Product")

                if update_button:
                    # Recalcular total_value se quantity ou unit_value foram alterados
                    edit_total_value = edit_quantity * edit_unit_value

                    # Atualiza o produto no banco usando a combinação de campos como filtro
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
                    # Confirmação antes de deletar
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

def stock_page():
    st.title("Stock")

    st.subheader("Add a new stock record")

    # Carregar a lista de produtos da tabela tb_products
    product_data = run_query("SELECT product FROM public.tb_products ORDER BY product;")
    product_list = [row[0] for row in product_data] if product_data else ["No products available"]

    with st.form(key='stock_form'):
        product = st.selectbox("Product", product_list)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        transaction = st.selectbox("Transaction Type", ["Entrada", "Saída"])
        date = st.date_input("Date", value=datetime.now().date())
        submit_stock = st.form_submit_button(label="Register")

    if submit_stock:
        if product and quantity > 0:
            current_datetime = datetime.combine(date, datetime.min.time())

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

    # Exibir todos os registros de estoque
    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        st.subheader("All Stock Records")
        columns = ["Product", "Quantity", "Transaction", "Date"]
        df_stock = pd.DataFrame(stock_data, columns=columns)
        
        # Depuração: Exibir nomes das colunas
        st.write("Columns in df_stock:", df_stock.columns.tolist())

        st.dataframe(df_stock, use_container_width=True)

        st.subheader("Edit or Delete an Existing Stock Record")
        # Criar uma chave única para identificar cada registro de estoque
        df_stock["unique_key"] = df_stock.apply(
            lambda row: f"{row['Product']}|{row['Transaction']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
            axis=1
        )
        unique_keys = df_stock["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select a stock record to edit/delete:", [""] + unique_keys)

        if selected_key:
            # Verificar quantos registros correspondem à chave única
            matching_rows = df_stock[df_stock["unique_key"] == selected_key]
            if len(matching_rows) > 1:
                st.warning("Multiple stock records found with the same key. Please refine your selection.")
            else:
                selected_row = matching_rows.iloc[0]
                original_product = selected_row["Product"]
                original_quantity = selected_row["Quantity"]
                original_transaction = selected_row["Transaction"]
                original_date = selected_row["Date"]  # Isso é um objeto datetime

                # Formulário para editar o registro de estoque
                with st.form(key='edit_stock_form'):
                    edit_product = st.selectbox(
                        "Product",
                        product_list,
                        index=product_list.index(original_product) if original_product in product_list else 0
                    )
                    edit_quantity = st.number_input(
                        "Quantity",
                        min_value=1,
                        step=1,
                        value=int(original_quantity)
                    )
                    edit_transaction = st.selectbox(
                        "Transaction Type",
                        ["Entrada", "Saída"],
                        index=["Entrada", "Saída"].index(original_transaction) if original_transaction in ["Entrada", "Saída"] else 0
                    )
                    edit_date = st.date_input("Date", value=original_date.date())

                    update_button = st.form_submit_button(label="Update Stock Record")
                    delete_button = st.form_submit_button(label="Delete Stock Record")

                if update_button:
                    edit_datetime = datetime.combine(edit_date, datetime.min.time())

                    # Atualiza o registro de estoque no banco usando a combinação de campos como filtro
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
                    # Confirmação antes de deletar
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

def clients_page():
    st.title("Clients")

    st.subheader("Register a New Client")

    # Formulário com apenas o campo Full Name
    with st.form(key='client_form'):
        nome_completo = st.text_input("Full Name", max_chars=100)
        submit_client = st.form_submit_button(label="Register New Client")

    if submit_client:
        if nome_completo:
            # Outros valores padrões
            data_nascimento = datetime(2000, 1, 1).date()
            genero = "Man"
            telefone = "0000-0000"
            
            # Gera um email único para evitar conflito de chave única
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

    # Mostrar a tabela de clientes cadastrados
    clients_data = run_query("SELECT nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro FROM public.tb_clientes ORDER BY data_cadastro DESC;")

    if clients_data:
        st.subheader("All Clients")
        columns = ["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"]
        df_clients = pd.DataFrame(clients_data, columns=columns)
        st.dataframe(df_clients, use_container_width=True)

        st.subheader("Edit or Delete an Existing Client")
        # Selecionar um cliente para edição
        client_emails = df_clients["Email"].unique().tolist()
        selected_email = st.selectbox("Select a client by Email:", [""] + client_emails)

        if selected_email:
            # Obtém dados do cliente selecionado
            selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
            original_name = selected_client_row["Full Name"]

            # Formulário para editar o nome
            with st.form(key='edit_client_form'):
                edit_name = st.text_input("Full Name", value=original_name, max_chars=100)
                col1, col2 = st.columns(2)
                with col1:
                    update_button = st.form_submit_button(label="Update Client")
                with col2:
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
                # Confirmação antes de deletar
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

            total_sum = df["total"].sum()
            st.subheader(f"Total Geral: R$ {total_sum:,.2f}")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Debit", key="debit_button"):
                    process_payment(selected_client, "Received - Debited")
            with col2:
                if st.button("Credit", key="credit_button"):
                    process_payment(selected_client, "Received - Credit")
            with col3:
                if st.button("Pix", key="pix_button"):
                    process_payment(selected_client, "Received - Pix")
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
        quantity = f"{row['Quantidade']:>5}"
        total = row['total']
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
        if username == "" and password == "":
            st.session_state.logged_in = True
            st.success("Login bem-sucedido!")
        else:
            st.error("Nome de usuário ou senha incorretos.")

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

    # Adicionar opção de logout no sidebar
    with st.sidebar:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.success("Desconectado com sucesso!")
            st.experimental_rerun()
