"""
Baseline Agent Enhanced - LLM生成过滤条件
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../packages/core/src'))

import pandas as pd
from openai import OpenAI
import json
import re
from dotenv import load_dotenv

# 加载环境变量
env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
print(f"[OK] Load env: {env_file}")
load_dotenv(env_file)

class EnhancedBaselineAgent:
    """优化的Baseline Agent - LLM生成pandas过滤条件"""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)

        self.client = OpenAI(
            api_key=os.getenv('BASELINE_OPENAI_API_KEY'),
            base_url=os.getenv('BASELINE_OPENAI_API_BASE')
        )
        self.model = os.getenv('BASELINE_MODEL', 'qwen-flash')

        # 获取数据样例
        self.sample_data = self.df.head(5).to_string()
        self.columns = list(self.df.columns)

        print(f"[OK] Loaded CSV: {len(self.df)} rows")
        print(f"[OK] Columns: {self.columns}")
        print(f"[OK] Model: {self.model}")
    
    def _generate_filter_conditions(self, question: str, no_data_history: list = None) -> dict:
        """LLM生成过滤条件（提取时间信息和品牌/车型关键词）"""
        feedback_msg = ""
        if no_data_history:
            feedback_msg = f"\n\n【重要反馈】\n以下时间范围未找到数据：{', '.join(no_data_history)}\n请尝试其他可能的时间范围或更灵活的时间解析策略。"

        prompt = f"""你是数据过滤专家。我们有一个CSV文件，包含汽车销量数据。

【数据结构】
列名: {self.columns}

【数据样例】
{self.sample_data}

【字段说明】
- indicator_key: 指标ID
- display_name: 格式为"指标类型：品牌_车型：频率"或"指标类型：品牌_车型A、车型B：频率"
  * 示例："乘用车销量市场份额：国内制造+CKD_1.0L以下：月"（市场份额类，使用+）
  * 示例："乘用车销量：上汽通用_凯迪拉克CT5、CT6：月"（销量类，使用_或、）
  * 示例："乘用车销量：比亚迪_海豚：月"（销量类，使用_）
- 89%的销量数据使用"_"或"、"分隔品牌和车型
- 品牌和车型在"："之后、"："之前，用"_"或"、"分隔
- data_time: 日期（格式：YYYY-MM-DD）
{feedback_msg}

【用户问题】
{question}

【任务】
分析问题，提取时间信息和品牌/车型关键词。返回JSON：
{{
    "time_start": "开始时间（YYYY-MM格式，如无则null）",
    "time_end": "结束时间（YYYY-MM格式，如无则null）",
    "need_comparison": true/false,
    "comparison_time": "对比期时间（YYYY-MM格式，如无则null）",
    "brand_keywords": ["品牌关键词1", "品牌关键词2", ...],
    "model_keywords": ["车型关键词1", "车型关键词2", ...]
}}

【提取规则】
1. 时间提取：
   - 如果问题只提到一个时间点（如"2023-06"），time_start和time_end都设为该时间
   - 如果问题提到时间范围（如"2023年上半年"），提取开始和结束时间
   - 如果问题未明确时间，time_start和time_end都设为null
   - 如果之前尝试的时间没有数据，尝试相邻月份或更宽泛范围

2. 品牌/车型提取：
   - 从问题中提取品牌名（如"一汽大众"、"比亚迪"、"上汽通用"等）
   - 从问题中提取车型名（如"海豚"、"揽境"、"凯迪拉克CT5"等）
   - 如果问品牌总销量，model_keywords为空数组
   - 如果问"全系"、"所有车型"等，model_keywords为空数组

3. 同比/环比：
   - 同比：comparison_time设为去年同期（如2023-06的同比，comparison_time="2022-06"）
   - 环比：comparison_time设为上期（如2023-06的环比，comparison_time="2023-05"）
   - need_comparison设为true

【重要】
- 如果找不到品牌/车型，brand_keywords和model_keywords都设为空数组
- 空数组表示不过滤品牌/车型，时间过滤后所有数据都传给LLM分析

