import streamlit as st
from supabase import create_client, Client
import random
import time
import io
import uuid
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
from datetime import datetime

# --- Initial Setup ---
st.set_page_config(
    page_title="Sistema de Atribuição de Números",
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- CSS Styling ---
st.markdown("""
<style>
    .main-header {text-align: center; margin-bottom: 30px;}
    .number-display {font-size: 72px; text-align: center; margin: 30px 0;}
    .success-msg {background-color: #d4edda; color: #155724; padding: 10px; border-radius: 5px;}
    .error-msg {background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px;}
</style>
""", unsafe_allow_html=True)

# --- Functions ---

def get_supabase_client() -> Client:
    """Estabelece conexão com o Supabase usando as credenciais armazenadas na sessão."""
    supabase_url = st.session_state.get("SUPABASE_URL")
    supabase_key = st.session_state.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        st.error("Configuração do Supabase não encontrada. Vá para 'Configuração'.")
        return None
    try:
        client = create_client(supabase_url, supabase_key)
        # Testa a conexão usando a tabela _dummy (certifique-se de que ela exista)
        client.table("_dummy").select("*").limit(1).execute()
        return client
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {str(e)}")
        return None

def check_table_exists(supabase, table_name):
    """Verifica se uma tabela específica existe no Supabase."""
    try:
        supabase.table(table_name).select("*").limit(1).execute()
        return True
    except Exception:
        return False

def create_meeting_table(supabase, table_name, meeting_name, max_number=999):
    """Cria uma nova tabela para uma reunião no Supabase e registra os metadados."""
    try:
        # Registra os metadados da reunião na tabela 'meetings_metadata'
        supabase.table("meetings_metadata").insert({
            "table_name": table_name,
            "meeting_name": meeting_name,
            "created_at": datetime.now().isoformat(),
            "max_number": max_number
        }).execute()
        
        # Inserir os números na nova tabela em lotes para evitar sobrecarga
        batch_size = 100
        for i in range(0, max_number, batch_size):
            end = min(i + batch_size, max_number)
            data = [{"number": j, "assigned": False, "assigned_at": None, "user_id": None} 
                    for j in range(i+1, end+1)]
            supabase.table(table_name).insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao criar tabela da reunião: {str(e)}")
        return False

def get_available_meetings(supabase):
    """Obtém a lista de reuniões disponíveis na tabela de metadados."""
    try:
        response = supabase.table("meetings_metadata").select("*").execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao obter reuniões: {str(e)}")
        return []

def generate_number_image(number):
    """Gera uma imagem com o número atribuído."""
    width, height = 600, 300
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Fundo com gradiente simples
    for y in range(height):
        r = int(220 - y/3)
        g = int(240 - y/3)
        b = 255
        for x in range(width):
            draw.point((x, y), fill=(r, g, b))
    
    # Tenta carregar uma fonte personalizada
    try:
        font = ImageFont.truetype("Arial.ttf", 120)
    except IOError:
        font = ImageFont.load_default()
    
    number_text = str(number)
    # Usando textbbox para calcular as dimensões do texto
    bbox = draw.textbbox((0, 0), number_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_position = ((width - text_width) // 2, (height - text_height) // 2 - 30)
    draw.text(text_position, number_text, font=font, fill=(0, 0, 100))
    
    # Texto de rodapé
    footer_text = "Seu número para o evento"
    footer_font = ImageFont.load_default()
    footer_bbox = draw.textbbox((0,0), footer_text, font=footer_font)
    footer_width = footer_bbox[2] - footer_bbox[0]
    footer_position = ((width - footer_width) // 2, height - 40)
    draw.text(footer_position, footer_text, font=footer_font, fill=(80, 80, 80))
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    return img_buffer

# --- Inicializar Variáveis de Sessão ---
if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())

# --- Sidebar Navigation ---
st.sidebar.title("Menu")
page = st.sidebar.radio("Escolha uma opção", [
    "Configuração", 
    "Gerenciar Reuniões", 
    "Atribuir Número",
    "Ver Estatísticas"
])

# --- Página 1: Configuração ---
if page == "Configuração":
    st.markdown("<h1 class='main-header'>Configuração do Supabase</h1>", unsafe_allow_html=True)
    saved_url = st.session_state.get("SUPABASE_URL", "")
    saved_key = st.session_state.get("SUPABASE_KEY", "")
    
    with st.form("config_form"):
        supabase_url = st.text_input("URL do Supabase", value=saved_url)
        supabase_key = st.text_input("Chave API do Supabase", type="password", value=saved_key)
        submit_button = st.form_submit_button("Salvar Configuração")
        
        if submit_button:
            if supabase_url and supabase_key:
                st.session_state["SUPABASE_URL"] = supabase_url
                st.session_state["SUPABASE_KEY"] = supabase_key
                try:
                    client = create_client(supabase_url, supabase_key)
                    client.table("_dummy").select("*").limit(1).execute()
                    st.success("Configuração salva e conexão testada com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao testar conexão: {str(e)}")
            else:
                st.warning("Por favor, preencha todos os campos.")
    
    with st.expander("Como configurar o Supabase"):
        st.markdown("""
1. Crie uma conta no [Supabase](https://supabase.com/)
2. Crie um novo projeto
3. Vá para Configurações > API
4. Copie a URL e a chave (anon/public)
5. Cole nos campos acima

**Importante**: Crie as seguintes tabelas no seu Supabase:

-- Tabela de metadados das reuniões
CREATE TABLE public.meetings_metadata (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    table_name TEXT NOT NULL,
    meeting_name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) NOT NULL,
    max_number INTEGER DEFAULT 999
);

-- Tabela dummy para teste de conexão
CREATE TABLE public._dummy (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    test_column TEXT
);
        """)

# --- Página 2: Gerenciar Reuniões ---
elif page == "Gerenciar Reuniões":
    st.markdown("<h1 class='main-header'>Gerenciar Reuniões</h1>", unsafe_allow_html=True)
    supabase = get_supabase_client()
    if not supabase:
        st.stop()
    
    with st.form("create_meeting_form"):
        st.subheader("Criar Nova Reunião")
        meeting_name = st.text_input("Nome da Reunião")
        max_number = st.number_input("Número Máximo", min_value=10, max_value=10000, value=999)
        submit_button = st.form_submit_button("Criar Reunião")
        
        if submit_button:
            if meeting_name:
                # Gera um nome único para a tabela
                table_name = f"meeting_{int(time.time())}_{meeting_name.lower().replace(' ', '_')}"
                if check_table_exists(supabase, table_name):
                    st.error("Já existe uma reunião com este nome. Tente outro nome.")
                else:
                    with st.spinner("Criando reunião..."):
                        success = create_meeting_table(supabase, table_name, meeting_name, max_number)
                        if success:
                            # Gera um link relativo para acessar a reunião
                            meeting_link = f"?page=Atribuir%20Número&table={table_name}"
                            st.markdown(f"[Clique aqui para acessar a reunião]({meeting_link})")
                        else:
                            st.error("Falha na criação da reunião.")
            else:
                st.warning("Digite um nome para a reunião.")
    
    st.subheader("Reuniões Existentes")
    meetings = get_available_meetings(supabase)
    if meetings:
        meeting_data = []
        for meeting in meetings:
            if "table_name" in meeting and "meeting_name" in meeting:
                try:
                    count_response = supabase.table(meeting["table_name"]).select("*", count="exact").eq("assigned", True).execute()
                    assigned_count = count_response.count if hasattr(count_response, 'count') else 0
                    meeting_data.append({
                        "Nome": meeting.get("meeting_name", "Sem nome"),
                        "Tabela": meeting.get("table_name", ""),
                        "Criada em": meeting.get("created_at", "")[:16].replace("T", " "),
                        "Números Atribuídos": assigned_count,
                        "Total de Números": meeting.get("max_number", 0)
                    })
                except Exception:
                    continue
        if meeting_data:
            df = pd.DataFrame(meeting_data)
            st.dataframe(df)
        else:
            st.info("Nenhuma reunião encontrada.")
    else:
        st.info("Nenhuma reunião disponível.")

# --- Página 3: Atribuir Número ---
elif page == "Atribuir Número":
    st.markdown("<h1 class='main-header'>Obtenha Seu Número</h1>", unsafe_allow_html=True)
    
    # Recupera os parâmetros da URL usando st.query_params
    query_params = st.query_params
    table_name = query_params.get("table", None)
    
    if not table_name:
        st.error("Tabela não especificada. Selecione uma reunião abaixo:")
        supabase = get_supabase_client()
        if supabase:
            meetings = get_available_meetings(supabase)
            if meetings:
                options = {f"{m['meeting_name']} ({m['table_name']})": m["table_name"] 
                           for m in meetings if "table_name" in m and "meeting_name" in m}
                selected = st.selectbox("Selecione uma reunião:", list(options.keys()))
                if st.button("Ir para a Reunião"):
                    selected_table = options[selected]
                    st.set_query_params(page="Atribuir Número", table=selected_table)
                    st.experimental_rerun()
        st.stop()
    else:
        supabase = get_supabase_client()
        if not supabase:
            st.stop()
        if not check_table_exists(supabase, table_name):
            st.error("Tabela da reunião não encontrada. A reunião pode ter sido encerrada.")
            st.stop()
        
        try:
            meeting_info = supabase.table("meetings_metadata").select("*").eq("table_name", table_name).execute()
            meeting_name = meeting_info.data[0]["meeting_name"] if meeting_info.data else "Reunião"
            st.subheader(f"Reunião: {meeting_name}")
        except Exception:
            st.subheader("Obter número para a reunião")
        
        user_id = st.session_state.get("user_id")
        try:
            # Verifica se o usuário já possui um número atribuído nesta reunião
            existing = supabase.table(table_name).select("*").eq("user_id", user_id).execute()
            if existing.data:
                st.session_state["assigned_number"] = existing.data[0]["number"]
                st.markdown(f"""
                <div class='success-msg'>
                    <p>Você já tem um número atribuído:</p>
                    <div class='number-display'>{st.session_state['assigned_number']}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                if "assigned_number" not in st.session_state:
                    with st.spinner("Atribuindo um número..."):
                        response = supabase.table(table_name).select("*").eq("assigned", False).execute()
                        if response.data:
                            available_numbers = [row["number"] for row in response.data]
                            assigned_number = random.choice(available_numbers)
                            supabase.table(table_name).update({
                                "assigned": True,
                                "assigned_at": datetime.now().isoformat(),
                                "user_id": user_id
                            }).eq("number", assigned_number).execute()
                            st.session_state["assigned_number"] = assigned_number
                        else:
                            st.error("Todos os números já foram atribuídos!")
                            st.stop()
                st.markdown(f"""
                <div class='success-msg'>
                    <p>Seu número atribuído é:</p>
                    <div class='number-display'>{st.session_state['assigned_number']}</div>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Erro ao atribuir número: {str(e)}")
            st.stop()
        
        if st.button("Salvar como Imagem"):
            with st.spinner("Gerando imagem..."):
                img_buffer = generate_number_image(st.session_state["assigned_number"])
                st.image(img_buffer)
                st.download_button(
                    "Baixar Imagem",
                    img_buffer,
                    file_name=f"meu_numero_{st.session_state['assigned_number']}.png",
                    mime="image/png"
                )

# --- Página 4: Ver Estatísticas ---
elif page == "Ver Estatísticas":
    st.markdown("<h1 class='main-header'>Estatísticas de Reuniões</h1>", unsafe_allow_html=True)
    supabase = get_supabase_client()
    if not supabase:
        st.stop()
    
    meetings = get_available_meetings(supabase)
    if not meetings:
        st.info("Não há reuniões disponíveis para análise.")
        st.stop()
    
    options = {f"{m['meeting_name']} ({m['table_name']})": m["table_name"] 
               for m in meetings if "table_name" in m and "meeting_name" in m}
    selected = st.selectbox("Selecione uma reunião:", list(options.keys()))
    
    if selected:
        selected_table = options[selected]
        try:
            total_response = supabase.table(selected_table).select("*", count="exact").execute()
            total_numbers = total_response.count if hasattr(total_response, 'count') else 0
            assigned_response = supabase.table(selected_table).select("*", count="exact").eq("assigned", True).execute()
            assigned_numbers = assigned_response.count if hasattr(assigned_response, 'count') else 0
            percentage = (assigned_numbers / total_numbers) * 100 if total_numbers > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Números", total_numbers)
            with col2:
                st.metric("Números Atribuídos", assigned_numbers)
            with col3:
                st.metric("Percentual Atribuído", f"{percentage:.1f}%")
            
            try:
                time_data_response = supabase.table(selected_table).select("*").eq("assigned", True).order("assigned_at").execute()
                if time_data_response.data:
                    time_data = []
                    for item in time_data_response.data:
                        if item.get("assigned_at"):
                            time_data.append({
                                "time": item.get("assigned_at")[:16].replace("T", " "),
                                "count": 1
                            })
                    if time_data:
                        df = pd.DataFrame(time_data)
                        df["time"] = pd.to_datetime(df["time"])
                        df["hour"] = df["time"].dt.floor("H")
                        hourly_counts = df.groupby("hour").count().reset_index()
                        hourly_counts["hour_str"] = hourly_counts["hour"].dt.strftime("%d/%m %H:00")
                        st.subheader("Atribuições de Números por Hora")
                        st.bar_chart(data=hourly_counts, x="hour_str", y="count")
            except Exception:
                st.info("Dados temporais não disponíveis para esta reunião.")
            
            if st.button("Exportar Dados"):
                try:
                    all_data_response = supabase.table(selected_table).select("*").execute()
                    if all_data_response.data:
                        df = pd.DataFrame(all_data_response.data)
                        csv = df.to_csv(index=False)
                        st.download_button(
                            "Baixar CSV",
                            csv,
                            file_name=f"{selected_table}_export.csv",
                            mime="text/csv"
                        )
                except Exception as e:
                    st.error(f"Erro ao exportar dados: {str(e)}")
        except Exception as e:
            st.error(f"Erro ao obter estatísticas: {str(e)}")
