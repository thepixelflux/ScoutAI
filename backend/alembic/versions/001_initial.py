"""Initial schema."""
from alembic import op
from app.models import Base
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    Base.metadata.create_all(bind=op.get_bind())
    op.execute('CREATE INDEX ix_opportunities_embedding_hnsw ON opportunities USING hnsw (embedding vector_cosine_ops)')

def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