只返回JSON。"""
        
        print(f"🧠 LLM生成过滤条件...")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        
        result_text = response.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            conditions = json.loads(json_match.group())
        else:
            conditions = json.loads(result_text)

        print(f"📋 过滤条件:")
        print(f"   品牌关键词: {conditions.get('brand_keywords')}")
        print(f"   车型关键词: {conditions.get('model_keywords')}")
        print(f"   时间范围: {conditions.get('time_start')} ~ {conditions.get('time_end')}")
        print(f"   需要对比: {conditions.get('need_comparison')}")

        return conditions
    
    def _filter_data(self, conditions: dict) -> pd.DataFrame:
        """
        根据条件过滤数据
        改进：先按时间过滤，再按品牌/车型关键词过滤，减少传给LLM的数据量
        """
        filtered = self.df.copy()

        # 1. 时间过滤（范围查询）
        time_start = conditions.get('time_start')
        time_end = conditions.get('time_end')
        comparison_time = conditions.get('comparison_time')
        brand_keywords = conditions.get('brand_keywords', [])
        model_keywords = conditions.get('model_keywords', [])

        if time_start or time_end or comparison_time:
            filtered = filtered.copy()
            filtered['time_prefix'] = filtered['data_time'].str[:7]

            time_mask = pd.Series([False] * len(filtered), index=filtered.index)

            # 如果有开始和结束时间，使用范围查询
            if time_start and time_end:
                time_mask |= (filtered['time_prefix'] >= time_start) & (filtered['time_prefix'] <= time_end)
            elif time_start:
                time_mask |= (filtered['time_prefix'] == time_start)
            elif time_end:
                time_mask |= (filtered['time_prefix'] == time_end)

            # 对比期单独处理
            if comparison_time:
                time_mask |= (filtered['time_prefix'] == comparison_time)

            filtered = filtered[time_mask]
            filtered = filtered.drop(columns=['time_prefix'])

        print(f"📊 时间筛选结果: {len(filtered)}行")

        # 2. 品牌/车型关键词过滤
        if brand_keywords or model_keywords:
            keyword_mask = pd.Series([True] * len(filtered), index=filtered.index)

            # 品牌关键词过滤
            if brand_keywords:
                brand_mask = pd.Series([False] * len(filtered), index=filtered.index)
                for keyword in brand_keywords:
                    brand_mask |= filtered['display_name'].str.contains(keyword, na=False)
                keyword_mask &= brand_mask

            # 车型关键词过滤
            if model_keywords:
                model_mask = pd.Series([False] * len(filtered), index=filtered.index)
                for keyword in model_keywords:
                    model_mask |= filtered['display_name'].str.contains(keyword, na=False)
                keyword_mask &= model_mask

            filtered = filtered[keyword_mask]
            print(f"📊 关键词筛选结果: {len(filtered)}行")

        return filtered
    
    def query(self, question: str, verbose: bool = True):
        """
        查询方法
        :param question: 问题文本
        :param verbose: 是否显示详细输出（测试时设为False）
        :return: 结构化结果字典
        """
        if verbose:
            print(f"\n{'='*80}")
            print(f"问题: {question}")
            print(f"{'='*80}")
        
        # 重试机制：最多3次
        max_retries = 3
        filtered_data = None
        conditions_history = []
        no_data_history = []  # 记录哪些时间没有数据

        for attempt in range(max_retries):
            # 1. LLM生成过滤条件
            if verbose and attempt > 0:
                print(f"\n🔄 重试 {attempt}/{max_retries-1}...")

            # 如果之前没有找到数据，在prompt中反馈
            if attempt > 0 and no_data_history:
                print(f"⚠️  提示：以下时间没有数据：{', '.join(no_data_history)}")

            conditions = self._generate_filter_conditions(question, no_data_history)
            conditions_history.append(conditions)

            # 2. 过滤数据
            filtered_data = self._filter_data(conditions)

            if len(filtered_data) > 0:
                break
            else:
                # 记录没有数据的时间范围
                time_range = conditions.get('time_start') or conditions.get('time_end')
                if time_range:
                    no_data_history.append(time_range)

        # 构建结果
        result = {
            "question": question,
            "success": False,
            "answer": None,
            "filtered_rows": 0,
            "conditions": None,
            "error": None,
            "tokens": None,
            "duration_ms": None
        }

        if filtered_data is None or len(filtered_data) == 0:
            result["success"] = True  # 改为True，因为这是正常情况
            result["answer"] = "【答案：null】"  # 直接返回null
            result["conditions"] = conditions_history[-1]
            
            if verbose:
                print("\n⚠️  未找到数据")
                print("【答案：null】")
            
            return result
        
        result["filtered_rows"] = len(filtered_data)
        result["conditions"] = conditions_history[-1]
        
        # 3. LLM分析数据
        context_text = filtered_data.to_string()

        prompt = f"""基于以下数据回答问题。

