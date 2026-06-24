from YPhotoSharing.YServer.classes.models import Base
from sqlalchemy import inspect as sqla_inspect

for mapper in Base.registry.mappers:
    cls = mapper.class_
    for rel in mapper.relationships:
        for col in mapper.columns:
            if rel.key == col.name:
                print(f"{cls.__name__}: Collision! Column {col.name} and relationship {rel.key}")

