import streamlit as st
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
import pytesseract
import numpy as np
from streamlit_drawable_canvas import st_canvas
import pandas as pd
from PIL import Image
import platform

# ==========================================
# CONFIGURAÇÃO DE PÁGINA
# ==========================================
st.set_page_config(page_title="Extrator de Ativos - GreenTech", layout="wide")

# ==========================================
# FUNÇÃO DE LOGIN E SEGURANÇA
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Login - GreenTech")
        st.text_input("E-mail Corporativo", key="username", placeholder="exemplo@greentech.log.br")
        st.text_input("Senha", type="password", key="password")
        if st.button("Entrar"):
            usuario = st.session_state["username"].strip().lower()
            senha = st.session_state["password"]
            
            if not usuario.endswith("@greentech.log.br"):
                st.error("❌ Acesso restrito a e-mails @greentech.log.br")
            elif senha == st.secrets["credentials"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("😕 Credenciais inválidas.")
        return False
    return True

# ==========================================
# CONFIGURAÇÃO DE AMBIENTE (LINUX vs WINDOWS)
# ==========================================
IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    # Ajuste estes caminhos para o seu PC local se necessário
    CAMINHO_POPPLER = r"C:\Users\victor.silva\OneDrive - Greentech\Área de Trabalho\Projetos Python\OpenCV\Release-25.12.0-0 (1)\poppler-25.12.0\Library\bin"
    pytesseract.pytesseract.tesseract_cmd = r"C:\Users\victor.silva\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
else:
    # No Streamlit Cloud (Linux), os binários já estão no PATH global
    CAMINHO_POPPLER = None
    pytesseract.pytesseract.tesseract_cmd = "tesseract"

# ==========================================
# FUNÇÕES DE PROCESSAMENTO (OTIMIZADAS)
# ==========================================
@st.cache_data(show_spinner=False)
def obter_info_pdf(pdf_bytes):
    kwargs = {"poppler_path": CAMINHO_POPPLER} if IS_WINDOWS else {}
    info = pdfinfo_from_bytes(pdf_bytes, **kwargs)
    return info["Pages"]

@st.cache_data(show_spinner=False)
def carregar_pagina_pdf(pdf_bytes, pagina):
    kwargs = {"poppler_path": CAMINHO_POPPLER} if IS_WINDOWS else {}
    # use_pdftocairo=True é mais estável em servidores Linux
    images = convert_from_bytes(
        pdf_bytes, 
        first_page=pagina, 
        last_page=pagina, 
        fmt="jpeg", 
        use_pdftocairo=not IS_WINDOWS,
        **kwargs
    )
    return images[0]

# ==========================================
# INÍCIO DO APP
# ==========================================
if check_password():
    
    # Barra Lateral
    st.sidebar.image("https://www.greentech.log.br/wp-content/uploads/2021/05/logo-greentech.png", width=150)
    if st.sidebar.button("🚪 Sair"):
        st.session_state.clear()
        st.rerun()

    st.title("📄 Extrator de Tabelas de PDF")
    st.markdown("---")

    if 'canvas_key_counter' not in st.session_state:
        st.session_state['canvas_key_counter'] = 0

    uploaded_file = st.file_uploader("Faça upload de um PDF", type="pdf")

    if uploaded_file is not None:
        pdf_bytes = uploaded_file.getvalue()
        
        try:
            total_pages = obter_info_pdf(pdf_bytes)
        except Exception as e:
            st.error(f"Erro ao ler PDF: {e}. Verifique se o arquivo não está corrompido.")
            st.stop()

        # Controles na Lateral
        st.sidebar.header("Navegação")
        pagina_selecionada = st.sidebar.number_input("Página:", min_value=1, max_value=total_pages, value=1)
        zoom = st.sidebar.slider("Zoom da Visualização (%)", min_value=20, max_value=150, value=70)
        
        # Processamento da Imagem
        with st.spinner("Renderizando página..."):
            image_original = carregar_pagina_pdf(pdf_bytes, pagina_selecionada)
            if image_original.mode != 'RGB':
                image_original = image_original.convert('RGB')
                
            image_np_original = np.array(image_original)
            
            # Cálculo de escala para manter o Canvas responsivo
            largura_base = 1000 
            fator_escala = (largura_base * (zoom / 100.0)) / image_original.width
            
            nova_largura = int(image_original.width * fator_escala)
            nova_altura = int(image_original.height * fator_escala)
            image_display = image_original.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)

        # Interface do Canvas
        col_titulo, col_botao = st.columns([3, 1])
        with col_titulo:
            st.subheader(f"1. Desenhe retângulos sobre as colunas (Pág. {pagina_selecionada})")
        with col_botao:
            if st.button("🧹 Limpar Seleções", use_container_width=True):
                st.session_state['canvas_key_counter'] += 1
                st.rerun()
        
        # O Canvas
        chave_canvas = f"canvas_{pagina_selecionada}_{st.session_state['canvas_key_counter']}"
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",
            stroke_width=2,
            stroke_color="#FF0000",
            background_image=image_display,
            height=nova_altura,
            width=nova_largura,
            drawing_mode="rect",
            key=chave_canvas,
            display_toolbar=True,
        )

        # Processamento do OCR
        if canvas_result.json_data is not None:
            retangulos = [obj for obj in canvas_result.json_data["objects"] if obj["type"] == "rect"]
            
            if len(retangulos) > 0:
                st.markdown("---")
                st.subheader("2. Resultado da Extração")
                
                selecoes = []
                for rect in retangulos:
                    # Reverter a escala para pegar as coordenadas na imagem original (alta resolução)
                    x_real = int(rect["left"] / fator_escala)
                    y_real = int(rect["top"] / fator_escala)
                    w_real = int(rect["width"] / fator_escala)
                    h_real = int(rect["height"] / fator_escala)
                    selecoes.append({'coord': (x_real, y_real, x_real + w_real, y_real + h_real), 'x_ordem': x_real})
                
                # Ordena da esquerda para a direita
                selecoes = sorted(selecoes, key=lambda s: s['x_ordem'])
                colunas_extraidas = []
                custom_config = r'--oem 3 --psm 6'
                
                with st.spinner("Extraindo texto com OCR..."):
                    for sel in selecoes:
                        x1, y1, x2, y2 = sel['coord']
                        # Crop na imagem original para máxima precisão
                        cropped = image_np_original[max(0, y1):y2, max(0, x1):x2]
                        
                        if cropped.size > 0:
                            texto = pytesseract.image_to_string(cropped, lang='por', config=custom_config)
                            linhas = [l.strip() for l in texto.split('\n') if l.strip()]
                            colunas_extraidas.append(linhas)
                    
                    if colunas_extraidas:
                        # Alinha as colunas em um DataFrame
                        max_l = max(len(c) for c in colunas_extraidas)
                        dados = [[col[i] if i < len(col) else "" for col in colunas_extraidas] for i in range(max_l)]
                        
                        df = pd.DataFrame(dados, columns=[f"Coluna {i+1}" for i in range(len(colunas_extraidas))])
                        st.dataframe(df, use_container_width=True)
                        
                        csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
                        st.download_button(
                            label="📥 Baixar Planilha (CSV)",
                            data=csv,
                            file_name=f'extracao_pag_{pagina_selecionada}.csv',
                            mime='text/csv',
                        )

# Seria útil eu te mostrar como configurar o arquivo secrets.toml para essa senha funcionar?