【数据说明】
- display_name格式："指标类型：品牌_车型：频率"或"指标类型：品牌_车型A、车型B：频率"
  * 示例："乘用车销量市场份额：国内制造+CKD_1.0L以下：月"（市场份额类）
  * 示例："乘用车销量：上汽通用_凯迪拉克CT5、CT6：月"（销量类）
  * 示例："乘用车销量：比亚迪_海豚：月"（销量类）
  * 销量数据使用"_"或"、"分隔品牌和车型
- 品牌+车型构成完整描述
- unit可能是"%"或"辆"等

【你的任务】
1. **先识别问题中询问的品牌和车型**
2. **从数据中筛选出所有匹配的记录**（基于display_name中的品牌和车型）
3. **按照计算规则计算答案**

【数据筛选规则】
- 如果问题问"一汽大众揽境"，需要筛选display_name包含"一汽大众"和"揽境"的记录
- 如果问题问"比亚迪海豚"，需要筛选display_name包含"比亚迪"和"海豚"的记录
- 如果问题问品牌总销量，需要筛选该品牌下所有车型的记录
- 注意：品牌和车型可能在display_name的不同位置，需要包含两者才匹配

【计算规则】
1. 同比/环比必须用销量数据计算，不能直接使用"月同比"字段
   - 同比 = (当期销量总和 - 去年同期销量总和) / 去年同期销量总和 × 100%
   - 环比 = (当期销量总和 - 上期销量总和) / 上期销量总和 × 100%
   - **同比/环比结果必须保留14位小数**
2. 品牌销量 = 该品牌所有车型销量之和（品牌相同的所有记录）
3. 只使用display_name包含"：月"且unit为"辆"的销量数据
4. 如果问"全系"或"总销量"，需要求和所有相关记录

数据：
{context_text}

问题：{question}

【交互风格要求】
- **简洁清晰**：说话要简洁清晰，抓住要点，不要冗长啰嗦
- **主动告知**：调用工具时要告诉用户你在做什么，让用户了解你的行动和思考过程
- **及时反馈**：执行耗时操作前说明"正在分析..."、"正在查询..."等
- **格式规范**：避免使用*号，用-号表示列表项，保持输出整洁专业
- **数值答案格式**：回答销量、数量等数值问题时，对每个问题单独输出格式：【答案：数字】

【⚠️ 最终答案格式要求（必须遵守）】
**所有数值查询问题，必须在回答末尾单独一行输出标准答案格式：**

格式：【答案：具体数值】

示例：
- 单个数值：【答案：4045】
- 百分比（14位小数）：【答案：-37.61942154168302%】
- 带单位：【答案：4045 辆】
- 排名结果：【答案：国内制造, 1349499 辆】
- 月度数据：【答案：1月: 4890辆; 2月: 3217辆; 3月: 7370辆】
- 数据不存在：【答案：null】

