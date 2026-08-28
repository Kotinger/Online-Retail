import pandas as pd
import pymysql

df = pd.read_excel(r"data\online_retail_II.xlsx")
print("shape:", df.shape)

df["Invoice"] = df["Invoice"].astype(str)
df["StockCode"] = df["StockCode"].astype(str)


def fix_customer(x):
    if pd.isna(x):
        return None
    return str(int(float(x)))


df["Customer ID"] = df["Customer ID"].apply(fix_customer)

# NaN → None для MySQL
df = df.astype(object).where(pd.notnull(df), None)

password = open(r"pass.txt", encoding="utf-8").read().strip()

conn = pymysql.connect(
    host="127.0.0.1",
    user="root",
    password=password,
    database="online_retail",
    charset="utf8mb4",
)

sql = """
INSERT INTO orders
(Invoice, StockCode, Description, Quantity, InvoiceDate, Price, `Customer ID`, Country)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""
with conn.cursor() as cur:
    batch = []
    for i, row in enumerate(df.itertuples(index=False, name=None), 1):
        batch.append(tuple(row))
        if len(batch) == 5000:
            cur.executemany(sql, batch)
            print(i)
            batch = []
    if batch:
        cur.executemany(sql, batch)
conn.commit()
conn.close()
print("ok")
