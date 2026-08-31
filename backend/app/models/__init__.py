from app.models.analysis_result import AnalysisResult
from app.models.season_review import SeasonReview
from app.models.ski_rating import SkiRating
from app.models.training_plan import TrainingPlan
from app.models.trip import Trip
from app.models.user import User
from app.models.video_upload import VideoUpload

__all__ = [
    "User",
    "Trip",
    "VideoUpload",
    "AnalysisResult",
    "SkiRating",
    "TrainingPlan",
    "SeasonReview",
]
