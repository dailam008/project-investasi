import streamlit as st
import pandas as pd
import gspread
import altair as alt
from datetime import datetime
import json

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
    if abs(n) >= 1_000_000_000:
        return f"Rp{n/1_000_000_000:.2f}M"
    if abs(n) >= 1_000_000:
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
GFORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScwfJXsqGB1g5gLAWv9W3bGpl2z2n2jUywWrf7WpgN5FhB3Zg/viewform"


# ========================
# KONEKSI GOOGLE SHEETS
# ========================
def get_gspread_client():
    """Buat koneksi gspread (cached di session_state)."""
    try:
        creds_dict = json.loads(st.secrets["GCP_CREDENTIALS_JSON"])
        return gspread.service_account_from_dict(creds_dict)
    except Exception:
        return gspread.service_account(filename="credentials.json")

def get_sheet():
    """Dapatkan object sheet langsung."""
    client = get_gspread_client()
    return client.open_by_url(SPREADSHEET_URL).sheet1


# ========================
# LOAD DATA
# ========================
@st.cache_data(ttl=300)
def load_data():
    sheet = get_sheet()
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip()
    df["Jenis"] = df["Jenis"].str.strip()

    # Parsing tanggal fleksibel (ISO & Google Form)
    def parse_tanggal(val):
        if not val:
            return pd.NaT
        dt = pd.to_datetime(val, errors='coerce')
        if pd.isna(dt):
            dt = pd.to_datetime(val, dayfirst=True, errors='coerce')
        return dt

    df["Tanggal"] = df["Tanggal"].apply(parse_tanggal)
    df["Nominal"] = pd.to_numeric(df["Nominal"], errors="coerce").fillna(0)
    df["Nilai Portofolio"] = pd.to_numeric(df["Nilai Portofolio"], errors="coerce").fillna(0)

    # Hapus baris tanpa tanggal valid
    df = df.dropna(subset=["Tanggal"])
    
    # Simpan posisi baris asli di Sheet SEBELUM sorting
    # Sheet: baris 1 = header, data mulai dari baris 2
    # DataFrame index 0 = Sheet baris 2, index 1 = Sheet baris 3, dst.
    df["_sheet_row"] = range(2, len(df) + 2)
    
    df = df.sort_values("Tanggal").reset_index(drop=True)
    return df


# ========================
# HAPUS BARIS DARI SHEET
# ========================
def delete_row_from_sheet(sheet_row: int):
    """Hapus baris dari Google Sheet berdasarkan nomor baris asli di Sheet."""
    sheet = get_sheet()
    sheet.delete_rows(sheet_row)
    st.cache_data.clear()


# ========================
# LOAD & ERROR HANDLING
# ========================
with st.spinner("Memuat data…"):
    try:
        df = load_data()
    except Exception as e:
        st.error(f"❌ Gagal memuat data: {e}")
        st.stop()


# ========================
# DATA MENTAH & FILTERED
# ========================
df_raw = df.copy()  # Data mentah untuk tabel (persis seperti Sheet)

# Pisahkan data Beli dan Update
df_beli = df[df["Jenis"] == "Beli"].copy()
df_update = df[df["Jenis"] == "Update"].copy().sort_values("Tanggal").reset_index(drop=True)


# ========================
# PERHITUNGAN KPI (SEDERHANA & AKURAT)
# ========================
# Total Modal = jumlah semua uang yang dibelanjakan
total_modal = df_beli["Nominal"].sum()

# Nilai Portofolio = data Update TERAKHIR dari Bibit (sumber kebenaran)
if not df_update.empty and df_update["Nilai Portofolio"].iloc[-1] > 0:
    nilai_portofolio = df_update["Nilai Portofolio"].iloc[-1]
else:
    nilai_portofolio = total_modal  # Jika belum pernah Update, anggap = modal

# Profit & Growth
profit = nilai_portofolio - total_modal
growth = (profit / total_modal * 100) if total_modal > 0 else 0.0

