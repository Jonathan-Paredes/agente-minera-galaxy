import streamlit as st
import anthropic

from agente import responder

st.set_page_config(page_title="Agente Minera Galaxy", page_icon="⛏️")
st.title("⛏️ Agente Minera Galaxy")
st.caption("Consulta tickets de equipos. Datos sintéticos, solo lectura.")

# Estado: 'mensajes' es lo que ve el modelo; 'historial' es lo que ve la pantalla
if "mensajes" not in st.session_state:
    st.session_state.mensajes = []
    st.session_state.historial = []

with st.sidebar:
    st.header("Ejemplos")
    st.markdown(
        "- ¿Cuántos tickets tiene el camión 374?\n"
        "- ¿Qué 5 equipos tienen más tickets?\n"
        "- ¿Qué tipo de equipo acumula más horas?\n"
        "- ¿Cómo evolucionan los tickets por mes?\n"
        "- ¿Qué palas hay?"
    )
    if st.button("🗑️ Nueva conversación"):
        st.session_state.mensajes = []
        st.session_state.historial = []
        st.rerun()

# Repintar la conversación anterior
for item in st.session_state.historial:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])
        if item.get("tools"):
            with st.expander("🔧 Herramientas usadas"):
                for t in item["tools"]:
                    st.code(t, language="python")

# Entrada nueva
pregunta = st.chat_input("Pregunta sobre equipos o tickets...")

if pregunta:
    st.session_state.historial.append({"role": "user", "content": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)

    largo_antes = len(st.session_state.mensajes)
    st.session_state.mensajes.append({"role": "user", "content": pregunta})

    with st.chat_message("assistant"):
        herramientas = []
        try:
            with st.spinner("Consultando la base..."):
                texto = responder(
                    st.session_state.mensajes,
                    on_tool=lambda n, a: herramientas.append(f"{n}({a})"),
                )
        except anthropic.APIError as e:
            # Deshacer el turno incompleto: un tool_use sin su tool_result
            # dejaría la conversación inválida para las preguntas siguientes
            st.session_state.mensajes = st.session_state.mensajes[:largo_antes]
            st.session_state.historial.pop()
            st.error(f"Error de la API de Anthropic: {e}")
            st.stop()

        st.markdown(texto)
        if herramientas:
            with st.expander("🔧 Herramientas usadas"):
                for t in herramientas:
                    st.code(t, language="python")

    st.session_state.historial.append(
        {"role": "assistant", "content": texto, "tools": herramientas}
    )