import streamlit as st
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
import pytesseract
import numpy as np
from streamlit_drawable_canvas import st_canvas
import pandas as pd
from PIL import Image
import platform

# ==========================================
# CONFIGURAÇÃO HÍBRIDA DE AMBIENTE (WINDOWS / NUVEM)
# ==========================================
if platform.system() == "Windows":
    # Caminhos locais na sua máquina (GreenTech)
    CAMINHO_POPPLER = r"C:\Users\victor.silva\OneDrive - Greentech\Área de Trabalho\Projetos Python\OpenCV\Release-25.12.0-0 (1)\poppler-25.12.0\Library\bin"
    pytesseract.pytesseract.tesseract_cmd = r"C:\Users\victor.silva\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
else:
    # Caminhos no servidor Linux (Streamlit Cloud)
    CAMINHO_POPPLER = None # O Linux encontra o Poppler automaticamente
    pytesseract.pytesseract.tesseract_cmd = "tesseract"
# ==========================================

# Configuração da página Streamlit
st.set_page_config(page_title="Extrator de Ativos - GreenTech", layout="wide")
st.title("📄 Extrator de Tabelas de PDF (Múltiplas Colunas)")
st.markdown("Faça o upload do PDF, ajuste o zoom e **desenhe até 4 retângulos** para extrair colunas separadas. A ferramenta alinhará tudo automaticamente da esquerda para a direita.")

# Inicializar o contador do Canvas no Session State para permitir a limpeza
if 'canvas_key_counter' not in st.session_state:
    st.session_state['canvas_key_counter'] = 0

# ==========================================
# FUNÇÕES COM CACHE (OTIMIZAÇÃO DE PERFORMANCE EXTREMA)
# ==========================================


@st.cache_data(show_spinner=False)
def obter_info_pdf(pdf_bytes):
    # Se for Windows, usa o caminho. Se for Linux (Nuvem), deixa o sistema achar sozinho.
    if CAMINHO_POPPLER:
        info = pdfinfo_from_bytes(pdf_bytes, poppler_path=CAMINHO_POPPLER)
    else:
        info = pdfinfo_from_bytes(pdf_bytes)
    return info["Pages"]

@st.cache_data(show_spinner=False)
def carregar_pagina_pdf(pdf_bytes, pagina):
    if CAMINHO_POPPLER:
        images = convert_from_bytes(
            pdf_bytes, 
            first_page=pagina, 
            last_page=pagina, 
            poppler_path=CAMINHO_POPPLER
        )
    else:
        images = convert_from_bytes(
            pdf_bytes, 
            first_page=pagina, 
            last_page=pagina
        )
    return images[0]

# Upload do arquivo
uploaded_file = st.file_uploader("Faça upload de um PDF (Manuais, Catálogos, Notas Fiscais)", type="pdf")

