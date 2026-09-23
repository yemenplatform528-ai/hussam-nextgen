from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.developer_platform import DeveloperExtension, DeveloperExtensionVersion

def test_developer_extension_persistence():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True)
    Base.metadata.create_all(e)
    db=sessionmaker(e,expire_on_commit=False)()
    db.add(Tenant(id=1,name='Dev',status='active'))
    db.add(User(id='u1',email='u@example.com',active=True))
    db.add(TenantMembership(user_id='u1',tenant_id=1,role='owner',active=True))
    db.add(DeveloperExtension(id='e1',tenant_id=1,code='yemen.delivery',name='Yemen Delivery',created_by='u1',market_scope=['YEM']))
    db.flush()
    db.add(DeveloperExtensionVersion(id='v1',extension_id='e1',version='1.0.0',manifest={'capabilities':['logistics.read']},source_hash='a'*64,compatibility={'api':'1.0'},created_by='u1'))
    db.commit()
    assert db.query(DeveloperExtension).one().code=='yemen.delivery'
    assert db.query(DeveloperExtensionVersion).one().source_hash=='a'*64