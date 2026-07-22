import re
import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client

# ==========================================
# ⚙️ CONFIGURAÇÃO DO ESTABELECIMENTO
# ==========================================
NOME_ESTABELECIMENTO = "Café Triangulo"
# Link corrigido para carregamento direto da imagem no GitHub (raw)
LOGO_URL = "https://raw.githubusercontent.com/danielrecto-art/snackbar-atendente/main/file_000000005f0881f49a73ed28f23b0776.png"

# Configuração da Página do Streamlit
st.set_page_config(
    page_title=f"{NOME_ESTABELECIMENTO} - Atendente Virtual",
    page_icon="☕",
    layout="centered"
)

# ==========================================
# 🎨 ESTILO ESTILO GEMINI (CUSTOM CSS)
# ==========================================
st.markdown("""
    <style>
    /* Estilo geral e fundo moderno */
    .stApp {
        background-color: #0f1117;
        color: #e2e8f0;
    }
    
    /* Centralizar e estilizar o cabeçalho */
    .header-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1.5rem 0 1rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 1.5rem;
    }
    
    .logo-img {
        width: 85px;
        height: 85px;
        object-fit: contain;
        margin-bottom: 0.8rem;
        filter: drop-shadow(0px 4px 10px rgba(0, 0, 0, 0.4));
    }
    
    .brand-title {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 1.8rem;
        letter-spacing: -0.5px;
        background: linear-gradient(135deg, #a8c7fa 0%, #e8def8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    
    /* Badge da Mesa estilo Pílula Gemini */
    .table-badge {
        background: rgba(168, 199, 250, 0.1);
        border: 1px solid rgba(168, 199, 250, 0.25);
        color: #a8c7fa;
        padding: 4px 16px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
        margin-top: 0.6rem;
        display: inline-block;
    }

    /* Balões de Chat fluídos */
    [data-testid="stChatMessage"] {
        background-color: #1a1d24 !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 18px !important;
        padding: 1rem !important;
        margin-bottom: 0.8rem !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }

    /* Caixa de entrada estilo caixa do Gemini */
    [data-testid="stChatInput"] {
        border-radius: 28px !important;
        background-color: #1e222d !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
    }
    
    [data-testid="stChatInput"]:focus-within {
        border-color: #a8c7fa !important;
        box-shadow: 0 0 10px rgba(168, 199, 250, 0.2) !important;
    }

    /* Esconder o cabeçalho padrão do Streamlit para manter visual limpo */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. CARREGAR SEGREDOS (ST.SECRETS)
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
# 3. CABEÇALHO DA APLICAÇÃO (LOGO + NOME)
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
És o Atendente Virtual simpático e eficiente do "{NOME_ESTABELECIMENTO}".
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

    # Formatar histórico para a API do Gemini
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
