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


def run_query(query, values=None):
    """
    Run a SELECT query and return the fetched results.
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
    Run an INSERT/UPDATE/DELETE query and commit changes.
    Return True if successful, False otherwise.
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
        st.error(f"Error executing insert/update: {e}")
        return False

#####################
# Data Loading
#####################
def load_all_data():
    """
    Load all initial data from the database and return as a dictionary.
    Using the original SELECT queries without any id columns.
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
            'SELECT "Produto", "Quantidade", "Valor", "Total", "Transação", "Data" FROM public.tb_estoque;'
        )
    except Exception as e:
        st.error(f"Error loading data: {e}")
    return data

def refresh_data():
    """
    Reload all data into session state.
    """
    st.session_state.data = load_all_data()

#####################
# Utility Functions
#####################
def process_payment(client, payment_status):
    """
    Update orders for a given client to a payment status and refresh data.
    """
    query = """
    UPDATE public.tb_pedido
    SET status = %s, "Data" = CURRENT_TIMESTAMP
    WHERE "Cliente" = %s AND status = 'em aberto';
    """
    success = run_insert(query, (payment_status, client))
    if success:
        st.success(f"Status updated to: {payment_status}")
        refresh_data()
    else:
        st.error("Error updating the status.")

#####################
# Menu Navigation
#####################
def sidebar_navigation():
    """
    Create the sidebar navigation menu.
    """
    with st.sidebar:
        st.title("Boituva Beach Club")
        selected = option_menu(
            "Beach Menu",
            ["Home", "Orders", "Invoice", "Stock", "Clients", "Commands"],
            icons=["house", "file-text", "file-invoice", "layers", "person", "list-task"],
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
    import altair as alt

    # Sidebar Filters
    st.sidebar.header("Filters")
    start_date = st.sidebar.date_input("Start Date", value=pd.to_datetime("today") - pd.Timedelta(days=6))
    end_date = st.sidebar.date_input("End Date", value=pd.to_datetime("today"))
    if start_date > end_date:
        st.sidebar.error("Start Date must be before or equal to End Date.")
    
    # Convert to strings for queries
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    # Page Title and Intro
    st.title("Boituva Beach Club Dashboard")
    st.write(
        "🎾 **BeachTennis** @ Av. Do Trabalhador, 1879\n"
        "🏆 5° Open BBC\n\n"
        "Welcome to the Boituva Beach Club operational dashboard. Here, you can track daily performance, "
        "examine trends over time, and gain insights into product and client behaviors."
    )

    st.subheader("Today's Highlights (Automatic Daily KPIs)")

    # Today's metrics
    total_orders_today = run_query("""
        SELECT COUNT(*) 
        FROM public.tb_pedido 
        WHERE DATE("Data") = CURRENT_DATE;
    """)
    total_orders = total_orders_today[0][0] if total_orders_today else 0

    total_revenue_today = run_query("""
        SELECT SUM("Quantidade" * unit_value) AS total_revenue
        FROM vw_pedido_produto
        WHERE DATE("Data") = CURRENT_DATE;
    """)
    total_revenue = total_revenue_today[0][0] if total_revenue_today and total_revenue_today[0][0] is not None else 0.0
    aov = (total_revenue / total_orders) if total_orders > 0 else 0.0

    unique_clients_today = run_query("""
        SELECT COUNT(DISTINCT "Cliente")
        FROM public.tb_pedido
        WHERE DATE("Data") = CURRENT_DATE;
    """)
    total_unique_clients = unique_clients_today[0][0] if unique_clients_today else 0

    distinct_products_today = run_query("""
        SELECT COUNT(DISTINCT "Produto")
        FROM public.tb_pedido
        WHERE DATE("Data") = CURRENT_DATE;
    """)
    total_distinct_products = distinct_products_today[0][0] if distinct_products_today else 0

    # KPI Row
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Orders", total_orders)
    col2.metric("Total Revenue", f"R$ {total_revenue:,.2f}")
    col3.metric("Unique Clients", total_unique_clients)
    col4.metric("Distinct Products", total_distinct_products)
    col5.metric("AOV", f"R$ {aov:,.2f}")

    st.divider()

    # Top products and clients (Today)
    st.subheader("Today's Product and Client Performance")

    # Queries for Today
    top_products_today = run_query("""
        SELECT "Produto", SUM("Quantidade") AS total_q
        FROM public.tb_pedido
        WHERE DATE("Data") = CURRENT_DATE
        GROUP BY "Produto"
        ORDER BY total_q DESC
        LIMIT 5;
    """)

    top_products_revenue_today = run_query("""
        SELECT "Produto", SUM("Quantidade" * unit_value) AS total_revenue
        FROM vw_pedido_produto
        WHERE DATE("Data") = CURRENT_DATE
        GROUP BY "Produto"
        ORDER BY total_revenue DESC
        LIMIT 5;
    """)

    top_clients_today = run_query("""
        SELECT "Cliente", SUM("Quantidade" * unit_value) AS client_revenue
        FROM vw_pedido_produto
        WHERE DATE("Data") = CURRENT_DATE
        GROUP BY "Cliente"
        ORDER BY client_revenue DESC
        LIMIT 5;
    """)

    # Top Products by Quantity (bar chart)
    st.write("**Top 5 Products by Quantity Sold Today**")
    if top_products_today:
        df_top_products_qty = pd.DataFrame(top_products_today, columns=["Product", "Quantity"])
        st.bar_chart(df_top_products_qty.set_index("Product"))
    else:
        st.write("No products sold today.")

    st.write("**Top 5 Products by Revenue Today**")
    if top_products_revenue_today:
        df_top_products_rev = pd.DataFrame(top_products_revenue_today, columns=["Product", "Revenue"])
        df_top_products_rev.set_index("Product", inplace=True)
        chart_data = df_top_products_rev.reset_index()
        pie_chart = (
            alt.Chart(chart_data)
            .mark_arc(innerRadius=50)
            .encode(
                theta='Revenue:Q',
                color='Product:N',
                tooltip=[
                    alt.Tooltip('Product:N', title='Product'),
                    alt.Tooltip('Revenue:Q', title='Revenue', format=',.2f')
                ]
            )
        )
        st.altair_chart(pie_chart, use_container_width=True)
    else:
        st.write("No revenue data available for products today.")

    st.write("**Top 5 Clients by Revenue Today**")
    if top_clients_today:
        df_top_clients = pd.DataFrame(top_clients_today, columns=["Client", "Revenue"])
        df_top_clients.set_index("Client", inplace=True)
        st.bar_chart(df_top_clients)
    else:
        st.write("No clients with orders today.")

    st.divider()

    # Scatter plot: Quantity vs Revenue for today's top products by revenue
    st.subheader("Correlation Insight: Product Quantity vs. Revenue (Today)")
    if top_products_revenue_today:
        product_names = tuple([p[0] for p in top_products_revenue_today])
        # Handle single product tuple formatting for SQL
        if len(product_names) == 1:
            product_names = f"('{product_names[0]}')"
        product_details = run_query(f"""
            SELECT "Produto", SUM("Quantidade") as q, SUM("Quantidade"*unit_value) as rev
            FROM vw_pedido_produto
            WHERE DATE("Data")=CURRENT_DATE 
              AND "Produto" IN {product_names}
            GROUP BY "Produto";
        """)
        if product_details:
            df_product_details = pd.DataFrame(product_details, columns=["Product", "Quantity", "Revenue"])
            scatter_chart = (
                alt.Chart(df_product_details)
                .mark_circle(size=100)
                .encode(
                    x=alt.X('Quantity:Q', title='Quantity Sold'),
                    y=alt.Y('Revenue:Q', title='Revenue'),
                    color='Product:N',
                    tooltip=['Product', alt.Tooltip('Quantity:Q', format=',.0f'), alt.Tooltip('Revenue:Q', format=',.2f')]
                )
                .interactive()
            )
            st.altair_chart(scatter_chart, use_container_width=True)
        else:
            st.write("Not enough product data for correlation analysis.")
    else:
        st.write("No product revenue data for correlation today.")

    st.divider()

    # Time-series trends based on selected date range
    st.subheader("Time-Series Trends")
    st.write(f"Analyzing orders and revenue from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}.")

    # Last X days orders
    date_filtered_orders = run_query(f"""
        SELECT DATE("Data") as order_date, COUNT(*) as total_orders
        FROM public.tb_pedido
        WHERE DATE("Data") >= '{start_str}' AND DATE("Data") <= '{end_str}'
        GROUP BY DATE("Data")
        ORDER BY DATE("Data");
    """)

    # Last X days revenue
    date_filtered_revenue = run_query(f"""
        SELECT DATE("Data") as order_date, SUM("Quantidade" * unit_value) as daily_revenue
        FROM vw_pedido_produto
        WHERE DATE("Data") >= '{start_str}' AND DATE("Data") <= '{end_str}'
        GROUP BY DATE("Data")
        ORDER BY DATE("Data");
    """)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.write("**Orders Over Selected Period**")
        if date_filtered_orders:
            df_orders_period = pd.DataFrame(date_filtered_orders, columns=["Date", "Total Orders"]).set_index("Date")
            st.line_chart(df_orders_period)
        else:
            st.info("No orders found for the selected period.")

    with col_t2:
        st.write("**Revenue Over Selected Period**")
        if date_filtered_revenue:
            df_revenue_period = pd.DataFrame(date_filtered_revenue, columns=["Date", "Revenue"]).set_index("Date")
            st.line_chart(df_revenue_period)
        else:
            st.info("No revenue data for the selected period.")

    st.write(
        "Use the filters on the left sidebar to adjust the date range and see how performance changes "
        "over different time horizons."
    )

    st.button("Refresh Data", on_click=refresh_data)

def orders_page():
    st.title("Orders")
    st.subheader("Register a new order")

    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["No products available"]

    # Fetch clients from tb_clientes table
    customer_names = run_query('SELECT nome_completo FROM public.tb_clientes')
    customer_list = [""] + [row[0] for row in customer_names] if customer_names else [""]

    with st.form(key='order_form'):
        customer_name = st.selectbox("Customer Name", customer_list, index=0)
        product = st.selectbox("Product", product_list, index=0)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        submit_button = st.form_submit_button(label="Register Order")

    if submit_button:
        if customer_name and product and quantity > 0:
            insert_query = """
            INSERT INTO public.tb_pedido ("Cliente", "Produto", "Quantidade", "Data", "status")
            VALUES (%s, %s, %s, %s, 'em aberto');
            """
            timestamp = datetime.now()
            success = run_insert(insert_query, (customer_name, product, quantity, timestamp))
            if success:
                st.success("Order registered successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all fields correctly.")

    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        st.dataframe(df_orders, use_container_width=True)

        # Generate a list of unique keys for selecting an order to edit
        # We'll use "Cliente | Produto | Data" as a unique key
        order_keys = [f"{o[0]} | {o[1]} | {o[3]}" for o in orders_data]
        selected_order_key = st.selectbox("Select an Order to Edit", [""] + order_keys)
        if selected_order_key:
            # Parse the selected key
            parts = selected_order_key.split("|")
            selected_cliente = parts[0].strip()
            selected_produto = parts[1].strip()
            selected_data_str = parts[2].strip()

            # Find the matching order
            selected_order = [o for o in orders_data if o[0] == selected_cliente and o[1] == selected_produto and str(o[3]) == selected_data_str]
            if selected_order:
                current_cliente, current_produto, current_quantidade, current_data, current_status = selected_order[0]

                st.subheader("Edit Selected Order")
                with st.form(key='edit_order_form'):
                    new_client = st.text_input("Client", value=current_cliente)
                    new_product = st.text_input("Product", value=current_produto)
                    new_quantity = st.number_input("Quantity", min_value=1, step=1, value=current_quantidade)
                    update_button = st.form_submit_button("Update Order")

                if update_button:
                    update_query = """
                    UPDATE public.tb_pedido
                    SET "Cliente" = %s, "Produto" = %s, "Quantidade" = %s
                    WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                    """
                    success = run_insert(update_query, (new_client, new_product, new_quantity, current_cliente, current_produto, current_data))
                    if success:
                        st.success("Order updated successfully!")
                        refresh_data()
    else:
        st.info("No orders found.")

def commands_page():
    st.title("Commands")

    clients_data = [""] + [row[0] for row in st.session_state.data.get("clients", [])]

    if clients_data:
        selected_client = st.selectbox("Select a Client", clients_data)

        if selected_client:
            query = """
            SELECT "Cliente", "Produto", "Quantidade", "Data", status, unit_value, 
                   ("Quantidade" * unit_value) AS total
            FROM vw_pedido_produto
            WHERE "Cliente" = %s;
            """
            client_orders = run_query(query, (selected_client,))

            if client_orders:
                columns = ["Client", "Product", "Quantity", "Date", "Status", "Unit Value", "Total"]
                df = pd.DataFrame(client_orders, columns=columns)
                st.divider()
                st.dataframe(df, use_container_width=True)

                total_sum = df["Total"].sum()
                st.subheader(f"Total Amount: R$ {total_sum:,.2f}")

                col1, col2, col3 = st.columns([1, 1, 1])
                payment_status = None

                with col1:
                    if st.button("Debit"):
                        payment_status = "Received - Debited"
                with col2:
                    if st.button("Credit"):
                        payment_status = "Received - Credit"
                with col3:
                    if st.button("Pix"):
                        payment_status = "Received - Pix"

                if payment_status:
                    process_payment(selected_client, payment_status)
            else:
                st.info("No orders found for this client.")
        else:
            st.info("Please select a client.")
    else:
        st.info("No clients found.")

def stock_page():
    st.title("Stock")

    st.subheader("Add a new stock record")
    with st.form(key='stock_form'):
        product = st.text_input("Product", max_chars=100)
        quantity = st.number_input("Quantity", min_value=1, step=1)
        value = st.number_input("Value", min_value=0.0, step=0.01, format="%.2f")
        transaction = "Entry"
        current_date = datetime.now().date()
        submit_stock = st.form_submit_button(label="Register")

    if submit_stock:
        if product and quantity > 0 and value >= 0:
            query = """
            INSERT INTO public.tb_estoque ("Produto", "Quantidade", "Valor", "Total", "Transação", "Data")
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            total = quantity * value
            success = run_insert(query, (product, quantity, value, total, transaction, current_date))
            if success:
                st.success("Stock record added successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all fields correctly.")

    stock_data = st.session_state.data.get("stock", [])
    columns = ["Product", "Quantity", "Value", "Total", "Transaction", "Date"]
    if stock_data:
        st.subheader("All Stock Records")
        df_stock = pd.DataFrame(stock_data, columns=columns)
        st.dataframe(df_stock, use_container_width=True)
    else:
        st.info("No stock records found.")

def clients_page():
    st.title("Clients")

    st.subheader("Register a New Client")
    with st.form(key='client_form'):
        nome_completo = st.text_input("Full Name", max_chars=100)
        data_nascimento = st.date_input("Date of Birth")
        genero = st.selectbox("Sex/Gender (optional)", ["Man", "Woman"], index=0)
        telefone = st.text_input("Phone", max_chars=15)
        email = st.text_input("Email", max_chars=100)
        endereco = st.text_area("Address")
        submit_client = st.form_submit_button(label="Register New Client")

    if submit_client:
        if nome_completo and data_nascimento and telefone and email and endereco:
            query = """
            INSERT INTO public.tb_clientes (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            success = run_insert(query, (nome_completo, data_nascimento, genero, telefone, email, endereco))
            if success:
                st.success("Client registered successfully!")
                refresh_data()
        else:
            st.warning("Please fill in all required fields.")

def invoice_page():
    st.title("Invoice")

    open_clients_query = 'SELECT DISTINCT "Cliente" FROM public.vw_pedido_produto WHERE status = %s;'
    open_clients = run_query(open_clients_query, ('em aberto',))

    client_list = [row[0] for row in open_clients] if open_clients else []
    selected_client = st.selectbox("Select a Client", [""] + client_list)

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
            st.info("No open orders for the selected client.")
    else:
        st.warning("Please select a client.")

def generate_invoice_for_printer(df):
    """
    Generate a textual invoice representation for printing.
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
# Initialization
#####################
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

st.session_state.page = sidebar_navigation()

if st.session_state.page == "Home":
    home_page()
elif st.session_state.page == "Orders":
    orders_page()
elif st.session_state.page == "Invoice":
    invoice_page()
elif st.session_state.page == "Stock":
    stock_page()
elif st.session_state.page == "Clients":
    clients_page()
elif st.session_state.page == "Commands":
    commands_page()
