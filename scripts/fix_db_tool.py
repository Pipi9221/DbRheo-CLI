import re

file_path = 'd:/pipi922/Desktop/text2sql/AgentFetchCalc-CLI/DbRheo-CLI/packages/core/src/dbrheo/tools/database_connect_tool.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复：将包含单引号的双引号字符串改为不包含引号的字符串
content = re.sub(
    r'default="[^"]*action=\'connect\'[^"]*"',
    'default="Use action=connect to connect database"',
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed!")
