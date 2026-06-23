"""
Mock Vision Service for YPhotoSharing.

Processes photos generated during the simulation and provides:
1. Simulated alt_text descriptions.
2. Simulated aesthetic scores.
3. Simulated dense vector embeddings (e.g., CLIP 512-d).
4. Simulated dominant emotions/sentiments.
"""

import logging
import random
import hashlib
import json
import numpy as np
import ray
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Typical Instagram-style visual sentiments
POSSIBLE_EMOTIONS = ["joy", "awe", "calm", "nostalgia", "excitement", "melancholy"]

@ray.remote
class VisionService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.embedding_dim = config.get("embedding_dim", 512)
        logger.info(f"VisionService initialized. Embedding dim: {self.embedding_dim}")

    def _generate_mock_embedding(self, seed_text: str) -> List[float]:
        """Generate a deterministic pseudo-random embedding based on text hash."""
        # Use hashlib to seed numpy random to keep embeddings deterministic per image
        seed_hash = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed_hash)
        
        # Generate random normal vector and L2 normalize it
        vec = rng.standard_normal(self.embedding_dim)
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()

    def process_photos_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a batch of photos to generate visual metadata.
        
        Args:
            batch: List of dictionaries containing 'id', 'image_url', and 'caption'.
            
        Returns:
            List of dictionaries containing the enriched metadata.
        """
        results = []
        for photo in batch:
            seed_text = photo.get("caption", photo.get("id", ""))
            
            # 1. Alt Text
            words = seed_text.split() if seed_text else ["a", "scene"]
            alt_text = f"An image containing {words[0]} elements."
            
            # 2. Aesthetic Score
            # Seeded random between 0.2 and 0.95
            seed_hash = int(hashlib.md5(f"aes_{seed_text}".encode("utf-8")).hexdigest()[:8], 16)
            aes_rng = random.Random(seed_hash)
            aesthetic_score = aes_rng.uniform(0.2, 0.95)
            
            # 3. Dense Embedding
            embedding = self._generate_mock_embedding(seed_text)
            
            # 4. Sentiments
            emotions = aes_rng.sample(POSSIBLE_EMOTIONS, k=2)
            
            results.append({
                "photo_id": photo["id"],
                "alt_text": alt_text,
                "aesthetic_score": aesthetic_score,
                "embedding": json.dumps(embedding),
                "emotions": emotions
            })
            
        logger.debug(f"VisionService processed {len(batch)} photos.")
        return results
