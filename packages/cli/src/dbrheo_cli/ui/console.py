"""
Rich Console封装
全局Console实例和输出配置管理
"""

from rich.console import Console as RichConsole
from rich.theme import Theme
import sys
import locale


# 定义简洁的主题（仅5种颜色）
db_theme = Theme({
    "default": "default",
    "success": "green",
    "error": "red",
    "warning": "yellow", 
    "info": "cyan"
})

# 智能检测终端编码并设置UTF-8
def _detect_console_settings():
    """检测终端编码并强制UTF-8"""
    settings = {
        'theme': db_theme,
        'force_terminal': True
    }
    
    # Windows控制台UTF-8设置
    if sys.platform == 'win32':
        try:
            import ctypes
            # 设置控制台为UTF-8 (65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except:
            pass
    
    return settings

# 创建全局Console实例（强制UTF-8）
console = RichConsole(**_detect_console_settings())


def set_no_color(no_color: bool):
    """设置是否禁用颜色"""
    global console
    if no_color:
        console = RichConsole(no_color=True)
    else:
        # 使用智能配置
        console = RichConsole(**_detect_console_settings())
