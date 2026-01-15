#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复database_connect_tool.py中的f-string语法错误"""

file_path = 'd:/pipi922/Desktop/text2sql/AgentFetchCalc-CLI/DbRheo-CLI/packages/core/src/dbrheo/tools/database_connect_tool.py'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 修复第681行的f-string错误：将双引号改为单引号
    content = content.replace(
        'default="使用 action=\'connect\' 来连接数据库"',
        'default=\'使用 action="connect" 来连接数据库\''
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("Fixed f-string syntax error in database_connect_tool.py")
except FileNotFoundError:
    print(f"File not found: {file_path}")
    print("Git clone may still be in progress. Please wait for it to complete.")
