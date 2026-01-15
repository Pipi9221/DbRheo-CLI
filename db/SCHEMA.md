# Vehicle Sales Database Schema

## 数据库：vehicle_sales.db

### 表1: vehicle_sales (车型销量表)

**用途：** 存储各品牌车型的月度销量数据

**字段：**
- `indicator_id` (TEXT): 指标ID
- `brand` (TEXT): 品牌名称（如：比亚迪、吉利、长城）
- `model` (TEXT): 车型名称（如：海豚、星瑞、哈弗H6）
- `sales_volume` (REAL): 销量（单位：辆）
- `date` (TEXT): 日期（格式：YYYY-MM-DD）

**索引：**
- `idx_sales_brand`: brand字段索引
- `idx_sales_date`: date字段索引

**数据量：** 8,763行

**示例查询：**
```sql
-- 查询比亚迪在2023年6月的所有车型销量
SELECT brand, model, sales_volume, date 
FROM vehicle_sales 
WHERE brand = '比亚迪' AND date LIKE '2023-06%';

-- 计算吉利品牌2023年6月的总销量
SELECT SUM(sales_volume) as total_sales
FROM vehicle_sales
WHERE brand = '吉利' AND date LIKE '2023-06%';

-- 计算同比增长率（需要当期和去年同期数据）
SELECT 
    (SUM(CASE WHEN date LIKE '2023-06%' THEN sales_volume ELSE 0 END) - 
     SUM(CASE WHEN date LIKE '2022-06%' THEN sales_volume ELSE 0 END)) * 100.0 /
    SUM(CASE WHEN date LIKE '2022-06%' THEN sales_volume ELSE 0 END) as yoy_growth
FROM vehicle_sales
WHERE brand = '吉利';
```

---

### 表2: market_share (市场份额表)

**用途：** 存储各品牌车型的市场占有率数据

**字段：**
- `indicator_id` (TEXT): 指标ID
- `brand` (TEXT): 品牌名称
- `model` (TEXT): 车型名称或统计分类
- `market_share` (REAL): 市场份额（单位：%）
- `date` (TEXT): 日期（格式：YYYY-MM-DD）

**索引：**
- `idx_share_brand`: brand字段索引
- `idx_share_date`: date字段索引

**数据量：** 1,051行

**示例查询：**
```sql
-- 查询比亚迪在2023年6月的市场份额
SELECT brand, model, market_share, date
FROM market_share
WHERE brand = '比亚迪' AND date LIKE '2023-06%';
```

---

## 重要说明

### 1. 同比/环比计算规则
**不要直接使用原始数据中的"月同比"字段！** 应该用销量数据计算：

- **同比增长率** = (当期销量 - 去年同期销量) / 去年同期销量 × 100%
- **环比增长率** = (当期销量 - 上月销量) / 上月销量 × 100%

### 2. 品牌销量聚合
品牌销量 = 该品牌所有车型销量之和

```sql
SELECT brand, SUM(sales_volume) as total_sales
FROM vehicle_sales
WHERE date = '2023-06-01'
GROUP BY brand;
```

### 3. 时间范围
- 数据时间范围：2005-01 ~ 2030-12
- 日期格式：YYYY-MM-DD（月度数据统一为每月1日）
