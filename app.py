import streamlit as st
import pandas as pd
import gspread
import altair as alt
import json
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
# KONFIGURASI
# ========================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/152F-tMvERYDC18XRKwfY2JWhIP1i0K5Z7pWmgiKazp0"
TARGET_INVESTASI = 100_000_000
GFORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScwfJXsqGB1g5gLAWv9W3bGpl2z2n2jUywWrf7WpgN5FhB3Zg/viewform"

# ========================
# HELPERS
# ========================
def fmt(n: float) -> str:
    """Format angka ke Rupiah singkat."""
    if abs(n) >= 1_000_000_000:
        return f"Rp{n / 1_000_000_000:.2f}M"
    if abs(n) >= 1_000_000:
        return f"Rp{n / 1_000_000:.2f}jt"
    return f"Rp{n:,.0f}"

def fmt_full(n: float) -> str:
    """Format angka ke Rupiah penuh."""
    return f"Rp{n:,.0f}"

def pct_badge(val: float) -> str:
    """Badge HTML untuk persentase."""
    cls = "badge-up" if val >= 0 else "badge-dn"
    arrow = "▲" if val >= 0 else "▼"
    sign = "+" if val >= 0 else ""
    return f'<span class="{cls}">{arrow} {sign}{val:.2f}%</span>'

def parse_tanggal(val: object) -> object:
    """Parse tanggal fleksibel: ISO (YYYY-MM-DD) & Google Form (DD/MM/YYYY)."""
    if not val:
        return pd.NaT
    dt = pd.to_datetime(val, errors="coerce")
    if pd.isna(dt):
        dt = pd.to_datetime(val, dayfirst=True, errors="coerce")
    return dt

# ========================
# GOOGLE SHEETS CONNECTION
# ========================
def get_sheet():
    """Koneksi ke Google Sheet."""
    try:
        creds = json.loads(st.secrets["GCP_CREDENTIALS_JSON"])
        client = gspread.service_account_from_dict(creds)
    except Exception:
        client = gspread.service_account(filename="credentials.json")
    return client.open_by_url(SPREADSHEET_URL).sheet1

# ========================
# LOAD DATA
# ========================
@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    """Load & parse data dari Google Sheet."""
    sheet = get_sheet()
    raw = sheet.get_all_records()
    if not raw:
        return pd.DataFrame(columns=["Tanggal", "Jenis", "Nominal", "Nilai Portofolio", "_sheet_row"])

    df = pd.DataFrame(raw)
    df.columns = df.columns.str.strip()
    df["Jenis"] = df["Jenis"].astype(str).str.strip()
    df["Tanggal"] = df["Tanggal"].apply(parse_tanggal)
    df["Nominal"] = pd.to_numeric(df["Nominal"], errors="coerce").fillna(0)
    df["Nilai Portofolio"] = pd.to_numeric(df["Nilai Portofolio"], errors="coerce").fillna(0)

    # Hapus baris tanpa tanggal
    df = df.dropna(subset=["Tanggal"])

    # Track posisi baris asli di Sheet (untuk fitur hapus)
    df["_sheet_row"] = range(2, len(df) + 2)

    # Sort berdasarkan tanggal
    df = df.sort_values("Tanggal").reset_index(drop=True)
    return df

# ========================
# HAPUS BARIS
# ========================
def delete_row_from_sheet(sheet_row: int) -> None:
    """Hapus baris dari Google Sheet berdasarkan nomor baris asli."""
    sheet = get_sheet()
    sheet.delete_rows(sheet_row)
    st.cache_data.clear()

# ========================
# LOAD DATA
# ========================
with st.spinner("Memuat data…"):
    try:
        df = load_data()
    except Exception as e:
        st.error(f"❌ Gagal memuat data: {e}")
        st.stop()

if df.empty:
    st.info("📭 Belum ada data. Silakan input data pertama lewat Google Form.")
    st.link_button("📝 Input Data Baru", GFORM_URL)
    st.stop()

# ========================
# KALKULASI AKURAT (TIME-SERIES)
# ========================
df_calc = df.copy()

current_val = 0
current_modal = 0
list_val = []
list_modal = []

