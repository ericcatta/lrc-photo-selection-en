from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

Identifier = str

class Photo(StrictModel):
    id: str = Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9:_-]+$')
    uuid: str = Field(min_length=1, max_length=128)
    local_id: int = Field(ge=0)
    filename: str = Field(max_length=1024)
    camera: str = Field(default='Unknown', max_length=256)
    captured_at: float | None = None
    baseline_rating: int = Field(ge=0, le=5)
    baseline_edit_time: float | None = None
    is_virtual_copy: bool = False

class ImportPhotos(StrictModel):
    schema_version: Literal[1] = 1
    id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')
    catalog_id: str = Field(min_length=1, max_length=128)
    photos: list[Photo] = Field(min_length=1, max_length=100000)

    @model_validator(mode='after')
    def unique(self):
        keys = [(p.uuid, p.local_id) for p in self.photos]
        if len(set(keys)) != len(keys) or len({p.id for p in self.photos}) != len(self.photos) or len({p.local_id for p in self.photos}) != len(self.photos):
            raise ValueError('Duplicate identifiers in the manifest')
        return self

class ImportManifest(StrictModel):
    schema_version: Literal[1] = 1
    id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')
    title: str = Field(min_length=1, max_length=200)
    catalog_id: str = Field(min_length=1, max_length=128)
    catalog_label: str = Field(default='', max_length=1024)
    photos: list[Photo] = Field(min_length=1, max_length=100000)

    @model_validator(mode='after')
    def unique(self):
        keys = [(p.uuid, p.local_id) for p in self.photos]
        if len(set(keys)) != len(keys) or len({p.id for p in self.photos}) != len(self.photos) or len({p.local_id for p in self.photos}) != len(self.photos):
            raise ValueError('Duplicate identifiers in the manifest')
        return self

class Settings(StrictModel):
    target: int = Field(ge=1)
    preset_id: str = ''
    preset_version: int = Field(default=0, ge=0)
    preset_snapshot: dict | None = None
    mode: Literal['local', 'hybrid'] = 'local'
    workflow_path: Literal['local', 'hybrid', 'openai'] | None = None
    instructions: str = Field(default='', max_length=10000)
    subject_query: str = Field(default='', max_length=500)
    service_criteria: list[str] | None = Field(default=None, max_length=50)
    camera_offsets: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode='after')
    def workflow_mode(self):
        if self.workflow_path is not None:
            self.mode = 'local' if self.workflow_path == 'local' else 'hybrid'
        return self

class SettingsUpdate(StrictModel):
    revision: int
    settings: Settings

class Revision(StrictModel):
    revision: int

class Archive(Revision):
    archived: bool

class Replace(Revision):
    from_photo_id: str
    to_photo_id: str

class BatchInput(StrictModel):
    batch_id: str

class CompleteImport(StrictModel):
    import_id: str

class Decision(StrictModel):
    revision: int
    state: Literal['candidate', 'preferred', 'alternative', 'excluded', 'review']
    locked: bool = False
    confirm_last: bool = False

class PresetInput(StrictModel):
    instructions: str = Field(default='', max_length=10000)
    subject_query: str = Field(default='', max_length=500)
    name: str = Field(min_length=1, max_length=100)
    criteria: list[str] = Field(max_length=50)
    version: int | None = None

class ReceiptResult(StrictModel):
    photo_id: str
    status: Literal['applied', 'skipped', 'conflict', 'uncertain']
    before: int | None = Field(default=None, ge=0, le=5)
    after: int | None = Field(default=None, ge=0, le=5)
    reason: str = Field(default='', max_length=2000)

class Receipt(StrictModel):
    batch_id: str
    results: list[ReceiptResult]
