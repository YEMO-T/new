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

__all__ = [
    'auth',
    'chat',
    'coursewares',
    'knowledge',
    'templates',
    'templates_v2',
    'exports',
]
