"""Federation hooks of YPhotoSharing (opt-in, guide 4.8).

With the `federation` section of the simulation configuration absent or `enabled: false` nothing here is imported
beyond this file, the server's `_federation_gate` stays None and it behaves exactly as without federation (INV-01).
With it enabled the SDK `ysocial_federation` must be importable on the server (the Ray actor)."""

import logging
import os

log = logging.getLogger("yphotosharing.federation")


def build_gate(server, config):
    """Create the gate from config["federation"] for `server`, or None when the federation is off."""
    section = (config or {}).get("federation") or {}
    if not section.get("enabled"):
        return None
    from ysocial_federation.gate import FederationGate

    from .adapter import YPhotoSharingAdapter
    from .gate import SafeGate

    section = dict(section)
    section.setdefault("exp_id", os.path.basename(str(server.config_path)) or None)
    adapter = YPhotoSharingAdapter(section["member"], int(section.get("federation_id", 1)), host=server,
                                   accounts=section.get("accounts"),
                                   export_policy=section.get("export_policy", "marked"),
                                   emit_exposures=bool(section.get("exposures", False)))
    server._federation_adapter = adapter
    gate = SafeGate(FederationGate(adapter, section))
    gate.start((server._current_day, server._current_hour))
    return gate
