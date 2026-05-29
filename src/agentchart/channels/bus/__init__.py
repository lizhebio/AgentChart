"""Message bus module for decoupled channel-agent communication."""

from agentchart.channels.bus.events import InboundMessage, OutboundMessage
from agentchart.channels.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
