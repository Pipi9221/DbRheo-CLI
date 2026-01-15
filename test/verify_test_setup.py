"""
验证测试脚本设置
检查文件、路径和导入是否正常
"""
import sys
from pathlib import Path

print("="*80)
print("验证测试环境")
print("="*80)

# 1. 检查项目路径
project_root = Path(__file__).parent.parent
print(f"\n✓ 项目根目录: {project_root}")
print(f"  存在: {project_root.exists()}")

# 2. 检查baseline目录
baseline_dir = project_root / "baseline"
print(f"\n✓ Baseline目录: {baseline_dir}")
print(f"  存在: {baseline_dir.exists()}")

# 3. 检查数据文件
csv_path = baseline_dir / "数据源_销量.csv"
print(f"\n✓ 数据文件: {csv_path}")
print(f"  存在: {csv_path.exists()}")
if csv_path.exists():
    print(f"  大小: {csv_path.stat().st_size / 1024:.1f} KB")

# 4. 检查测试问题文件
questions_csv = Path(__file__).parent / "question" / "automotive_questions_list_100.csv"
print(f"\n✓ 测试问题文件: {questions_csv}")
print(f"  存在: {questions_csv.exists()}")
if questions_csv.exists():
    with open(questions_csv, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    print(f"  问题数量: {len(lines)}")
    print(f"  前3个问题:")
    for i, q in enumerate(lines[:3], 1):
        print(f"    {i}. {q}")

# 5. 检查agent文件
agent_file = baseline_dir / "baseline_agent_enhanced.py"
print(f"\n✓ Agent文件: {agent_file}")
print(f"  存在: {agent_file.exists()}")

# 6. 检查packages目录
packages_dir = project_root / "packages" / "core" / "src"
print(f"\n✓ Packages目录: {packages_dir}")
print(f"  存在: {packages_dir.exists()}")

# 7. 检查日志系统
logger_file = packages_dir / "dbrheo" / "telemetry" / "logger.py"
print(f"\n✓ 日志系统文件: {logger_file}")
print(f"  存在: {logger_file.exists()}")

# 8. 检查result目录
result_dir = Path(__file__).parent / "result"
print(f"\n✓ Result目录: {result_dir}")
print(f"  存在: {result_dir.exists()}")
if not result_dir.exists():
    result_dir.mkdir(parents=True, exist_ok=True)
    print(f"  已创建目录")

# 9. 测试导入
print(f"\n{'='*80}")
print("测试导入")
print("="*80)

sys.path.insert(0, str(baseline_dir))
sys.path.insert(0, str(packages_dir))

# 测试pandas
try:
    import pandas as pd
    print(f"\n✓ pandas导入成功 (版本: {pd.__version__})")
except ImportError as e:
    print(f"\n✗ pandas导入失败: {e}")

# 测试agent
try:
    from baseline_agent_enhanced import EnhancedBaselineAgent
    print(f"✓ baseline_agent_enhanced导入成功")
except ImportError as e:
    print(f"✗ baseline_agent_enhanced导入失败: {e}")

# 测试日志系统
try:
    from dbrheo.telemetry.logger import DatabaseLogger
    from dbrheo.config.base import DatabaseConfig
    print(f"✓ 日志系统导入成功")
except ImportError as e:
    print(f"✗ 日志系统导入失败: {e}")

# 10. 总结
print(f"\n{'='*80}")
print("验证完成")
print("="*80)

issues = []
if not csv_path.exists():
    issues.append("数据文件不存在")
if not questions_csv.exists():
    issues.append("测试问题文件不存在")
if not agent_file.exists():
    issues.append("Agent文件不存在")

if issues:
    print(f"\n⚠️  发现问题:")
    for issue in issues:
        print(f"  - {issue}")
    print(f"\n请修复以上问题后再运行测试。")
else:
    print(f"\n✅ 所有必要文件都存在，可以开始测试。")
    print(f"\n运行命令:")
    print(f"  cd test")
    print(f"  python run_baseline_test.py")

print("="*80)
