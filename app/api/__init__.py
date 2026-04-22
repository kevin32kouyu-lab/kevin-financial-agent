from .admin import router as admin_router
from .agent import router as agent_router
from .auth import router as auth_router
from .backtests import router as backtests_router
from .debug import router as debug_router
from .history import router as history_router
from .profile import router as profile_router
from .runs import router as runs_router
from .tools import router as tools_router

__all__ = [
    "admin_router",
    "agent_router",
    "auth_router",
    "backtests_router",
    "debug_router",
    "history_router",
    "profile_router",
    "runs_router",
    "tools_router",
]
