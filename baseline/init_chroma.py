"""快速初始化Chroma向量数据库"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from baseline_agent_rag_chroma import BaselineAgentChroma
import time

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

if __name__ == "__main__":
    csv_path = os.path.join(os.path.dirname(__file__), "课题数据(1).csv")
    
    print("="*80)
    print("初始化Chroma向量数据库")
    print("="*80)
    
    start = time.time()
    agent = BaselineAgentChroma(csv_path, rebuild=True)
    init_time = time.time() - start
    
    print(f"\n初始化完成！耗时: {init_time:.2f}秒")
    print(f"向量数量: {agent.collection.count()}条")
    print(f"存储位置: ./chroma_db")
    print("\n下次启动将直接加载，无需重新初始化！")
