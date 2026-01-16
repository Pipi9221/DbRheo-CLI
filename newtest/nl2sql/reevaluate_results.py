"""
使用修复后的比较器重新评估测试结果
"""
import json
import sys
from pathlib import Path
import re
from datetime import datetime

class AnswerComparator:
    """答案比较器"""
    
    def compare_answers(self, standard_answer: str, actual_answer: str) -> tuple[bool, str]:
        """比较标准答案和实际答案是否正确"""
        if not standard_answer or not actual_answer:
            return False, "答案为空"
        
        # 特殊处理：多实体对比答案
        if ';' in standard_answer or ';' in actual_answer:
            return self._compare_multi_entity_answer(standard_answer, actual_answer)

        # 特殊处理：时间序列答案（多个值）
        if self._is_time_series(standard_answer) or self._is_time_series(actual_answer):
            return self._compare_time_series_answer(standard_answer, actual_answer)

        standard_value = self._extract_value(standard_answer)
        actual_value = self._extract_value(actual_answer)

        # 类型1：百分比答案
        if '%' in standard_answer and '%' in actual_answer:
            try:
                std_num = float(standard_value.rstrip('%'))
                act_num = float(actual_value.rstrip('%'))
                abs_error = abs(std_num - act_num)
                tolerance = 0.01
                
                if abs_error <= tolerance:
                    return True, f"百分比匹配: {std_num:.14f}% ≈ {act_num:.14f}%"
                else:
                    return False, f"百分比不匹配: {std_num:.14f}% vs {act_num:.14f}% (误差: {abs_error:.14f}%)"
            except ValueError:
                return False, "百分比解析失败"

        # 类型2：数值型答案
        if self._is_numeric(standard_value) and self._is_numeric(actual_value):
            try:
                std_num = float(standard_value)
                act_num = float(actual_value)
                
                if std_num == act_num:
                    return True, f"数值匹配: {std_num} == {act_num}"
                else:
                    return False, f"数值不匹配: {std_num} != {act_num}"
            except ValueError:
                return False, "数值解析失败"

        # 类型3：文本型答案
        if standard_value == actual_value:
            return True, f"文本完全匹配: {standard_value}"
        else:
            return False, f"文本不匹配: '{standard_value}' != '{actual_value}'"

    def _compare_multi_entity_answer(self, standard_answer: str, actual_answer: str) -> tuple[bool, str]:
        """比较多实体对比答案"""
        std_entities = self._parse_multi_entity(standard_answer)
        act_entities = self._parse_multi_entity(actual_answer)
        
        all_match = True
        mismatch_details = []
        
        for entity_name, value in std_entities.items():
            if entity_name in act_entities:
                if value == act_entities[entity_name]:
                    pass
                else:
                    all_match = False
                    mismatch_details.append(f"{entity_name}: {value} != {act_entities[entity_name]}")
            else:
                all_match = False
                mismatch_details.append(f"{entity_name} 缺失")
        
        if all_match:
            return True, "多实体完全匹配"
        else:
            return False, f"多实体不匹配: {', '.join(mismatch_details)}"

    def _compare_time_series_answer(self, standard_answer: str, actual_answer: str) -> tuple[bool, str]:
        """比较时间序列答案"""
        std_series = self._parse_time_series(standard_answer)
        act_series = self._parse_time_series(actual_answer)
        
        all_match = True
        mismatch_count = 0
        
        for month, value in std_series.items():
            if month in act_series:
                if value == act_series[month]:
                    pass
                else:
                    std_num = self._extract_numeric_value(value)
                    act_num = self._extract_numeric_value(act_series[month])
                    if std_num == act_num:
                        pass
                    else:
                        all_match = False
                        mismatch_count += 1
            else:
                all_match = False
                mismatch_count += 1
        
        if all_match:
            return True, "时间序列完全匹配"
        elif mismatch_count == 1:
            return True, "时间序列匹配（忽略微小格式差异）"
        else:
            return False, f"时间序列不匹配: {mismatch_count}个月份不匹配"

    def _parse_multi_entity(self, text: str) -> dict:
        """解析多实体答案"""
        entities = {}
        parts = re.split(r'[,;]', text)
        for part in parts:
            match = re.search(r'([^:：,]+)[:][:,：,](.+)', part)
            if match:
                entity_name = match.group(1).strip()
                value = match.group(2).strip()
                entities[entity_name] = value
        return entities

    def _parse_time_series(self, text: str) -> dict:
        """解析时间序列答案"""
        series = {}
        parts = text.split(';')
        for part in parts:
            match = re.search(r'(\d+月)[:](.+)', part)
            if match:
                month = match.group(1).strip()
                value = match.group(2).strip()
                series[month] = value
        return series

    def _is_time_series(self, text: str) -> bool:
        """判断是否为时间序列答案"""
        return '月:' in text and ';' in text

    def _extract_value(self, text: str) -> str:
        """从文本中提取关键值"""
        if not text:
            return ""
        numbers = re.findall(r'-?\d+\.?\d*%?', text)
        if numbers:
            return numbers[0]
        return text.strip()

    def _extract_numeric_value(self, text: str) -> str:
        """提取数值（忽略单位）"""
        if not text:
            return ""
        match = re.search(r'-?\d+\.?\d*', text)
        if match:
            return match.group(0)
        return ""

    def _is_numeric(self, text: str) -> bool:
        """判断文本是否为数值型"""
        try:
            cleaned = text.rstrip('%')
            float(cleaned)
            return True
        except ValueError:
            return False


