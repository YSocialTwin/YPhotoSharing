import logging
import networkx as nx
from YPhotoSharing.YServer.classes.models import User_mgmt, Follow

logger = logging.getLogger(__name__)

class InfluenceService:
    """
    Computes graph analytics on the follow graph.
    - PageRank models the influence of a user (likelihood of information starting there spreading far).
    - Betweenness Centrality models the information brokering capacity of a user.
    """

    def __init__(self, db_middleware):
        self.db = db_middleware

    def compute_influence_metrics(self):
        """
        Builds the follow graph, computes PageRank and Betweenness Centrality,
        and updates the User_mgmt records.
        """
        logger.debug("Computing networkx influence metrics...")
        with self.db.session_scope() as session:
            # Build directed graph
            G = nx.DiGraph()
            
            # Fetch all users
            users = session.query(User_mgmt.id).all()
            for (uid,) in users:
                G.add_node(uid)
            
            # Fetch all edges
            edges = session.query(Follow.follower_id, Follow.user_id).all()
            for follower_id, user_id in edges:
                # follower_id -> user_id (following)
                # But PageRank models influence based on inbound links (who follows you).
                # So the edge should be follower_id -> user_id (meaning user_id is the influencer)
                G.add_edge(follower_id, user_id)
                
            if len(G.nodes) == 0:
                return

            try:
                pagerank = nx.pagerank(G)
                # Scale betweenness centrality to avoid tiny floats
                betweenness = nx.betweenness_centrality(G)
                
                updated = 0
                for user in session.query(User_mgmt).all():
                    uid = user.id
                    pr_score = pagerank.get(uid, 0.0)
                    bw_score = betweenness.get(uid, 0.0)
                    
                    if user.influence_score != pr_score or user.broker_score != bw_score:
                        user.influence_score = pr_score
                        user.broker_score = bw_score
                        updated += 1
                        
                if updated > 0:
                    logger.info(f"Updated influence metrics for {updated} users.")
            except Exception as e:
                logger.error(f"Failed to compute graph metrics: {e}")
