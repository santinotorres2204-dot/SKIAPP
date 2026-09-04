from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AnalysisStatus, Discipline, TerrainTag


class VideoUploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    trip_id: int | None
    file_url: str
    discipline_tag: Discipline
    terrain_tag: TerrainTag | None
    uploaded_at: datetime
    analysis_status: AnalysisStatus
