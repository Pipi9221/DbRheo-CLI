@echo off
chcp 65001 >nul
echo ========================================
echo DbRheo 项目文件清理工具
echo ========================================
echo.

echo [1/5] 清理分析报告文件...
del /q nl2sql_failures_by_time.txt 2>nul
del /q nl2sql_failures_report.txt 2>nul
del /q untested_questions_report.txt 2>nul
echo ✓ 分析报告已清理

echo.
echo [2/5] 清理日志文件...
del /q dbrheo.log 2>nul
del /q packages\cli\dbrheo_realtime.log 2>nul
echo ✓ 日志文件已清理

echo.
echo [3/5] 清理Python缓存...
if exist __pycache__ (
    rmdir /s /q __pycache__ 2>nul
    echo ✓ Python缓存已清理
) else (
    echo ✓ 无Python缓存需要清理
)

echo.
echo [4/5] 清理旧的评估导出文件...
cd test\result
del /q evaluation_export_20260115_030744.csv 2>nul
del /q evaluation_export_20260115_031201.xlsx 2>nul
del /q evaluation_export_20260115_031209.csv 2>nul
del /q evaluation_export_20260115_031221.xlsx 2>nul
cd ..\..
echo ✓ 旧评估导出已清理

echo.
echo [5/5] 清理旧的评估数据目录...
if exist .gradio_evaluations (
    rmdir /s /q .gradio_evaluations 2>nul
    echo ✓ 旧评估目录已清理
) else (
    echo ✓ 无旧评估目录需要清理
)

echo.
echo ========================================
echo 清理完成！
echo ========================================
echo.
echo 保留的重要文件：
echo - test/result/evaluations.jsonl (主数据)
echo - test/result/evaluations.jsonl.bak (备份)
echo - test/result/evaluation_export_20260115_101112.xlsx (最新导出)
echo.
pause
