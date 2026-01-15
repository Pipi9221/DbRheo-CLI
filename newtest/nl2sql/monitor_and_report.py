"""监控测试进度并生成报告"""
import json
import time
from pathlib import Path
from datetime import datetime

def monitor_test_progress(jsonl_file: str, total_questions: int = 100):
    """监控测试进度"""
    jsonl_path = Path(jsonl_file)
    
    if not jsonl_path.exists():
        print(f"文件不存在: {jsonl_file}")
        return
    
    print("=" * 80)
    print("NL2SQL 测试进度监控")
    print("=" * 80)
    
    last_count = 0
    while True:
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                current_count = len(lines)
            
            if current_count != last_count:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 已完成: {current_count}/{total_questions} ({current_count/total_questions*100:.1f}%)")
                last_count = current_count
            
            if current_count >= total_questions:
                print("\n✅ 测试完成！")
                break
            
            time.sleep(5)  # 每5秒检查一次
            
        except KeyboardInterrupt:
            print("\n\n⚠️ 监控中断")
            break
        except Exception as e:
            print(f"错误: {e}")
            time.sleep(5)
    
    # 生成报告
    generate_report(jsonl_file)


def generate_report(jsonl_file: str):
    """生成测试报告"""
    print("\n" + "=" * 80)
    print("生成测试报告")
    print("=" * 80)
    
    results = []
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    
    total = len(results)
    correct = sum(1 for r in results if r.get('is_correct', False))
    incorrect = total - correct
    accuracy = (correct / total * 100) if total > 0 else 0
    
    print(f"\n📊 测试统计:")
    print(f"  总问题数: {total}")
    print(f"  正确数量: {correct}")
    print(f"  错误数量: {incorrect}")
    print(f"  准确率: {accuracy:.2f}%")
    
    # 保存报告
    report_file = Path(jsonl_file).parent / "nl2sql_test_report.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# NL2SQL Agent 测试报告\n\n")
        f.write(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## 测试统计\n\n")
        f.write(f"- 总问题数: {total}\n")
        f.write(f"- 正确数量: {correct}\n")
        f.write(f"- 错误数量: {incorrect}\n")
        f.write(f"- **准确率: {accuracy:.2f}%**\n\n")
        
        if incorrect > 0:
            f.write(f"## 错误问题列表\n\n")
            for r in results:
                if not r.get('is_correct', False):
                    f.write(f"### 问题 {r['id']}\n")
                    f.write(f"- **问题**: {r['question']}\n")
                    f.write(f"- **标准答案**: {r['standard_answer']}\n")
                    f.write(f"- **实际答案**: {r['actual_answer']}\n")
                    f.write(f"- **原因**: {r['comparison_reason']}\n\n")
    
    print(f"\n✅ 报告已保存: {report_file}")


if __name__ == '__main__':
    jsonl_file = str(Path(__file__).parent / 'evaluations_20260115_144535.jsonl')
    monitor_test_progress(jsonl_file, total_questions=100)
