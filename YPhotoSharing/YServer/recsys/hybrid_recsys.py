from typing import List
from sqlalchemy.orm import Session

from YPhotoSharing.YServer.recsys.base_recsys import BaseRecsys
from YPhotoSharing.YServer.recsys.popularity_recsys import PopularityRecsys
from YPhotoSharing.YServer.recsys.cf_recsys import CollaborativeFilteringRecsys
from YPhotoSharing.YServer.recsys.content_recsys import ContentBasedRecsys

class HybridRecsys(BaseRecsys):
    """
    A weighted ensemble combining scores from Popularity, CF, and Content-based approaches.
    """
    
    def __init__(self, w_pop=0.3, w_cf=0.4, w_content=0.3):
        self.w_pop = w_pop
        self.w_cf = w_cf
        self.w_content = w_content
        self.pop_recsys = PopularityRecsys()
        self.cf_recsys = CollaborativeFilteringRecsys()
        self.content_recsys = ContentBasedRecsys()

    def evaluate(self, user_id: str, round_id: str, db: Session, limit: int = 10) -> List[str]:
        # Get extended limits to allow merging
        pop_recs = self.pop_recsys.evaluate(user_id, round_id, db, limit=limit*3)
        cf_recs = self.cf_recsys.evaluate(user_id, round_id, db, limit=limit*3)
        content_recs = self.content_recsys.evaluate(user_id, round_id, db, limit=limit*3)
        
        scores = {}
        
        def add_scores(recs, weight):
            # Recs are sorted, so first gets score N, second N-1, etc.
            n = len(recs)
            for i, pid in enumerate(recs):
                score = (n - i) * weight
                scores[pid] = scores.get(pid, 0) + score
                
        add_scores(pop_recs, self.w_pop)
        add_scores(cf_recs, self.w_cf)
        add_scores(content_recs, self.w_content)
        
        sorted_pids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [pid for pid, score in sorted_pids[:limit]]
