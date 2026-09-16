from datetime import datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)
class FiscalPeriod(Base):
    __tablename__='fiscal_periods'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    name: Mapped[str]=mapped_column(String(100),nullable=False)
    starts_on: Mapped[object]=mapped_column(Date,nullable=False)
    ends_on: Mapped[object]=mapped_column(Date,nullable=False)
    closed: Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    __table_args__=(UniqueConstraint('tenant_id','name',name='uq_period_tenant_name'),)
class ExchangeRate(Base):
    __tablename__='exchange_rates'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    base_currency: Mapped[str]=mapped_column(String(10),nullable=False)
    quote_currency: Mapped[str]=mapped_column(String(10),nullable=False)
    rate: Mapped[object]=mapped_column(Numeric(20,8),nullable=False)
    effective_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class JournalLink(Base):
    __tablename__='journal_links'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    journal_id: Mapped[int]=mapped_column(ForeignKey('journals.id',ondelete='CASCADE'),nullable=False)
    reversal_of_journal_id: Mapped[int]=mapped_column(ForeignKey('journals.id'),nullable=False)
    __table_args__=(UniqueConstraint('tenant_id','reversal_of_journal_id',name='uq_one_reversal_per_journal'),)
