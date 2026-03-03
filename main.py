import streamlit as st
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
import pytesseract
import numpy as np
from streamlit_drawable_canvas import st_canvas
import pandas as pd
from PIL import Image
import platform

# ==========================================
# CONFIGURAÇÃO DE PÁGINA (Deve ser a primeira linha)
# ==========================================
st.set_page_config(page_title="Extrator de Ativos - GreenTech", layout="wide")

# ==========================================
# FUNÇÃO DE LOGIN E SEGURANÇA
# ==========================================
def check_password():
    """Retorna True se o usuário inseriu o e-mail @greentech e a senha correta."""

    def password_entered():
        """Verifica as credenciais inseridas."""
        usuario = st.session_state["username"].strip().lower()
        senha = st.session_state["password"]
        
        # 1. Verifica o domínio do e-mail
        if not usuario.endswith("@greentech.log.br"):
            st.session_state["password_correct"] = False
            st.error("❌ Acesso restrito a e-mails @greentech.log.br")
            return

        # 2. Verifica a senha comparando com o que está nos Secrets do Streamlit
        # Lembre-se de configurar no painel do Streamlit: [credentials] password = "sua_senha"
        if senha == st.secrets["credentials"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Limpa a senha da memória por segurança
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔐 Login - GreenTech")
        st.text_input("E-mail Corporativo", key="username", placeholder="exemplo@greentech.log.br")
        st.text_input("Senha", type="password", key="password", on_change=password_entered)
        st.info("Utilize seu e-mail @greentech.log.br para acessar a ferramenta.")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔐 Login - GreenTech")
        st.text_input("E-mail Corporativo", key="username", placeholder="exemplo@greentech.log.br")
        st.text_input("Senha", type="password", key="password", on_change=password_entered)
        st.error("😕 Credenciais inválidas.")
        return False
    else:
        return True

# ==========================================
# INÍCIO DO APP (SÓ RODA SE O LOGIN FOR SUCESSO)
# ==========================================
if check_password():
    
    # Configuração de Ambiente
    if platform.system() == "Windows":
        CAMINHO_POPPLER = r"C:\Users\victor.silva\OneDrive - Greentech\Área de Trabalho\Projetos Python\OpenCV\Release-25.12.0-0 (1)\poppler-25.12.0\Library\bin"
        pytesseract.pytesseract.tesseract_cmd = r"C:\Users\victor.silva\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    else:
        CAMINHO_POPPLER = None 
        pytesseract.pytesseract.tesseract_cmd = "tesseract"

    # Barra Lateral
    st.sidebar.image("https://www.greentech.log.br/wp-content/uploads/2021/05/logo-greentech.png", width=150) # Exemplo de logo
    if st.sidebar.button("🚪 Sair"):
        st.session_state.clear()
        st.rerun()

    st.title("📄 Extrator de Tabelas de PDF (Múltiplas Colunas)")
    st.markdown("---")

    if 'canvas_key_counter' not in st.session_state:
        st.session_state['canvas_key_counter'] = 0

    # Funções Otimizadas
    @st.cache_data(show_spinner=False)
    def obter_info_pdf(pdf_bytes):
        if CAMINHO_POPPLER:
            info = pdfinfo_from_bytes(pdf_bytes, poppler_path=CAMINHO_POPPLER)
        else:
            info = pdfinfo_from_bytes(pdf_bytes)
        return info["Pages"]

    @st.cache_data(show_spinner=False)
    def carregar_pagina_pdf(pdf_bytes, pagina):
        if CAMINHO_POPPLER:
            images = convert_from_bytes(pdf_bytes, first_page=pagina, last_page=pagina, poppler_path=CAMINHO_POPPLER)
        else:
            images = convert_from_bytes(pdf_bytes, first_page=pagina, last_page=pagina)
        return images[0]

    uploaded_file = st.file_uploader("Faça upload de um PDF", type="pdf")

    if uploaded_file is not None:
        pdf_bytes = uploaded_file.getvalue()
        
        try:
            total_pages = obter_info_pdf(pdf_bytes)
        except Exception as e:
            st.error(f"Erro ao ler PDF: {e}")
            st.stop()

        st.sidebar.header("Navegação")
        pagina_selecionada = st.sidebar.number_input("Página:", min_value=1, max_value=total_pages, value=1)
        zoom = st.sidebar.slider("Zoom (%)", min_value=20, max_value=150, value=60)
        fator_escala = zoom / 100.0
        
        with st.spinner("Carregando página..."):
            image_original = carregar_pagina_pdf(pdf_bytes, pagina_selecionada)
            image_np_original = np.array(image_original)
            nova_largura = int(image_original.width * fator_escala)
            nova_altura = int(image_original.height * fator_escala)
            image_display = image_original.resize((nova_largura, nova_altura))

        col_titulo, col_botao = st.columns([3, 1])
        with col_titulo:
            st.subheader(f"1. Selecione as Colunas (Página {pagina_selecionada})")
        with col_botao:
            if st.button("🧹 Limpar Seleções", use_container_width=True):
                st.session_state['canvas_key_counter'] += 1
                st.rerun()
                
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
        )

        if canvas_result.json_data is not None:
            retangulos = [obj for obj in canvas_result.json_data["objects"] if obj["type"] == "rect"]
            
            if len(retangulos) > 0:
                st.subheader("2. Resultado da Extração")
                selecoes = []
                for rect in retangulos:
                    x_real = int(rect["left"] / fator_escala)
                    y_real = int(rect["top"] / fator_escala)
                    w_real = int(rect["width"] / fator_escala)
                    h_real = int(rect["height"] / fator_escala)
                    selecoes.append({'coord': (x_real, y_real, x_real + w_real, y_real + h_real), 'x_ordem': x_real})
                
                selecoes = sorted(selecoes, key=lambda s: s['x_ordem'])[:4]
                colunas_extraidas = []
                custom_config = r'--oem 3 --psm 6'
                
                with st.spinner("Realizando OCR..."):
                    for sel in selecoes:
                        x1, y1, x2, y2 = sel['coord']
                        cropped = image_np_original[y1:y2, x1:x2]
                        texto = pytesseract.image_to_string(cropped, lang='por', config=custom_config)
                        colunas_extraidas.append([l.strip() for l in texto.split('\n') if l.strip()])
                    
                    if colunas_extraidas:
                        max_l = max(len(c) for c in colunas_extraidas)
                        dados = [[col[i] if i < len(col) else "--" for col in colunas_extraidas] for i in range(max_l)]
                        df = pd.DataFrame(dados, columns=[f"Coluna {i+1}" for i in range(len(colunas_extraidas))])
                        st.dataframe(df, use_container_width=True)
                        
                        csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
                        st.download_button("📥 Baixar Planilha (CSV)", data=csv, file_name=f'extração_greentech.csv', mime='text/csv')