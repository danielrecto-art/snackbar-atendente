import re
import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client

# ==========================================
# 1. CONFIGURAÇÕES & CHAVES DE API
# ==========================================
GEMINI_API_KEY = "AIzaSyDFiOMw9_JhWNq6nzk_sJKSINlzytl0dTg"
SUPABASE_URL = "https://ycuvvjpwyzwlbarmemrw.supabase.co"
SUPABASE_KEY = "sb_publishable_AuV5aTNqFoht005aZMZ9nQ_0eWNLXAs"

# Configuração da página web para telemóvel
st.set_page_config(
    page_title="Snack-Bar Atendente",
    page_icon="🍔",
    layout="centered"
)

# Detectar a mesa pela URL (ex: ?mesa=03)
query_params = st.query_params
mesa_atual = query_params.get("mesa", "Mesa 01")

# Inicialização dos Clientes
@st.cache_resource
def iniciar_clientes():
    client_gemini = genai.Client(api_key=GEMINI_API_KEY)
    client_supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return client_gemini, client_supabase

gemini_client, supabase = iniciar_clientes()

# ==========================================
# 2. PROMPT DE SISTEMA DO GEMINI
# ==========================================
SYSTEM_INSTRUCTION = f"""
És o assistente virtual de atendimento ao cliente num Snack-Bar / Cafetaria.
O cliente está sentado na {mesa_atual}.

REGRAS OBRIGATÓRIAS DE ATENDIMENTO:
1. Sê sempre breve, simpático e direto.
2. NUNCA inventes produtos que não estejam listados no MENU. Se o cliente pedir algo fora do menu, informa educadamente que não temos disponível.
3. Regista com atenção os detalhes do pedido (ex: "com gelo e limão", "sem alho", "bem passado").
4. Quando o cliente indicar que quer terminar, faz um RESUMO CLARO do pedido com preços e total acumulado.
5. Pergunta explicitamente: "Posso confirmar e enviar este pedido para o balcão?"
6. QUANDO O CLIENTE CONFIRMAR EXPLICITAMENTE (ex: "sim", "podes", "confirmo"), deves responder a confirmar ao cliente E incluir obrigatoriamente no FINAL da tua resposta esta etiqueta técnica exata:
   [GRAVAR_DB: <lista de itens resumida> | <valor_total_numerico>]
   Exemplo: [GRAVAR_DB: 1x Tosta Mista, 1x Imperial | 5.00]

MENU DISPONÍVEL:

[BEBIDAS]
- Imperial 20cl: 1.50€
- Caneca 40cl: 2.80€
- Coca-Cola / Sumol / Guaraná (Lata 33cl): 1.80€
- Água Mineral 50cl: 1.20€
- Água das Pedras / Frisante 25cl: 1.50€

[CAFETARIA E SNACKS]
- Café Express / Descafeinado: 0.90€
- Meia de Leite: 1.40€
- Torrada em Pão de Forma: 1.80€
- Tosta Mista em Pão Caseiro: 3.50€

[PETISCOS E PRATOS RÁPIDOS]
- Prego no Pão (Novilho): 4.50€
- Prego em Prato (com Batata Frita e Ovo): 7.50€
- Pica-Pau de Porco (Dose): 8.50€
- Porção de Batata Frita: 2.50€
"""

# ==========================================
# 3. GESTÃO DE SESSÃO & CHAT
# ==========================================
if "chat" not in st.session_state:
    st.session_state.chat = gemini_client.chats.create(
        model="gemini-3.1-flash-lite",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2
        )
    )

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": f"Olá! 👋 Bem-vindo ao Snack-Bar. Estou a atender a **{mesa_atual}**. O que lhe apetece hoje?"}
    ]

# Header na Interface
st.title("🍔 Snack-Bar Digital")
st.caption(f"📍 A atender na **{mesa_atual}**")
st.divider()

# Exibir histórico de mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Entrada do Utilizador
if user_input := st.chat_input("Escreva aqui o seu pedido..."):
    # Guardar e mostrar a mensagem do cliente
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Obter resposta da IA
    with st.chat_message("assistant"):
        with st.spinner("A pensar..."):
            resposta = st.session_state.chat.send_message(user_input)
            texto_resposta = resposta.text

            # Verificar se a IA enviou a etiqueta de gravação no Supabase
            padrao = r"\[GRAVAR_DB:\s*(.*?)\s*\|\s*([\d\.]+)\]"
            match = re.search(padrao, texto_resposta)

            if match:
                itens = match.group(1)
                total = float(match.group(2))

                # Gravar na Base de Dados
                try:
                    dados_pedido = {
                        "mesa": mesa_atual,
                        "itens": itens,
                        "total": total,
                        "estado": "pendente"
                    }
                    supabase.table("pedidos").insert(dados_pedido).execute()
                    st.success("🚀 Pedido enviado para o balcão com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao enviar pedido para o balcão: {e}")

                # Limpar a etiqueta técnica do texto exibido ao cliente
                texto_resposta = re.sub(padrao, "", texto_resposta).strip()

            st.write(texto_resposta)
            st.session_state.messages.append({"role": "assistant", "content": texto_resposta})