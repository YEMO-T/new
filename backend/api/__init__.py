"""
API 路由模块
"""
from . import auth
from . import chat
from . import coursewares
from . import knowledge
from . import templates
from . import templates_v2
from . import exports
from . import ppt_templates

try:
    from . import voice
except ImportError as e:
    import logging
    logging.warning(f"voice 模块导入失败（可选功能）: {e}")
    voice = None

__all__ = [
    'auth',
    'chat',
    'coursewares',
    'knowledge',
    'templates',
    'templates_v2',
    'exports',
    'voice',
    'ppt_templates',
]