**❗ 绝对禁止编造数据：**
- 答案必须100%来自SQL查询结果
- 如果SQL结果中没有某个月份的数据，答案中也不能包含该月份
- 绝不允许推测、估算或编造任何数值
- 如果数据缺失，必须在答案中明确标注为null或缺失"""
        
        if verbose:
            print(f"🤖 LLM生成答案...")

        import time
        start_time = time.time()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )

        answer = response.choices[0].message.content
        usage = response.usage

        duration_ms = (time.time() - start_time) * 1000

        if verbose:
            print(f"\n📊 Token消耗:")
            print(f"   输入: {usage.prompt_tokens}")
            print(f"   输出: {usage.completion_tokens}")
            print(f"   总计: {usage.total_tokens}")
            print(f"\n{'='*80}")
            print(f"答案:")
            print(f"{'='*80}")
            print(answer)
            print(f"{'='*80}\n")

        # 检查答案是否为null（新格式：【答案：null】）
        if "【答案：null】" in answer or "【答案： null】" in answer:
            result["success"] = False
            result["answer"] = answer
            result["error"] = "LLM未能从筛选后的数据中找到匹配的品牌/车型"
            # 提供详细分析
            if verbose:
                print("⚠️  LLM无法从数据中找到匹配项，正在分析原因...")
                analysis = self._analyze_data_availability(question, filtered_data)
                result["error_analysis"] = analysis
                print(f"\n分析结果：\n{analysis}")
        else:
            result["success"] = True
            result["answer"] = answer

        result["tokens"] = {
            "prompt": usage.prompt_tokens,
            "completion": usage.completion_tokens,
            "total": usage.total_tokens
        }
        result["duration_ms"] = round(duration_ms, 2)

        return result

    def _analyze_no_data(self, question: str, no_data_history: list) -> str:
        """
        分析为什么没有找到数据
        :param question: 用户问题
        :param no_data_history: 没有数据的时间列表
        :return: LLM分析结果
        """
        prompt = f"""用户问了一个关于汽车销量的问题，但是我们没有找到数据。

【用户问题】
{question}

【未找到数据的时间范围】
{', '.join(no_data_history)}

【数据概况】
- 总行数: {len(self.df)}
- 数据时间范围: {self.df['data_time'].min()} ~ {self.df['data_time'].max()}
- 可用品牌示例: {', '.join(self.df['display_name'].str.split('+').str[1].str.split('：').str[0].unique()[:10].tolist())}

【你的任务】
分析为什么没有找到数据，并给用户一个清晰的解释。请考虑以下可能的原因：
1. 问题中提到的时间在数据范围内吗？
2. 问题中提到的品牌/车型在数据中存在吗？
3. 是否有拼写错误或表述方式不同？
4. 是否需要更宽泛的时间范围？

请用简洁、友好的语言解释原因，并提供建议。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"分析失败: {str(e)}"

    def _analyze_data_availability(self, question: str, filtered_data: pd.DataFrame) -> str:
        """
        分析筛选后的数据中为什么没有匹配的品牌/车型
        :param question: 用户问题
        :param filtered_data: 筛选后的数据
        :return: LLM分析结果
        """
        # 提取数据中的品牌和车型
        display_names = filtered_data['display_name'].unique()

        prompt = f"""用户问了一个关于汽车销量的问题。我们已经按时间筛选了数据，但是LLM仍然无法从这些数据中找到匹配的品牌/车型。

【用户问题】
{question}

【筛选后的数据（共{len(filtered_data)}行）】
前20行的display_name:
{chr(10).join(display_names[:20])}

【你的任务】
分析为什么没有找到匹配的品牌/车型。请检查：
1. 问题中提到的品牌是否在数据中？
2. 问题中提到的车型是否在数据中？
3. 是否有表述方式的差异（如"一汽大众" vs "一汽大众+"）？
4. 数据中的display_name格式是否理解正确？

请给出清晰的分析，并建议可能的解决方案。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"分析失败: {str(e)}"


def main():
    # 支持从任意目录运行
    csv_name = os.getenv('BASELINE_CSV_PATH', '数据源_销量.csv')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, csv_name)
    
    if not os.path.exists(csv_path):
        print(f"❌ CSV文件不存在: {csv_path}")
        return
    
    print("\n" + "="*80)
    print("🚀 Baseline Agent Enhanced - LLM生成过滤条件")
    print("="*80)
    print("流程：LLM生成过滤条件 → pandas过滤 → LLM分析")
    print("="*80 + "\n")
    
    agent = EnhancedBaselineAgent(csv_path)
    
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
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
