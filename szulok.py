import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Oldal konfiguráció
st.set_page_config(page_title="Komplex UK Nyugdíj & Kifizetés Tervező", layout="wide", page_icon="🇬🇧")

st.title("🇬🇧 UK Nyugdíj, Örökség & Dinamikus Kifizetés Szimulátor")
st.write("Modellezd a vagyon felépítését, majd tervezd meg a kifizetéseket (házvásárlás, havi járadék) 57 éves kor felett.")

# Felhasználói Profil kiválasztása
st.sidebar.markdown("## ⚙️ Felhasználói Profil")
user_mode = st.sidebar.radio(
    "Válaszd ki a státuszodat:",
    ("Sima alkalmazott (Szülők mintája)", "Céges igazgató / Vállalkozó")
)

st.sidebar.markdown("---")
st.sidebar.header("📌 Életkor és Időtáv")
current_age = st.sidebar.slider("Jelenlegi életkor", 18, 90, 43 if user_mode == "Céges igazgató / Vállalkozó" else 66)
working_years = st.sidebar.slider("Hány évig működik még a munka / a cég?", 0, 60, 14 if user_mode == "Céges igazgató / Vállalkozó" else 2)
target_age = 100 

# Kifizetési fázis korlát meghatározása (Minimum 57 év a brit szabályok szerint)
pension_access_age = max(57, current_age)

st.sidebar.markdown("---")
st.sidebar.header("💰 57 év feletti Kifizetési Beállítások")

# 1. Egyszeri nagy kivétel (pl. házvásárlás)
enable_lump_sum = st.sidebar.checkbox("Egyszeri nagyobb összeg kivétele (pl. Házra)", value=True if user_mode == "Sima alkalmazott (Szülők mintája)" else False)
if enable_lump_sum:
    lump_sum_age = st.sidebar.slider("Hány évesen történjen az egyszeri kivétel?", int(pension_access_age), 95, 68 if user_mode == "Sima alkalmazott (Szülők mintája)" else 60)
    lump_sum_amount = st.sidebar.number_input("Kivenni kívánt egyszeri összeg (£)", value=24000 if user_mode == "Sima alkalmazott (Szülők mintája)" else 50000)
else:
    lump_sum_age = 999
    lump_sum_amount = 0

# 2. Rendszeres havi kifizetés (járadék)
enable_monthly_drawdown = st.sidebar.checkbox("Rendszeres havi járadékfizetés indítása", value=True if user_mode == "Sima alkalmazott (Szülők mintája)" else False)
if enable_monthly_drawdown:
    drawdown_start_age = st.sidebar.slider("Hány éves kortól induljon a havi járadék?", int(pension_access_age), 95, 75 if user_mode == "Sima alkalmazott (Szülők mintája)" else 57)
    monthly_drawdown_payout = st.sidebar.number_input("Havi rendszeres kifizetés nagysága (£)", value=747 if user_mode == "Sima alkalmazott (Szülők mintája)" else 1500)
else:
    drawdown_start_age = 999
    monthly_drawdown_payout = 0

# VÁLTOZÓK INICIALIZÁLÁSA MÓDOK SZERINT
st.sidebar.markdown("---")
monthly_wpp = 0
sipp_monthly_gross = 0
monthly_director_corporate = 0
initial_balance = 0

if user_mode == "Sima alkalmazott (Szülők mintája)":
    st.sidebar.header("🏢 Aviva Workplace Pension (WPP)")
    initial_balance = st.sidebar.number_input("Jelenlegi Aviva egyenleg (£)", value=0)
    gross_salary = st.sidebar.number_input("Havi bruttó fizetés (£)", value=950)
    ee_pct = st.sidebar.slider("Saját hozzájárulás (%)", 0, 20, 4)
    get_er_pct = st.sidebar.slider("Munkáltatói hozzájárulás (%)", 0, 20, 4)
    
    st.sidebar.header("🏹 Vanguard SIPP megtakarítás")
    net_monthly_input = st.sidebar.number_input("Havi tiszta megtakarítás a zsebből (£)", value=80)
    
    monthly_wpp = gross_salary * ((ee_pct + get_er_pct) / 100)
    sipp_monthly_gross = net_monthly_input * 1.25
    monthly_user_out_of_pocket = (gross_salary * (ee_pct / 100)) + net_monthly_input

else:
    st.sidebar.header("🏢 Igazgatói alapbeállítások")
    initial_balance = st.sidebar.number_input("Jelenlegi nyugdíj / induló egyenleg (£)", value=11000)
    gross_salary = st.sidebar.number_input("Hivatalos havi igazgatói bér (£)", value=1047.50)
    
    st.sidebar.header("💼 Céges Nyugdíj Befizetés")
    monthly_director_corporate = st.sidebar.number_input("Havi extra CÉGES nyugdíjbefizetés (£)", value=5000, max_value=5000)
    
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
ins_months = int((target_age - current_age) * 12)
working_months = working_years * 12

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
max_tax_free_drawdown = 747.50

# Kiszámoljuk pontosan azt az egyetlen hónapindexet, amikor a nagy tőkekivonás történik
target_lump_sum_month = int((lump_sum_age - current_age) * 12) if enable_lump_sum else -1