if uploaded_file is not None:
    pdf_bytes = uploaded_file.getvalue()
    
    try:
        total_pages = obter_info_pdf(pdf_bytes)
    except Exception as e:
        st.error(f"Erro ao ler informações do PDF. Detalhe: {e}")
        st.stop()

    # ==========================================
    # SELETOR DE PÁGINAS E ZOOM (BARRA LATERAL)
    # ==========================================
    st.sidebar.header("Navegação e Visualização")
    st.sidebar.write(f"**Total de páginas:** {total_pages}")
    
    pagina_selecionada = st.sidebar.number_input(
        "Ir para a página:", 
        min_value=1, 
        max_value=total_pages, 
        value=1, 
        step=1
    )
    
    zoom = st.sidebar.slider(
        "Zoom da Imagem (%)", 
        min_value=20, 
        max_value=150, 
        value=60, 
        step=10
    )
    fator_escala = zoom / 100.0
    
    with st.spinner(f"Carregando a página {pagina_selecionada}..."):
        try:
            image_original = carregar_pagina_pdf(pdf_bytes, pagina_selecionada)
            image_np_original = np.array(image_original)
            
            nova_largura = int(image_original.width * fator_escala)
            nova_altura = int(image_original.height * fator_escala)
            image_display = image_original.resize((nova_largura, nova_altura))
            
        except Exception as e:
            st.error(f"Erro ao converter a página. Detalhe: {e}")
            st.stop()
    
    # ==========================================
    # ÁREA DE SELEÇÃO E BOTÃO DE LIMPEZA
    # ==========================================
    col_titulo, col_botao = st.columns([3, 1])
    with col_titulo:
        st.subheader(f"1. Área de Seleção (Página {pagina_selecionada})")
    with col_botao:
        if st.button("🧹 Limpar Todas as Seleções", use_container_width=True):
            st.session_state['canvas_key_counter'] += 1
            st.rerun()
            
    st.info("💡 **Dica Operacional:** Desenhe retângulos apenas sobre as colunas que importam (ex: ItemCode e Valor). Ignore o texto no meio.")
    
    chave_dinamica_canvas = f"canvas_page_{pagina_selecionada}_{st.session_state['canvas_key_counter']}"
    
    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",
        stroke_width=2,
        stroke_color="#FF0000",
        background_image=image_display,
        update_streamlit=True,
        height=nova_altura,
        width=nova_largura,
        drawing_mode="rect",
        key=chave_dinamica_canvas, 
    )
    
    # ==========================================
    # MOTOR DE EXTRAÇÃO (MÚLTIPLAS COLUNAS)
    # ==========================================
    if canvas_result.json_data is not None:
        objects = canvas_result.json_data["objects"]
        
        # Filtra apenas os retângulos desenhados
        retangulos = [obj for obj in objects if obj["type"] == "rect"]
        
        if len(retangulos) > 0:
            st.subheader("2. Tabela Estruturada (Pronta para Power Query)")
            
            if len(retangulos) > 4:
                st.warning("⚠️ Você desenhou mais de 4 seleções. Apenas as 4 primeiras (da esquerda para a direita) serão processadas para manter a integridade dos dados.")
            
            # 1. Mapear coordenadas e voltar para a escala original (alta resolução)
            selecoes = []
            for rect in retangulos:
                x_tela, y_tela = rect["left"], rect["top"]
                w_tela, h_tela = rect["width"], rect["height"]
                
                x_real = int(x_tela / fator_escala)
                y_real = int(y_tela / fator_escala)
                w_real = int(w_tela / fator_escala)
                h_real = int(h_tela / fator_escala)
                
                selecoes.append({
                    'coord': (x_real, y_real, x_real + w_real, y_real + h_real),
                    'x_ordem': x_real # Usado para ordenar da esquerda para a direita
                })
            
            # 2. Ordenar da esquerda para a direita e limitar a 4 colunas
            selecoes = sorted(selecoes, key=lambda s: s['x_ordem'])[:4]
            
            colunas_extraidas = []
            custom_config = r'--oem 3 --psm 6'
            
            with st.spinner("Processando OCR das colunas selecionadas..."):
                try:
                    # 3. Fazer OCR de cada bloco separadamente
                    for sel in selecoes:
                        x1, y1, x2, y2 = sel['coord']
                        cropped = image_np_original[y1:y2, x1:x2]
                        texto = pytesseract.image_to_string(cropped, lang='por', config=custom_config)
                        
                        # Limpar linhas vazias
                        linhas = [linha.strip() for linha in texto.split('\n') if linha.strip()]
                        colunas_extraidas.append(linhas)
                        
                    # 4. Juntar as colunas (Zip) preenchendo com '--'
                    if colunas_extraidas:
                        max_linhas = max(len(col) for col in colunas_extraidas)
                        dados_finais = []
                        
                        for i in range(max_linhas):
                            linha_atual = []
                            for col in colunas_extraidas:
                                if i < len(col):
                                    linha_atual.append(col[i])
                                else:
                                    linha_atual.append("--")
                            dados_finais.append(linha_atual)

                        # 5. Criar DataFrame e Exibir
                        df = pd.DataFrame(dados_finais)
                        df.columns = [f"Coluna {i+1}" for i in range(len(df.columns))]
                        
                        st.dataframe(df, use_container_width=True)
                        
                        # ==========================================
                        # EXPORTAÇÃO (PADRÃO POWER QUERY: SEP=';')
                        # ==========================================
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Exporta CSV com ponto e vírgula e encoding correto para acentos
                            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
                            st.download_button(
                                label="📥 Baixar CSV (Separado por ;)",
                                data=csv,
                                file_name=f'extracao_ativos_pag_{pagina_selecionada}.csv',
                                mime='text/csv',
                                use_container_width=True
                            )
                            
                        with col2:
                            # Cópia para área de transferência (apenas funciona rodando localmente)
                            if platform.system() == "Windows":
                                if st.button("📋 Copiar Dados", use_container_width=True):
                                    try:
                                        df.to_clipboard(index=False, header=False, sep=';')
                                        st.success("✅ Dados copiados! Pode colar no Excel.")
                                    except Exception as e:
                                        st.error(f"Erro ao copiar: {e}")
                            else:
                                st.info("📌 O botão de copiar direto funciona apenas na versão Desktop. Use o botão 'Baixar CSV' para exportar os dados.")
                                
                except Exception as e:
                    st.error(f"Erro no processamento OCR. Detalhe: {e}")