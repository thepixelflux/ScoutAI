"""Track the embedding space to avoid comparing different models."""
from alembic import op
import sqlalchemy as sa
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    # Revision 001 uses current metadata, so fresh installations may already have this column.
    if 'embedding_model' not in {column['name'] for column in sa.inspect(op.get_bind()).get_columns('opportunities')}:
        op.add_column('opportunities', sa.Column('embedding_model', sa.String(512), nullable=True))
    op.execute("UPDATE opportunities SET embedding_model = 'local:sentence-transformers/all-MiniLM-L6-v2' WHERE embedding IS NOT NULL AND embedding_model IS NULL")

def downgrade():
    op.drop_column('opportunities', 'embedding_model')