# Fő havi életút szimuláció
for m in range(ins_months + 1):
    age_at_m = current_age + (m / 12)
    ins_ages.append(age_at_m)
    ins_payout_nominal.append(30000)
    
    real_payout = 30000 / ((1 + (inflation_rate/100)) ** (m / 12))
    ins_payout_real.append(real_payout)
    
    ins_total_paid.append(running_insurance_paid)
    
    # DINAMIKUS KIFIZETÉSI MOTOR
    if m > 0 and age_at_m >= 57:
        # A: Egyszeri nagy kivétel
        if enable_lump_sum and (m == target_lump_sum_month):
            if sim_isa_balance >= lump_sum_amount:
                sim_isa_balance -= lump_sum_amount
            else:
                rem_amount = lump_sum_amount - sim_isa_balance
                sim_isa_balance = 0
                sim_sipp_balance = max(0.0, sim_sipp_balance - rem_amount)

        # B: Rendszeres havi járadék
        if enable_monthly_drawdown and (age_at_m >= drawdown_start_age):
            if sim_isa_balance >= monthly_drawdown_payout:
                sim_isa_balance -= monthly_drawdown_payout
            else:
                rem_drawdown = monthly_drawdown_payout - sim_isa_balance
                sim_isa_balance = 0
                sim_sipp_balance = max(0.0, sim_sipp_balance - rem_drawdown)

    # Elmentjük az aktuális kombinált vagyont
    current_combined_wealth = sim_sipp_balance + sim_isa_balance
    hybrid_wealth_trajectory.append(current_combined_wealth)
    
    if exact_cross_age is None and running_insurance_paid >= real_payout:
        exact_cross_age = age_at_m
        cross_month_index = m
        
    if gold_cross_age is None and m > 0 and current_combined_wealth >= real_payout:
        gold_cross_age = age_at_m
        
    if m > 0:
        running_insurance_paid += 80 
        
        # --- ALAPVETŐ VAGYONÉPÍTÉSI LOGIKA ---
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
            
        # --- MELLÉKFÁZIS: PONTOSAN 75 ÉVES KORBAN ---
        elif age_at_m > 75 and not lump_sum_moved:
            lump_sum_25 = sim_sipp_balance * 0.25
            sim_sipp_balance = sim_sipp_balance * 0.75
            sim_isa_balance += lump_sum_25 
            lump_sum_moved = True
            
            sim_sipp_balance = sim_sipp_balance * (1 + monthly_rate)
            sim_isa_balance = sim_isa_balance * (1 + monthly_rate) + net_monthly_input
            
        # --- 2. FÁZIS: 75 ÉV FELETT ---
        else:
            sim_sipp_balance = sim_sipp_balance * (1 + monthly_rate)
            sim_isa_balance = sim_isa_balance * (1 + monthly_rate) + net_monthly_input

if exact_cross_age is None:
    exact_cross_age = 100

total_months_to_cross = int((exact_cross_age - current_age) * 12)
cross_years = total_months_to_cross // 12
cross_months = total_months_to_cross % 12

# Felső információs sávok
if user_mode == "Céges igazgató / Vállalkozó":
    total_corporate_pension_paid = monthly_director_corporate * min(working_months, max(0, int((75-current_age)*12)))
    corporation_tax_saved = total_corporate_pension_paid * 0.25
    col_dir1, col_dir2 = st.columns(2)
    col_dir1.success(f"💰 **A céged által megspórolt Társasági adó (Corporation Tax):** £{corporation_tax_saved:,.2f}")
    col_dir2.info(f"📈 **Összes céges tőke adómentesen kimentve a nyugdíjba:** £{total_corporate_pension_paid:,.2f}")
else:
    col1, col2 = st.columns(2)
    col1.error(f"⚠️ **Valódi (vásárlóértékű) Biztosítási Veszteségpont:** {exact_cross_age:.1f} évesen (pontosan {cross_years} év és {cross_months} hónap múlva) több tagdíjat fizetnek be, mint a biztosítás ér.")
    hybrid_at_cross = hybrid_wealth_trajectory[cross_month_index]
    col2.success(f"💰 **Ugyanekkor az Arany Stratégia együttes értéke:** £{hybrid_at_cross:,.2f} (Mai reálértéken!)")

st.markdown("---")

# 🔒 BOMBABIZTOS, ÚJ DATAFRAME LÉTREHOZÁS KAPCSOS ZÁRÓJELEK NÉLKÜL!
df_szulok = pd.DataFrame()
df_szulok["Életkor"] = ins_ages
df_szulok["Biztosítónak befizetett tagdíj (£80/hó)"] = ins_total_paid
df_szulok["Biztosítási kifizetés (Fix £30,000 névleges)"] = ins_payout_nominal
df_szulok["A £30,000 VALÓDI vásárlóértéke (Zöld vonal)"] = ins_payout_real
df_szulok["ADÓOPTIMALIZÁLT HIBRID STRATÉGIA (Arany vonal)"] = hybrid_wealth_trajectory

# Grafikon kirajzolása
fig = go.Figure()
