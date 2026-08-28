CREATE DATABASE IF NOT EXISTS online_retail
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE online_retail;

DROP TABLE IF EXISTS orders;

CREATE TABLE orders (
  Invoice VARCHAR(20) NOT NULL,
  StockCode VARCHAR(20) NOT NULL,
  Description VARCHAR(255) NULL,
  Quantity INT NOT NULL,
  InvoiceDate DATETIME NOT NULL,
  Price DECIMAL(10,2) NOT NULL,
  `Customer ID` VARCHAR(20)   NULL,
  Country VARCHAR(50)   NOT NULL
);


SELECT COUNT(*) FROM orders;

SHOW TABLES;
DESCRIBE orders;
SELECT * FROM orders LIMIT 5;

SELECT COLUMN_NAME, DATA_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_NAME = 'orders';

SELECT COUNT(*) AS row_n,
  COUNT(DISTINCT Invoice) AS orsers_n,
  COUNT(*)/ COUNT(DISTINCT Invoice) AS lines_per_order
FROM orders;

SELECT
  Invoice,
  Quantity * Price AS revenue
FROM orders
LIMIT 5;

SELECT COUNT(*) AS c_rows
FROM orders
WHERE TRIM (Invoice) LIKE 'C%';

CREATE OR REPLACE VIEW clean_orders AS
SELECT
  Invoice,
  StockCode,
  Quantity,
  Price,
  InvoiceDate,
  `Customer ID`,
  Country,
  Quantity * Price AS revenue
FROM orders
WHERE Invoice IS NOT NULL
  AND TRIM(Invoice) NOT LIKE 'C%'
  AND Quantity > 0
  AND Price > 0;

SELECT
  (SELECT COUNT(*) FROM orders) AS raw_rows,
  (SELECT COUNT(*) FROM clean_orders) AS clean_rows,
  (SELECT COUNT(DISTINCT Invoice) FROM orders) AS raw_orders,
  (SELECT COUNT(DISTINCT Invoice) FROM clean_orders) AS clean_orders,
  (SELECT SUM(Quantity * Price) FROM orders) AS raw_gmv,
  (SELECT SUM(revenue) FROM clean_orders) AS clean_gmv;

SELECT Invoice,
  COUNT(DISTINCT `Customer ID`) AS cust_n,
  COUNT(DISTINCT InvoiceDate) AS dt_n
FROM clean_orders
GROUP BY Invoice
HAVING COUNT(DISTINCT `Customer ID`) > 1
  OR COUNT(DISTINCT InvoiceDate) > 1;

CREATE OR REPLACE VIEW people_orders AS
SELECT *
FROM clean_orders
WHERE `Customer ID` IS NOT NULL;

SELECT
  SUM(revenue) AS gmv,
  COUNT(DISTINCT Invoice) AS orders,
  COUNT(*) AS line_cnt,
  SUM(revenue) / COUNT(DISTINCT Invoice) AS aov
FROM clean_orders;

SELECT
  StockCode,
  SUM(revenue) AS gmv,
  SUM(Quantity) AS qty,
  COUNT(DISTINCT Invoice) AS orders
FROM clean_orders
GROUP BY StockCode
ORDER BY gmv DESC
LIMIT 10;


SELECT
  Country,
  SUM(revenue) AS gmv,
  COUNT(DISTINCT Invoice) AS orders,
  COUNT(*) AS line_cnt,
  SUM(revenue) / COUNT(DISTINCT Invoice) AS aov
FROM clean_orders
GROUP BY Country
ORDER BY gmv DESC
LIMIT 5;

SELECT
  COUNT(*) AS customers,
  AVG(CASE WHEN n_orders >= 2 THEN 1 ELSE 0 END) AS repeat_rate
FROM (
  SELECT `Customer ID`, COUNT(DISTINCT Invoice) AS n_orders
  FROM people_orders
  GROUP BY `Customer ID`
) t;

SELECT
  DATE_FORMAT(InvoiceDate, '%Y-%m') AS ym,
  SUM(revenue) AS gmv,
  COUNT(DISTINCT Invoice) AS orders,
  COUNT(*) AS line_cnt,
  SUM(revenue) / COUNT(DISTINCT Invoice) AS aov
FROM clean_orders
GROUP BY ym
ORDER BY gmv DESC
LIMIT 5;

