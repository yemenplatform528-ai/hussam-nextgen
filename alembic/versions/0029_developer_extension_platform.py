"""add internal developer extension control plane"""
from alembic import op
import sqlalchemy as sa
revision='0029_developer_extension_platform'
down_revision='0028_market_readiness_evidence'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind(); insp=sa.inspect(bind); tables=set(insp.get_table_names())
    if 'developer_extensions' not in tables:
        op.create_table('developer_extensions',
            sa.Column('id',sa.String(64),primary_key=True),
            sa.Column('tenant_id',sa.Integer(),sa.ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False),
            sa.Column('code',sa.String(120),nullable=False),
            sa.Column('name',sa.String(200),nullable=False),
            sa.Column('description',sa.Text(),nullable=False,server_default=''),
            sa.Column('extension_type',sa.String(30),nullable=False,server_default='module'),
            sa.Column('status',sa.String(30),nullable=False,server_default='draft'),
            sa.Column('market_scope',sa.JSON(),nullable=False),
            sa.Column('capabilities',sa.JSON(),nullable=False),
            sa.Column('permissions',sa.JSON(),nullable=False),
            sa.Column('created_by',sa.String(255),nullable=False),
            sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
            sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
            sa.UniqueConstraint('tenant_id','code',name='uq_developer_extension_tenant_code'),
            sa.CheckConstraint("extension_type IN ('config','module','adapter','platform')",name='ck_developer_extension_type'),
            sa.CheckConstraint("status IN ('draft','validated','testing','published','active','suspended','retired')",name='ck_developer_extension_status'))
        op.create_index('ix_developer_extensions_tenant_id','developer_extensions',['tenant_id'])
    if 'developer_extension_versions' not in tables:
        op.create_table('developer_extension_versions',
            sa.Column('id',sa.String(64),primary_key=True),
            sa.Column('extension_id',sa.String(64),sa.ForeignKey('developer_extensions.id',ondelete='CASCADE'),nullable=False),
            sa.Column('version',sa.String(40),nullable=False),
            sa.Column('manifest',sa.JSON(),nullable=False),
            sa.Column('source_hash',sa.String(64),nullable=False),
            sa.Column('compatibility',sa.JSON(),nullable=False),
            sa.Column('test_status',sa.String(30),nullable=False,server_default='pending'),
            sa.Column('release_status',sa.String(30),nullable=False,server_default='draft'),
            sa.Column('rollback_version',sa.String(40),nullable=True),
            sa.Column('created_by',sa.String(255),nullable=False),
            sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
            sa.UniqueConstraint('extension_id','version',name='uq_developer_extension_version'),
            sa.CheckConstraint("test_status IN ('pending','passed','failed')",name='ck_developer_extension_test_status'),
            sa.CheckConstraint("release_status IN ('draft','sandbox','published','active','suspended','rolled_back')",name='ck_developer_extension_release_status'))
        op.create_index('ix_developer_extension_versions_extension_id','developer_extension_versions',['extension_id'])
    if 'developer_extension_audit' not in tables:
        op.create_table('developer_extension_audit',
            sa.Column('id',sa.Integer(),primary_key=True),
            sa.Column('extension_id',sa.String(64),sa.ForeignKey('developer_extensions.id',ondelete='CASCADE'),nullable=False),
            sa.Column('actor_id',sa.String(255),nullable=False),
            sa.Column('action',sa.String(60),nullable=False),
            sa.Column('version',sa.String(40),nullable=True),
            sa.Column('details',sa.JSON(),nullable=False),
            sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
        op.create_index('ix_developer_extension_audit_extension_id','developer_extension_audit',['extension_id'])

def downgrade():
    op.drop_index('ix_developer_extension_audit_extension_id',table_name='developer_extension_audit')
    op.drop_table('developer_extension_audit')
    op.drop_index('ix_developer_extension_versions_extension_id',table_name='developer_extension_versions')
    op.drop_table('developer_extension_versions')
    op.drop_index('ix_developer_extensions_tenant_id',table_name='developer_extensions')
    op.drop_table('developer_extensions')