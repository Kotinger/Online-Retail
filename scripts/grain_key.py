import pandas as pd
import pyarrow
# 1. Загрузка и профиль
df = pd.read_excel(r"data\online_retail_II.xlsx")

"""
#(525461, 8)
print (df.shape)
#На первый взгял норм 
print (df.dtypes)
print (df.head(5))
#Description 2928 ,Customer ID 107927 
print(df.isna().sum())
#['Invoice', 'StockCode', 'Description', 'Quantity', 'InvoiceDate', 'Price', 'Customer ID', 'Country']
print(df.columns.tolist())  
"""
# 2. Зерно
"""
# 18 скок строк на заказ, 28816 уникальных инвойсов 
print(df["Invoice"].nunique())
print (len(df)/df["Invoice"].nunique())
"""
# 3. Типы 

money_col = "revenue" 
df["revenue"] = df["Quantity"] * df["Price"] 
#print(df[money_col].dtype) 
#print(df[money_col].head(3)) 
#print(df[money_col].sum())
date_col = "InvoiceDate" 
df["month"] = df[date_col].dt.to_period("M") 
#print(df[date_col].dtype) 
#print(df["month"].head(3)) 
#print(df[date_col].min(), "→", df[date_col].max())

#inv = df["Invoice"].astype(str)
#print((inv != inv.str.strip()).sum()) 


# 4. Чистка 

#inv = df["Invoice"].astype(str).str.strip() 
#print(inv.str.startswith("C").sum())

clean = df.copy() 
clean["Invoice"] = clean["Invoice"].astype(str).str.strip() 
#print("старт", len(clean)) 
clean = clean[~clean["Invoice"].str.startswith("C")] 
#print("без C", len(clean)) 
clean = clean[clean["Quantity"] > 0]
#print("qty>0", len(clean)) 
clean = clean[clean["Price"] > 0] 
#print("price>0", len(clean)) 
#print("orders", clean["Invoice"].nunique()) 
#print("gmv", clean["revenue"].sum())

# 5. Sanity 
"""
order_col = "Invoice" 
print("--- sanity ---")
print("rows", len(df), "→", len(clean)) 
print("orders", df[order_col].nunique(), "→", clean[order_col].nunique()) 
print("gmv clean", clean[money_col].sum()) 
print(clean[["Quantity", "Price"]].describe().loc[["min", "50%", "max"]]) 
print(clean[date_col].min(), "→", clean[date_col].max())
"""

# 6. Ключи

order_col = "Invoice" 

customer_col = "Customer ID"
check = clean.groupby(order_col)[[date_col, customer_col]].nunique() 
bad = (check[date_col] > 1) | (check[customer_col] > 1) 
#print(bad.sum())

people = clean[clean["Customer ID"].notna()].copy()
#print(len(people))
#print(people["Customer ID"].nunique())

# 7. Метрики

g = clean.groupby("Country").agg( gmv=("revenue", "sum"), orders=("Invoice", "nunique"), lines=("Invoice", "size"))
g["aov"] = g["gmv"] / g["orders"] 
print(g.sort_values("gmv", ascending=False).head())

m = clean.groupby("month", as_index=False)["revenue"].sum() 
m = m.sort_values("month") 
m["mom_pct"] = m["revenue"].pct_change() 
print(m)

n = people.groupby("Customer ID")["Invoice"].nunique()
repeat_rate = (n >= 2).mean()
print("repeat_rate", repeat_rate)
print(n.value_counts().sort_index().head(10))


top_t = clean.groupby("StockCode").agg(
    gmv=("revenue", "sum"),
    qty=("Quantity", "sum"),
    orders=("Invoice", "nunique"),
)
top = top_t.sort_values("gmv", ascending=False)
print(top.head(10))

clean["year"] = clean["InvoiceDate"].dt.year
y = clean.groupby("year").agg(
    gmv=("revenue", "sum"),
    orders=("Invoice", "nunique")
)
y["aov"]= y["gmv"] / y["orders"]
print (y.sort_index(ascending=False))

clean["month_num"] = clean["InvoiceDate"].dt.month
gm = clean.groupby(["year", "month_num"]).agg(
    gmv=("revenue", "sum"),
    orders=("Invoice", "nunique"),
)
gm["aov"] = gm["gmv"] / gm["orders"]
gm = gm.sort_values ("gmv", ascending=False)
print(gm.head(5))

"""
# Сохраняю для визуализации
clean["StockCode"] = clean["StockCode"].astype(str)
clean["Invoice"] = clean["Invoice"].astype(str)

clean.to_parquet(r"data\clean.parquet", index=False)
df2 = pd.read_parquet(r"data\clean.parquet")

print(df2.shape)
print(df2.dtypes)
print(df2["StockCode"].head())"""