WITH m AS (
  SELECT DATE_FORMAT(InvoiceDate, '%Y-%m') AS ym,
         SUM(revenue) AS gmv
  FROM clean_orders
  GROUP BY ym
)
SELECT
  ym,
  gmv,
  LAG(gmv) OVER (ORDER BY ym) AS prev,
  (gmv - LAG(gmv) OVER (ORDER BY ym))
    / LAG(gmv) OVER (ORDER BY ym) AS mom_pct
FROM m
ORDER BY ym;

SELECT
  DATE_FORMAT(InvoiceDate, '%Y-%m') AS ym,
  SUM(revenue) AS gmv,
  SUM(SUM(revenue)) OVER (ORDER BY DATE_FORMAT(InvoiceDate, '%Y-%m')) AS gmv_cum
FROM clean_orders
GROUP BY ym
ORDER BY ym;

-- КОГОРТЫ (как в scripts/cohort_rfm.py)

-- Шаг 1. один клиент = одна строка
CREATE OR REPLACE VIEW customer_orders AS
SELECT
  `Customer ID`,
  MIN(InvoiceDate) AS first_order,
  DATE_FORMAT(MIN(InvoiceDate), '%Y-%m') AS cohort_ym,
  MAX(InvoiceDate) AS last_order,
  COUNT(DISTINCT Invoice) AS order_cnt,
  SUM(revenue) AS gmv
FROM people_orders
GROUP BY `Customer ID`;

SELECT * FROM customer_orders LIMIT 5;
SELECT COUNT(*) AS clients_n FROM customer_orders;

SELECT cohort_ym AS Когорта, COUNT(*) AS Клиентов
FROM customer_orders
GROUP BY cohort_ym
ORDER BY cohort_ym
LIMIT 5;


-- Шаг 2.  когорта × месяц жизни)
WITH cust AS (
  SELECT
    `Customer ID`,
    DATE_FORMAT(MIN(InvoiceDate), '%Y-%m') AS cohort_ym
  FROM people_orders
  GROUP BY `Customer ID`
),
activity AS (
  SELECT DISTINCT
    `Customer ID`,
    DATE_FORMAT(InvoiceDate, '%Y-%m') AS activity_ym
  FROM people_orders
),
cohort_activity AS (
  SELECT
    c.`Customer ID`,
    c.cohort_ym,
    a.activity_ym,
    PERIOD_DIFF(
      CAST(REPLACE(a.activity_ym, '-', '') AS UNSIGNED),
      CAST(REPLACE(c.cohort_ym, '-', '') AS UNSIGNED)
    ) AS period
  FROM cust c
  JOIN activity a ON c.`Customer ID` = a.`Customer ID`
),
cohort_size AS (
  SELECT cohort_ym, COUNT(*) AS cohort_size
  FROM cust
  GROUP BY cohort_ym
)
SELECT
  ca.cohort_ym AS Когорта,
  ca.period AS Месяц,
  COUNT(DISTINCT ca.`Customer ID`) AS Клиентов,
  cs.cohort_size AS Размер_когорты,
  COUNT(DISTINCT ca.`Customer ID`) / cs.cohort_size AS Удержание
FROM cohort_activity ca
JOIN cohort_size cs ON ca.cohort_ym = cs.cohort_ym
GROUP BY ca.cohort_ym, ca.period, cs.cohort_size
ORDER BY ca.cohort_ym, ca.period;


