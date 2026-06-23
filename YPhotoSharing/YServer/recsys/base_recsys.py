from abc import ABC, abstractmethod
from typing import List
from sqlalchemy.orm import Session

class BaseRecsys(ABC):
    """Abstract base class for all recommendation systems."""

    @abstractmethod
    def evaluate(self, user_id: str, round_id: str, db: Session, limit: int = 10) -> List[str]:
        """
        Compute recommendations for the given user.

        Args:
            user_id: The ID of the user.
            round_id: The current round ID.
            db: SQLAlchemy session.
            limit: Maximum number of recommendations to return.

        Returns:
            A list of photo_ids.
        """
        pass
