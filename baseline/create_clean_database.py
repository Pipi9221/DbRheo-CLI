"""
基于清洗后的数据创建新的SQLite数据库
表结构：
1. vehicle_sales - 车型销量表（单位：辆）
2. market_share - 市场份额表（单位：%）
"""
import pandas as pd
import sqlite3
import os

# 读取数据源
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "数据源_销量.csv")
df = pd.read_csv(csv_path)

print(f"加载数据: {len(df)}行")

# 分离销量数据和市场份额数据
sales_df = df[df['unit'] == '辆'].copy()
share_df = df[df['unit'] == '%'].copy()

print(f"销量数据: {len(sales_df)}行")
print(f"市场份额数据: {len(share_df)}行")

# 解析display_name：乘用车销量：品牌_车型：月
def parse_display_name(display_name):
    """解析display_name，提取品牌和车型"""
    try:
        # 格式：乘用车销量：品牌_车型：月
        parts = display_name.split('：')
        if len(parts) >= 3:
            brand_model = parts[1]
            if '_' in brand_model:
                brand, model = brand_model.split('_', 1)
                return brand, model
    except:
        pass
    return None, None

# 处理销量数据
sales_df[['brand', 'model']] = sales_df['display_name'].apply(
    lambda x: pd.Series(parse_display_name(x))
)
sales_df = sales_df.dropna(subset=['brand', 'model'])

# 处理市场份额数据
share_df[['brand', 'model']] = share_df['display_name'].apply(
    lambda x: pd.Series(parse_display_name(x))
)
share_df = share_df.dropna(subset=['brand', 'model'])

print(f"\n解析后:")
print(f"销量数据: {len(sales_df)}行")
print(f"市场份额数据: {len(share_df)}行")

# 创建数据库
db_path = os.path.join(script_dir, "../db/vehicle_sales.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)

conn = sqlite3.connect(db_path)

# 创建销量表
sales_table = sales_df[[
    'indicator_key', 'brand', 'model', 'ind_value', 'data_time'
]].rename(columns={
    'indicator_key': 'indicator_id',
    'ind_value': 'sales_volume',
    'data_time': 'date'
})

sales_table.to_sql('vehicle_sales', conn, if_exists='replace', index=False)

# 创建市场份额表
share_table = share_df[[
    'indicator_key', 'brand', 'model', 'ind_value', 'data_time'
]].rename(columns={
    'indicator_key': 'indicator_id',
    'ind_value': 'market_share',
    'data_time': 'date'
})

share_table.to_sql('market_share', conn, if_exists='replace', index=False)

# 创建索引
conn.execute('CREATE INDEX IF NOT EXISTS idx_sales_brand ON vehicle_sales(brand)')
conn.execute('CREATE INDEX IF NOT EXISTS idx_sales_date ON vehicle_sales(date)')
conn.execute('CREATE INDEX IF NOT EXISTS idx_share_brand ON market_share(brand)')
conn.execute('CREATE INDEX IF NOT EXISTS idx_share_date ON market_share(date)')

conn.commit()

# 显示表结构
print(f"\n✅ 数据库创建完成: {db_path}")
print(f"\n表1: vehicle_sales (车型销量)")
print(f"  - 行数: {len(sales_table)}")
print(f"  - 字段: indicator_id, brand, model, sales_volume, date")
print(f"  - 单位: 辆")

print(f"\n表2: market_share (市场份额)")
print(f"  - 行数: {len(share_table)}")
print(f"  - 字段: indicator_id, brand, model, market_share, date")
print(f"  - 单位: %")

# 显示样例
print(f"\n📋 vehicle_sales 样例:")
print(pd.read_sql("SELECT * FROM vehicle_sales LIMIT 5", conn))

print(f"\n📋 market_share 样例:")
print(pd.read_sql("SELECT * FROM market_share LIMIT 5", conn))

conn.close()