# Growth antar-Update (performa pasar sesungguhnya dari Bibit)
if len(df_update) >= 2:
    df_update["Growth (%)"] = df_update["Nilai Portofolio"].pct_change() * 100
else:
    df_update["Growth (%)"] = 0.0

# Statistik portofolio (hanya dari data Update — data real dari Bibit)
porto_update = df_update[df_update["Nilai Portofolio"] > 0]["Nilai Portofolio"]
max_porto = porto_update.max() if not porto_update.empty else nilai_portofolio
min_porto = porto_update.min() if not porto_update.empty else nilai_portofolio
avg_porto = porto_update.mean() if not porto_update.empty else nilai_portofolio

durasi_hari = (df["Tanggal"].max() - df["Tanggal"].min()).days if len(df) >= 2 else 0
now_str = datetime.now().strftime("%d %b %Y, %H:%M")

# Tren (berdasarkan 2 Update terakhir dari Bibit)
if len(df_update) >= 2:
    tren_label = "naik" if df_update["Nilai Portofolio"].iloc[-1] > df_update["Nilai Portofolio"].iloc[-2] else "turun"
    tren_icon = "📈" if tren_label == "naik" else "📉"
else:
    tren_label = "stabil"
    tren_icon = "➡️"


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
    st.link_button("📝 Input Data Baru", GFORM_URL, use_container_width=True)

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

# Filter data Update untuk grafik (data real dari Bibit)
now_date = pd.Timestamp.now()
df_chart = df_update.copy()

if time_filter == "Tahun Ini":
    df_chart = df_chart[df_chart["Tanggal"].dt.year == now_date.year]
elif time_filter == "Bulan Ini":
    df_chart = df_chart[(df_chart["Tanggal"].dt.year == now_date.year) & (df_chart["Tanggal"].dt.month == now_date.month)]
elif time_filter == "30 Hari Terakhir":
    df_chart = df_chart[df_chart["Tanggal"] >= (now_date - pd.Timedelta(days=30))]
elif time_filter == "7 Hari Terakhir":
    df_chart = df_chart[df_chart["Tanggal"] >= (now_date - pd.Timedelta(days=7))]

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

col_a, col_b = st.columns([3, 2])

with col_a:
    st.markdown('<div class="sec-card">', unsafe_allow_html=True)
    st.markdown('<div class="sec-title">📈 Performa Nilai Portofolio (dari Bibit)</div>', unsafe_allow_html=True)

    if not df_chart.empty and df_chart["Nilai Portofolio"].sum() > 0:
        chart_df = df_chart[["Tanggal", "Nilai Portofolio"]].copy()

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
        st.info("Belum ada data Update dari Bibit. Input \"Update\" lewat Google Form untuk melihat grafik performa.")

    st.markdown("</div>", unsafe_allow_html=True)

with col_b:
    st.markdown('<div class="sec-card">', unsafe_allow_html=True)
    st.markdown('<div class="sec-title">📊 Growth antar Update (%)</div>', unsafe_allow_html=True)

    # Growth chart: hanya dari Update (performa pasar real dari Bibit)
    df_g = df_chart.dropna(subset=["Growth (%)"]).copy()
    df_g = df_g[df_g["Growth (%)"].notna() & (df_g["Growth (%)"] != 0) & (df_g["Nilai Portofolio"] > 0)]

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
                alt.Tooltip("Nilai Portofolio:Q", title="Nilai Porto", format=","),
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
            <div class="stat-mini-lbl">Naik</div>
          </div>
          <div class="stat-mini">
            <div class="stat-mini-val" style="color:#ef4444">{neg_n}</div>
            <div class="stat-mini-lbl">Turun</div>
          </div>
          <div class="stat-mini">
            <div class="stat-mini-val">{avg_g:.2f}%</div>
            <div class="stat-mini-lbl">Rata-rata</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Butuh minimal 2 data Update dari Bibit untuk melihat grafik growth. Rutin input \"Update\" setiap hari agar grafik performa Anda terlihat.")

    st.markdown("</div>", unsafe_allow_html=True)


