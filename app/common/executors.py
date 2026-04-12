"""
全局共享线程池管理
避免每个 API 模块独立创建无法关闭
"""

import atexit
from concurrent.futures import ThreadPoolExecutor

# 全局共享 IO 密集型任务线程池
# 用于外部 API 请求抓取，默认大小取决于 CPU 核心数，但这里固定为 10 比较合适
DEFAULT_MAX_WORKERS = 10

_shared_executor: ThreadPoolExecutor | None = None


def get_shared_executor(max_workers: int = DEFAULT_MAX_WORKERS) -> ThreadPoolExecutor:
    global _shared_executor
    if _shared_executor is None:
        _shared_executor = ThreadPoolExecutor(max_workers=max_workers)
        # 注册退出时自动关闭
        atexit.register(_shutdown_executor)
    return _shared_executor


def _shutdown_executor() -> None:
    global _shared_executor
    if _shared_executor is not None:
        _shared_executor.shutdown(wait=True)
        _shared_executor = None
