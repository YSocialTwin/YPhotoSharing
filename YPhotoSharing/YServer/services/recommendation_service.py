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

        # Replace any previous snapshot for the same round so the operation is
        # safe to re-run if the round gets replayed or retried.
        db.query(TrendingHashtag).filter_by(round_id=round_id).delete(
            synchronize_session=False
        )

        # Query top 10 hashtags by usage in photos.
        top_tags = (
            db.query(
                Hashtag.id.label("hashtag_id"),
                Hashtag.hashtag.label("hashtag"),
                func.count(PhotoHashtag.photo_id).label("count"),
            )
            .join(PhotoHashtag, Hashtag.id == PhotoHashtag.hashtag_id)
            .group_by(Hashtag.id, Hashtag.hashtag)
            .order_by(func.count(PhotoHashtag.photo_id).desc())
            .limit(10)
            .all()
        )

        if top_tags:
            rank = 1
            for hashtag_id, _tag, count in top_tags:
                trend_record = TrendingHashtag(
                    id=str(uuid.uuid4()),
                    hashtag_id=hashtag_id,
                    round_id=round_id,
                    photo_count=count,
                    rank=rank,
                )
                db.add(trend_record)
                rank += 1
            db.commit()
            logger.info(f"Trending hashtags for round {round_id} updated.")
