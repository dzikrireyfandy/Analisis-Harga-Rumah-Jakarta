
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

#konofgurasi halaman
st.set_page_config(
    page_title="Dashboard Harga Rumah Jakarta",
    layout="wide",
)

DATA_PATH = Path(__file__).parent / "jakarta_house.csv"
WARNA_WILAYAH = {
    "Jakarta Selatan": "#2563eb",
    "Jakarta Pusat": "#dc2626",
    "Jakarta Utara": "#059669",
    "Jakarta Barat": "#d97706",
    "Jakarta Timur": "#7c3aed",
}
URUTAN_SEGMEN = [
    "Ekonomis (< 2 M)",
    "Menengah (2-5 M)",
    "Atas (5-10 M)",
    "Mewah (10-30 M)",
    "Super Mewah (> 30 M)",
]


# untuk helper
def fmt_rp(nilai: float) -> str:
    """Format rupiah ringkas: 4.5e9 -> 'Rp 4,50 M'."""
    if pd.isna(nilai):
        return "-"
    if nilai >= 1e12:
        teks = f"{nilai / 1e12:,.2f} T"
    elif nilai >= 1e9:
        teks = f"{nilai / 1e9:,.2f} M"
    else:
        teks = f"{nilai / 1e6:,.0f} jt"
    # format Indonesia
    teks = teks.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"Rp {teks}"


def id_num(nilai: float, desimal: int = 2) -> str:
    """Format angka gaya Indonesia: 1234.5 -> '1.234,50'."""
    teks = f"{nilai:,.{desimal}f}"
    return teks.replace(",", "_").replace(".", ",").replace("_", ".")


@st.cache_data(show_spinner="Memuat dan membersihkan data...")
def load_data():
    """Baca CSV, bersihkan, dan tambah kolom turunan."""
    mentah = pd.read_csv(DATA_PATH)
    log = {"Data mentah": len(mentah)}

    df = mentah.drop(columns=["index"]).drop_duplicates()
    log["Setelah hapus duplikat"] = len(df)

    df = df.dropna(subset=["land_area", "building_area"])
    log["Setelah hapus data kosong"] = len(df)

    # Outlier
    df = df[df["price"].between(2e8, 2e11)]
    df = df[(df["land_area"] <= 5000) & (df["building_area"] <= 5000)]
    df = df[(df["bed_rooms"] <= 15) & (df["bath_rooms"] <= 15) & (df["carport"] <= 10)]
    log["Setelah hapus outlier"] = len(df)

    df = df.rename(
        columns={
            "price": "harga",
            "district": "kawasan",
            "city": "wilayah",
            "bed_rooms": "kamar_tidur",
            "bath_rooms": "kamar_mandi",
            "carport": "carport",
            "land_area": "luas_tanah",
            "building_area": "luas_bangunan",
        }
    ).reset_index(drop=True)

    df["harga_miliar"] = df["harga"] / 1e9
    df["harga_per_m2_bangunan"] = df["harga"] / df["luas_bangunan"]  # Rp per m2
    df["segmen"] = pd.cut(
        df["harga"],
        bins=[0, 2e9, 5e9, 10e9, 30e9, float("inf")],
        labels=URUTAN_SEGMEN,
        right=False,
    )
    return df, log


df, log_cleaning = load_data()

#judul
st.title("Dashboard Analisis Harga Rumah Jakarta")
st.markdown(
    "Dashboard untuk mengetahui **harga rumah yang dijual di lima wilayah "
    "DKI Jakarta**: berapa harga rata-ratanya, wilayah dan kawasan mana yang paling mahal, "
    "dan seberapa besar pengaruh luas tanah serta luas bangunan terhadap harga. "
    "Gunakan filter di sebelah kiri untuk mencari lebih spesifik."
)
st.caption(
    "Sumber data: *Jakarta House Price Dataset* (Kaggle), hasil scraping listing Rumah123.com."
)

# filter
st.sidebar.header(" Filter Data")

wilayah_all = sorted(df["wilayah"].unique())
pilih_wilayah = st.sidebar.multiselect("Wilayah", wilayah_all, default=wilayah_all)

kawasan_tersedia = sorted(df[df["wilayah"].isin(pilih_wilayah)]["kawasan"].unique())
pilih_kawasan = st.sidebar.multiselect(
    "Kawasan (kosongkan = semua)",
    kawasan_tersedia,
    help="Daftar kawasan menyesuaikan wilayah yang dipilih.",
)

harga_min = float(df["harga_miliar"].min())
harga_max = float(df["harga_miliar"].max())
pilih_harga = st.sidebar.slider(
    "Rentang harga (miliar Rp)",
    min_value=round(harga_min, 1),
    max_value=round(harga_max, 1),
    value=(round(harga_min, 1), round(harga_max, 1)),
    step=0.5,
)

