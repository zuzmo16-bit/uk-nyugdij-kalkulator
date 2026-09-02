import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Oldal konfiguráció
st.set_page_config(page_title="Univerzális UK Örökség & Nyugdíj Tervező", layout="wide", page_icon="🇬🇧")

st.title("🇬🇧 Komplett UK Nyugdíj, Örökség & Vállalkozói Adóoptimalizáló")
st.write("Ez a kombinált szimulátor alkalmas a magánszemélyek (alkalmazottak) és a saját Limited Company-val rendelkező igazgatók stratégiáinak modellezésére is.")

# 🎛️ ÚJ: STRATÉGIA KIVÁLASZTÁSA A TETEJÉN
st.sidebar.markdown("## ⚙️ Felhasználói Profil")
user_mode = st.sidebar.radio(
    "Válaszd ki a státuszodat:",
    ("Sima alkalmazott (Szülők mintája)", "Céges igazgató / Vállalkozó")
)

st.sidebar.markdown("---")
st.sidebar.header("📌 Életkor és Időtáv")
current_age = st.sidebar.slider("Jelenlegi életkor", 18, 90, 43 if user_mode == "Céges igazgató / Vállalkozó" else 66)
working_years = st.sidebar.slider("Hány évig működik még a munka / a cég?", 0, 60, 14 if user_mode == "Céges igazgató / Vállalkozó" else 2)
target_age = 100 # Fixen 100 éves korig követjük az életutat az örökség és élethossz miatt

# VÁLTOZÓK INICIALIZÁLÁSA MÓDOK SZERINT
monthly_wpp = 0
sipp_monthly_gross = 0
monthly_director_corporate = 0
initial_balance = 0

if user_mode == "Sima alkalmazott (Szülők mintája)":
    st.sidebar.header("🏢 Aviva Workplace Pension (WPP)")
    initial_balance = st.sidebar.number_input("Jelenlegi Aviva egyenleg (£)", value=0)
    gross_salary = st.sidebar.number_input("Havi bruttó fizetés (£)", value=950)
    ee_pct = st.sidebar.slider("Saját hozzájárulás (%)", 0, 20, 4)
    er_pct = st.sidebar.slider("Munkáltatói hozzájárulás (%)", 0, 20, 4)
    
    st.sidebar.header("🏹 Vanguard SIPP megtakarítás")
    net_monthly_input = st.sidebar.number_input("Havi tiszta megtakarítás a zsebből (£)", value=80)
    
    monthly_wpp = gross_salary * ((ee_pct + er_pct) / 100)
    sipp_monthly_gross = net_monthly_input * 1.25
    monthly_user_out_of_pocket = (gross_salary * (ee_pct / 100)) + net_monthly_input

else:
    st.sidebar.header("🏢 Igazgatói alapbeállítások")
    initial_balance = st.sidebar.number_input("Jelenlegi nyugdíj / induló egyenleg (£)", value=11000)
    gross_salary = st.sidebar.number_input("Hivatalos havi igazgatói bér (£)", value=1047.50, help="Az évi £12,570-os adómentes limit pontosan havi £1,047.50.")
    
    st.sidebar.header("💼 Céges Nyugdíj Befizetés (Director's Contribution)")
    monthly_director_corporate = st.sidebar.number_input("Havi extra CÉGES nyugdíjbefizetés (£)", value=5000, max_value=5000, help="Az évi max £60k kerethez írj be havi £5000-et. Ez 100%-ban leírható a cég profitjából!")
    
    st.sidebar.header("🏹 Vanguard Magán Megtakarítás (ISA)")
    net_monthly_input = st.sidebar.number_input("Havi tiszta MAGÁN megtakarítás a zsebedből (£)", value=0)
    
    monthly_user_out_of_pocket = net_monthly_input

st.sidebar.header("📈 Piaci és Inflációs Beállítások")
nominal_return = st.sidebar.slider("Várható éves piaci hozam (%)", 1.0, 12.0, 7.5)
inflation_rate = st.sidebar.slider("Várható éves infláció (%)", 0.0, 8.0, 2.5)

