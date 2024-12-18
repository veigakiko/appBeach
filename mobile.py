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
            host=st.secrets["DB"]["DB_HOST"],
            database=st.secrets["DB"]["DB_NAME"],
            user=st.secrets["DB"]["DB_USER"],
            password=st.secrets["DB"]["DB_PASSWORD"],
            port=st.secrets["DB"]["DB_PORT"]
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
        st.error(f"Error executing query: {e}")
        return []
    finally:
        if conn:
            conn.close()

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
        st.error(f"Error executing insert: {e}")
        return False
    finally:
        if conn:
            conn.close()

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
            icons=["house", "file-text", "box", "list-task", "people", "file-invoice"],
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
    st.write("🎾 BeachTennis📍Av. Do Trabalhador, 1879🏆 5° Open BBC")
    st.button("Refresh Data", on_click=refresh_data)

def orders_page():
    st.title("Orders")
    st.subheader("Register a new order")

    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["No products available"]

    # Formulário para inserir novo pedido
    with st.form(key='order_form'):
        # Carregando lista de clientes para o novo pedido
        clientes = run_query('SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;')
        customer_list = [""] + [row[0] for row in clientes] if clientes else ["No clients available"]

        customer_name = st.selectbox("Customer Name", customer_list, index=0)
        product = st.selectbox("Product", product_list, index=0)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Register Order")

    if submit_button:
        if customer_name and product and quantity > 0:
            query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", "status")
            VALUES (%s, %s, %s, %s, 'em aberto');
            """
            timestamp = datetime.now()
            success = run_insert(query, (customer_name, product, quantity, timestamp))
            if success:
                st.success("Order registered successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all fields correctly.")

    # Exibir todos os pedidos
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        st.dataframe(df_orders, use_container_width=True)

        # Cria identificadores únicos temporários com base em Cliente, Produto e Data
        # Convertendo Data para string, caso esteja em datetime, para exibição
        df_orders["unique_key"] = df_orders.apply(lambda row: f"{row['Cliente']}|{row['Produto']}|{row['Data']}", axis=1)

        st.subheader("Edit an existing order")
        # Selecionar um pedido pelo identificador único
        unique_keys = df_orders["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select an order to edit:", [""] + unique_keys)

        if selected_key:
            # Extrair valores originais do pedido selecionado
            selected_row = df_orders[df_orders["unique_key"] == selected_key].iloc[0]

            original_client = selected_row["Client"]
            original_product = selected_row["Product"]
            original_date = selected_row["Date"]  # provavelmente datetime
            original_quantity = selected_row["Quantity"]
            original_status = selected_row["Status"]

            # Prepara o formulário de edição
            # Para o produto, reutiliza a mesma lista product_list, ajustando o índice se possível.
            product_index = product_list.index(original_product) if original_product in product_list else 0

            with st.form(key='edit_order_form'):
                edit_product = st.selectbox("Product", product_list, index=product_index)
                edit_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(original_quantity))
                edit_status_list = ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix"]
                edit_status_index = edit_status_list.index(original_status) if original_status in edit_status_list else 0
                edit_status = st.selectbox("Status", edit_status_list, index=edit_status_index)

                update_button = st.form_submit_button(label="Update Order")

            if update_button:
                # Atualiza o pedido no banco
                # Usa (Cliente, Produto, Data) originais no WHERE, pois são únicos.
                update_query = """
                UPDATE public.tb_pedido
                SET "Produto" = %s, "Quantidade" = %s, status = %s, "Data" = %s
                WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                """
                new_timestamp = datetime.now()
                success = run_insert(update_query, (edit_product, edit_quantity, edit_status, new_timestamp, original_client, original_product, original_date))
                if success:
                    st.success("Order updated successfully!")
                    refresh_data()
                else:
                    st.error("Failed to update the order.")

            st.subheader("Delete an Order")
            with st.form(key='delete_order_form'):
                st.warning("Are you sure you want to delete this order?")
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
    else:
        st.info("No orders found.")

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

    products_data = st.session_state.data.get("products", [])
    columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
    if products_data:
        st.subheader("All Products")
        df_products = pd.DataFrame(products_data, columns=columns)
        st.dataframe(df_products, use_container_width=True)

        # Criando uma chave única a partir de (Supplier, Product, Creation Date)
        # Supondo que cada combinação dessas colunas é única.
        df_products["unique_key"] = df_products.apply(
            lambda row: f"{row['Supplier']}|{row['Product']}|{row['Creation Date']}", axis=1
        )

        st.subheader("Edit an existing product")

        unique_keys = df_products["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select a product to edit:", [""] + unique_keys)

        if selected_key:
            selected_row = df_products[df_products["unique_key"] == selected_key].iloc[0]

            original_supplier = selected_row["Supplier"]
            original_product = selected_row["Product"]
            original_quantity = selected_row["Quantity"]
            original_unit_value = selected_row["Unit Value"]
            original_total_value = selected_row["Total Value"]
            original_creation_date = selected_row["Creation Date"]

            # Formulário de edição
            with st.form(key='edit_product_form'):
                edit_supplier = st.text_input("Supplier", value=original_supplier, max_chars=100)
                edit_product = st.text_input("Product", value=original_product, max_chars=100)
                edit_quantity = st.number_input("Quantity", min_value=1, step=1, value=int(original_quantity))
                edit_unit_value = st.number_input("Unit Value", min_value=0.0, step=0.01, format="%.2f", value=float(original_unit_value))
                edit_creation_date = st.date_input("Creation Date", value=original_creation_date)

                update_button = st.form_submit_button(label="Update Product")

            if update_button:
                # Recalcular total_value se quantity ou unit_value foram alterados
                edit_total_value = edit_quantity * edit_unit_value

                # Atualiza o produto no banco
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
                success = run_insert(update_query, (edit_supplier, edit_product, edit_quantity, edit_unit_value, edit_total_value, edit_creation_date, 
                                                     original_supplier, original_product, original_creation_date))
                if success:
                    st.success("Product updated successfully!")
                    refresh_data()
                else:
                    st.error("Failed to update the product.")

            st.subheader("Delete a Product")
            with st.form(key='delete_product_form'):
                st.warning("Are you sure you want to delete this product?")
                delete_button = st.form_submit_button(label="Delete Product")

            if delete_button:
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
    product_data = run_query("SELECT product FROM public.tb_products;")
    product_list = [row[0] for row in product_data] if product_data else ["No products available"]

    with st.form(key='stock_form'):
        product = st.selectbox("Product", product_list)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        transaction_type = st.selectbox("Transaction Type", ["Entrada", "Saída"])
        submit_stock = st.form_submit_button(label="Register")

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
                st.success("Stock record added successfully!")
                refresh_data()
            else:
                st.error("Failed to add stock record.")
        else:
            st.warning("Please select a product and enter a quantity greater than 0.")

    # Carregar os registros do estoque atualizados
    stock_data = st.session_state.data.get("stock", [])
    columns = ["Product", "Quantity", "Transaction", "Date"]

    if stock_data:
        st.subheader("All Stock Records")
        try:
            # Convertendo tuplas para dicionário para exibir no DataFrame
            df_stock = pd.DataFrame(stock_data, columns=columns)
            st.dataframe(df_stock, use_container_width=True)
        except ValueError as ve:
            st.error(f"DataFrame creation failed: {ve}")
            st.write("Columns Expected:", columns)
            st.write("Number of elements per row:", [len(row) for row in stock_data])
            st.write("Example Row:", stock_data[0] if stock_data else "No data")
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

        # Selecionar um cliente para edição
        st.subheader("Edit or Delete an existing client")
        client_emails = df_clients["Email"].unique().tolist()
        selected_email = st.selectbox("Select a client by Email:", [""] + client_emails)

        if selected_email:
            # Obtém dados do cliente selecionado
            selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
            original_name = selected_client_row["Full Name"]

            # Formulário para editar o nome
            with st.form(key='edit_client_form'):
                edit_name = st.text_input("Full Name", value=original_name, max_chars=100)
                update_button = st.form_submit_button(label="Update Client")

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

            # Formulário separado para excluir o cliente
            st.subheader("Delete a Client")
            with st.form(key='delete_client_form'):
                st.warning("Are you sure you want to delete this client?")
                delete_button = st.form_submit_button(label="Delete Client")

            if delete_button:
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
    Updates the status of specific orders to the selected payment status.
    
    Parameters:
    - invoice_keys (list): List of unique identifiers for the orders (Cliente|Produto|Data).
    - payment_status (str): New status to assign.
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
    Generates a formatted invoice for printing.
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
        quantity = f"{row['Quantidade']:>5}"
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
# Initialization
#####################

# Inicializar variáveis de estado da sessão
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

# Menu Navigation
selected_page = sidebar_navigation()

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
