from datetime import datetime, date, timezone
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase): pass

class Opportunity(Base):
    __tablename__ = 'opportunities'
    __table_args__ = (CheckConstraint("kind IN ('internship', 'project')", name='ck_kind'), CheckConstraint("source_type IN ('sample', 'verified')", name='ck_source_type'), Index('ix_opportunity_filters', 'kind', 'remote', 'location'))
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    organization: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20))
    location: Mapped[str] = mapped_column(String(200))
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    source_type: Mapped[str] = mapped_column(String(20), default='sample')
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    embedding = mapped_column(Vector(384), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(512), nullable=True)
    skills: Mapped[list['Skill']] = relationship(secondary='opportunity_skills', lazy='selectin')

class Skill(Base):
    __tablename__ = 'skills'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)

class OpportunitySkill(Base):
    __tablename__ = 'opportunity_skills'
    opportunity_id: Mapped[int] = mapped_column(ForeignKey('opportunities.id', ondelete='CASCADE'), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey('skills.id', ondelete='CASCADE'), primary_key=True)

class UserProfile(Base):
    __tablename__ = 'user_profiles'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default='')
    interests: Mapped[str] = mapped_column(Text, default='')
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    remote_preference: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    skills: Mapped[list['Skill']] = relationship(secondary='profile_skills', lazy='selectin')

class ProfileSkill(Base):
    __tablename__ = 'profile_skills'
    profile_id: Mapped[int] = mapped_column(ForeignKey('user_profiles.id', ondelete='CASCADE'), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey('skills.id', ondelete='CASCADE'), primary_key=True)

class SearchLog(Base):
    __tablename__ = 'search_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    result_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
