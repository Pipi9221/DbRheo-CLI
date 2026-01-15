# CSV 数据处理脚本

本目录包含处理 CSV 数据的脚本，用于数据拆分和数据库导入。

## 文件说明

- `split_csv.py` - 将原始CSV文件拆分为测试集和数据源
- `import_to_sqlite.py` - 将数据源导入SQLite数据库
- `README.md` - 本文件

## 使用方法

### 1. 拆分CSV文件

将 `课题数据(1).csv` 拆分为测试集和数据源：

```bash
cd baseline/data_scripts
python split_csv.py
```

**输出文件：**
- `../测试集_月同比.csv` - 包含月同比、环比等预计算指标（用于测试）
- `../数据源_销量.csv` - 包含原始销量数据和市场份额数据（用于数据库导入）

**拆分逻辑：**
- 测试集：`display_name` 包含"同比"或"环比"的数据
- 数据源：其他所有数据（销量和市场份额）

### 2. 导入SQLite数据库

将拆分后的数据源导入数据库：

```bash
cd baseline/data_scripts
python import_to_sqlite.py
```

**输出数据库：**
- `../../db/vehicle_sales.db` - SQLite数据库文件

**数据库表结构：**

#### 表1: vehicle_sales (车型销量表)
- `indicator_id` (TEXT) - 指标ID
- `brand` (TEXT) - 品牌名称
- `model` (TEXT) - 车型名称
- `sales_volume` (REAL) - 销量（单位：辆）
- `date` (TEXT) - 日期（格式：YYYY-MM-DD）

**索引：**
- `idx_sales_brand` - brand字段索引
- `idx_sales_date` - date字段索引

#### 表2: market_share (市场份额表)
- `indicator_id` (TEXT) - 指标ID
- `brand` (TEXT) - 品牌名称
- `model` (TEXT) - 车型名称
- `market_share` (REAL) - 市场份额（单位：%）
- `date` (TEXT) - 日期（格式：YYYY-MM-DD）

**索引：**
- `idx_share_brand` - brand字段索引
- `idx_share_date` - date字段索引

## 完整工作流程

1. **拆分数据**
   ```bash
   python split_csv.py
   ```

2. **导入数据库**
   ```bash
   python import_to_sqlite.py
   ```

3. **验证数据**
   ```bash
   # 使用sqlite3命令行工具
   sqlite3 ../../db/vehicle_sales.db

   # 查询表结构
   .schema vehicle_sales
   .schema market_share

   # 查询数据样例
   SELECT * FROM vehicle_sales LIMIT 5;
   SELECT * FROM market_share LIMIT 5;

   # 统计数据
   SELECT brand, COUNT(*) as count FROM vehicle_sales GROUP BY brand ORDER BY count DESC LIMIT 10;
   ```

## 数据说明

### 原始数据 (课题数据(1).csv)
- 总行数：约1.6万行
- 数据类型：销量数据、市场份额数据、预计算指标（同比/环比）
- 时间范围：2005-01 ~ 2030-12
- 日期格式：YYYY-MM-DD（月度数据统一为每月1日）

### 测试集 (测试集_月同比.csv)
- 包含月同比、环比等预计算指标
- 用于验证 AgentFetch-Calc-CLI 的计算准确性
- 不导入数据库，仅用于对比测试

### 数据源 (数据源_销量.csv)
- 包含原始销量数据（unit="辆"）
- 包含原始市场份额数据（unit="%"）
- 导入数据库供 AgentFetch-Calc-CLI 查询和分析

## 注意事项

1. **日期格式**：所有日期统一为 `YYYY-MM-DD` 格式
2. **单位标识**：
   - 销量数据：`unit="辆"`
   - 市场份额数据：`unit="%"`
   - 同比环比数据：`unit="%"` 且 `display_name` 包含"同比"或"环比"
3. **品牌车型解析**：从 `display_name` 字段解析，格式为"乘用车销量：品牌_车型：月"
4. **数据库路径**：默认为 `../../db/vehicle_sales.db`，可根据需要修改

## 错误处理

脚本包含完整的错误检查和日志输出：
- 数据拆分完整性验证
- 品牌车型解析统计
- 数据库导入行数统计
- 索引创建状态
- 样例数据展示

如遇到问题，请查看控制台输出的详细日志。
