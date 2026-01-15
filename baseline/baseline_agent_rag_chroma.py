"""
Baseline2 Agent - 使用Chroma持久化向量数据库
"""

import sys
import os

# Windows UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../packages/core/src'))

import pandas as pd
import chromadb
from openai import OpenAI
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

class BaselineAgentChroma:
    """使用Chroma的RAG方案"""
    
    def __init__(self, csv_path: str, rebuild: bool = False):
        import time
        t0 = time.time()
        
        self.csv_path = csv_path
        t1 = time.time()
        self.df = pd.read_csv(csv_path)
        t2 = time.time()
        print(f"⏱️  读取CSV: {t2-t1:.3f}秒 ({len(self.df)}行)")
        
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('OPENAI_API_BASE')
        )
        self.model = os.getenv('AFC_MODEL', 'qwen-plus-2025-12-01')
        t3 = time.time()
        print(f"⏱️  初始化OpenAI客户端: {t3-t2:.3f}秒")
        
        # 初始化Chroma - 使用绝对路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        chroma_path = os.path.join(os.path.dirname(script_dir), "chroma_db")
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        print(f"📁 向量库路径: {chroma_path}")
        t4 = time.time()
        print(f"⏱️  连接Chroma: {t4-t3:.3f}秒")
        
        if rebuild:
            try:
                chroma_client.delete_collection("sales_data")
                print("🗑️  删除旧数据")
            except:
                pass
        
        self.collection = chroma_client.get_or_create_collection(
            name="sales_data",
            metadata={"hnsw:space": "cosine"}
        )
        t5 = time.time()
        print(f"⏱️  获取/创建集合: {t5-t4:.3f}秒")
        
        # 检查是否需要初始化
        if self.collection.count() == 0:
            print("🔄 首次初始化，正在处理数据...")
            self._initialize_data()
        else:
            print(f"✅ 向量库已有: {self.collection.count()}条")
        
        t_total = time.time() - t0
        print(f"\n⏱️  总耗时: {t_total:.3f}秒")
    
    def _initialize_data(self):
        """初始化数据到Chroma"""
        texts = []
        metadatas = []
        ids = []
        
        for idx, row in self.df.iterrows():
            display = row['display_name']
            
            if '：' in display and '_' in display:
                parts = display.split('：')
                if len(parts) >= 2:
                    brand_model = parts[1].split('：')[0]
                    date = row['data_time'][:7]
                    value = row['ind_value']
                    unit = row['unit']
                    
                    text = f"{date}，{brand_model}的销量为{value}{unit}"
                    texts.append(text)
                    metadatas.append({
                        'indicator_key': str(row['indicator_key']),
                        'display_name': str(row['display_name']),
                        'unit': str(row['unit']),
                        'ind_value': float(row['ind_value']),
                        'data_time': str(row['data_time'])
                    })
                    ids.append(f"doc_{idx}")
        
        print(f"📝 处理完成: {len(texts)}条文本")
        
        # 分批添加到Chroma
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_meta = metadatas[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            
            self.collection.add(
                documents=batch_texts,
                metadatas=batch_meta,
                ids=batch_ids
            )
            print(f"   进度: {min(i+batch_size, len(texts))}/{len(texts)}")
        
        print(f"✅ 向量库构建完成")
    
    def _retrieve(self, question: str, top_k: int = 50) -> List[Dict]:
        """检索"""
        results = self.collection.query(
            query_texts=[question],
            n_results=top_k
        )
        
        retrieved = []
        for i in range(len(results['ids'][0])):
            retrieved.append({
                'text': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i] if 'distances' in results else 0
            })
        
        print(f"📊 检索到{len(retrieved)}条相关数据")
        for i, r in enumerate(retrieved[:3]):
            print(f"   {i+1}. {r['text'][:50]}...")
        
        return retrieved
    
    def query(self, question: str) -> str:
        """处理查询"""
        print(f"\n{'='*80}")
        print(f"问题: {question}")
        print(f"{'='*80}")
        
        results = self._retrieve(question, top_k=50)
        
        if not results:
            return "❌ 未找到相关数据"
        
        context_data = pd.DataFrame([r['metadata'] for r in results])
        context_text = context_data.to_string()
        
        prompt = f"""基于以下数据回答问题。

数据：
{context_text}

问题：{question}

请给出准确答案。"""
        
        print(f"🤖 调用LLM...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            answer = response.choices[0].message.content
            
            # Token统计
            usage = response.usage
            print(f"\n📊 Token消耗:")
            print(f"   输入: {usage.prompt_tokens}")
            print(f"   输出: {usage.completion_tokens}")
            print(f"   总计: {usage.total_tokens}")
            
            print(f"\n{'='*80}")
            print(f"LLM回答:")
            print(f"{'='*80}")
            print(answer)
            print(f"{'='*80}\n")
            
            return answer
            
        except Exception as e:
            return f"❌ LLM调用失败: {e}"


def main():
    """运行Baseline2 Chroma"""
    csv_path = "baseline/数据源_销量.csv"
    
    if not os.path.exists(csv_path):
        print(f"❌ CSV文件不存在: {csv_path}")
        return
    
    print("\n" + "="*80)
    print("🚀 Baseline2 Agent - Chroma持久化向量库")
    print("="*80)
    print("输入 /quit 退出, /rebuild 重建向量库")
    print("="*80 + "\n")
    
    agent = BaselineAgentChroma(csv_path)
    
    while True:
        try:
            question = input("\n💬 请输入问题: ").strip()
            
            if question.lower() in ['/quit', '/exit']:
                print("\n👋 再见！")
                break
            
            if question.lower() == '/rebuild':
                print("🔄 重建向量库...")
                agent = BaselineAgentChroma(csv_path, rebuild=True)
                continue
            
            if not question:
                continue
            
            agent.query(question)
            
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    main()
