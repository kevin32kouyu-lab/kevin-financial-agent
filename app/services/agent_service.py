"""旧 AgentService 导入兼容层，实际实现已迁移到可控多智能体协调器。"""

from __future__ import annotations

from app.services.agent_coordinator import AgentCoordinator, AgentRunHooks


AgentService = AgentCoordinator


__all__ = ["AgentCoordinator", "AgentRunHooks", "AgentService"]