-- Шаг 3. Retention 
WITH cust AS (
  SELECT
    `Customer ID`,
    DATE_FORMAT(MIN(InvoiceDate), '%Y-%m') AS cohort_ym
  FROM people_orders
  GROUP BY `Customer ID`
),
activity AS (
  SELECT DISTINCT
    `Customer ID`,
    DATE_FORMAT(InvoiceDate, '%Y-%m') AS activity_ym
  FROM people_orders
),
cohort_activity AS (
  SELECT
    c.cohort_ym,
    PERIOD_DIFF(
      CAST(REPLACE(a.activity_ym, '-', '') AS UNSIGNED),
      CAST(REPLACE(c.cohort_ym, '-', '') AS UNSIGNED)
    ) AS period,
    c.`Customer ID`
  FROM cust c
  JOIN activity a ON c.`Customer ID` = a.`Customer ID`
),
cohort_size AS (
  SELECT cohort_ym, COUNT(*) AS cohort_size
  FROM cust
  GROUP BY cohort_ym
),
retention_long AS (
  SELECT
    ca.cohort_ym,
    ca.period,
    COUNT(DISTINCT ca.`Customer ID`) / cs.cohort_size AS retention
  FROM cohort_activity ca
  JOIN cohort_size cs ON ca.cohort_ym = cs.cohort_ym
  GROUP BY ca.cohort_ym, ca.period, cs.cohort_size
)
SELECT
  cohort_ym AS Когорта,
  ROUND(MAX(CASE WHEN period = 0 THEN retention END), 3) AS `Месяц 0`,
  ROUND(MAX(CASE WHEN period = 1 THEN retention END), 3) AS `Месяц 1`,
  ROUND(MAX(CASE WHEN period = 2 THEN retention END), 3) AS `Месяц 2`,
  ROUND(MAX(CASE WHEN period = 3 THEN retention END), 3) AS `Месяц 3`,
  ROUND(MAX(CASE WHEN period = 4 THEN retention END), 3) AS `Месяц 4`,
  ROUND(MAX(CASE WHEN period = 5 THEN retention END), 3) AS `Месяц 5`,
  ROUND(MAX(CASE WHEN period = 6 THEN retention END), 3) AS `Месяц 6`
FROM retention_long
GROUP BY cohort_ym
ORDER BY cohort_ym
LIMIT 8;


-- RFM (как в scripts/cohort_rfm.py)

CREATE OR REPLACE VIEW customer_rfm AS
WITH as_of AS (
  SELECT MAX(InvoiceDate) AS as_of_date
  FROM clean_orders
),
rfm_base AS (
  SELECT
    co.`Customer ID`,
    co.first_order,
    co.last_order,
    co.cohort_ym,
    co.order_cnt,
    co.gmv,
    DATEDIFF(a.as_of_date, co.last_order) AS R,
    co.order_cnt AS F,
    co.gmv AS M
  FROM customer_orders co
  CROSS JOIN as_of a
),
rfm_scored AS (
  SELECT
    *,
    6 - NTILE(5) OVER (ORDER BY R ASC) AS R_score,
    NTILE(5) OVER (ORDER BY F, `Customer ID`) AS F_score,
    NTILE(5) OVER (ORDER BY M, `Customer ID`) AS M_score
  FROM rfm_base
)
SELECT
  `Customer ID`,
  first_order,
  last_order,
  cohort_ym,
  order_cnt,
  gmv,
  R,
  F,
  M,
  R_score,
  F_score,
  M_score,
  CONCAT(R_score, F_score, M_score) AS rfm_code,
  CASE
    WHEN R_score >= 4 AND F_score >= 4 AND M_score >= 4 THEN 'Чемпионы'
    WHEN R_score >= 4 AND F_score <= 2 THEN 'Новички'
    WHEN R_score >= 3 AND F_score >= 3 THEN 'Лояльные'
    WHEN R_score <= 2 AND F_score >= 3 THEN 'Под риском'
    WHEN R_score <= 2 THEN 'Потерянные'
    ELSE 'Прочие'
  END AS segment
FROM rfm_scored;


-- Шаг 1.проверка RFM на клиенте
SELECT
  `Customer ID` AS `ID клиента`,
  R AS `Давность, дни`,
  F AS `Частота`,
  M AS `Сумма`,
  R_score AS `Балл R`,
  F_score AS `Балл F`,
  M_score AS `Балл M`,
  rfm_code AS `RFM-код`,
  segment AS `Сегмент`
FROM customer_rfm
LIMIT 5;

SELECT COUNT(*) AS `Клиентов` FROM customer_rfm;


-- Шаг 2.сегменты 
SELECT
  segment AS `Сегмент`,
  COUNT(*) AS `Клиентов`,
  ROUND(AVG(M), 0) AS `Средний_GMV`
FROM customer_rfm
GROUP BY segment
ORDER BY `Клиентов` DESC;


-- Шаг 3.топ RFM-кодов
SELECT
  rfm_code AS `RFM-код`,
  COUNT(*) AS `Клиентов`
FROM customer_rfm
GROUP BY rfm_code
ORDER BY `Клиентов` DESC
LIMIT 10;
