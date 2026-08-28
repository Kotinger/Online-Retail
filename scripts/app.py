from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).resolve().parent.parent / "data"


@st.cache_data
def load_clean():
    return pd.read_parquet(DATA / "clean.parquet")


@st.cache_data
def load_customers():
    return pd.read_parquet(DATA / "customers.parquet")


@st.cache_data
def build_retention(clean: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    people = clean[clean["Customer ID"].notna()].copy()
    people["month"] = people["InvoiceDate"].dt.to_period("M")

    cohorts = customers[["ID клиента", "Когорта"]].rename(
        columns={"ID клиента": "Customer ID"}
    )
    act = (
        people.groupby(["Customer ID", "month"], as_index=False)
        .agg(orders=("Invoice", "nunique"))
    )
    act = act.merge(cohorts, on="Customer ID")
    act["period"] = (act["month"] - act["Когорта"]).apply(lambda x: x.n)

    cohort_size = cohorts.groupby("Когорта").size().rename("cohort_size")
    cohort = (
        act.groupby(["Когорта", "period"], as_index=False)["Customer ID"]
        .nunique()
        .rename(columns={"Customer ID": "customers"})
    )
    cohort = cohort.merge(cohort_size, on="Когорта")
    cohort["retention"] = cohort["customers"] / cohort["cohort_size"]

    retention = cohort.pivot(index="Когорта", columns="period", values="retention")
    retention.index = retention.index.astype(str)
    retention.columns = [f"Месяц {c}" for c in retention.columns]
    return retention.sort_index()


def filter_clean(df: pd.DataFrame, countries: list, years: list) -> pd.DataFrame:
    out = df.copy()
    if countries:
        out = out[out["Country"].isin(countries)]
    if years:
        out = out[out["InvoiceDate"].dt.year.isin(years)]
    return out


def fmt_money(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


st.set_page_config(page_title="Online Retail", layout="wide")
st.title("Online Retail — дашборд")

clean = load_clean()
customers = load_customers()

countries = sorted(clean["Country"].dropna().unique())
years = sorted(clean["InvoiceDate"].dt.year.unique())

with st.sidebar:
    st.header("Фильтры")
    sel_countries = st.multiselect("Страна", countries, default=countries)
    sel_years = st.multiselect("Год", years, default=years)

df = filter_clean(clean, sel_countries, sel_years)

tab1, tab2, tab3, tab4 = st.tabs(["Обзор", "Продажи", "Когорты", "RFM"])

with tab1:
    gmv = df["revenue"].sum()
    orders = df["Invoice"].nunique()
    aov = gmv / orders if orders else 0
    lines = len(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GMV", fmt_money(gmv))
    c2.metric("Заказы", f"{orders:,}".replace(",", " "))
    c3.metric("AOV", fmt_money(aov))
    c4.metric("Строк (line)", f"{lines:,}".replace(",", " "))

    st.caption("Период: дек 2009 — дек 2010 · зерно строки = позиция в чеке")

    by_country = (
        df.groupby("Country", as_index=False)
        .agg(gmv=("revenue", "sum"), orders=("Invoice", "nunique"))
        .assign(aov=lambda x: x["gmv"] / x["orders"])
        .sort_values("gmv", ascending=False)
        .head(10)
    )
    fig = px.bar(
        by_country,
        x="Country",
        y="gmv",
        title="Топ-10 стран по GMV",
        labels={"Country": "Страна", "gmv": "GMV"},
    )
    st.plotly_chart(fig, width="stretch")

with tab2:
    monthly = (
        df.groupby(df["InvoiceDate"].dt.to_period("M"), as_index=False)
        .agg(gmv=("revenue", "sum"), orders=("Invoice", "nunique"))
    )
    monthly["month"] = monthly["InvoiceDate"].astype(str)
    monthly["mom_pct"] = monthly["gmv"].pct_change()

    fig_line = px.line(
        monthly,
        x="month",
        y="gmv",
        markers=True,
        title="GMV по месяцам",
        labels={"month": "Месяц", "gmv": "GMV"},
    )
    st.plotly_chart(fig_line, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        top_months = monthly.nlargest(5, "gmv")[["month", "gmv", "orders"]]
        st.subheader("Топ-5 месяцев")
        st.dataframe(top_months, hide_index=True, width="stretch")
    with c2:
        top_sku = (
            df.groupby("StockCode", as_index=False)
            .agg(gmv=("revenue", "sum"), qty=("Quantity", "sum"), orders=("Invoice", "nunique"))
            .sort_values("gmv", ascending=False)
            .head(10)
        )
        st.subheader("Топ-10 SKU")
        st.dataframe(top_sku, hide_index=True, width="stretch")

with tab3:
    st.caption("Когорты и RFM — по всему датасету (не зависят от фильтра слева)")
    retention = build_retention(clean, customers)

    fig_hm = px.imshow(
        retention.astype(float),
        text_auto=".0%",
        aspect="auto",
        color_continuous_scale="Blues",
        title="Retention: когорта × месяц жизни",
        labels=dict(x="Месяц жизни", y="Когорта", color="Доля"),
    )
    fig_hm.update_traces(texttemplate="%{z:.0%}")
    st.plotly_chart(fig_hm, width="stretch")

    st.subheader("Таблица retention")
    st.dataframe(retention.round(3), width="stretch")

with tab4:
    st.caption("RFM на дату последнего заказа в датасете")

    seg = (
        customers.groupby("Сегмент", as_index=False)
        .agg(Клиентов=("ID клиента", "count"), Средний_GMV=("Сумма", "mean"))
        .sort_values("Клиентов", ascending=False)
    )

    c1, c2 = st.columns(2)
    with c1:
        fig_pie = px.pie(
            seg,
            names="Сегмент",
            values="Клиентов",
            title="Клиенты по сегментам",
        )
        st.plotly_chart(fig_pie, width="stretch")
    with c2:
        fig_bar = px.bar(
            seg,
            x="Сегмент",
            y="Средний_GMV",
            title="Средний GMV по сегменту",
            labels={"Средний_GMV": "GMV"},
        )
        st.plotly_chart(fig_bar, width="stretch")

    st.subheader("Сегменты")
    st.dataframe(seg.round(0), hide_index=True, width="stretch")

    st.subheader("Топ клиентов по GMV")
    top_clients = customers.nlargest(20, "Сумма")[
        ["ID клиента", "Заказов", "Сумма", "Сегмент", "RFM-код", "Когорта"]
    ]
    st.dataframe(top_clients, hide_index=True, width="stretch")
