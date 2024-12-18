# pages/clients.py

import streamlit as st
from database import run_query, run_insert
from helpers import refresh_data, display_dataframe
from datetime import datetime
import pandas as pd

def clients_page():
    st.title("Clients")
    st.subheader("Register a New Client")

    # Form to register a new client
    with st.form(key='client_form'):
        nome_completo = st.text_input("Full Name", max_chars=100)
        data_nascimento = st.date_input("Birth Date", value=datetime(2000, 1, 1).date())
        genero = st.selectbox("Gender", ["Man", "Woman", "Other"])
        telefone = st.text_input("Phone", max_chars=15)
        endereco = st.text_input("Address", max_chars=200)
        submit_client = st.form_submit_button(label="Register New Client")

    if submit_client:
        if nome_completo and telefone and endereco:
            # Generate a unique email to avoid conflicts
            unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
            email = f"{nome_completo.replace(' ', '_').lower()}_{unique_id}@example.com"

            query = """
            INSERT INTO public.tb_clientes (nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            success = run_insert(query, (nome_completo, data_nascimento, genero, telefone, email, endereco))
            if success:
                st.success("Client registered successfully!")
                refresh_data(load_all_data=lambda: st.session_state.data.update(load_all_data()))
        else:
            st.warning("Please fill in all required fields.")

    # Display all clients
    clients_data = st.session_state.data.get("clients", [])
    if clients_data:
        st.subheader("All Clients")
        columns = ["Client ID", "Full Name"]
        df_clients = pd.DataFrame(clients_data, columns=columns)
        display_dataframe(df_clients)

        # Editing or deleting an existing client
        st.subheader("Edit or Delete an Existing Client")
        client_ids = df_clients["Client ID"].astype(str).tolist()
        selected_client_id = st.selectbox("Select a client by ID:", [""] + client_ids)

        if selected_client_id:
            selected_client = df_clients[df_clients["Client ID"].astype(str) == selected_client_id].iloc[0]

            # Fetch complete client details
            client_details_query = """
            SELECT nome_completo, data_nascimento, genero, telefone, email, endereco, data_cadastro
            FROM public.tb_clientes
            WHERE client_id = %s;
            """
            client_details = run_query(client_details_query, (selected_client_id,))
            if client_details:
                client = client_details[0]
                with st.form(key='edit_client_form'):
                    edit_name = st.text_input("Full Name", value=client[0], max_chars=100)
                    edit_birth_date = st.date_input("Birth Date", value=client[1])
                    edit_gender = st.selectbox("Gender", ["Man", "Woman", "Other"], index=["Man", "Woman", "Other"].index(client[2]) if client[2] in ["Man", "Woman", "Other"] else 0)
                    edit_phone = st.text_input("Phone", value=client[3], max_chars=15)
                    edit_email = st.text_input("Email", value=client[4], max_chars=100)
                    edit_address = st.text_input("Address", value=client[5], max_chars=200)

                    col1, col2 = st.columns(2)
                    with col1:
                        update_button = st.form_submit_button(label="Update Client")
                    with col2:
                        delete_button = st.form_submit_button(label="Delete Client")

                if update_button:
                    if edit_name and edit_phone and edit_address:
                        update_query = """
                        UPDATE public.tb_clientes
                        SET nome_completo = %s,
                            data_nascimento = %s,
                            genero = %s,
                            telefone = %s,
                            email = %s,
                            endereco = %s
                        WHERE client_id = %s;
                        """
                        success = run_insert(update_query, (
                            edit_name,
                            edit_birth_date,
                            edit_gender,
                            edit_phone,
                            edit_email,
                            edit_address,
                            selected_client_id
                        ))
                        if success:
                            st.success("Client updated successfully!")
                            refresh_data(load_all_data=lambda: st.session_state.data.update(load_all_data()))
                        else:
                            st.error("Failed to update the client.")
                    else:
                        st.warning("Please fill in all required fields.")

                if delete_button:
                    delete_query = "DELETE FROM public.tb_clientes WHERE client_id = %s;"
                    success = run_insert(delete_query, (selected_client_id,))
                    if success:
                        st.success("Client deleted successfully!")
                        refresh_data(load_all_data=lambda: st.session_state.data.update(load_all_data()))
                    else:
                        st.error("Failed to delete the client.")
    else:
        st.info("No clients found.")
