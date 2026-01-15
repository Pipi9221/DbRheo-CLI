"""
基线Agent - 模拟通义千问等平台处理大文件的方式
使用分块+检索策略，展示纯LLM方案的局限性
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../packages/core/src'))

import pandas as pd
from openai import OpenAI
from typing import List, Dict
import re
from dotenv import load_dotenv

# 加载环境变量
env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
print(f"✓ 加载环境变量: {env_file}")
load_dotenv(env_file)

class BaselineAgent:
    """
    基线Agent - 模拟主流AI平台的文件处理方式
    
    策略：
    1. 将CSV文件分块（每块100-200行）
    2. 根据用户问题检索相关块（关键词匹配）
    3. 将相关块提供给LLM进行分析和计算
    
    局限性：
    - 可能遗漏数据（检索不准确）
    - 计算可能出错（LLM计算能力有限）
    - 不稳定（每次结果可能不同）
    """
    
    def __init__(self, csv_path: str, chunk_size: int = None):
        """
        初始化基线Agent

        Args:
            csv_path: CSV文件路径
            chunk_size: 每个数据块的行数（None则从环境变量读取）
        """
        self.csv_path = csv_path
        self.chunk_size = chunk_size or int(os.getenv('BASELINE_CHUNK_SIZE', '150'))
        self.df = pd.read_csv(csv_path)
        self.chunks = self._create_chunks()

        # 初始化OpenAI客户端（使用通义千问）
        self.client = OpenAI(
            api_key=os.getenv('BASELINE_OPENAI_API_KEY'),
            base_url=os.getenv('BASELINE_OPENAI_API_BASE')
        )
        self.model = os.getenv('BASELINE_MODEL', 'qwen-flash')

        print(f"✅ 加载CSV文件: {len(self.df)}行数据")
        print(f"✅ 分块策略: 每块{self.chunk_size}行，共{len(self.chunks)}块")
        print(f"✅ 使用模型: {self.model}")
    
    def _create_chunks(self) -> List[Dict]:
        """将数据分块"""
        chunks = []
        for i in range(0, len(self.df), self.chunk_size):
            chunk_df = self.df.iloc[i:i+self.chunk_size]
            chunks.append({
                'id': len(chunks),
                'start_row': i,
                'end_row': min(i+self.chunk_size, len(self.df)),
                'data': chunk_df,
                'text': chunk_df.to_string()
            })
        return chunks
    
    def _retrieve_relevant_chunks(self, question: str, top_k: int = 10) -> List[Dict]:
        """
        改进的检索策略：更多关键词+更多块
        """
        # 提取所有可能的关键词
        keywords = []
        
        # 从问题中提取品牌和车型（更智能）
        # 分词提取
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', question)
        for word in words:
            if len(word) >= 2:  # 至少2个字符
                keywords.append(word)
        
        # 年份和月份
        years = re.findall(r'20\d{2}', question)
        keywords.extend(years)
        months = re.findall(r'(\d{1,2})月', question)
        keywords.extend([f"{m}月" for m in months])
        
        print(f"🔍 检索关键词: {keywords}")
        
        # 计算每个块的相关性得分
        scored_chunks = []
        for chunk in self.chunks:
            score = 0
            chunk_text = chunk['text']
            for keyword in keywords:
                # 关键词匹配得分
                count = chunk_text.count(str(keyword))
                if count > 0:
                    score += count * len(keyword)  # 长关键词权重更高
            
            if score > 0:
                scored_chunks.append((score, chunk))
        
        # 如果没找到，返回所有块（兜底策略）
        if not scored_chunks:
            print(f"⚠️  未找到匹配块，使用所有数据")
            return self.chunks
        
        # 按得分排序，取top_k
        scored_chunks.sort(reverse=True, key=lambda x: x[0])
        relevant_chunks = [chunk for score, chunk in scored_chunks[:top_k]]
        
        print(f"📊 检索到{len(relevant_chunks)}个相关数据块")
        for chunk in relevant_chunks[:3]:  # 只显示前3个
            print(f"   - 块{chunk['id']}: 第{chunk['start_row']}-{chunk['end_row']}行")
        if len(relevant_chunks) > 3:
            print(f"   ... 还有{len(relevant_chunks)-3}个块")
        
        return relevant_chunks
    
    def query(self, question: str) -> str:
        """
        处理用户查询
        
        Args:
            question: 用户问题
            
        Returns:
            LLM的回答
        """
        print(f"\n{'='*80}")
        print(f"问题: {question}")
        print(f"{'='*80}")
        
        # 1. 检索相关数据块
        relevant_chunks = self._retrieve_relevant_chunks(question, top_k=10)
        
        if not relevant_chunks:
            return "❌ 未找到相关数据"
        
        # 2. 构建上下文（将相关数据块合并）
        context_data = pd.concat([chunk['data'] for chunk in relevant_chunks])
        context_text = context_data.to_string()
        
        print(f"📝 上下文数据: {len(context_data)}行")
        
        # 3. 构建提示词
        prompt = f"""你是一个数据分析助手。基于以下CSV数据回答用户问题。

数据格式：品牌 | 车型 | 指标名称 | 日期 | 数值

数据内容：
{context_text}

用户问题：{question}

请仔细分析数据，进行必要的计算，并给出准确答案。如果需要汇总、同比、环比等计算，请明确列出计算过程。"""
        
        # 4. 调用LLM
        print(f"🤖 调用LLM...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1  # 降低温度以提高稳定性
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
    """运行基线Agent - 交互式CLI"""

    # CSV文件路径（从环境变量读取）
    csv_name = os.getenv('BASELINE_CSV_PATH', '数据源_销量.csv')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, csv_name)
    
    # 检查CSV文件是否存在
    if not os.path.exists(csv_path):
        print(f"❌ CSV文件不存在: {csv_path}")
        return
    
    # 显示欢迎信息
    print("\n" + "="*80)
    print("🔬 Baseline Agent - 纯LLM方案（方案A）")
    print("="*80)
    print("模拟通义千问等平台的文件处理方式：分块+检索+LLM计算")
    print("输入 /quit 或 /exit 退出")
    print("="*80 + "\n")
    
    # 初始化基线Agent
    agent = BaselineAgent(csv_path, chunk_size=150)
    
    # 交互式循环
    while True:
        try:
            # 获取用户输入
            question = input("\n💬 请输入问题: ").strip()
            
            # 处理退出命令
            if question.lower() in ['/quit', '/exit', 'quit', 'exit']:
                print("\n👋 再见！")
                break
            
            # 跳过空输入
            if not question:
                continue
            
            # 处理查询
            agent.query(question)
            
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except EOFError:
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    main()
