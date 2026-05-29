"""AgentChart channels subsystem.

Provides a message-bus architecture for integrating chat platforms
(Telegram, Discord, Slack, etc.) with the AgentChart query engine.

Usage::

    from agentchart.channels import BaseChannel, ChannelManager, MessageBus
"""

from agentchart.channels.bus.events import InboundMessage, OutboundMessage
from agentchart.channels.bus.queue import MessageBus
from agentchart.channels.impl.base import BaseChannel
from agentchart.channels.impl.manager import ChannelManager

__all__ = [
    "BaseChannel",
    "ChannelManager",
    "InboundMessage",
    "MessageBus",
    "OutboundMessage",
]