for _, row in df_calc.iterrows():
    if row["Jenis"] == "Beli":
        current_modal += row["Nominal"]
        current_val += row["Nominal"]
    elif row["Jenis"] == "Update" and row["Nilai Portofolio"] > 0:
        current_val = row["Nilai Portofolio"]
    
    list_val.append(current_val)
    list_modal.append(current_modal)

df_calc["Total Aset"] = list_val
df_calc["Total Modal S berjalan"] = list_modal
df_calc["Profit Berjalan"] = df_calc["Total Aset"] - df_calc["Total Modal S berjalan"]
df_calc["Return (%)"] = 0.0

mask = df_calc["Total Modal S berjalan"] > 0
df_calc.loc[mask, "Return (%)"] = (df_calc.loc[mask, "Profit Berjalan"] / df_calc.loc[mask, "Total Modal S berjalan"]) * 100

# Ekstrak KPI dari baris terakhir
if not df_calc.empty:
    last_row = df_calc.iloc[-1]
    nilai_portofolio = last_row["Total Aset"]
    total_modal = last_row["Total Modal S berjalan"]
    profit = last_row["Profit Berjalan"]
    growth = last_row["Return (%)"]
else:
    nilai_portofolio = total_modal = profit = growth = 0

df_beli = df_calc[df_calc["Jenis"] == "Beli"]
df_update = df_calc[df_calc["Jenis"] == "Update"]

# Statistik (dari Update — data real Bibit)
porto_vals = df_update[df_update["Nilai Portofolio"] > 0]["Nilai Portofolio"]
max_porto = porto_vals.max() if not porto_vals.empty else nilai_portofolio
min_porto = porto_vals.min() if not porto_vals.empty else nilai_portofolio
avg_porto = porto_vals.mean() if not porto_vals.empty else nilai_portofolio

durasi = (df["Tanggal"].max() - df["Tanggal"].min()).days if len(df) >= 2 else 0
now_str = datetime.now().strftime("%d %b %Y, %H:%M")

# Tren (2 Update terakhir)
if len(df_update) >= 2:
    tren = "naik" if df_update["Nilai Portofolio"].iloc[-1] > df_update["Nilai Portofolio"].iloc[-2] else "turun"
    tren_icon = "📈" if tren == "naik" else "📉"
else:
    tren = "stabil"
    tren_icon = "➡️"

profit_color = "#10b981" if profit >= 0 else "#ef4444"
growth_color = "#10b981" if growth >= 0 else "#ef4444"

# ========================
# TOPBAR
# ========================
st.markdown(f"""
<div class="topbar">
  <div>
    <div class="topbar-title">💼 Dashboard Investasi</div>
    <div class="topbar-sub">Update: {now_str} · {len(df)} entri data</div>
  </div>
  <div class="live-pill"><div class="live-dot"></div>Live · Google Sheets</div>
</div>
""", unsafe_allow_html=True)

# ── Progress Bar ──
pct = min((nilai_portofolio / TARGET_INVESTASI * 100) if TARGET_INVESTASI > 0 else 0, 100)
st.markdown(f"""
<div class="target-bar">
  <div class="target-header">
    <span>🎯 Target: <span style="color:#f1f5f9">{fmt(TARGET_INVESTASI)}</span></span>
    <span style="color:#60a5fa">{pct:.1f}%</span>
  </div>
  <div class="target-track"><div class="target-fill" style="width:{pct}%"></div></div>
</div>
""", unsafe_allow_html=True)

