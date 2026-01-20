#!/usr/bin/env python3

from sqlalchemy import create_engine, text
from app.database import Base

# Engine für die bestehende DB
engine = create_engine("sqlite:///./app.db")

# Neue Spalten zur groups Tabelle hinzufügen
with engine.connect() as conn:
    # detail_enabled hinzufügen
    try:
        conn.execute(text("ALTER TABLE groups ADD COLUMN detail_enabled BOOLEAN DEFAULT 0"))
        print("Added detail_enabled to groups")
    except Exception as e:
        print(f"detail_enabled already exists or error: {e}")
    
    # description hinzufügen
    try:
        conn.execute(text("ALTER TABLE groups ADD COLUMN description TEXT"))
        print("Added description to groups")
    except Exception as e:
        print(f"description already exists or error: {e}")

# Neue Tabelle group_images erstellen
Base.metadata.create_all(bind=engine)
print("Created tables if not exist")