import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from api.v1.saved_analyses.db_models import SavedAnalysis, SavedAnalysisMapLayer
from api.v1.user.db_models import User
from api.v1.catalogue.db_models import DisplayCatalogue
from uuid import UUID
from datetime import datetime

logger = logging.getLogger("projects")


def validate_user(db: Session, user_id: str):
    # validate user
    user = db.query(func.count(User.uuid)).filter(User.uuid == user_id).scalar()
    if user == 0:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid user")


def save_analysis(db: Session, user_id: str,
                  name: str, description: str,
                  geometry: str, feature_type: str, zoom_level: float,
                  map_layers: [], project_id: int = None):
    """
    Create a saved analysis
    :param db: db session
    :param user_id: owner of this saved analysis
    :param name: name of this saved analysis
    :param description: description of this saved analysis
    :param geometry: geometry, usually needed as a starting point by the analysis
    :param feature_type: feature type, must be one of the constants.FEATURE_TYPE allowed
    :param zoom_level: set the map to this zoom level when analysis is loaded
    :param map_layers: map layers loaded in this analysis
    :param project_id: tie analysis to a project
    :return:
    """

    validate_user(db, user_id)

    analysis = SavedAnalysis(user_id=user_id,
                             name=name,
                             description=description,
                             geometry=geometry,
                             feature_type=feature_type,
                             zoom_level=zoom_level,
                             project_id=project_id)
    db.add(analysis)
    db.flush()

    for layer in map_layers:
        # validate map layers
        map_layer = db.query(func.count(DisplayCatalogue.display_data_name)) \
            .filter(DisplayCatalogue.display_data_name == layer) \
            .scalar()
        if map_layer == 0:
            raise HTTPException(status_code=422, detail=f"Invalid map layer `{layer}`")

        saved_analysis_map_layer = SavedAnalysisMapLayer(
            saved_analysis_uuid=analysis.saved_analysis_uuid,
            map_layer=layer
        )
        db.add(saved_analysis_map_layer)

    db.commit()
    return get_saved_analysis(db, analysis.saved_analysis_uuid)


def get_saved_analyses_by_user(db: Session, user_id: str):
    analyses = db.query(SavedAnalysis).filter(
        SavedAnalysis.user_id == user_id,
        SavedAnalysis.deleted_on.is_(None)
    )

    return analyses.all()


def get_saved_analysis(db: Session, saved_analysis_uuid: UUID, include_deleted=False):
    if include_deleted:
        analysis = db.query(SavedAnalysis).get(saved_analysis_uuid)
    else:
        analysis = db.query(SavedAnalysis).filter(
            SavedAnalysis.saved_analysis_uuid == saved_analysis_uuid,
            SavedAnalysis.deleted_on.is_(None)
        ).first()

    return analysis


def delete_saved_analysis(db: Session, saved_analysis_uuid: UUID):
    analysis = db.query(SavedAnalysis).get(saved_analysis_uuid)
    analysis.deleted_on = datetime.now()
    db.commit()


def update_saved_analysis(db: Session, saved_analysis_uuid: UUID,
                          user_id: str,
                          name: str, description: str,
                          geometry: str, feature_type: str, zoom_level: float,
                          map_layers: [], project_id: int = None
                          ):
    validate_user(db, user_id)

    analysis = db.query(SavedAnalysis).get(saved_analysis_uuid)
    analysis.name = name
    analysis.description = description
    analysis.geometry = geometry
    analysis.feature_type = feature_type
    analysis.zoom_level = zoom_level
    analysis.project_id = project_id

    for layer in map_layers:
        # validate map layers
        map_layer = db.query(func.count(DisplayCatalogue.display_data_name)) \
            .filter(DisplayCatalogue.display_data_name == layer) \
            .scalar()
        if map_layer == 0:
            raise HTTPException(status_code=422, detail=f"Invalid map layer `{layer}`")

        saved_analysis_map_layer = SavedAnalysisMapLayer(
            saved_analysis_uuid=analysis.saved_analysis_uuid,
            map_layer=layer
        )
        db.add(saved_analysis_map_layer)

    db.commit()