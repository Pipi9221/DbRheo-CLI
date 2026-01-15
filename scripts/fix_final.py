file_path = 'd:/pipi922/Desktop/text2sql/AgentFetchCalc-CLI/DbRheo-CLI/packages/core/src/dbrheo/tools/database_connect_tool.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 修复第681行（索引680）
for i, line in enumerate(lines):
    if 'db_connect_use_connect_hint' in line and 'default=' in line:
        # 将整行改为使用单引号包裹f-string
        lines[i] = '            display_text += f"\\n{self._(\'db_connect_use_connect_hint\', default=\'Use action=connect to connect database\')}"\n'
        print(f'Fixed line {i+1}')
        break

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Done!')