# ── Tombol Aksi ──
col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 5])
with col_btn1:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with col_btn2:
    st.link_button("📝 Input Data Baru", GFORM_URL, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ========================
# KPI CARDS
# ========================
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""<div class="kpi-card">
      <div class="kpi-accent-top" style="background:linear-gradient(90deg,#3b82f6,#60a5fa)"></div>
      <div class="kpi-label">Nilai Portofolio</div>
      <div class="kpi-value">{fmt(nilai_portofolio)}</div>
      {pct_badge(growth)}
      <div class="kpi-sub">modal: {fmt(total_modal)}</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""<div class="kpi-card">
      <div class="kpi-accent-top" style="background:linear-gradient(90deg,#8b5cf6,#a78bfa)"></div>
      <div class="kpi-label">Total Modal</div>
      <div class="kpi-value">{fmt(total_modal)}</div>
      <div class="kpi-sub">{len(df_beli)}x transaksi beli</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""<div class="kpi-card">
      <div class="kpi-accent-top" style="background:linear-gradient(90deg,{profit_color},{profit_color}88)"></div>
      <div class="kpi-label">Profit / Loss</div>
      <div class="kpi-value" style="color:{profit_color}">{"+" if profit>=0 else ""}{fmt(profit)}</div>
      <div class="kpi-sub">{'✅ untung bersih' if profit >= 0 else '❌ rugi bersih'}</div>
    </div>""", unsafe_allow_html=True)

with c4:
    bm = "outperform 🚀" if growth >= 7 else "underperform ⚠️"
    st.markdown(f"""<div class="kpi-card">
      <div class="kpi-accent-top" style="background:linear-gradient(90deg,#f59e0b,#fbbf24)"></div>
      <div class="kpi-label">Return (%)</div>
      <div class="kpi-value" style="color:{growth_color}">{growth:+.2f}%</div>
      <div class="kpi-sub">{bm} vs 7%</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

# ========================
# INSIGHT BOXES
# ========================
st.markdown(f"""
<div class="insight-row">
  <div class="insight-box">
    <div class="insight-icon">🎯</div>
    <div>
      <div class="insight-title">Posisi Portofolio</div>
      <div class="insight-sub">{'Di atas' if profit>=0 else 'Di bawah'} modal <b style="color:#f1f5f9">{fmt(abs(profit))}</b> ({abs(growth):.1f}%)</div>
    </div>
  </div>
  <div class="insight-box">
    <div class="insight-icon">{tren_icon}</div>
    <div>
      <div class="insight-title">Tren Terakhir</div>
      <div class="insight-sub">Porto sedang <b style="color:#f1f5f9">{tren}</b></div>
    </div>
  </div>
  <div class="insight-box">
    <div class="insight-icon">🏆</div>
    <div>
      <div class="insight-title">Peak Value</div>
      <div class="insight-sub">Max: <b style="color:#f1f5f9">{fmt(max_porto)}</b><br>Min: <b style="color:#f1f5f9">{fmt(min_porto)}</b></div>
    </div>
  </div>
  <div class="insight-box">
    <div class="insight-icon">📅</div>
    <div>
      <div class="insight-title">Durasi Investasi</div>
      <div class="insight-sub"><b style="color:#f1f5f9">{durasi} hari</b> sejak transaksi pertama</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ========================
# GRAFIK
# ========================
st.markdown('<div class="sec-title" style="margin-bottom:8px;margin-top:10px">📅 Filter Rentang Waktu</div>', unsafe_allow_html=True)

col_f, _ = st.columns([1, 4])
with col_f:
    time_filter = st.selectbox("Waktu", ["Semua Waktu", "Tahun Ini", "Bulan Ini", "30 Hari", "7 Hari"], label_visibility="collapsed")

# Filter data gabungan untuk grafik
now_dt = pd.Timestamp.now()
df_chart = df_calc.copy()
if time_filter == "Tahun Ini":
    df_chart = df_chart[df_chart["Tanggal"].dt.year == now_dt.year]
elif time_filter == "Bulan Ini":
    df_chart = df_chart[(df_chart["Tanggal"].dt.year == now_dt.year) & (df_chart["Tanggal"].dt.month == now_dt.month)]
elif time_filter == "30 Hari":
    df_chart = df_chart[df_chart["Tanggal"] >= (now_dt - pd.Timedelta(days=30))]
elif time_filter == "7 Hari":
    df_chart = df_chart[df_chart["Tanggal"] >= (now_dt - pd.Timedelta(days=7))]

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

col_a, col_b = st.columns([3, 2])

# ── Grafik Performa ──
with col_a:
    st.markdown('<div class="sec-card">', unsafe_allow_html=True)
    st.markdown('<div class="sec-title">📈 Performa Portofolio</div>', unsafe_allow_html=True)

    chart_data = df_chart[df_chart["Total Aset"] > 0]
    if len(chart_data) >= 1:
        cdf = chart_data[["Tanggal", "Total Aset", "Jenis", "Nominal", "Profit Berjalan"]].copy()

        area = alt.Chart(cdf).mark_area(
            line={"color": "#3b82f6", "strokeWidth": 2.5},
            color=alt.Gradient(gradient="linear",
                stops=[alt.GradientStop(color="rgba(59,130,246,0.3)", offset=0),
                       alt.GradientStop(color="rgba(59,130,246,0.0)", offset=1)],
                x1=1, x2=1, y1=1, y2=0),
        ).encode(
            x=alt.X("Tanggal:T", axis=alt.Axis(labelColor="#64748b", gridColor="#1e293b", labelFontSize=10, title=None, format="%d %b")),
            y=alt.Y("Total Aset:Q", axis=alt.Axis(labelColor="#64748b", gridColor="#1e293b", labelFontSize=10, title=None, format=",")),
            tooltip=[
                alt.Tooltip("Tanggal:T", title="Tanggal", format="%d %b %Y"), 
                alt.Tooltip("Total Aset:Q", title="Total Aset", format=","),
                alt.Tooltip("Nominal:Q", title="Nominal Transaksi", format=","),
                alt.Tooltip("Jenis:N", title="Jenis")
            ]
        )
        pts = alt.Chart(cdf).mark_point(color="#60a5fa", size=70, filled=True).encode(x="Tanggal:T", y="Total Aset:Q")
        rule = alt.Chart(pd.DataFrame({"y": [total_modal]})).mark_rule(color="#f59e0b", strokeDash=[4,3], strokeWidth=1.5).encode(y="y:Q")

        st.altair_chart((area + pts + rule).properties(height=220, background="transparent").configure_view(strokeWidth=0).configure_axis(domainColor="#1e293b"), use_container_width=True)

        st.markdown(f"""<div class="stat-row">
          <div class="stat-mini"><div class="stat-mini-val">{fmt(max_porto)}</div><div class="stat-mini-lbl">Tertinggi</div></div>
          <div class="stat-mini"><div class="stat-mini-val">{fmt(min_porto)}</div><div class="stat-mini-lbl">Terendah</div></div>
          <div class="stat-mini"><div class="stat-mini-val">{fmt(avg_porto)}</div><div class="stat-mini-lbl">Rata-rata</div></div>
        </div>""", unsafe_allow_html=True)
    else:
        st.info("📊 Belum ada data transaksi. Input lewat Google Form.")

    st.markdown("</div>", unsafe_allow_html=True)

# ── Grafik Return ──
with col_b:
    st.markdown('<div class="sec-card">', unsafe_allow_html=True)
    st.markdown('<div class="sec-title">📊 Return Portofolio (%)</div>', unsafe_allow_html=True)

    df_g = df_chart.copy()

    if not df_g.empty:
        df_g["warna"] = df_g["Return (%)"].apply(lambda v: "naik" if v >= 0 else "turun")

        bar = alt.Chart(df_g).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("Tanggal:T", axis=alt.Axis(labelColor="#64748b", gridColor="#1e293b", labelFontSize=10, title=None, format="%d %b")),
            y=alt.Y("Return (%):Q", axis=alt.Axis(labelColor="#64748b", gridColor="#1e293b", labelFontSize=10, title=None)),
            color=alt.Color("warna:N", scale=alt.Scale(domain=["naik","turun"], range=["#10b981","#ef4444"]), legend=None),
            tooltip=[
                alt.Tooltip("Tanggal:T", title="Tanggal", format="%d %b %Y"), 
                alt.Tooltip("Return (%):Q", title="Return", format=".2f"), 
                alt.Tooltip("Profit Berjalan:Q", title="Profit", format=","),
                alt.Tooltip("Jenis:N", title="Jenis")
            ]
        ).properties(height=220, background="transparent").configure_view(strokeWidth=0).configure_axis(domainColor="#1e293b")

        st.altair_chart(bar, use_container_width=True)

        pos_n = len(df_g[df_g["Return (%)"] > 0])
        neg_n = len(df_g[df_g["Return (%)"] < 0])
        avg_g = df_g["Return (%)"].mean()

        st.markdown(f"""<div class="stat-row">
          <div class="stat-mini"><div class="stat-mini-val" style="color:#10b981">{pos_n}</div><div class="stat-mini-lbl">Sesi Profit</div></div>
          <div class="stat-mini"><div class="stat-mini-val" style="color:#ef4444">{neg_n}</div><div class="stat-mini-lbl">Sesi Rugi</div></div>
          <div class="stat-mini"><div class="stat-mini-val">{avg_g:.2f}%</div><div class="stat-mini-lbl">Rata-rata Return</div></div>
        </div>""", unsafe_allow_html=True)
    else:
        st.info("📈 Belum ada data transaksi.")

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
    sort_o = st.selectbox("Urutan", ["Terbaru", "Terlama"], label_visibility="collapsed")

df_show = df_calc.copy()
if filter_j != "Semua":
    df_show = df_show[df_show["Jenis"] == filter_j]
df_show = df_show.sort_values("Tanggal", ascending=(sort_o == "Terlama"))

rows_html = ""
for _, r in df_show.iterrows():
    if r["Jenis"] == "Beli":
        tag = '<span class="tag-beli">Beli</span>'
    else:
        tag = '<span class="tag-update">Update</span>'
        
    nom = fmt_full(r["Nominal"]) if r["Nominal"] > 0 else "—"
    porto = fmt_full(r["Nilai Portofolio"]) if r["Nilai Portofolio"] > 0 else "—"
    tgl = r["Tanggal"].strftime("%d %b %Y") if pd.notnull(r["Tanggal"]) else "—"
    rows_html += f'<tr><td>{tgl}</td><td>{tag}</td><td style="color:#f1f5f9;font-weight:600">{nom}</td><td style="color:#f1f5f9;font-weight:600">{porto}</td></tr>'

st.markdown(f"""<div style="overflow-x:auto">
<table class="tx-table">
  <thead><tr><th>Tanggal</th><th>Jenis</th><th>Nominal</th><th>Nilai Portofolio</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table></div>""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ========================
# HAPUS DATA
# ========================
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
st.markdown('<div class="sec-card">', unsafe_allow_html=True)
st.markdown('<div class="sec-title">🗑️ Hapus Data</div>', unsafe_allow_html=True)
st.caption("Pilih data yang salah input. Data langsung terhapus dari Google Sheet.")

options_list = []
row_map = {}

for _, r in df.iterrows():
    tgl = r["Tanggal"].strftime("%d %b %Y") if pd.notnull(r["Tanggal"]) else "?"
    nom = fmt_full(r["Nominal"]) if r["Nominal"] > 0 else "—"
    porto = fmt_full(r["Nilai Portofolio"]) if r["Nilai Portofolio"] > 0 else "—"
    label = f"{tgl} | {r['Jenis']} | Nominal: {nom} | Porto: {porto}"
    options_list.append(label)
    row_map[label] = int(r["_sheet_row"])

selected = st.selectbox("Pilih:", options_list, label_visibility="collapsed")

if st.button("🗑️ Hapus Baris Ini", type="primary"):
    st.session_state["confirm_delete"] = True
    st.session_state["delete_target"] = selected

if st.session_state.get("confirm_delete"):
    target = st.session_state.get("delete_target", "")
    st.warning(f"⚠️ Yakin hapus: **{target}**?")
    c_yes, c_no, _ = st.columns([1, 1, 6])
    with c_yes:
        if st.button("✅ Ya, Hapus!", key="yes_del"):
            try:
                delete_row_from_sheet(row_map[target])
                st.session_state["confirm_delete"] = False
                st.success("✅ Berhasil dihapus!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Gagal: {e}")
    with c_no:
        if st.button("❌ Batal", key="no_del"):
            st.session_state["confirm_delete"] = False
            st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# ========================
# FOOTER
# ========================
st.markdown(f"""<div class="dash-footer">
  Streamlit · Google Sheets · {len(df)} data · cache 5 menit
</div>""", unsafe_allow_html=True)