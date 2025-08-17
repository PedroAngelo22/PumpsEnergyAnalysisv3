import streamlit as st
import pandas as pd
from fpdf import FPDF
import math
import time
import numpy as np
import io
import matplotlib.pyplot as plt
import matplotlib

# Configura o Matplotlib para não usar um backend de GUI
matplotlib.use('Agg')

# --- Dicionário de Fluidos ---
FLUIDOS = {
    "Água a 20°C": {"rho": 998.2, "nu": 1.004e-6},
    "Etanol a 20°C": {"rho": 789.0, "nu": 1.51e-6},
    "Glicerina a 20°C": {"rho": 1261.0, "nu": 1.49e-3},
    "Óleo Leve (genérico)": {"rho": 880.0, "nu": 1.5e-5}
}

# --- Funções de Cálculo de Engenharia (sem alterações) ---
def calcular_perda_carga(vazao_m3h, diametro_mm, comprimento_m, rugosidade_mm, k_total, fluido_selecionado):
    if diametro_mm <= 0: return {"principal": 0, "localizada": 0, "velocidade": 0}
    vazao_m3s = vazao_m3h / 3600
    diametro_m = diametro_mm / 1000
    rugosidade_m = rugosidade_mm / 1000
    nu = FLUIDOS[fluido_selecionado]["nu"]
    area = (math.pi * diametro_m**2) / 4
    velocidade = vazao_m3s / area
    reynolds = (velocidade * diametro_m) / nu if nu > 0 else 0
    fator_atrito = 0
    if reynolds > 4000:
        log_term = math.log10((rugosidade_m / (3.7 * diametro_m)) + (5.74 / reynolds**0.9))
        fator_atrito = 0.25 / (log_term**2)
    elif reynolds > 0:
        fator_atrito = 64 / reynolds
    perda_carga_principal = fator_atrito * (comprimento_m / diametro_m) * (velocidade**2 / (2 * 9.81))
    perda_carga_localizada = k_total * (velocidade**2 / (2 * 9.81))
    return {"principal": perda_carga_principal, "localizada": perda_carga_localizada, "velocidade": velocidade}

def calcular_analise_energetica(vazao_m3h, h_man, eficiencia_bomba, eficiencia_motor, horas_dia, custo_kwh, fluido_selecionado):
    rho = FLUIDOS[fluido_selecionado]["rho"]
    vazao_m3s = vazao_m3h / 3600
    potencia_hidraulica_W = vazao_m3s * rho * 9.81 * h_man
    potencia_eixo_W = potencia_hidraulica_W / eficiencia_bomba if eficiencia_bomba > 0 else 0
    potencia_eletrica_W = potencia_eixo_W / eficiencia_motor if eficiencia_motor > 0 else 0
    potencia_eletrica_kW = potencia_eletrica_W / 1000
    consumo_mensal_kWh = (potencia_eletrica_kW * horas_dia) * 30
    custo_anual = (consumo_mensal_kWh * custo_kwh) * 12
    return {"potencia_eletrica_kW": potencia_eletrica_kW, "consumo_mensal_kWh": consumo_mensal_kWh, "custo_anual": custo_anual}

def gerar_grafico_diametro_custo(diam_min, diam_max, passo, **kwargs):
    if diam_min >= diam_max or passo <= 0: return pd.DataFrame()
    faixa_diametros = np.arange(diam_min, diam_max + passo, passo)
    custos_anuais = []
    for diam in faixa_diametros:
        perdas = calcular_perda_carga(kwargs["vazao"], diam, kwargs["comp_tub"], kwargs["rug_tub"], kwargs["k_total_acessorios"], kwargs["fluido_selecionado"])
        h_man_total_calc = kwargs["h_geometrica"] + perdas["principal"] + perdas["localizada"]
        resultados_calc = calcular_analise_energetica(kwargs["vazao"], h_man_total_calc, kwargs["rend_bomba"], kwargs["rend_motor"], kwargs["horas_por_dia"], kwargs["tarifa_energia"], kwargs["fluido_selecionado"])
        custos_anuais.append(resultados_calc['custo_anual'])
    chart_data = pd.DataFrame({'Diâmetro da Tubulação (mm)': faixa_diametros, 'Custo Anual de Energia (R$)': custos_anuais})
    return chart_data

def gerar_sugestoes(eficiencia_bomba, eficiencia_motor, custo_anual):
    sugestoes = []
    if eficiencia_bomba < 0.6: sugestoes.append("Eficiência da bomba abaixo de 60%. Considere a substituição por um modelo mais moderno.")
    if eficiencia_motor < 0.85: sugestoes.append("Eficiência do motor abaixo de 85%. Motores de alto rendimento (IR3+) podem gerar grande economia.")
    if custo_anual > 5000: sugestoes.append("Se a vazão for variável, um inversor de frequência pode reduzir drasticamente o consumo.")
    sugestoes.append("Realize manutenções preventivas, verifique vazamentos e o estado dos componentes da bomba.")
    return sugestoes

