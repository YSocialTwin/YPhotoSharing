from typing import List, Dict
import random
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from YPhotoSharing.YServer.recsys.base_recsys import BaseRecsys

class ExploreRecsys(BaseRecsys):
    """
    Implements a pseudo-Two-Tower / Matrix Factorization system for the Explore Feed.
    Uses scikit-learn TfidfVectorizer and cosine_similarity to match the requester's 
    interests against the candidates' captions.
    """

    def evaluate(self, user_id: str, round_id: str, db, candidates: List[Dict], limit: int = 30) -> List[Dict]:
        if not candidates:
            return []
            
        from YPhotoSharing.YServer.classes.models import UserInterest, Interest, User_mgmt
        
        # 1. Get user's interests as a single document string
        user_interests = db.query(Interest.interest).join(UserInterest).filter(
            UserInterest.user_id == user_id
        ).all()
        user_interest_str = " ".join([ui[0].lower() for ui in user_interests])
        user_interest_set = {ui[0].lower() for ui in user_interests if ui and ui[0]}
        
        # 2. Get user's persona cluster
        user_row = db.query(User_mgmt.recsys_type).filter(User_mgmt.id == user_id).first()
        user_cluster = str(user_row[0]) if user_row else None
        
        # If no user interests, fallback to random/virality
        if not user_interest_str.strip():
            candidates.sort(key=lambda x: x.get("viral_score", 1.0) + random.uniform(0, 0.1), reverse=True)
            return candidates[:limit]
            
        # 3. Prepare corpus: Index 0 is the User Profile, Indices 1..N are Candidate Captions
        corpus = [user_interest_str]
        for photo in candidates:
            corpus.append((photo.get("caption") or "").lower())
            
        # 4. Compute TF-IDF and Cosine Similarity
        vectorizer = TfidfVectorizer(stop_words='english')
        try:
            tfidf_matrix = vectorizer.fit_transform(corpus)
            # Similarity between user (index 0) and all photos (indices 1..)
            cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        except ValueError:
            # Vocabulary empty (e.g., only stop words)
            cosine_sim = [0.0] * len(candidates)
        
        ranked_candidates = []
        for i, photo in enumerate(candidates):
            score = float(cosine_sim[i]) * 10.0  # Scale up similarity

            photo_topic_overlap = 0.0
            from YPhotoSharing.YServer.classes.models import PhotoTopic
            topic_rows = db.query(Interest.interest).join(PhotoTopic, PhotoTopic.topic_id == Interest.iid).filter(
                PhotoTopic.photo_id == photo["id"]
            ).all()
            photo_topic_set = {row[0].lower() for row in topic_rows if row and row[0]}
            if user_interest_set and photo_topic_set:
                overlap = user_interest_set.intersection(photo_topic_set)
                if overlap:
                    photo_topic_overlap = len(overlap) / float(max(1, len(photo_topic_set)))
                    score += photo_topic_overlap * 1.5
            
            # Feature: Author Cluster match (mimicking collaborative filtering)
            author_row = db.query(User_mgmt.recsys_type).filter(User_mgmt.id == photo["user_id"]).first()
            if author_row and str(author_row[0]) == user_cluster:
                score += 0.5
                
            # Feature: Inherent Virality
            viral_score = photo.get("viral_score", 1.0)
            score += viral_score * 0.2

            sentiment_score = photo.get("sentiment_score")
            if sentiment_score is not None:
                try:
                    score += max(-0.2, min(0.2, float(sentiment_score) * 0.1))
                except Exception:
                    pass
            
            # Feature: Trend Momentum (Phase 10)
            import re
            from YPhotoSharing.YServer.recsys.trend_service import TrendService
            hashtags = re.findall(r'#(\w+)', photo.get("caption") or "")
            if hashtags:
                trend_service = TrendService(db)
                trend_multiplier = trend_service.get_trending_multiplier(hashtags)
                score *= trend_multiplier
            
            # Add a tiny bit of noise to break ties
            score += random.uniform(0.0, 0.05)
            
            ranked_candidates.append((score, photo))
            
        # Sort by score descending
        ranked_candidates.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in ranked_candidates[:limit]]
