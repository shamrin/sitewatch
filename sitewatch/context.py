"""Task context"""

from contextvars import ContextVar

pageid_var: ContextVar[int] = ContextVar('pageid')
