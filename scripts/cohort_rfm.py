import pandas as pd

df = pd.read_parquet(r"data\clean.parquet")
print("чистые данные:", df.shape)

#  клиенты с id 
people = df[df["Customer ID"].notna()].copy()
print("строк с клиентом:", people.shape[0], "| уникальных клиентов:", people["Customer ID"].nunique())

# 1 клиент = 1 строка 
orders = (
    people.groupby("Customer ID", as_index=False)
    .agg(
        first_order=("InvoiceDate", "min"),
        last_order=("InvoiceDate", "max"),
        order_cnt=("Invoice", "nunique"),
        gmv=("revenue", "sum"),
    )
)
orders["cohort_month"] = orders["first_order"].dt.to_period("M")

orders_ru = orders.rename(
    columns={
        "Customer ID": "ID клиента",
        "first_order": "Первый заказ",
        "last_order": "Последний заказ",
        "order_cnt": "Заказов",
        "gmv": "GMV",
        "cohort_month": "Когорта",
    }
)
print("\nклиенты (первые 5):")
print(orders_ru.head())
print("всего клиентов:", len(orders))
print("\nразмер когорт:")
print(
    orders_ru["Когорта"]
    .value_counts()
    .sort_index()
    .head()
    .rename("Клиентов")
)

#  когорта × месяц жизни 
act = (
    people.groupby(["Customer ID", "month"], as_index=False)
    .agg(orders=("Invoice", "nunique"), gmv=("revenue", "sum"))
)
act = act.merge(orders[["Customer ID", "cohort_month"]], on="Customer ID")
act["period"] = (act["month"] - act["cohort_month"]).apply(lambda x: x.n)

cohort = (
    act.groupby(["cohort_month", "period"], as_index=False)["Customer ID"]
    .nunique()
    .rename(columns={"Customer ID": "customers"})
)
cohort_size = orders.groupby("cohort_month").size().rename("cohort_size")
cohort = cohort.merge(cohort_size, on="cohort_month")
cohort["retention"] = cohort["customers"] / cohort["cohort_size"]

retention = cohort.pivot(index="cohort_month", columns="period", values="retention")
retention.index.name = "Когорта"
retention.columns = [f"Месяц {c}" for c in retention.columns]
print("\nудержание (retention), доля клиентов:")
print(retention.round(3).head(8))

# RFM 
as_of = df["InvoiceDate"].max()
rfm = orders.copy()
rfm["R"] = (as_of - rfm["last_order"]).dt.days
rfm["F"] = rfm["order_cnt"]
rfm["M"] = rfm["gmv"]

rfm["R_score"] = pd.qcut(rfm["R"], 5, labels=[5, 4, 3, 2, 1])  # недавно = 5
rfm["F_score"] = pd.qcut(rfm["F"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5])
rfm["M_score"] = pd.qcut(rfm["M"], 5, labels=[1, 2, 3, 4, 5])
rfm["RFM"] = (
    rfm["R_score"].astype(str) + rfm["F_score"].astype(str) + rfm["M_score"].astype(str)
)


def rfm_segment(row):
    r, f, m = int(row["R_score"]), int(row["F_score"]), int(row["M_score"])
    if r >= 4 and f >= 4 and m >= 4:
        return "Чемпионы"
    if r >= 4 and f <= 2:
        return "Новички"
    if r >= 3 and f >= 3:
        return "Лояльные"
    if r <= 2 and f >= 3:
        return "Под риском"
    if r <= 2:
        return "Потерянные"
    return "Прочие"


rfm["segment"] = rfm.apply(rfm_segment, axis=1)

rfm_ru = rfm.rename(
    columns={
        "Customer ID": "ID клиента",
        "first_order": "Первый заказ",
        "last_order": "Последний заказ",
        "order_cnt": "Заказов",
        "gmv": "GMV",
        "cohort_month": "Когорта",
        "R": "Давность, дни",
        "F": "Частота",
        "M": "Сумма",
        "R_score": "Балл R",
        "F_score": "Балл F",
        "M_score": "Балл M",
        "RFM": "RFM-код",
        "segment": "Сегмент",
    }
)

print("\nRFM — описание:")
print(rfm_ru[["Давность, дни", "Частота", "Сумма"]].describe())
print("\nтоп RFM-кодов:")
print(rfm_ru["RFM-код"].value_counts().head(10).rename("Клиентов"))

print("\nсегменты:")
print(rfm_ru["Сегмент"].value_counts().rename("Клиентов"))
print(
    rfm_ru.groupby("Сегмент", as_index=False)
    .agg(Клиентов=("ID клиента", "count"), Средний_GMV=("Сумма", "mean"))
    .round(0)
)

rfm_ru.to_parquet(r"data\customers.parquet", index=False)
print("\nсохранено: data/customers.parquet | строк:", rfm_ru.shape[0], "| колонок:", rfm_ru.shape[1])
