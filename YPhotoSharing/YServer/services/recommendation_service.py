import logging
import uuid
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from YPhotoSharing.YServer.recsys import (
    PopularityRecsys,
    CollaborativeFilteringRecsys,
    ContentBasedRecsys,
    HybridRecsys,
)
from YPhotoSharing.YServer.classes.models import User_mgmt, Recommendation, TrendingHashtag, PhotoHashtag, Hashtag

logger = logging.getLogger(__name__)

class RecommendationService:
    """
    Service to compute and persist recommendations and trending hashtags.
    """
    def __init__(self):
        self.strategies = {
            "popularity": PopularityRecsys(),
            "cf": CollaborativeFilteringRecsys(),
            "content": ContentBasedRecsys(),
            "hybrid": HybridRecsys(),
        }
        self.default_strategy = "hybrid"

    def compute_recommendations_for_round(self, round_id: str, db: Session):
        """
        Computes the explore feed recommendations for all users and persists them.
        """
        logger.info(f"Computing recommendations for round {round_id}")
        users = db.query(User_mgmt.id, User_mgmt.recsys_type).all()
        
        recs_to_insert = []
        for user_id, recsys_type in users:
            strategy_name = recsys_type if recsys_type in self.strategies else self.default_strategy
            strategy = self.strategies[strategy_name]
            
            photo_ids = strategy.evaluate(user_id=user_id, round_id=round_id, db=db, limit=20)
            
            if photo_ids:
                rec_id = str(uuid.uuid4())
                import json
                recs_to_insert.append(Recommendation(
                    id=rec_id,
                    user_id=user_id,
                    round=round_id,
                    photo_ids=json.dumps(photo_ids)
                ))
                
        if recs_to_insert:
            db.bulk_save_objects(recs_to_insert)
            db.commit()
            
        logger.info(f"Generated {len(recs_to_insert)} recommendation sets.")

    def compute_trending_hashtags(self, round_id: str, db: Session):
        """
        Computes the top trending hashtags for the current round and persists them.
        For simplicity, we count all hashtag occurrences.
        """
        logger.info(f"Computing trending hashtags for round {round_id}")
        
        # Query top 10 hashtags by usage in photos
        top_tags = (
            db.query(Hashtag.hashtag, func.count(PhotoHashtag.photo_id).label("count"))
            .join(PhotoHashtag, Hashtag.id == PhotoHashtag.hashtag_id)
            .group_by(Hashtag.id)
            .order_by(func.count(PhotoHashtag.photo_id).desc())
            .limit(10)
            .all()
        )
        
        if top_tags:
            trend_id = str(uuid.uuid4())
            trends_str = ",".join([tag[0] for tag in top_tags])
            trend_record = TrendingHashtag(
                id=trend_id,
                round=round_id,
                trending_hashtags=trends_str
            )
            db.add(trend_record)
            db.commit()
            logger.info(f"Trending hashtags for round {round_id}: {trends_str}")