# ========================
# TABEL TRANSAKSI (DATA ASLI DARI SHEET)
# ========================
st.markdown('<div class="sec-card">', unsafe_allow_html=True)
st.markdown('<div class="sec-title">📄 Riwayat Transaksi</div>', unsafe_allow_html=True)

f1, f2, _ = st.columns([1, 1, 3])
with f1:
    filter_j = st.selectbox("Jenis", ["Semua", "Beli", "Update"], label_visibility="collapsed")
with f2:
    sort_o = st.selectbox("Urutan", ["Terbaru", "Terlama"], label_visibility="collapsed")

# Gunakan data MENTAH (df_raw) agar sesuai Sheet
df_show = df_raw.copy()
if filter_j != "Semua":
    df_show = df_show[df_show["Jenis"] == filter_j]
df_show = df_show.sort_values("Tanggal", ascending=(sort_o == "Terlama"))

rows = ""
for _, r in df_show.iterrows():
    tag = '<span class="tag-beli">Beli</span>' if r["Jenis"] == "Beli" \
         else '<span class="tag-update">Update</span>'
    nom = fmt_full(r["Nominal"]) if r["Nominal"] > 0 else "—"
    porto = fmt_full(r["Nilai Portofolio"]) if r["Nilai Portofolio"] > 0 else "—"

    if pd.notnull(r["Tanggal"]):
        date_s = r["Tanggal"].strftime("%d %b %Y")
    else:
        date_s = "—"

    rows += f"""
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
# HAPUS DATA (FITUR BARU)
# ========================
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
st.markdown('<div class="sec-card">', unsafe_allow_html=True)
st.markdown('<div class="sec-title">🗑️ Hapus Data Transaksi</div>', unsafe_allow_html=True)
st.caption("Pilih baris yang ingin dihapus jika ada kesalahan input. Data akan langsung terhapus dari Google Sheet.")

if not df_raw.empty:
    # Buat pilihan dropdown dengan info lengkap + simpan sheet_row
    options = []
    sheet_row_map = {}  # mapping label → sheet row number
    
    for idx, r in df_raw.iterrows():
        tgl = r["Tanggal"].strftime("%d %b %Y") if pd.notnull(r["Tanggal"]) else "?"
        nom = fmt_full(r["Nominal"]) if r["Nominal"] > 0 else "—"
        porto = fmt_full(r["Nilai Portofolio"]) if r["Nilai Portofolio"] > 0 else "—"
        label = f"{tgl} | {r['Jenis']} | Nominal: {nom} | Porto: {porto}"
        options.append(label)
        sheet_row_map[label] = r["_sheet_row"]  # Posisi baris asli di Sheet

    selected = st.selectbox("Pilih data yang akan dihapus:", options, label_visibility="collapsed")

    col_del1, col_del2, _ = st.columns([1.5, 1.5, 5])
    with col_del1:
        if st.button("🗑️ Hapus Baris Ini", type="primary", use_container_width=True):
            st.session_state["confirm_delete"] = True
            st.session_state["delete_target"] = selected

    # Konfirmasi
    if st.session_state.get("confirm_delete", False):
        target = st.session_state.get("delete_target", "")
        st.warning(f"⚠️ Yakin ingin menghapus: **{target}**?")
        col_yes, col_no, _ = st.columns([1, 1, 6])
        with col_yes:
            if st.button("✅ Ya, Hapus!", key="confirm_yes", use_container_width=True):
                try:
                    # Gunakan _sheet_row yang sudah di-track dari awal
                    actual_sheet_row = sheet_row_map.get(target)
                    if actual_sheet_row:
                        delete_row_from_sheet(actual_sheet_row)
                        st.session_state["confirm_delete"] = False
                        st.success("✅ Data berhasil dihapus! Memuat ulang...")
                        st.rerun()
                    else:
                        st.error("❌ Baris tidak ditemukan.")
                except Exception as e:
                    st.error(f"❌ Gagal menghapus: {e}")
        with col_no:
            if st.button("❌ Batal", key="confirm_no", use_container_width=True):
                st.session_state["confirm_delete"] = False
                st.rerun()

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