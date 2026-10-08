"""Deterministic request-routing scaffold for the phone gateway.

Routing selects a model class and suggests a non-executing workflow. It never
grants tool access or silently transfers a request to a cloud provider.
"""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RouteDecision:
    model: str
    reason: str
    suggested_workflow: str | None = None

    def public(self):
        return asdict(self)


def route_request(*, requested: str, text: str, has_image: bool, operation: str,
                  local_available: bool, cloud_available: bool) -> RouteDecision:
    """`auto` remains private/local; cloud is selected only by the user."""
    lowered = text.lower()
    if requested == 'kimi':
        return RouteDecision('kimi', 'User explicitly selected cloud reasoning')
    if requested == 'local':
        return RouteDecision('local', 'User explicitly selected the local model')
    if has_image and operation == 'scan':
        return RouteDecision('local' if local_available else 'none',
                             'Document extraction uses the configured local vision model',
                             'review_then_save')
    if has_image:
        return RouteDecision('local' if local_available else 'none',
                             'Visual question uses the configured local vision model', 'vision_answer')
    if any(phrase in lowered for phrase in ('remember ', 'save this memory', 'note this')):
        return RouteDecision('local' if local_available else 'none',
                             'Text remains local; memory requires an explicit separate save',
                             'explicit_memory_confirmation')
    if any(phrase in lowered for phrase in ('send email', 'add to calendar', 'upload to drive', 'control my computer')):
        return RouteDecision('local' if local_available else 'none',
                             'Chat does not execute actions; an approved integration is required',
                             'approval_required')
    return RouteDecision('local' if local_available else 'none',
                         'Auto routes to the local model; cloud is never selected silently')
