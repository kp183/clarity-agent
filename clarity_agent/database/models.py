from sqlalchemy import Column, String, DateTime, Text, JSON, Float, Integer, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

Base = declarative_base()

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(50), nullable=False, default="open")
    
    analysis_results = relationship("AnalysisResultDB", back_populates="incident")
    conversations = relationship("Conversation", back_populates="incident")

class AnalysisResultDB(Base):
    __tablename__ = "analysis_results"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"))
    agent_type = Column(String(50), nullable=False)  # "Analyst", "Sentinel"
    result_data = Column(JSON, nullable=False) # Stores the Pydantic model as JSON
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    incident = relationship("Incident", back_populates="analysis_results")

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"))
    conversation_data = Column(JSON, nullable=False) # Stores a list of chat messages
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    incident = relationship("Incident", back_populates="conversations")