"""批量修复Content.get()问题"""
import re
import os
from pathlib import Path

# 切换到脚本所在目录
os.chdir(Path(__file__).parent)

files_to_fix = [
    "packages/core/src/dbrheo/services/gemini_service.py",
    "packages/core/src/dbrheo/services/openai_service.py",
    "packages/core/src/dbrheo/services/claude_service.py",
    "packages/core/src/dbrheo/core/next_speaker.py",
    "packages/core/src/dbrheo/core/compression.py",
    "packages/core/src/dbrheo/core/chat.py",
    "packages/core/src/dbrheo/core/turn.py",
    "packages/core/src/dbrheo/utils/log_integration.py",
]

for file_path in files_to_fix:
    path = Path(file_path)
    if not path.exists():
        print(f"跳过不存在的文件: {file_path}")
        continue
    
    content = path.read_text(encoding='utf-8')
    original = content
    
    # 添加import（如果还没有）
    if 'from ..utils.content_helper import' not in content and 'from dbrheo.utils.content_helper import' not in content:
        # 找到第一个import语句后插入
        import_pos = content.find('import ')
        if import_pos > 0:
            # 找到这一行的开始
            line_start = content.rfind('\n', 0, import_pos) + 1
            content = content[:line_start] + 'from ..utils.content_helper import get_parts, get_role, get_text\n' + content[line_start:]
    
    # 替换模式
    # msg.get('parts', []) -> get_parts(msg)
    content = re.sub(r'(\w+)\.get\([\'"]parts[\'"]\s*,\s*\[\]\)', r'get_parts(\1)', content)
    
    # msg.get('role') -> get_role(msg)
    content = re.sub(r'(\w+)\.get\([\'"]role[\'"]\s*,\s*[\'"]unknown[\'"]\)', r'get_role(\1)', content)
    content = re.sub(r'(\w+)\.get\([\'"]role[\'"]\)', r'get_role(\1)', content)
    
    # part.get('text', '') -> get_text(part)
    content = re.sub(r'(\w+)\.get\([\'"]text[\'"]\s*,\s*[\'"][\'"]\)', r'get_text(\1)', content)
    content = re.sub(r'(\w+)\.get\([\'"]text[\'"]\)', r'get_text(\1)', content)
    
    if content != original:
        path.write_text(content, encoding='utf-8')
        print(f"Fixed: {file_path}")
    else:
        print(f"Skip: {file_path}")

print("\nDone!")