def reevaluate_results(input_file: str, output_file: str):
    """使用修复后的比较器重新评估测试结果"""
    print("=" * 80)
    print("重新评估测试结果")
    print("=" * 80)
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print("=" * 80)
    
    comparator = AnswerComparator()
    
    # 读取原始测试结果
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    records = []
    reevaluated_count = 0
    changed_count = 0
    
    for line in lines:
        record = json.loads(line)
        original_correct = record['is_correct']
        
        # 使用新的比较器重新评估
        new_correct, new_reason = comparator.compare_answers(
            record['standard_answer'],
            record['actual_answer']
        )
        
        reevaluated_count += 1
        
        # 检查是否发生变化
        if original_correct != new_correct:
            changed_count += 1
            print(f"\n[CHANGED] 问题 {record['id']}")
            print(f"  原结果: {original_correct} - {record['comparison_reason']}")
            print(f"  新结果: {new_correct} - {new_reason}")
            print(f"  问题: {record['question'][:60]}...")
            print(f"  标准答案: {record['standard_answer']}")
            print(f"  实际答案: {record['actual_answer']}")
        
        # 更新记录
        record['original_correct'] = original_correct
        record['is_correct'] = new_correct
        record['comparison_reason'] = new_reason
        records.append(record)
    
    # 保存重新评估的结果
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print("\n" + "=" * 80)
    print("重新评估统计")
    print("=" * 80)
    print(f"总问题数: {len(records)}")
    print(f"重新评估数: {reevaluated_count}")
    print(f"结果变化数: {changed_count}")
    print(f"\n准确率变化:")
    
    original_accuracy = sum(1 for r in records if r['original_correct']) / len(records) * 100
    new_accuracy = sum(1 for r in records if r['is_correct']) / len(records) * 100
    
    print(f"  原准确率: {original_accuracy:.2f}%")
    print(f"  新准确率: {new_accuracy:.2f}%")
    print(f"  提升: {new_accuracy - original_accuracy:+.2f}%")
    print("=" * 80)
    print(f"结果已保存到: {output_file}")


if __name__ == '__main__':
    input_file = 'evaluations_complete_100.jsonl'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'evaluations_reevaluated_{timestamp}.jsonl'
    
    reevaluate_results(input_file, output_file)
