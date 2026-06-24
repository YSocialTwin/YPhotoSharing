import ray
from YPhotoSharing.YServer.server import OrchestratorServer
ray.init()
actor = OrchestratorServer.remote(db_config={"type":"sqlite","sqlite":{"filename":"yphotosharing.db"}})
ray.get(actor.get_simulation_status.remote())
print("Actor is alive!")