# Matematikai reálhozam számítás
annual_real_return = ((1 + (nominal_return / 100)) / (1 + (inflation_rate / 100))) - 1
monthly_rate = (1 + annual_real_return) ** (1/12) - 1

# Alapértékek előkészítése
ins_months = (target_age - current_age) * 12
working_months = working_years * 12
max_tax_free_drawdown = 747.50

# Idősoros tömbök a szimulációhoz
ins_ages = []
ins_payout_nominal = []
ins_payout_real = []
ins_total_paid = []
hybrid_wealth_trajectory = []

running_insurance_paid = 0
sim_sipp_balance = initial_balance
sim_isa_balance = 0

exact_cross_age = None
gold_cross_age = None
cross_month_index = ins_months
lump_sum_moved = False
months_to_75 = max(0, int((75 - current_age) * 12))

# Havi szimuláció futtatása a háttérben
for m in range(ins_months + 1):
    age_at_m = current_age + (m / 12)
    ins_ages.append(age_at_m)
    ins_payout_nominal.append(30000)
    
    real_payout = 30000 / ((1 + (inflation_rate/100)) ** (m / 12))
    ins_payout_real.append(real_payout)
    
    ins_total_paid.append(running_insurance_paid)
    
    current_combined_wealth = sim_sipp_balance + sim_isa_balance
    hybrid_wealth_trajectory.append(current_combined_wealth)
    
    if exact_cross_age is None and running_insurance_paid >= real_payout:
        exact_cross_age = age_at_m
        cross_month_index = m
        
    if gold_cross_age is None and m > 0 and current_combined_wealth >= real_payout:
        gold_cross_age = age_at_m
        
    if m > 0:
        running_insurance_paid += 80 
        
        # --- 1. FÁZIS: 75 ÉVES KORIG ---
        if age_at_m <= 75:
            if m <= working_months:
                if user_mode == "Sima alkalmazott (Szülők mintája)":
                    sim_sipp_balance = sim_sipp_balance * (1 + monthly_rate) + (monthly_wpp + sipp_monthly_gross)
                else:
                    sim_sipp_balance = sim_sipp_balance * (1 + monthly_rate) + monthly_director_corporate
            else:
                if user_mode == "Sima alkalmazott (Szülők mintája)":
                    sim_sipp_balance = sim_sipp_balance * (1 + monthly_rate) + sipp_monthly_gross
                else:
                    sim_sipp_balance = sim_sipp_balance * (1 + monthly_rate)
            sim_isa_balance = 0
            
        # --- MELLÉKFÁZIS: PONTOSAN 75 ÉVES KORBAN ---
        elif age_at_m > 75 and not lump_sum_moved:
            lump_sum_25 = sim_sipp_balance * 0.25
            sim_sipp_balance = sim_sipp_balance * 0.75
            sim_isa_balance = lump_sum_25 
            lump_sum_moved = True
            
            sim_sipp_balance = sim_sipp_balance * (1 + monthly_rate)
            if sim_sipp_balance >= max_tax_free_drawdown:
                sim_sipp_balance -= max_tax_free_drawdown
                actual_drawdown = max_tax_free_drawdown
            else:
                actual_drawdown = sim_sipp_balance
                sim_sipp_balance = 0
            sim_isa_balance = sim_isa_balance * (1 + monthly_rate) + net_monthly_input + actual_drawdown
            
        # --- 2. FÁZIS: 75 ÉV FELETT ---
        else:
            sim_sipp_balance = sim_sipp_balance * (1 + monthly_rate)
            if sim_sipp_balance >= max_tax_free_drawdown:
                sim_sipp_balance -= max_tax_free_drawdown
                actual_drawdown = max_tax_free_drawdown
            else:
                actual_drawdown = sim_sipp_balance
                sim_sipp_balance = 0
                
            sim_isa_balance = sim_isa_balance * (1 + monthly_rate) + net_monthly_input + actual_drawdown

if exact_cross_age is None:
    exact_cross_age = 100

total_months_to_cross = int((exact_cross_age - current_age) * 12)
cross_years = total_months_to_cross // 12
cross_months = total_months_to_cross % 12

