from YPhotoSharing.YClient.client import SimulationClient
from YPhotoSharing.YServer.server import OrchestratorServer


def test_server_is_exposed_as_ray_actor():
    assert hasattr(OrchestratorServer, "options")


def test_client_is_exposed_as_ray_actor():
    assert hasattr(SimulationClient, "options")
