
from sqlalchemy import Column, Integer, String, ForeignKey, Table, Boolean, Text
from sqlalchemy.orm import relationship
from .database import Base

helper_secondary_functions = Table(
    "helper_secondary_functions",
    Base.metadata,
    Column("helper_id", Integer, ForeignKey("helpers.id"), primary_key=True),
    Column("function_id", Integer, ForeignKey("functions.id"), primary_key=True),
)

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    sort_order = Column(Integer, default=0, nullable=True)
    detail_enabled = Column(Boolean, default=False, nullable=False)
    description = Column(Text, nullable=True)

    parent = relationship("Group", remote_side=[id], backref="children")
    helpers = relationship("Helper", back_populates="group", cascade="all, delete")
    images = relationship("GroupImage", back_populates="group", cascade="all, delete")

class Function(Base):
    __tablename__ = "functions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    short_name = Column(String, nullable=True)
    emblem_svg_path = Column(String, nullable=True)
    sort_order = Column(Integer, default=0, nullable=True)

    helpers_main = relationship("Helper", back_populates="main_function")

class Helper(Base):
    __tablename__ = "helpers"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    photo_path = Column(String, nullable=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    main_function_id = Column(Integer, ForeignKey("functions.id"), nullable=False)

    group = relationship("Group", back_populates="helpers")
    main_function = relationship("Function", back_populates="helpers_main")
    secondary_functions = relationship("Function", secondary=helper_secondary_functions, backref="helpers_secondary")

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)

class CarouselImage(Base):
    __tablename__ = "carousel_images"
    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, nullable=False)
    sort_order = Column(Integer, default=0, nullable=True)

class GroupImage(Base):
    __tablename__ = "group_images"
    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    sort_order = Column(Integer, default=0, nullable=True)

    group = relationship("Group", back_populates="images")
