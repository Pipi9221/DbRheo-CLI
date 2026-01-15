"""
Content对象辅助函数 - 统一处理dict和对象两种格式
"""
from typing import Any, List, Dict


def get_parts(content: Any) -> List[Any]:
    """获取content的parts，支持dict和对象格式"""
    if isinstance(content, dict):
        return content.get('parts', [])
    elif hasattr(content, 'parts'):
        return content.parts
    return []


def get_role(content: Any) -> str:
    """获取content的role，支持dict和对象格式"""
    if isinstance(content, dict):
        return content.get('role', 'unknown')
    elif hasattr(content, 'role'):
        return content.role
    return 'unknown'


def get_text(part: Any) -> str:
    """获取part的text，支持dict和对象格式"""
    if isinstance(part, dict):
        return part.get('text', '')
    elif hasattr(part, 'text'):
        return part.text or ''
    return ''
