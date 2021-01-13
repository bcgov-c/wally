from sqlalchemy import String, Column, DateTime, ARRAY, TEXT, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from api.db.base_class import BaseTable


class Base(object):
    __table_args__ = {'schema': 'metadata'}

    create_date = Column(
        DateTime, comment='Date and time (UTC) when the physical record was created in the database.')
    update_date = Column(DateTime, comment='Date and time (UTC) when the physical record was updated in the database. '
                                           'It will be the same as the create_date until the record is first '
                                           'updated after creation.')


Base = declarative_base(cls=Base, metadata=BaseTable.metadata)


class Project(Base):
    __tablename__ = 'project'
    __table_args__ = {'schema': 'public'}

    project_id = Column(Integer, primary_key=True, comment='primary key id for a project')
    name = Column(String, comment='name of the project')              
    description = Column(String, comment='description of the project')
    user_id = Column(String, ForeignKey('public.user.uuid'),
                          comment='foreign key to the user who created this project')


class ProjectDocument(Base):
    __tablename__ = 'project_document'
    __table_args__ = {'schema': 'public'}

    project_document_id = Column(Integer, primary_key=True, comment='primary key id for a project')
    s3_path = Column(String, comment='path to document in s3 storage system')              
    filename = Column(String, comment='filename of the document')
    project_id = Column(Integer, ForeignKey('public.project.project_id'),
                          comment='foreign key to the project this document is associated with')