# EXTRA KPI KIJELZŐK CÉGVEZETŐKNEK
if user_mode == "Céges igazgató / Vállalkozó":
    total_corporate_pension_paid = monthly_director_corporate * working_months
    corporation_tax_saved = total_corporate_pension_paid * 0.25
    
    col_dir1, col_dir2 = st.columns(2)
    col_dir1.success(f"💰 **A céged által megspórolt Társasági adó (Corporation Tax):** £{corporation_tax_saved:,.2f}")
    col_dir2.info(f"📈 **Összes céges pénz, amit adómentesen kimentettél:** £{total_corporate_pension_paid:,.2f}")
else:
    col1, col2 = st.columns(2)
    col1.error(f"⚠️ **Valódi (vásárlóértékű) Veszteségpont:** {exact_cross_age:.1f} évesen (pontosan {cross_years} év és {cross_months} hónap múlva) több pénzt fizetnek be zsebből, mint a biztosítás!")
    hybrid_at_cross = hybrid_wealth_trajectory[cross_month_index]
    col2.success(f"💰 **Ugyanekkor a Hibrid (SIPP+ISA) vagyon összege:** £{hybrid_at_cross:,.2f} (Mai reálértéken!)")

st.markdown("---")

df_szulok = pd.DataFrame({
    "Életkor": ins_ages,
    "Biztosítónak befizetett tagdíj (£80/hó)": ins_total_paid,
    "Biztosítási kifizetés (Fix £30,000 névleges)": ins_payout_nominal,
    "A £30,000 VALÓDI vásárlóértéke (Zöld vonal)": ins_payout_real,
    "ADÓOPTIMALIZÁLT HIBRID STRATÉGIA (Arany vonal)": hybrid_wealth_trajectory
})

# Grafikon felépítése
fig = go.Figure()
fig.add_trace(go.Scatter(x=df_szulok["Életkor"], y=df_szulok["Biztosítónak befizetett tagdíj (£80/hó)"], mode='lines', name='Biztosítónak befizetett pénz (Piros)', line=dict(color='red', width=2.5)))
fig.add_trace(go.Scatter(x=df_szulok["Életkor"], y=df_szulok["Biztosítási kifizetés (Fix £30,000 névleges)"], mode='lines', name='Garantált kifizetés (Sárga - Fix £30k)', line=dict(color='yellow', dash='dash')))
fig.add_trace(go.Scatter(x=df_szulok["Életkor"], y=df_szulok["A £30,000 VALÓDI vásárlóértéke (Zöld vonal)"], mode='lines', name='A £30k igazi értéke az infláció után (Zöld)', line=dict(color='#00CC96', width=2.5)))
fig.add_trace(go.Scatter(x=df_szulok["Életkor"], y=df_szulok["ADÓOPTIMALIZÁLT HIBRID STRATÉGIA (Arany vonal)"], mode='lines', name='Arany stratégia egyenlege (Mai reálérték)', line=dict(color='#FFD700', width=4)))

# Mérföldkő vonalak
fig.add_vline(x=exact_cross_age, line_dash="dot", line_color="orange", annotation_text=f"Biztosítási veszteségpont ({exact_cross_age:.1f} év)")
if current_age < 75:
    fig.add_vline(x=75, line_dash="dash", line_color="white", annotation_text="75 év: 25% kifizetés + Max áttöltés indítása")
if working_years > 0:
    fig.add_vline(x=current_age + working_years, line_dash="dash", line_color="cyan", annotation_text="Aktív fázis / Befizetések vége")
if gold_cross_age is not None:
    fig.add_vline(x=gold_cross_age, line_dash="dashdot", line_color="#FFD700", annotation_text=f"Tőzsde lekörözi a biztosítást ({gold_cross_age:.1f} év)")

fig.update_layout(
    title="UK ADÓOPTIMALIZÁLT ÉLETÚT ÉS VAGYONSTRATÉGIA SZIMULÁTOR",
    xaxis_title="Életkor (év)",
    yaxis_title="Összeg (£)",
    template="plotly_dark",
    height=800,
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
)
st.plotly_chart(fig, use_container_width=True)

