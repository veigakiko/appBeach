# pages/home.py

import streamlit as st
from helpers import refresh_data

def home_page():
    st.title("Boituva Beach Club")
    st.write("🎾 Beach Tennis 📍 Av. Do Trabalhador, 1879 🏆 5° Open BBC")
    if st.button("Refresh Data"):
        refresh_data(load_all_data=lambda: st.session_state.data.update(load_all_data()))
        st.success("Data refreshed successfully!")
