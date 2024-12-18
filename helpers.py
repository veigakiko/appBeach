# helpers.py

import streamlit as st
import pandas as pd
from datetime import datetime

def refresh_data(load_all_data_func):
    """
    Reloads all data and updates the session state.
    """
    st.session_state.data = load_all_data_func()

def generate_unique_key(*args):
    """
    Generates a unique key by concatenating multiple fields.
    """
    return "|".join(map(str, args))

def format_currency(value):
    """
    Formats a numeric value into Brazilian Real currency format.
    """
    return f"R$ {value:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')

def display_dataframe(df):
    """
    Displays a pandas DataFrame in Streamlit with enhanced formatting.
    """
    st.dataframe(df, use_container_width=True)

def generate_invoice_for_printer(df):
    """
    Generates a formatted invoice suitable for printing.
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
        total_formatted = format_currency(total)
        invoice_note.append(f"{description} {quantity} {total_formatted}")

    formatted_general_total = format_currency(total_general)
    invoice_note.append("--------------------------------------------------")
    invoice_note.append(f"TOTAL GERAL: {formatted_general_total:>28}")
    invoice_note.append("==================================================")
    invoice_note.append("OBRIGADO PELA SUA PREFERÊNCIA!")
    invoice_note.append("==================================================")

    st.text("\n".join(invoice_note))
