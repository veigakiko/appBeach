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
    Returns a persistent connection to the PostgreSQL database using psycopg2.
    Utilizes Streamlit Secrets for secure credential management.
    """
    try:
        conn = psycopg2.connect(
            host=st.secrets["postgres"]["host"],
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            port=st.secrets["postgres"]["port"]
        )
        return conn
    except OperationalError as e:
        st.error("Não foi possível conectar ao banco de dados. Por favor, tente novamente mais tarde.")
        return None

def run_query(query, values=None):
    """
    Executes a SELECT query and returns the fetched data.

    Args:
        query (str): The SQL query to execute.
        values (tuple, optional): The values to pass into the query.

    Returns:
        list: The fetched data from the query.
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
        if conn:
            conn.close()

def run_insert(query, values):
    """
    Executes an INSERT, UPDATE, or DELETE query.

    Args:
        query (str): The SQL query to execute.
        values (tuple): The values to pass into the query.

    Returns:
        bool: True if the operation was successful, False otherwise.
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
        st.error(f"Erro ao executar a operação: {e}")
        return False
    finally:
        if conn:
            conn.close()

#####################
# Data Loading
#####################
def load_all_data():
    """
    Loads all necessary data for the application.

    Returns:
        dict: A dictionary containing all loaded data.
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
    Reloads all data and updates the session state.
    """
    st.session_state.data = load_all_data()

#####################
# Menu Navigation
#####################
def sidebar_navigation():
    """
    Creates a sidebar menu for navigation using streamlit_option_menu.

    Returns:
        str: The name of the selected menu item.
    """
    with st.sidebar:
        st.title("Boituva Beach Club")
        selected = option_menu(
            "Menu Principal", ["Home", "Orders", "Products", "Stock", "Clients", "Nota Fiscal"],
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

#####################
# Page Functions
#####################
def home_page():
    """
    Renders the Home page, displaying summaries of open orders, closed orders,
    status, products, and a combined summary of products and stock.
    """
    st.title("Boituva Beach Club")
    st.write("🎾 BeachTennis 📍 Av. Do Trabalhador, 1879 🏆 5° Open BBC")
    st.info("Os dados são atualizados automaticamente ao navegar entre as páginas.")

    ############################
    # Open Orders Summary
    ############################
    st.subheader("Open Orders Summary")

    # Query to fetch open orders grouped by Client and Date
    open_orders_query = """
    SELECT "Cliente", DATE("Data") as Date, SUM("total") as Total
    FROM public.vw_pedido_produto
    WHERE status = %s
    GROUP BY "Cliente", DATE("Data")
    ORDER BY "Cliente", DATE("Data") DESC;
    """
    open_orders_data = run_query(open_orders_query, ('em aberto',))

    if open_orders_data:
        # Create DataFrame
        df_open_orders = pd.DataFrame(open_orders_data, columns=["Client", "Date", "Total"])

        # Calculate total
        total_open = df_open_orders["Total"].sum()

        # Format 'Date'
        df_open_orders["Date"] = pd.to_datetime(df_open_orders["Date"]).dt.strftime('%Y-%m-%d')

        # Format 'Total' as currency
        df_open_orders["Total"] = df_open_orders["Total"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        # Reset index and select columns
        df_open_orders = df_open_orders.reset_index(drop=True)[["Client", "Date", "Total"]]

        # Apply styles
        styled_open_orders = df_open_orders.style.set_properties(**{
            'text-align': 'left',
            'font-size': '12px',
            'white-space': 'pre-wrap',
            'word-wrap': 'break-word'
        })

        # Display table
        st.dataframe(
            styled_open_orders,
            use_container_width=True
        )

        # Display total
        st.markdown(f"**Total Geral (Open Orders):** R$ {total_open:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    else:
        st.info("Nenhum pedido em aberto encontrado.")

    st.markdown("---")  # Visual separator

    ############################
    # Closed Orders Summary
    ############################
    st.subheader("Closed Orders Summary")

    # Query to fetch closed orders grouped by Client and Date
    closed_orders_query = """
    SELECT "Cliente", DATE("Data") as Date, SUM("total") as Total
    FROM public.vw_pedido_produto
    WHERE status != %s
    GROUP BY "Cliente", DATE("Data")
    ORDER BY "Cliente", DATE("Data") DESC;
    """
    closed_orders_data = run_query(closed_orders_query, ('em aberto',))

    if closed_orders_data:
        # Create DataFrame
        df_closed_orders = pd.DataFrame(closed_orders_data, columns=["Client", "Date", "Total"])

        # Calculate total
        total_closed = df_closed_orders["Total"].sum()

        # Format 'Date'
        df_closed_orders["Date"] = pd.to_datetime(df_closed_orders["Date"]).dt.strftime('%Y-%m-%d')

        # Format 'Total' as currency
        df_closed_orders["Total"] = df_closed_orders["Total"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        # Reset index and select columns
        df_closed_orders = df_closed_orders.reset_index(drop=True)[["Client", "Date", "Total"]]

        # Apply styles
        styled_closed_orders = df_closed_orders.style.set_properties(**{
            'text-align': 'left',
            'font-size': '12px',
            'white-space': 'pre-wrap',
            'word-wrap': 'break-word'
        })

        # Display table
        st.dataframe(
            styled_closed_orders,
            use_container_width=True
        )

        # Display total
        st.markdown(f"**Total Geral (Closed Orders):** R$ {total_closed:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    else:
        st.info("Nenhum pedido fechado encontrado.")

    st.markdown("---")  # Visual separator

    ############################
    # Status Summary
    ############################
    st.subheader("Status Summary")

    # Query to fetch status summary
    status_summary_query = """
    SELECT status, SUM("total") as Total
    FROM public.vw_pedido_produto
    GROUP BY status
    ORDER BY status;
    """
    status_summary_data = run_query(status_summary_query)

    if status_summary_data:
        # Create DataFrame
        df_status_summary = pd.DataFrame(status_summary_data, columns=["Status", "Total"])

        # Format 'Total' as currency
        df_status_summary["Total"] = df_status_summary["Total"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        # Reset index and select columns
        df_status_summary = df_status_summary.reset_index(drop=True)[["Status", "Total"]]

        # Apply styles
        styled_status_summary = df_status_summary.style.set_properties(**{
            'text-align': 'left',
            'font-size': '12px',
            'white-space': 'pre-wrap',
            'word-wrap': 'break-word'
        })

        # Display table
        st.dataframe(
            styled_status_summary,
            use_container_width=True
        )
    else:
        st.info("Nenhum pedido encontrado para resumo por status.")

    st.markdown("---")  # Visual separator

    ############################
    # Product Summary
    ############################
    st.subheader("Product Summary")

    # Query to fetch product summary
    product_summary_query = """
    SELECT "Produto", SUM("Quantidade") as Quantity, SUM("total") as Total
    FROM public.vw_pedido_produto
    GROUP BY "Produto"
    ORDER BY "Produto";
    """
    product_summary_data = run_query(product_summary_query)

    if product_summary_data:
        # Create DataFrame
        df_product_summary = pd.DataFrame(product_summary_data, columns=["Product", "Quantity", "Total"])

        # Format 'Total' as currency
        df_product_summary["Total"] = df_product_summary["Total"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        # Format 'Quantity' with thousands separators
        df_product_summary["Quantity"] = df_product_summary["Quantity"].apply(
            lambda x: f"{int(x):,}".replace(",", ".")
        )

        # Reset index and select columns
        df_product_summary = df_product_summary.reset_index(drop=True)[["Product", "Quantity", "Total"]]

        # Apply styles
        styled_product_summary = df_product_summary.style.set_properties(**{
            'text-align': 'left',
            'font-size': '12px',
            'white-space': 'pre-wrap',
            'word-wrap': 'break-word'
        })

        # Display table
        st.dataframe(
            styled_product_summary,
            use_container_width=True
        )
    else:
        st.info("Nenhum pedido encontrado para resumo por produto.")

    st.markdown("---")  # Visual separator

    ############################
    # Combined Product and Stock Summary
    ############################
    st.subheader("Combined Product and Stock Summary")

    # Query to fetch product summary
    combined_product_query = """
    SELECT "Produto", SUM("Quantidade") as Summary_Quantity, SUM("total") as Summary_Total
    FROM public.vw_pedido_produto
    GROUP BY "Produto"
    ORDER BY "Produto";
    """
    combined_product_data = run_query(combined_product_query)

    # Query to fetch stock records
    stock_records_query = """
    SELECT "Produto", SUM("Quantidade") as Stock_Quantity
    FROM public.tb_estoque
    GROUP BY "Produto"
    ORDER BY "Produto";
    """
    stock_records_data = run_query(stock_records_query)

    if combined_product_data and stock_records_data:
        # Create DataFrames
        df_product_summary_combined = pd.DataFrame(combined_product_data, columns=["Product", "Summary_Quantity", "Summary_Total"])
        df_stock_records = pd.DataFrame(stock_records_data, columns=["Product", "Stock_Quantity"])

        # Merge DataFrames on 'Product'
        df_combined = pd.merge(df_product_summary_combined, df_stock_records, on="Product", how="left")

        # Fill NaN in 'Stock_Quantity' with 0 and convert to int
        df_combined["Stock_Quantity"] = df_combined["Stock_Quantity"].fillna(0).astype(int)

        # Rename columns for clarity
        df_combined = df_combined.rename(columns={
            "Summary_Quantity": "Total Vendido",
            "Summary_Total": "Total (Product Summary)",
            "Stock_Quantity": "Total em Estoque"
        })

        # Convert 'Total Vendido' to float (already numeric, ensure no currency formatting)
        # Since we removed currency formatting earlier, ensure it's numeric
        # No additional formatting needed

        # Calculate 'Estoque_Atual' = 'Total em Estoque' - 'Total Vendido'
        df_combined["Estoque_Atual"] = df_combined["Total em Estoque"] - df_combined["Total Vendido"]

        # Format 'Total em Estoque' with thousands separators
        df_combined["Total em Estoque"] = df_combined["Total em Estoque"].apply(
            lambda x: f"{x:,}".replace(",", ".")
        )

        # Format 'Estoque_Atual' with thousands separators and no decimals
        df_combined["Estoque_Atual"] = df_combined["Estoque_Atual"].apply(
            lambda x: f"{x:,.0f}".replace(",", ".")
        )

        # Select desired columns
        df_combined = df_combined[["Product", "Total Vendido", "Total em Estoque", "Estoque_Atual"]]

        # Apply styles
        styled_combined = df_combined.style.set_properties(**{
            'text-align': 'left',
            'font-size': '12px',
            'white-space': 'pre-wrap',
            'word-wrap': 'break-word'
        })

        # Display combined table
        st.dataframe(
            styled_combined,
            use_container_width=True
        )
    else:
        st.info("Dados insuficientes para criar o resumo combinado de Produto e Estoque.")

def orders_page():
    st.title("Orders")
    st.subheader("Register a new order")

    product_data = st.session_state.data.get("products", [])
    product_list = [""] + [row[1] for row in product_data] if product_data else ["No products available"]

    # Form to insert new order
    with st.form(key='order_form'):
        # Loading list of clients for the new order
        clientes = run_query('SELECT nome_completo FROM public.tb_clientes ORDER BY nome_completo;')
        customer_list = [""] + [row[0] for row in clientes]
        
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
                st.error("Failed to register the order.")
        else:
            st.warning("Please fill in all fields correctly.")

    # Display all orders
    orders_data = st.session_state.data.get("orders", [])
    if orders_data:
        st.subheader("All Orders")
        columns = ["Client", "Product", "Quantity", "Date", "Status"]
        df_orders = pd.DataFrame(orders_data, columns=columns)
        
        # Reset index
        df_orders = df_orders.reset_index(drop=True)

        st.dataframe(df_orders, use_container_width=True)

        st.subheader("Edit or Delete an Existing Order")
        # Create a unique key to identify each order
        # Format the date to string in the same format as the database
        df_orders["unique_key"] = df_orders.apply(
            lambda row: f"{row['Client']}|{row['Product']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
            axis=1
        )
        unique_keys = df_orders["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select an order to edit/delete:", [""] + unique_keys)

        if selected_key:
            # Check how many records match the unique key
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

                # Form to edit the order
                with st.form(key='edit_order_form'):
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
                    edit_status_list = ["em aberto", "Received - Debited", "Received - Credit", "Received - Pix"]
                    edit_status_index = edit_status_list.index(original_status) if original_status in edit_status_list else 0
                    edit_status = st.selectbox("Status", edit_status_list, index=edit_status_index)

                    update_button = st.form_submit_button(label="Update Order")
                    delete_button = st.form_submit_button(label="Delete Order")

                # Delete order immediately after clicking the button, without confirmation
                if delete_button:
                    delete_query = """
                    DELETE FROM public.tb_pedido
                    WHERE "Cliente" = %s AND "Produto" = %s AND "Data" = %s;
                    """
                    success = run_insert(delete_query, (
                        original_client, original_product, original_date
                    ))
                    if success:
                        st.success("Order deleted successfully!")
                        refresh_data()
                    else:
                        st.error("Failed to delete the order.")

                if update_button:
                    # Update the order in the database using the combination of fields as a filter
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

    # Display all products
    products_data = st.session_state.data.get("products", [])
    if products_data:
        st.subheader("All Products")
        columns = ["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]
        df_products = pd.DataFrame(products_data, columns=columns)
        
        # Reset index
        df_products = df_products.reset_index(drop=True)
        
        # Select desired columns
        df_products = df_products[["Supplier", "Product", "Quantity", "Unit Value", "Total Value", "Creation Date"]]
        
        # Display table
        st.dataframe(df_products.style.set_properties(**{
            'text-align': 'left',
            'font-size': '12px'
        }), use_container_width=True)

        st.subheader("Edit or Delete an Existing Product")
        # Create a unique key to identify each product
        df_products["unique_key"] = df_products.apply(
            lambda row: f"{row['Supplier']}|{row['Product']}|{row['Creation Date'].strftime('%Y-%m-%d')}",
            axis=1
        )
        unique_keys = df_products["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select a product to edit/delete:", [""] + unique_keys)

        if selected_key:
            # Check how many records match the unique key
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

                # Form to edit the product
                with st.form(key='edit_product_form'):
                    edit_supplier = st.text_input("Supplier", value=original_supplier, max_chars=100)
                    edit_product = st.text_input("Product", value=original_product, max_chars=100)
                    edit_quantity = st.number_input(
                        "Quantity",
                        min_value=1,
                        step=1,
                        value=int(original_quantity)
                    )
                    edit_unit_value = st.number_input(
                        "Unit Value",
                        min_value=0.0,
                        step=0.01,
                        format="%.2f",
                        value=float(original_unit_value)
                    )
                    edit_creation_date = st.date_input("Creation Date", value=original_creation_date)
                    
                    update_button = st.form_submit_button(label="Update Product")
                    delete_button = st.form_submit_button(label="Delete Product")

                # Delete product immediately after clicking the button, without confirmation
                if delete_button:
                    delete_query = """
                    DELETE FROM public.tb_products
                    WHERE supplier = %s AND product = %s AND creation_date = %s;
                    """
                    success = run_insert(delete_query, (
                        original_supplier, original_product, original_creation_date
                    ))
                    if success:
                        st.success("Product deleted successfully!")
                        refresh_data()
                    else:
                        st.error("Failed to delete the product.")

                if update_button:
                    # Recalculate total_value if quantity or unit_value have changed
                    edit_total_value = edit_quantity * edit_unit_value

                    # Update the product in the database using the combination of fields as a filter
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
    else:
        st.info("No products found.")

def stock_page():
    st.title("Stock")

    st.subheader("Add a new stock record")

    # Load the list of products from tb_products table
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

    # Display all stock records
    stock_data = st.session_state.data.get("stock", [])
    if stock_data:
        st.subheader("All Stock Records")
        columns = ["Product", "Quantity", "Transaction", "Date"]
        df_stock = pd.DataFrame(stock_data, columns=columns)
        
        # Reset index
        df_stock = df_stock.reset_index(drop=True)
        
        # Select desired columns
        df_stock = df_stock[["Product", "Quantity", "Transaction", "Date"]]
        
        # Display table
        st.dataframe(df_stock.style.set_properties(**{
            'text-align': 'left',
            'font-size': '12px'
        }), use_container_width=True)

        st.subheader("Edit or Delete an Existing Stock Record")
        # Create a unique key to identify each stock record
        df_stock["unique_key"] = df_stock.apply(
            lambda row: f"{row['Product']}|{row['Transaction']}|{row['Date'].strftime('%Y-%m-%d %H:%M:%S')}",
            axis=1
        )
        unique_keys = df_stock["unique_key"].unique().tolist()
        selected_key = st.selectbox("Select a stock record to edit/delete:", [""] + unique_keys)

        if selected_key:
            # Check how many records match the unique key
            matching_rows = df_stock[df_stock["unique_key"] == selected_key]
            if len(matching_rows) > 1:
                st.warning("Multiple stock records found with the same key. Please refine your selection.")
            else:
                selected_row = matching_rows.iloc[0]
                original_product = selected_row["Product"]
                original_quantity = selected_row["Quantity"]
                original_transaction = selected_row["Transaction"]
                original_date = selected_row["Date"]

                # Form to edit the stock record
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

                # Delete stock record immediately after clicking the button, without confirmation
                if delete_button:
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

                if update_button:
                    edit_datetime = datetime.combine(edit_date, datetime.min.time())

                    # Update the stock record in the database using the combination of fields as a filter
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
    else:
        st.info("No stock records found.")

def clients_page():
    st.title("Clients")

    st.subheader("Register a New Client")

    # Form with only the Full Name field
    with st.form(key='client_form'):
        nome_completo = st.text_input("Full Name", max_chars=100)
        submit_client = st.form_submit_button(label="Register New Client")

    if submit_client:
        if nome_completo:
            # Other default values
            data_nascimento = datetime(2000, 1, 1).date()
            genero = "Man"
            telefone = "0000-0000"
            
            # Generate a unique email to avoid unique key conflict
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

    # Show the table of registered clients
    clients_data = run_query("SELECT nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro FROM public.tb_clientes ORDER BY data_cadastro DESC;")

    if clients_data:
        st.subheader("All Clients")
        columns = ["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"]
        df_clients = pd.DataFrame(clients_data, columns=columns)
        # Reset index
        df_clients = df_clients.reset_index(drop=True)
        # Select desired columns
        df_clients = df_clients[["Full Name", "Birth Date", "Gender", "Phone", "Email", "Address", "Register Date"]]
        # Display table
        st.dataframe(df_clients.style.set_properties(**{
            'text-align': 'left',
            'font-size': '12px'
        }), use_container_width=True)

        st.subheader("Edit or Delete an Existing Client")
        # Select a client to edit
        client_emails = df_clients["Email"].unique().tolist()
        selected_email = st.selectbox("Select a client by Email:", [""] + client_emails)

        if selected_email:
            # Get data of the selected client
            selected_client_row = df_clients[df_clients["Email"] == selected_email].iloc[0]
            original_name = selected_client_row["Full Name"]

            # Form to edit the name
            with st.form(key='edit_client_form'):
                edit_name = st.text_input("Full Name", value=original_name, max_chars=100)
                col1, col2 = st.columns(2)
                with col1:
                    update_button = st.form_submit_button(label="Update Client")
                with col2:
                    delete_button = st.form_submit_button(label="Delete Client")

            # Delete Client immediately after clicking the button, without confirmation
            if delete_button:
                delete_query = "DELETE FROM public.tb_clientes WHERE email = %s;"
                success = run_insert(delete_query, (selected_email,))
                if success:
                    st.success("Client deleted successfully!")
                    refresh_data()
                else:
                    st.error("Failed to delete the client.")

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
            # Display total as a number
            st.subheader(f"Total Geral: {total_sum:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

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
        total_formatted = f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        invoice_note.append(f"{description} {quantity} {total_formatted}")

    formatted_general_total = f"{total_general:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
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
    st.title("Login")
    st.write("Por favor, insira suas credenciais para acessar o aplicativo.")

    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_login = st.form_submit_button(label="Login")

    if submit_login:
        # Replace these credentials with a secure authentication method
        if username == "admin" and password == "admin":
            st.session_state.logged_in = True
            st.success("Login bem-sucedido!")
        else:
            st.error("Nome de usuário ou senha incorretos.")

#####################
# Initialization
#####################

# Initialize session state for data and login
if 'data' not in st.session_state:
    st.session_state.data = load_all_data()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# Check if the user is logged in
if not st.session_state.logged_in:
    login_page()
else:
    # Menu Navigation
    selected_page = sidebar_navigation()

    # Detect page change and update data if necessary
    if 'current_page' not in st.session_state:
        st.session_state.current_page = selected_page
        # Data is already loaded initially
    elif selected_page != st.session_state.current_page:
        # Page changed, reload data
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

    # Add logout option in the sidebar
    with st.sidebar:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.success("Desconectado com sucesso!")
            st.experimental_rerun()
