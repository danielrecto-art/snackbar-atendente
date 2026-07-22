import re
import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client

# ==========================================
# ⚙️ CONFIGURAÇÃO DO ESTABELECIMENTO
# ==========================================
NOME_ESTABELECIMENTO = ""
LOGO_URL = "https://raw.githubusercontent.com/danielrecto-art/snackbar-atendente/main/logo2.png"

# Configuração da Página
st.set_page_config(
    page_title=f"{NOME_ESTABELECIMENTO} - Atendente Virtual",
    page_icon="☕",
    layout="centered"
)

# ==========================================
# 🎨 DESIGN FLUIDO ESTILO GEMINI (CSS REVISADO)
# ==========================================
st.markdown("""
    <style>
    /* 1. Fundo do App e Fonte Geral */
    .stApp {
        background-color: #131314 !important;
        color: #e3e3e3 !important;
        font-family: 'Google Sans', 'Inter', -apple-system, sans-serif;
    }
    
    /* 2. Cabeçalho Centralizado */
    .header-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1.5rem 0 1rem 0;
        margin-bottom: 1.5rem;
    }
    
    .logo-img {
        width: 200px;
        height: 200px;
        object-fit: cover;
        border-radius: 18px;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.12);
        margin-bottom: 0.8rem;
    }
    
    .brand-title {
        font-weight: 600;
        font-size: 2.1rem;
        letter-spacing: -0.5px;
        background: linear-gradient(90deg, #4285f4, #9b51e0, #d96570);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    
    .table-badge {
        background: rgba(66, 133, 244, 0.12);
        border: 1px solid rgba(66, 133, 244, 0.25);
        color: #7cacf8;
        padding: 4px 16px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
        margin-top: 0.7rem;
    }

    /* 3. Balões de Conversa e Correção de Texto */
    div[data-testid="stChatMessage"] {
        background-color: #1e1f20 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 20px !important;
        padding: 1rem 1.2rem !important;
        margin-bottom: 1rem !important;
    }

    /* Garante visibilidade e contraste absoluto do texto */
    div[data-testid="stChatMessage"] p, 
    div[data-testid="stChatMessage"] span,
    div[data-testid="stChatMessage"] div {
        color: #e3e3e3 !important;
        font-size: 1rem !important;
        line-height: 1.6 !important;
    }

    /* 4. Correção da Caixa Inferior (Elimina a Barra Branca) */
    div[data-testid="stBottomBlockContainer"] {
        background-color: #131314 !important;
    }

    div[data-testid="stChatInput"] {
        background-color: #1e1f20 !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 28px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    div[data-testid="stChatInput"] textarea {
        color: #e3e3e3 !important;
        background-color: transparent !important;
    }

    div[data-testid="stChatInput"] textarea::placeholder {
        color: #8e918f !important;
    }

    /* Ocultar elementos nativos desnecessários */
    header, footer {
        visibility: hidden !important;
        height: 0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. CARREGAR SEGREDOS
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("⚠️ As chaves de API não foram encontradas no 'Secrets' do Streamlit Cloud.")
    st.stop()

# ==========================================
# 2. INICIALIZAR LIGAÇÕES
# ==========================================
@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 3. CABEÇALHO
# ==========================================
mesa_atual = st.query_params.get("mesa", "Mesa 01")

st.markdown(f"""
    <div class="header-container">
        <img src="{LOGO_URL}" class="logo-img" alt="Logo">
        <h1 class="brand-title">{NOME_ESTABELECIMENTO}</h1>
        <div class="table-badge">📍 {mesa_atual}</div>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# 4. INSTRUÇÃO DO SISTEMA
# ==========================================
SYSTEM_INSTRUCTION = f"""
És o Empregado Virtual simpático e eficiente do "Café Triângulo".
O teu objetivo é ajudar o cliente a fazer o pedido para a mesa onde se encontra.
Podes pontualmente ser divertido, e com algumas piadas.

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
4. Quando o cliente CONFIRMAR EXPLICITAMENTE que quer enviar/finalizar o pedido:
   - Responde ao cliente a confirmar que o pedido vai dar entrada na cozinha/balcão.
   - No FINAL ABSOLUTO da tua resposta, adiciona OBRIGATORIAMENTE esta tag exata:
     [PEDIDO_CONFIRMADO: <lista_dos_itens> | <total_numerico>]

   Exemplo: [PEDIDO_CONFIRMADO: 1x Café, 1x Tosta Mista | 4.50]
"""

# ==========================================
# 5. HISTÓRICO DE MENSAGENS
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant", 
            "content": f"Olá! Bem-vindo ao **{NOME_ESTABELECIMENTO}**! 👋\nComo posso ajudar o teu pedido na **{mesa_atual}** hoje?"
        }
    ]

# Mostrar histórico
for msg in st.session_state.messages:
    avatar = "✨" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ==========================================
# 6. ENTRADA DE DADOS DO CLIENTE
# ==========================================
if prompt := st.chat_input("Pede aqui o teu café, bebida ou refeição..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    chat_history = []
    for m in st.session_state.messages:
        role = "user" if m["role"] == "user" else "model"
        chat_history.append(
            types.Content(
                role=role, 
                parts=[types.Part.from_text(text=m["content"])]
            )
        )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=chat_history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,
            )
        )
        
        resposta_texto = response.text
        tag_match = re.search(r"\[PEDIDO_CONFIRMADO:\s*(.*?)\s*\|\s*([\d\.]+)\]", resposta_texto)

        if tag_match:
            itens_pedido = tag_match.group(1)
            total_pedido = float(tag_match.group(2))
            resposta_visivel = re.sub(r"\[PEDIDO_CONFIRMADO:.*?\]", "", resposta_texto).strip()

            try:
                supabase.table("pedidos").insert({
                    "mesa": mesa_atual,
                    "itens": itens_pedido,
                    "total": total_pedido,
                    "estado": "pendente"
                }).execute()

                st.session_state.messages.append({"role": "assistant", "content": resposta_visivel})
                with st.chat_message("assistant", avatar="✨"):
                    st.markdown(resposta_visivel)
                    st.success("✅ **Pedido enviado com sucesso para o balcão!**")
                    
            except Exception as db_err:
                st.error(f"Erro ao registar o pedido: {db_err}")
        else:
            st.session_state.messages.append({"role": "assistant", "content": resposta_texto})
            with st.chat_message("assistant", avatar="✨"):
                st.markdown(resposta_texto)

    except Exception as e:
        st.error(f"Erro na ligação com o assistente: {e}")
