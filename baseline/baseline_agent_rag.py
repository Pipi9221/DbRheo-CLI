"""
Baseline2 Agent - RAG向量检索方案
使用向量数据库进行语义检索，提升检索准确率
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../packages/core/src'))

import pandas as pd
import numpy as np
from openai import OpenAI
from typing import List, Dict
import re
from dotenv import load_dotenv

# 加载环境变量
env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
print(f"✓ 加载环境变量: {env_file}")
load_dotenv(env_file)

class BaselineAgentRAG:
    """
    Baseline2 - RAG向量检索方案
    
    改进：
    1. 数据预处理：CSV转自然语言
    2. 向量化：使用embedding模型
    3. 语义检索：向量相似度匹配
    """
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)

        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=os.getenv('BASELINE_OPENAI_API_KEY'),
            base_url=os.getenv('BASELINE_OPENAI_API_BASE')
        )
        self.model = os.getenv('BASELINE_MODEL', 'qwen-flash')

        print(f"✅ 加载CSV: {len(self.df)}行")
        print(f"✅ 使用模型: {self.model}")

        # 数据预处理
        self.texts, self.metadata = self._preprocess_data()
        print(f"✅ 数据预处理完成: {len(self.texts)}条文本")

        # 构建向量库
        self.vectors = self._build_vectors()
        print(f"✅ 向量库构建完成")
    
    def _preprocess_data(self) -> tuple:
        """数据预处理：CSV转自然语言"""
        texts = []
        metadata = []
        
        for idx, row in self.df.iterrows():
            # 解析display_name提取品牌和车型
            display = row['display_name']
            
            # 提取品牌_车型
            if '：' in display and '_' in display:
                parts = display.split('：')
                if len(parts) >= 2:
                    brand_model = parts[1].split('：')[0]
                    
                    # 转换成自然语言
                    date = row['data_time'][:7]  # 2012-12-01 -> 2012-12
                    value = row['ind_value']
                    unit = row['unit']
                    
                    text = f"{date}，{brand_model}的销量为{value}{unit}"
                    texts.append(text)
                    metadata.append(row.to_dict())
        
        return texts, metadata
    
    def _build_vectors(self) -> np.ndarray:
        """构建向量库（使用OpenAI embedding）"""
        print("🔄 正在生成向量...")
        
        vectors = []
        batch_size = 25  # 通义千问限制最多25条
        
        for i in range(0, len(self.texts), batch_size):
            batch = self.texts[i:i+batch_size]
            
            try:
                response = self.client.embeddings.create(
                    model="text-embedding-v1",
                    input=batch
                )
                
                batch_vectors = [item.embedding for item in response.data]
                vectors.extend(batch_vectors)
                
                print(f"   进度: {min(i+batch_size, len(self.texts))}/{len(self.texts)}")
                
            except Exception as e:
                print(f"⚠️  向量化失败: {e}")
                # 使用简单的TF-IDF作为fallback
                return self._build_tfidf_vectors()
        
        return np.array(vectors)
    
    def _build_tfidf_vectors(self) -> np.ndarray:
        """Fallback: 使用TF-IDF"""
        from sklearn.feature_extraction.text import TfidfVectorizer
        
        print("⚠️  使用TF-IDF作为fallback")
        vectorizer = TfidfVectorizer(max_features=512)
        vectors = vectorizer.fit_transform(self.texts).toarray()
        self.vectorizer = vectorizer
        return vectors
    
    def _retrieve(self, question: str, top_k: int = 20) -> List[Dict]:
        """向量检索"""
        # 问题向量化
        try:
            response = self.client.embeddings.create(
                model="text-embedding-v1",
                input=[question]
            )
            query_vector = np.array(response.data[0].embedding)
        except:
            # Fallback to TF-IDF
            if hasattr(self, 'vectorizer'):
                query_vector = self.vectorizer.transform([question]).toarray()[0]
            else:
                return []
        
        # 计算相似度
        similarities = np.dot(self.vectors, query_vector)
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        # 返回结果
        results = []
        for idx in top_indices:
            results.append({
                'text': self.texts[idx],
                'metadata': self.metadata[idx],
                'score': float(similarities[idx])
            })
        
        print(f"📊 检索到{len(results)}条相关数据")
        for i, r in enumerate(results[:3]):
            print(f"   {i+1}. {r['text'][:50]}... (得分: {r['score']:.3f})")
        
        return results
    
    def query(self, question: str) -> str:
        """处理查询"""
        print(f"\n{'='*80}")
        print(f"问题: {question}")
        print(f"{'='*80}")
        
        # 向量检索
        results = self._retrieve(question, top_k=20)
        
        if not results:
            return "❌ 未找到相关数据"
        
        # 构建上下文
        context_data = pd.DataFrame([r['metadata'] for r in results])
        context_text = context_data.to_string()
        
        # 调用LLM
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
            print(f"\n{'='*80}")
            print(f"LLM回答:")
            print(f"{'='*80}")
            print(answer)
            print(f"{'='*80}\n")
            
            return answer
            
        except Exception as e:
            return f"❌ LLM调用失败: {e}"


def main():
    """运行Baseline2"""
    # CSV文件路径（从环境变量读取）
    csv_name = os.getenv('BASELINE_CSV_PATH', '数据源_销量.csv')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, csv_name)
    
    if not os.path.exists(csv_path):
        print(f"❌ CSV文件不存在: {csv_path}")
        return
    
    print("\n" + "="*80)
    print("🚀 Baseline2 Agent - RAG向量检索方案")
    print("="*80)
    print("使用向量数据库进行语义检索")
    print("输入 /quit 退出")
    print("="*80 + "\n")
    
    agent = BaselineAgentRAG(csv_path)
    
    while True:
        try:
            question = input("\n💬 请输入问题: ").strip()
            
            if question.lower() in ['/quit', '/exit']:
                print("\n👋 再见！")
                break
            
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