pilih_kamar = st.sidebar.slider(
    "Jumlah kamar tidur",
    int(df["kamar_tidur"].min()),
    int(df["kamar_tidur"].max()),
    (int(df["kamar_tidur"].min()), int(df["kamar_tidur"].max())),
)

# Terapkan filter
mask = (
    df["wilayah"].isin(pilih_wilayah)
    & df["harga_miliar"].between(*pilih_harga)
    & df["kamar_tidur"].between(*pilih_kamar)
)
if pilih_kawasan:
    mask &= df["kawasan"].isin(pilih_kawasan)
data = df[mask]

if data.empty:
    st.warning("Tidak ada data yang cocok dengan filter. Longgarkan filter di sidebar.")
    st.stop()

# kpi-
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Jumlah Listing", f"{len(data):,}".replace(",", "."))
k2.metric("Harga Rata-rata", fmt_rp(data["harga"].mean()))
k3.metric("Harga Median", fmt_rp(data["harga"].median()))
k4.metric("Median Harga / m² Bangunan", fmt_rp(data["harga_per_m2_bangunan"].median()))
k5.metric("Rata-rata Luas Bangunan", f"{data['luas_bangunan'].mean():,.0f} m²".replace(",", "."))
st.caption(
    "Median dipakai sebagai pembanding karena harga rumah condong ke kanan "
    "(sedikit rumah mewah yang harganya tinggi bisa menaikkan rata-rata)."
)

st.divider()


# Baris 1 Bar chart dan Donut chart
c1, c2 = st.columns([3, 2])

with c1:
    st.subheader("Median Harga per Wilayah")
    per_wilayah = (
        data.groupby("wilayah")["harga_miliar"].median().sort_values().reset_index()
    )
    fig = px.bar(
        per_wilayah,
        x="harga_miliar",
        y="wilayah",
        orientation="h",
        color="wilayah",
        color_discrete_map=WARNA_WILAYAH,
        text=per_wilayah["harga_miliar"].map(lambda v: f"{v:,.2f}".replace(".", ",")),
        labels={"harga_miliar": "Median harga (miliar Rp)", "wilayah": ""},
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False, height=360, margin=dict(l=0, r=30, t=10, b=0))
    st.plotly_chart(fig, width="stretch")

with c2:
    st.subheader("Komposisi Listing per Segmen Harga")
    per_segmen = (
        data["segmen"].value_counts().reindex(URUTAN_SEGMEN).dropna().reset_index()
    )
    per_segmen.columns = ["segmen", "jumlah"]
    fig = px.pie(
        per_segmen,
        names="segmen",
        values="jumlah",
        hole=0.45,
        color="segmen",
        color_discrete_sequence=["#93c5fd", "#60a5fa", "#2563eb", "#1e3a8a", "#0f172a"],
        category_orders={"segmen": URUTAN_SEGMEN},
    )
    fig.update_traces(sort=False, textinfo="percent")
    fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")


# Baris 2 Histogram dan Top kawasan
c3, c4 = st.columns(2)

with c3:
    st.subheader("Sebaran Harga Rumah")
    # Histogram dengan bin berjarak logaritmik (harga sangat condong ke kanan)
    harga = data["harga_miliar"].to_numpy()
    batas = np.logspace(np.log10(harga.min()), np.log10(harga.max() * 1.0001), 41)
    jumlah, _ = np.histogram(harga, bins=batas)
    median_harga = float(np.median(harga))
    fig = go.Figure(
        go.Bar(
            x=batas[:-1],
            y=jumlah,
            width=np.diff(batas),
            offset=0,
            marker_color="#2563eb",
            customdata=np.column_stack([batas[:-1], batas[1:]]),
            hovertemplate="Rp %{customdata[0]:.2f} - %{customdata[1]:.2f} miliar<br>%{y} listing<extra></extra>",
        )
    )
    fig.add_shape(
        type="line",
        x0=median_harga,
        x1=median_harga,
        y0=0,
        y1=1,
        yref="paper",
        line=dict(color="#dc2626", dash="dash", width=2),
    )
    fig.add_annotation(
        x=float(np.log10(median_harga)),  # sumbu log: anotasi memakai nilai log10
        y=1,
        yref="paper",
        text=f"median {median_harga:.2f} M".replace(".", ","),
        showarrow=False,
        yanchor="bottom",
        font=dict(color="#dc2626"),
    )
    fig.update_xaxes(type="log", title="Harga (miliar Rp, skala log)")
    fig.update_yaxes(title="Jumlah listing")
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=30, b=0), bargap=0.02)
    st.plotly_chart(fig, width="stretch")