# --- Função de Geração de PDF (MODIFICADA) ---
class PDF(FPDF):
    def header(self): self.set_font('Arial', 'B', 12); self.cell(0, 10, 'Relatório de Análise Energética de Bombeamento', 0, 1, 'C'); self.ln(5)
    def footer(self): self.set_y(-15); self.set_font('Arial', 'I', 8); self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
    def chapter_title(self, title): self.set_font('Arial', 'B', 11); self.cell(0, 10, title, 0, 1, 'L'); self.ln(2)
    def chapter_body(self, data):
        self.set_font('Arial', '', 10)
        for key, value in data.items(): self.cell(80, 7, f"  {key}:", 0, 0); self.cell(0, 7, str(value), 0, 1)
        self.ln(5)

def criar_relatorio_pdf(inputs, resultados, sugestoes, chart_data=None):
    pdf = PDF()
    pdf.add_page()
    pdf.chapter_title("Parâmetros de Entrada"); pdf.chapter_body(inputs)
    pdf.chapter_title("Resultados da Análise"); pdf.chapter_body(resultados)
    pdf.chapter_title("Sugestões de Melhoria"); pdf.set_font('Arial', '', 10)
    for sugestao in sugestoes: pdf.multi_cell(0, 5, f"- {sugestao}"); pdf.ln(2)

    # Lógica para adicionar o gráfico ao PDF
    if chart_data is not None and not chart_data.empty:
        pdf.add_page(orientation='L') # Paisagem para o gráfico
        pdf.chapter_title("Gráfico de Análise de Custo por Diâmetro")

        # Cria o gráfico usando Matplotlib
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(chart_data['Diâmetro da Tubulação (mm)'], chart_data['Custo Anual de Energia (R$)'], color='skyblue')
        ax.set_xlabel('Diâmetro da Tubulação (mm)')
        ax.set_ylabel('Custo Anual de Energia (R$)')
        ax.set_title('Custo Anual vs. Diâmetro da Tubulação')
        ax.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()

        # Salva o gráfico em um buffer de memória
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        
        # Insere a imagem do buffer no PDF
        pdf.image(buf, x=10, y=35, w=277) # Largura de 277mm para preencher a página paisagem
        plt.close(fig)

    return bytes(pdf.output())

# --- Interface do Aplicativo Streamlit ---
st.set_page_config(layout="wide", page_title="Análise de Sistemas de Bombeamento")
st.title("💧 Análise Avançada de Sistemas de Bombeamento")

# --- Barra Lateral para Entradas ---
with st.sidebar:
    st.header("⚙️ Parâmetros do Sistema")
    fluido_selecionado = st.selectbox("Selecione o Fluido", list(FLUIDOS.keys()))
    vazao = st.number_input("Vazão Desejada (m³/h)", 0.1, value=50.0, step=1.0)
    tipo_calculo_h = st.radio("Cálculo da Altura Manométrica", ["Informar manualmente", "Calcular a partir da tubulação"], key="tipo_h")
    
    # Inicialização de variáveis
    h_man_manual, diam_tub, h_geometrica, comp_tub, rug_tub, k_total_acessorios = 0, 100.0, 15.0, 100.0, 0.15, 5.0
    diam_min_graf, diam_max_graf, passo_graf = 50, 300, 25

    if tipo_calculo_h == "Informar manualmente":
        h_man_manual = st.number_input("Altura Manométrica Total (m)", 1.0, value=30.0, step=0.5)
    else:
        with st.expander("Dados para Cálculo da Perda de Carga", expanded=True):
            h_geometrica = st.number_input("Altura Geométrica (m)", 0.0, value=15.0)
            comp_tub = st.number_input("Comprimento da Tubulação (m)", 1.0, value=100.0)
            diam_tub = st.number_input("Diâmetro Interno da Tubulação (mm)", 1.0, value=100.0)
            rug_tub = st.number_input("Rugosidade do Material (mm)", 0.001, value=0.15, format="%.3f")
            k_total_acessorios = st.number_input("Soma dos Coeficientes de Perda (K)", 0.0, value=5.0)
            
            st.markdown("---")
            st.subheader("Faixa de Análise do Gráfico")
            c1, c2, c3 = st.columns(3)
            diam_min_graf = c1.number_input("Ø Mínimo (mm)", 10, value=50, step=5)
            diam_max_graf = c2.number_input("Ø Máximo (mm)", 50, value=300, step=5)
            passo_graf = c3.number_input("Passo (mm)", 1, value=25, step=1)
            
    st.header("🔧 Eficiência dos Equipamentos"); rend_bomba = st.slider("Eficiência da Bomba (%)", 10, 100, 70); rend_motor = st.slider("Eficiência do Motor (%)", 50, 100, 90)
    st.header("🗓️ Operação e Custo"); horas_por_dia = st.number_input("Horas por Dia", 1.0, 24.0, 8.0, 0.5); tarifa_energia = st.number_input("Custo da Energia (R$/kWh)", 0.10, 2.00, 0.75, 0.01, format="%.2f")

