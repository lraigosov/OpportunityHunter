from datetime import date
from src.licitaciones.domain.models import Tender, Bidder
from src.licitaciones.infrastructure.repositories import InMemoryTenderRepository
from src.licitaciones.domain.services import AnomalyService


def make_tender(amount: float, country: str = "CO", code: str = "72200000"):
    return Tender(
        source="TEST",
        country=country,
        tender_id=f"T-{amount}",
        title="Servicio software",
        description="Prueba",
        buyer_name="Entidad X",
        item_code=code,
        currency="COP",
        amount=amount,
        publish_date=date.today(),
        bidders=[Bidder(name="A", amount=amount*0.9), Bidder(name="B", amount=amount*1.1)],
        raw={},
    )


def test_repo_filters_keywords_and_amount():
    repo = InMemoryTenderRepository()
    repo.save_all([
        make_tender(100),
        make_tender(200, country="CL"),
        make_tender(300, country="MX"),
    ])
    res = repo.query({"keywords": ["software"], "countries": ["CO", "CL"], "min_amount": 150, "max_amount": 250})
    assert len(res) == 1
    assert res[0].amount == 200


def test_anomaly_zscore_flags_outlier():
    amounts = [100]*10 + [1000]
    tenders = [make_tender(a) for a in amounts]
    service = AnomalyService()
    alerts = service.detect_price_anomalies(tenders, z=3.0, min_points=5)
    assert any("Anomalía" in a.message for a in alerts)