with c4:
    st.subheader("10 Kawasan dengan Median Harga Tertinggi")
    kawasan = (
        data.groupby("kawasan")
        .agg(median_harga=("harga_miliar", "median"), listing=("harga", "size"), wilayah=("wilayah", "first"))
        .query("listing >= 15")
        .nlargest(10, "median_harga")
        .sort_values("median_harga")
        .reset_index()
    )
    if kawasan.empty:
        st.info("Belum ada kawasan dengan ≥ 15 listing pada filter ini.")
    else:
        fig = px.bar(
            kawasan,
            x="median_harga",
            y="kawasan",
            orientation="h",
            color="wilayah",
            color_discrete_map=WARNA_WILAYAH,
            hover_data={"listing": True},
            labels={"median_harga": "Median harga (miliar Rp)", "kawasan": "", "wilayah": "Wilayah"},
        )
        fig.update_layout(height=380, margin=dict(l=0, r=0, t=20, b=0), legend_title_text="")
        st.plotly_chart(fig, width="stretch")

# Baris 3 Scatter dan Heatmap
c5, c6 = st.columns([3, 2])

with c5:
    st.subheader("Luas Bangunan vs Harga")
    contoh = data.sample(min(len(data), 3000), random_state=42)
    fig = px.scatter(
        contoh,
        x="luas_bangunan",
        y="harga_miliar",
        color="wilayah",
        color_discrete_map=WARNA_WILAYAH,
        opacity=0.55,
        log_x=True,
        log_y=True,
        hover_data={"kawasan": True, "luas_tanah": True, "kamar_tidur": True},
        labels={
            "luas_bangunan": "Luas bangunan (m², skala log)",
            "harga_miliar": "Harga (miliar Rp, skala log)",
            "wilayah": "Wilayah",
        },
    )
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0), legend_title_text="")
    st.plotly_chart(fig, width="stretch")
   

with c6:
    st.subheader("Korelasi Antar Variabel")
    kolom_korelasi = {
        "harga": "Harga",
        "luas_tanah": "Luas tanah",
        "luas_bangunan": "Luas bangunan",
        "kamar_tidur": "Kamar tidur",
        "kamar_mandi": "Kamar mandi",
        "carport": "Carport",
    }
    korelasi = data[list(kolom_korelasi)].corr().rename(index=kolom_korelasi, columns=kolom_korelasi)
    fig = go.Figure(
        go.Heatmap(
            z=korelasi.values,
            x=korelasi.columns,
            y=korelasi.index,
            zmin=-1,
            zmax=1,
            colorscale="RdBu_r",
            text=korelasi.round(2).values,
            texttemplate="%{text}",
            colorbar=dict(title="r"),
        )
    )
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0), yaxis_autorange="reversed")
    st.plotly_chart(fig, width="stretch")

st.divider()

# insight
st.subheader("💡 Insight dari Data Terfilter")
termahal = per_wilayah.iloc[-1]
termurah = per_wilayah.iloc[0]
r_lb = data["harga"].corr(data["luas_bangunan"])
r_lt = data["harga"].corr(data["luas_tanah"])
share_atas = (data["harga"] >= 10e9).mean() * 100

st.markdown(
    f"""
- **Wilayah termahal** adalah **{termahal['wilayah']}** (median Rp {id_num(termahal['harga_miliar'])} miliar),
  sedangkan yang termurah adalah **{termurah['wilayah']}** (median Rp {id_num(termurah['harga_miliar'])} miliar).
- **Luas bangunan** berkorelasi **{id_num(r_lb)}** dengan harga dan **luas tanah** **{id_num(r_lt)}**,
  sehingga ukuran properti menjadi penentu harga.
- Rata-rata harga (Rp {id_num(data['harga'].mean() / 1e9)} miliar) lebih tinggi dari median
  (Rp {id_num(data['harga'].median() / 1e9)} miliar): sebagian kecil rumah mewah menarik rata-rata ke atas.
- Rumah dengan harga **≥ Rp 10 miliar** mencakup **{id_num(share_atas, 1)}%** dari listing.
"""
)

#tabel yang digunakan
with st.expander("📄 Lihat dan unduh data terfilter"):
    tampil = data.drop(columns=["harga_miliar", "segmen"]).copy()
    tampil["harga_per_m2_bangunan"] = tampil["harga_per_m2_bangunan"].round(0)
    st.dataframe(tampil, width="stretch", height=300)
    st.download_button(
        "⬇️ Unduh CSV",
        tampil.to_csv(index=False).encode("utf-8"),
        file_name="rumah_jakarta_terfilter.csv",
        mime="text/csv",
    )