# --- Lógica Principal e Exibição de Resultados (LAYOUT MODIFICADO) ---
st.header("📊 Resultados da Análise")
velocidade_fluido, chart_data = 0, pd.DataFrame()
h_man_total = h_man_manual if tipo_calculo_h == "Informar manualmente" else h_geometrica

if tipo_calculo_h == "Calcular a partir da tubulação":
    perdas_dict = calcular_perda_carga(vazao, diam_tub, comp_tub, rug_tub, k_total_acessorios, fluido_selecionado)
    h_man_total += perdas_dict["principal"] + perdas_dict["localizada"]
    velocidade_fluido = perdas_dict["velocidade"]
    st.subheader("Parâmetros Hidráulicos Calculados"); c1, c2, c3, c4 = st.columns(4)
    c1.metric("Altura Total", f"{h_man_total:.2f} m", "Calculado"); c2.metric("Perda Principal", f"{perdas_dict['principal']:.2f} m"); c3.metric("Perda Localizada", f"{perdas_dict['localizada']:.2f} m"); c4.metric("Velocidade", f"{velocidade_fluido:.2f} m/s")

resultados = calcular_analise_energetica(vazao, h_man_total, rend_bomba/100, rend_motor/100, horas_por_dia, tarifa_energia, fluido_selecionado)
st.subheader("Potências e Custos para o Diâmetro Informado"); c1, c2, c3 = st.columns(3)
c1.metric("Potência Elétrica", f"{resultados['potencia_eletrica_kW']:.2f} kW"); c2.metric("Custo Mensal", f"R$ {(resultados['consumo_mensal_kWh'] * tarifa_energia):.2f}"); c3.metric("Custo Anual", f"R$ {resultados['custo_anual']:.2f}")

if tipo_calculo_h == "Calcular a partir da tubulação":
    st.subheader("Gráfico: Custo Anual de Energia vs. Diâmetro da Tubulação")
    params_grafico = {"diam_min": diam_min_graf, "diam_max": diam_max_graf, "passo": passo_graf, "vazao": vazao, "h_geometrica": h_geometrica, "comp_tub": comp_tub, "rug_tub": rug_tub, "k_total_acessorios": k_total_acessorios, "rend_bomba": rend_bomba/100, "rend_motor": rend_motor/100, "horas_por_dia": horas_por_dia, "tarifa_energia": tarifa_energia, "fluido_selecionado": fluido_selecionado}
    chart_data = gerar_grafico_diametro_custo(**params_grafico)
    if not chart_data.empty: st.bar_chart(chart_data.set_index('Diâmetro da Tubulação (mm)'))
    else: st.warning("A faixa de diâmetros informada é inválida.")

st.divider()

# --- Seção de Sugestões e Relatório (NOVO LAYOUT) ---
sugestoes_col, relatorio_col = st.columns(2)
with sugestoes_col:
    st.header("💡 Sugestões para Economia")
    sugestoes = gerar_sugestoes(rend_bomba/100, rend_motor/100, resultados['custo_anual'])
    for sugestao in sugestoes: st.info(sugestao)
with relatorio_col:
    st.header("📄 Gerar Relatório")
    st.markdown("Clique no botão abaixo para gerar um relatório completo em PDF com todos os parâmetros, resultados e o gráfico de análise de diâmetro.")
    
    # Coleta de dados para o relatório
    inputs_relatorio = {"Fluido": fluido_selecionado, "Vazão": f"{vazao} m³/h", "Altura Manométrica Total": f"{h_man_total:.2f} m", "Eficiência da Bomba": f"{rend_bomba}%", "Eficiência do Motor": f"{rend_motor}%", "Horas/Dia": f"{horas_por_dia} h", "Tarifa": f"R$ {tarifa_energia:.2f}/kWh"}
    if velocidade_fluido > 0: inputs_relatorio["Velocidade do Fluido"] = f"{velocidade_fluido:.2f} m/s"
    resultados_relatorio = {"Potência Elétrica": f"{resultados['potencia_eletrica_kW']:.2f} kW", "Custo Mensal": f"R$ {(resultados['consumo_mensal_kWh'] * tarifa_energia):.2f}", "Custo Anual": f"R$ {resultados['custo_anual']:.2f}"}
    
    # Gera o PDF em memória (passando os dados do gráfico)
    pdf_bytes = criar_relatorio_pdf(inputs_relatorio, resultados_relatorio, sugestoes, chart_data)
    st.download_button(label="Download do Relatório em PDF", data=pdf_bytes, file_name=f"Relatorio_Bombeamento_{time.strftime('%Y%m%d-%H%M%S')}.pdf", mime="application/octet-stream")
