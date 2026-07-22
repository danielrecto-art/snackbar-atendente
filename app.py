import re
import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client

# Configuração da Página do Streamlit
st.set_page_config(
    page_title="N's Snack-Bar - Atendente Virtual",
    page_icon="🍔",
    layout="centered"
)

# ==========================================
# 1. CARREGAR SEGREDOS (ST.SECRETS)
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception as e:
    st.error("⚠️ As chaves de API não foram encontradas. Configura os 'Secrets' no Streamlit Cloud.")
    st.stop()

# ==========================================
# 2. INICIALIZAR LIGAÇÕES (SUPABASE E GEMINI)
# ==========================================
@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 3. IDENTIFICAÇÃO DA MESA (VIA URL)
# ==========================================
# Lê o parâmetro ?mesa=Mesa%2001 da URL (Predefinição: Mesa 01)
mesa_atual = st.query_params.get("mesa", "Mesa 01")

st.title("🍔 N's Snack-Bar")
st.caption(f"📍 A atender na: **{mesa_atual}**")

# ==========================================
# 4. INSTRUÇÃO DO SISTEMA (EMENTA E REGRAS DA IA)
# ==========================================
SYSTEM_INSTRUCTION = """
És o Atendente Virtual simpático e eficiente do "N's Snack-Bar".
O teu objetivo é ajudar o cliente a fazer o pedido para a mesa onde se encontra.

EMENTA & PREÇOS:
- Café / Descafeinado: 1.00 EUR
- Galão / Meia de Leite: 1.50 EUR
- Água (50cl): 1.00 EUR
- Refrigerantes (Coca-Cola, Sumol, Fanta, Ice Tea): 1.80 EUR
- Cerveja / Imperial: 1.50 EUR
- Tosta Mista (Pão de Forma ou Caseiro): 3.50 EUR
- Sandes de Fiambre / Queijo: 2.00 EUR
- Hambúrguer no Pão (com queijo e alface): 5.50 EUR
- Batata Frita: 2.50 EUR

REGRAS DE ATENDIMENTO:
1. Responde sempre em Português de Portugal.
2. Ajuda com personalizações (ex: tosta sem manteiga, café curto).
3. Mantém a conta atualizada e indica sempre o total acumulado ao cliente.
4. Quando o cliente CONFIRMAR EXPLICITAMENTE que quer enviar/finalizar o pedido (ex: "podes enviar", "confirmo", "está tudo"):
   - Responde ao cliente a confirmar que o pedido vai dar entrada na cozinha/balcão.
   - No FINAL ABSOLUTO da tua resposta, adiciona OBRIGATORIAMENTE esta tag exata (sem mais nada a seguir):
     [PEDIDO_CONFIRMADO: <lista_dos_itens> | <total_numerico>]

   Exemplo de tag no final:
   [PEDIDO_CONFIRMADO: 1x Café, 1x Tosta Mista sem manteiga | 4.50]
"""

# ==========================================
# 5. GERIR HISTÓRICO DAS MENSAGENS
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant", 
            "content": f"Olá! Bem-vindo ao **N's Snack-Bar**! 👋\nEstou a atender a **{mesa_atual}**. O que vai desejar hoje?"
        }
    ]

# Mostrar histórico de conversa no ecrã
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# 6. PROCESSAR ENTRADA DO CLIENTE
# ==========================================
if prompt := st.chat_input("Escreve o teu pedido aqui..."):
    # Guardar e exibir mensagem do utilizador
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Converter histórico para o formato exigido pelo Gemini SDK
    chat_history = []
    for m in st.session_state.messages:
        role = "user" if m["role"] == "user" else "model"
        chat_history.append(
            types.Content(
                role=role, 
                parts=[types.Part.from_text(text=m["content"])]
            )
        )

    # Chamar a API do Gemini
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=chat_history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,
            )
        )
        
        resposta_texto = response.text

        # Verificar se a IA confirmou o pedido (procura pela tag secreta)
        tag_match = re.search(r"\[PEDIDO_CONFIRMADO:\s*(.*?)\s*\|\s*([\d\.]+)\]", resposta_texto)

        if tag_match:
            itens_pedido = tag_match.group(1)
            total_pedido = float(tag_match.group(2))

            # Limpa a tag para não ser mostrada ao cliente no ecrã
            resposta_visivel = re.sub(r"\[PEDIDO_CONFIRMADO:.*?\]", "", resposta_texto).strip()

            # Enviar para a tabela 'pedidos' no Supabase
            try:
                supabase.table("pedidos").insert({
                    "mesa": mesa_atual,
                    "itens": itens_pedido,
                    "total": total_pedido,
                    "estado": "pendente"
                }).execute()

                # Guardar resposta e mostrar mensagem de sucesso
                st.session_state.messages.append({"role": "assistant", "content": resposta_visivel})
                with st.chat_message("assistant"):
                    st.markdown(resposta_visivel)
                    st.success("✅ **Pedido enviado com sucesso para o balcão!**")
                    
            except Exception as db_err:
                st.error(f"Erro ao guardar o pedido no Supabase: {db_err}")
        else:
            # Resposta normal durante a conversa
            st.session_state.messages.append({"role": "assistant", "content": resposta_texto})
            with st.chat_message("assistant"):
                st.markdown(resposta_texto)

    except Exception as e:
        st.error(f"Erro ao comunicar com o assistente: {e}")
