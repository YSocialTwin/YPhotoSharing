from pathlib import Path

from YPhotoSharing.YClient.client import SimulationClient
from YPhotoSharing.YServer.server import OrchestratorServer
from run_server import build_isolated_namespace


def test_server_is_exposed_as_ray_actor():
    assert hasattr(OrchestratorServer, "options")


def test_client_is_exposed_as_ray_actor():
    assert hasattr(SimulationClient, "options")


def test_isolated_namespace_is_stable_for_same_config_dir(tmp_path):
    namespace_a = build_isolated_namespace("yphotosharing", Path(tmp_path))
    namespace_b = build_isolated_namespace("yphotosharing", Path(tmp_path))

    assert namespace_a == namespace_b
    assert namespace_a.startswith("yphotosharing_")


def test_isolated_namespace_differs_for_different_config_dirs(tmp_path_factory):
    config_a = tmp_path_factory.mktemp("photo_ns_a")
    config_b = tmp_path_factory.mktemp("photo_ns_b")

    namespace_a = build_isolated_namespace("yphotosharing", Path(config_a))
    namespace_b = build_isolated_namespace("yphotosharing", Path(config_b))

    assert namespace_a != namespace_b
