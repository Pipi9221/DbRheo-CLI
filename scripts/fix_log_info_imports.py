"""
批量修复 log_info 导入问题
将函数内部的条件导入移到文件顶部
"""

import os
import re

# 需要修复的文件列表
files_to_fix = [
    "packages/core/src/dbrheo/tools/table_details_tool.py",
    "packages/core/src/dbrheo/tools/database_connect_tool.py",
    "packages/core/src/dbrheo/tools/code_execution_tool.py",
    "packages/core/src/dbrheo/services/openai_service.py",
    "packages/core/src/dbrheo/services/gemini_service_new.py",
    "packages/core/src/dbrheo/services/gemini_service.py",
    "packages/core/src/dbrheo/services/claude_service.py",
    "packages/core/src/dbrheo/core/turn.py",
    "packages/core/src/dbrheo/core/token_statistics.py",
    "packages/core/src/dbrheo/core/scheduler.py",
    "packages/core/src/dbrheo/core/next_speaker.py",
    "packages/core/src/dbrheo/core/client.py",
    "packages/core/src/dbrheo/adapters/mysql_adapter.py",
]

def fix_file(filepath):
    """修复单个文件"""
    if not os.path.exists(filepath):
        print(f"跳过不存在的文件: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已经在顶部导入
    if re.search(r'^from \.\.utils\.debug_logger import.*log_info', content, re.MULTILINE):
        print(f"已修复: {filepath}")
        return False
    
    # 检查是否有条件导入
    if 'from ..utils.debug_logger import' not in content:
        print(f"无需修复: {filepath}")
        return False
    
    # 移除所有条件导入语句
    lines = content.split('\n')
    new_lines = []
    removed_count = 0
    
    for line in lines:
        # 跳过缩进的导入语句（条件导入）
        if re.match(r'^\s+from \.\.utils\.debug_logger import', line):
            removed_count += 1
            continue
        new_lines.append(line)
    
    if removed_count == 0:
        print(f"无需修复: {filepath}")
        return False
    
    # 在文件顶部添加导入（在其他导入之后）
    content = '\n'.join(new_lines)
    
    # 找到最后一个 import 语句的位置
    import_pattern = r'^(from .+ import .+|import .+)$'
    last_import_line = 0
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        if re.match(import_pattern, line):
            last_import_line = i
    
    # 在最后一个导入后插入
    if last_import_line > 0:
        lines.insert(last_import_line + 1, 'from ..utils.debug_logger import log_info, DebugLogger')
        content = '\n'.join(lines)
    
    # 写回文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 已修复: {filepath} (移除了 {removed_count} 个条件导入)")
    return True

def main():
    """主函数"""
    import sys
    import io
    
    # 修复 Windows 控制台编码问题
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("开始批量修复 log_info 导入问题...\n")
    
    fixed_count = 0
    for filepath in files_to_fix:
        if fix_file(filepath):
            fixed_count += 1
    
    print(f"\n完成！共修复 {fixed_count} 个文件")

if __name__ == "__main__":
    main()
