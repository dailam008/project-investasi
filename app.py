import streamlit as st
import pandas as pd
import gspread
import altair as alt
from datetime import datetime

# ========================
# PAGE CONFIG
# ========================
st.set_page_config(
    page_title="Dashboard Investasi",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ========================
# CSS
# ========================
try:
    with open("style.css", "r", encoding="utf-8") as f:
        st.markdown(f"<style>\n{f.read()}\n</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass



# ========================
# HELPERS
# ========================
def fmt(n: float) -> str:
    if n >= 1_000_000_000:
        return f"Rp{n/1_000_000_000:.2f}M"
    if n >= 1_000_000:
        return f"Rp{n/1_000_000:.2f}jt"
    return f"Rp{n:,.0f}"

def fmt_full(n: float) -> str:
    return f"Rp{n:,.0f}"

def pct_badge(val: float) -> str:
    if val >= 0:
        return f'<span class="badge-up">▲ +{val:.2f}%</span>'
    return f'<span class="badge-dn">▼ {val:.2f}%</span>'


# ========================
# KONFIGURASI
# ========================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/152F-tMvERYDC18XRKwfY2JWhIP1i0K5Z7pWmgiKazp0"
TARGET_INVESTASI = 100000000  # Target 100 Juta

import json

# ========================
# LOAD DATA
# ========================
@st.cache_data(ttl=300)
def load_data():
    try:
        # Coba menggunakan Streamlit Secrets (untuk deployment)
        creds_dict = json.loads(st.secrets["GCP_CREDENTIALS_JSON"])
        client = gspread.service_account_from_dict(creds_dict)
    except Exception:
        # Fallback ke file lokal jika rahasia tidak ditemukan
        client = gspread.service_account(filename="credentials.json")
        
    sheet  = client.open_by_url(SPREADSHEET_URL).sheet1
    df = pd.DataFrame(sheet.get_all_records())
    df.columns          = df.columns.str.strip()
    df["Jenis"]         = df["Jenis"].str.strip()
    
    # Fungsi parsing tanggal yang lebih fleksibel
    def parse_tanggal(val):
        if not val: return pd.NaT
        # Coba format default (ISO)
        dt = pd.to_datetime(val, errors='coerce')
        if pd.isna(dt):
            # Coba format DayFirst (Google Form)
            dt = pd.to_datetime(val, dayfirst=True, errors='coerce')
        return dt

    df["Tanggal"] = df["Tanggal"].apply(parse_tanggal)
    df["Nominal"] = pd.to_numeric(df["Nominal"], errors="coerce").fillna(0)
    df["Nilai Portofolio"] = pd.to_numeric(df["Nilai Portofolio"], errors="coerce").fillna(0)
    
    # ========================
    # LOGIKA KALKULASI DINAMIS
    # ========================
    df = df.sort_values("Tanggal")
    
    current_val = 0
    list_dynamic_val = []
    
    for i, row in df.iterrows():
        if row["Jenis"] == "Beli":
            current_val += row["Nominal"]
        elif row["Jenis"] == "Update" and row["Nilai Portofolio"] > 0:
            current_val = row["Nilai Portofolio"]
        
        list_dynamic_val.append(current_val)
        
    df["Nilai Portofolio"] = list_dynamic_val # Override dengan nilai dinamis
    return df

with st.spinner("Memuat data…"):
    try:
        df = load_data()
    except Exception as e:
        st.error(f"❌ Gagal memuat data: {e}")
        st.stop()


# ========================
# KALKULASI
# ========================
# Perhitungan KPI
total_modal      = df[df["Jenis"] == "Beli"]["Nominal"].sum()
df_beli          = df[df["Jenis"] == "Beli"].copy()
nilai_portofolio = df["Nilai Portofolio"].iloc[-1] if not df.empty else 0
profit           = nilai_portofolio - total_modal
growth           = (profit / total_modal * 100) if total_modal > 0 else 0

df_update = df[df["Jenis"] == "Update"].copy().sort_values("Tanggal").reset_index(drop=True)
df_update["Growth (%)"] = df_update["Nilai Portofolio"].pct_change() * 100

porto_valid = df[df["Nilai Portofolio"] > 0]
all_porto = porto_valid["Nilai Portofolio"] if not porto_valid.empty else pd.Series([nilai_portofolio])
max_porto = all_porto.max()
min_porto = all_porto.min()
avg_porto = all_porto.mean()

durasi_hari = (df["Tanggal"].max() - df["Tanggal"].min()).days
now_str     = datetime.now().strftime("%d %b %Y, %H:%M")

if len(df) >= 2:
    tren_label = "naik" if df["Nilai Portofolio"].iloc[-1] > df["Nilai Portofolio"].iloc[-2] else "turun"
    tren_icon  = "📈" if tren_label == "naik" else "📉"
else:
    tren_label = "stabil"
    tren_icon  = "➡️"


# ========================
# TOPBAR
# ========================
st.markdown(f"""
<div class="topbar">
  <div>
    <div class="topbar-title">💼 Dashboard Investasi</div>
    <div class="topbar-sub">Update: {now_str} &nbsp;·&nbsp; {len(df)} entri data</div>
  </div>
  <div class="live-pill"><div class="live-dot"></div>Live · Google Sheets</div>
</div>
""", unsafe_allow_html=True)

# --- PROGRESS BAR TARGET ---
target_progress = (nilai_portofolio / TARGET_INVESTASI) * 100 if TARGET_INVESTASI > 0 else 0
target_progress_clamped = min(target_progress, 100)

st.markdown(f"""
<div style="margin-bottom: 24px; padding: 16px 20px; background: #111827; border: 1px solid #1e293b; border-radius: 14px;">
    <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 600; color: #94a3b8; margin-bottom: 8px;">
        <span>🎯 Target Investasi: <span style="color:#f1f5f9">{fmt(TARGET_INVESTASI)}</span></span>
        <span style="color:#60a5fa">{target_progress:.1f}%</span>
    </div>
    <div style="width: 100%; background-color: #1e293b; border-radius: 8px; height: 10px;">
        <div style="width: {target_progress_clamped}%; background: linear-gradient(90deg, #3b82f6, #60a5fa); height: 10px; border-radius: 8px; transition: width 1s ease-in-out;"></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ========================
# TOMBOL AKSI
# ========================
c1, c2, _ = st.columns([1.5, 1.5, 5])
with c1:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with c2:
    st.link_button("📝 Input Data Baru", "https://docs.google.com/forms/d/e/1FAIpQLScwfJXsqGB1g5gLAWv9W3bGpl2z2n2jUywWrf7WpgN5FhB3Zg/viewform", use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# ========================
# KPI CARDS
# ========================
c1, c2, c3, c4 = st.columns(4)

profit_color = "#10b981" if profit >= 0 else "#ef4444"
growth_color = "#10b981" if growth >= 0 else "#ef4444"

with c1:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-accent-top" style="background:linear-gradient(90deg,#3b82f6,#60a5fa)"></div>
      <div class="kpi-label">Nilai Portofolio</div>
      <div class="kpi-value">{fmt(nilai_portofolio)}</div>
      {pct_badge(growth)}
      <div class="kpi-sub">modal awal: {fmt(total_modal)}</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-accent-top" style="background:linear-gradient(90deg,#8b5cf6,#a78bfa)"></div>
      <div class="kpi-label">Total Modal</div>
      <div class="kpi-value">{fmt(total_modal)}</div>
      <div class="kpi-sub">{len(df_beli)} kali transaksi beli</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-accent-top" style="background:linear-gradient(90deg,{profit_color},{profit_color}88)"></div>
      <div class="kpi-label">Profit / Loss</div>
      <div class="kpi-value" style="color:{profit_color}">{"+" if profit>=0 else ""}{fmt(profit)}</div>
      <div class="kpi-sub">{'✅ untung bersih' if profit >= 0 else '❌ rugi bersih'}</div>
    </div>""", unsafe_allow_html=True)

with c4:
    benchmark_label = "outperform 🚀" if growth >= 7 else "underperform ⚠️"
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-accent-top" style="background:linear-gradient(90deg,#f59e0b,#fbbf24)"></div>
      <div class="kpi-label">Return (%)</div>
      <div class="kpi-value" style="color:{growth_color}">{growth:+.2f}%</div>
      <div class="kpi-sub">{benchmark_label} vs 7%</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)


# ========================
# INSIGHT BOXES
# ========================
st.markdown(f"""
<div class="insight-row">
  <div class="insight-box">
    <div class="insight-icon">🎯</div>
    <div>
      <div class="insight-title">Posisi Portofolio</div>
      <div class="insight-sub">{'Di atas' if profit>=0 else 'Di bawah'} modal sebesar <b style="color:#f1f5f9">{fmt(abs(profit))}</b> ({abs(growth):.1f}%)</div>
    </div>
  </div>
  <div class="insight-box">
    <div class="insight-icon">{tren_icon}</div>
    <div>
      <div class="insight-title">Tren Terakhir</div>
      <div class="insight-sub">Nilai porto sedang <b style="color:#f1f5f9">{tren_label}</b> berdasarkan update terbaru</div>
    </div>
  </div>
  <div class="insight-box">
    <div class="insight-icon">🏆</div>
    <div>
      <div class="insight-title">Peak Value</div>
      <div class="insight-sub">Tertinggi: <b style="color:#f1f5f9">{fmt(max_porto)}</b><br>Terendah: <b style="color:#f1f5f9">{fmt(min_porto)}</b></div>
    </div>
  </div>
  <div class="insight-box">
    <div class="insight-icon">📅</div>
    <div>
      <div class="insight-title">Durasi Investasi</div>
      <div class="insight-sub"><b style="color:#f1f5f9">{durasi_hari} hari</b> sejak transaksi pertama</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ========================
# CHART & FILTER WAKTU
# ========================
st.markdown('<div class="sec-title" style="margin-bottom: 8px; margin-top: 10px;">📅 Filter Rentang Waktu Grafik</div>', unsafe_allow_html=True)

col_f1, _ = st.columns([1, 4])
with col_f1:
    time_filter = st.selectbox(
        "Waktu", 
        ["Semua Waktu", "Tahun Ini", "Bulan Ini", "30 Hari Terakhir", "7 Hari Terakhir"], 
        label_visibility="collapsed"
    )

# Filter Dataframe for Charts
now_date = pd.Timestamp.now()
porto_valid_filtered = porto_valid.copy()

if time_filter == "Tahun Ini":
    porto_valid_filtered = porto_valid_filtered[porto_valid_filtered["Tanggal"].dt.year == now_date.year]
elif time_filter == "Bulan Ini":
    porto_valid_filtered = porto_valid_filtered[(porto_valid_filtered["Tanggal"].dt.year == now_date.year) & (porto_valid_filtered["Tanggal"].dt.month == now_date.month)]
elif time_filter == "30 Hari Terakhir":
    porto_valid_filtered = porto_valid_filtered[porto_valid_filtered["Tanggal"] >= (now_date - pd.Timedelta(days=30))]
elif time_filter == "7 Hari Terakhir":
    porto_valid_filtered = porto_valid_filtered[porto_valid_filtered["Tanggal"] >= (now_date - pd.Timedelta(days=7))]

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

col_a, col_b = st.columns([3, 2])

with col_a:
    st.markdown('<div class="sec-card">', unsafe_allow_html=True)
    st.markdown('<div class="sec-title">📈 Performa Nilai Portofolio</div>', unsafe_allow_html=True)

    if not porto_valid_filtered.empty:
        chart_df = porto_valid_filtered[["Tanggal", "Nilai Portofolio"]].copy()

        area = alt.Chart(chart_df).mark_area(
            line={"color": "#3b82f6", "strokeWidth": 2.5},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="rgba(59,130,246,0.3)", offset=0),
                    alt.GradientStop(color="rgba(59,130,246,0.0)", offset=1),
                ],
                x1=1, x2=1, y1=1, y2=0,
            ),
        ).encode(
            x=alt.X("Tanggal:T", axis=alt.Axis(
                labelColor="#64748b", gridColor="#1e293b",
                labelFontSize=10, title=None, format="%d %b"
            )),
            y=alt.Y("Nilai Portofolio:Q", axis=alt.Axis(
                labelColor="#64748b", gridColor="#1e293b",
                labelFontSize=10, title=None, format=","
            )),
            tooltip=[
                alt.Tooltip("Tanggal:T", title="Tanggal", format="%d %b %Y"),
                alt.Tooltip("Nilai Portofolio:Q", title="Nilai Porto", format=","),
            ]
        )
        points = alt.Chart(chart_df).mark_point(
            color="#60a5fa", size=70, filled=True
        ).encode(
            x="Tanggal:T",
            y="Nilai Portofolio:Q",
            tooltip=[
                alt.Tooltip("Tanggal:T", title="Tanggal", format="%d %b %Y"),
                alt.Tooltip("Nilai Portofolio:Q", title="Nilai Porto", format=","),
            ]
        )
        modal_rule = alt.Chart(pd.DataFrame({"y": [total_modal]})).mark_rule(
            color="#f59e0b", strokeDash=[4, 3], strokeWidth=1.5
        ).encode(y="y:Q")

        final_chart = (area + points + modal_rule).properties(
            height=220, background="transparent"
        ).configure_view(strokeWidth=0).configure_axis(domainColor="#1e293b")

        st.altair_chart(final_chart, use_container_width=True)

        st.markdown(f"""
        <div class="stat-row">
          <div class="stat-mini">
            <div class="stat-mini-val">{fmt(max_porto)}</div>
            <div class="stat-mini-lbl">Tertinggi</div>
          </div>
          <div class="stat-mini">
            <div class="stat-mini-val">{fmt(min_porto)}</div>
            <div class="stat-mini-lbl">Terendah</div>
          </div>
          <div class="stat-mini">
            <div class="stat-mini-val">{fmt(avg_porto)}</div>
            <div class="stat-mini-lbl">Rata-rata</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Belum ada data Update portofolio.")

    st.markdown("</div>", unsafe_allow_html=True)

with col_b:
    st.markdown('<div class="sec-card">', unsafe_allow_html=True)
    st.markdown('<div class="sec-title">📊 Growth per Update (%)</div>', unsafe_allow_html=True)

    # Gunakan porto_valid_filtered untuk filter waktu yang konsisten
    df_g = df_update.loc[df_update.index.isin(porto_valid_filtered.index)].dropna(subset=["Growth (%)"]).copy()
    if not df_g.empty:
        df_g["warna"] = df_g["Growth (%)"].apply(lambda v: "naik" if v >= 0 else "turun")

        bar = alt.Chart(df_g).mark_bar(
            cornerRadiusTopLeft=3, cornerRadiusTopRight=3
        ).encode(
            x=alt.X("Tanggal:T", axis=alt.Axis(
                labelColor="#64748b", gridColor="#1e293b",
                labelFontSize=10, title=None, format="%d %b"
            )),
            y=alt.Y("Growth (%):Q", axis=alt.Axis(
                labelColor="#64748b", gridColor="#1e293b",
                labelFontSize=10, title=None,
            )),
            color=alt.Color("warna:N", scale=alt.Scale(
                domain=["naik", "turun"], range=["#10b981", "#ef4444"]
            ), legend=None),
            tooltip=[
                alt.Tooltip("Tanggal:T", title="Tanggal", format="%d %b %Y"),
                alt.Tooltip("Growth (%):Q", title="Growth", format=".2f"),
            ]
        ).properties(
            height=220, background="transparent"
        ).configure_view(strokeWidth=0).configure_axis(domainColor="#1e293b")

        st.altair_chart(bar, use_container_width=True)

        pos_n = len(df_g[df_g["Growth (%)"] > 0])
        neg_n = len(df_g[df_g["Growth (%)"] < 0])
        avg_g = df_g["Growth (%)"].mean()

        st.markdown(f"""
        <div class="stat-row">
          <div class="stat-mini">
            <div class="stat-mini-val" style="color:#10b981">{pos_n}</div>
            <div class="stat-mini-lbl">Update Naik</div>
          </div>
          <div class="stat-mini">
            <div class="stat-mini-val" style="color:#ef4444">{neg_n}</div>
            <div class="stat-mini-lbl">Update Turun</div>
          </div>
          <div class="stat-mini">
            <div class="stat-mini-val">{avg_g:.2f}%</div>
            <div class="stat-mini-lbl">Rata-rata</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Butuh minimal 2 data Update untuk melihat growth.")

    st.markdown("</div>", unsafe_allow_html=True)


# ========================
# TABEL TRANSAKSI
# ========================
st.markdown('<div class="sec-card">', unsafe_allow_html=True)
st.markdown('<div class="sec-title">📄 Riwayat Transaksi</div>', unsafe_allow_html=True)

f1, f2, _ = st.columns([1, 1, 3])
with f1:
    filter_j = st.selectbox("Jenis", ["Semua", "Beli", "Update"], label_visibility="collapsed")
with f2:
    sort_o   = st.selectbox("Urutan", ["Terbaru", "Terlama"], label_visibility="collapsed")

df_show = df.copy()
if filter_j != "Semua":
    df_show = df_show[df_show["Jenis"] == filter_j]
df_show = df_show.sort_values("Tanggal", ascending=(sort_o == "Terlama"))

rows = ""
for _, r in df_show.iterrows():
    tag    = '<span class="tag-beli">Beli</span>' if r["Jenis"] == "Beli" \
             else '<span class="tag-update">Update</span>'
    nom    = fmt_full(r["Nominal"]) if r["Nominal"] > 0 else "—"
    porto  = fmt_full(r["Nilai Portofolio"]) if r["Nilai Portofolio"] > 0 else "—"
    
    # Pastikan Tanggal valid sebelum strftime
    if pd.notnull(r["Tanggal"]):
        date_s = r["Tanggal"].strftime("%d %b %Y")
    else:
        date_s = "Invalid Date"
        
    rows  += f"""
    <tr>
      <td>{date_s}</td>
      <td>{tag}</td>
      <td style="color:#f1f5f9;font-weight:600">{nom}</td>
      <td style="color:#f1f5f9;font-weight:600">{porto}</td>
    </tr>"""

st.markdown(f"""
<div style="overflow-x:auto">
<table class="tx-table">
  <thead><tr>
    <th>Tanggal</th><th>Jenis</th><th>Nominal</th><th>Nilai Portofolio</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>
</div>
""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)


# ========================
# FOOTER
# ========================
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

st.markdown(f"""
<div class="dash-footer">
  Streamlit · Google Sheets · {len(df)} baris data · cache 5 menit
</div>
""", unsafe_allow_html=True)