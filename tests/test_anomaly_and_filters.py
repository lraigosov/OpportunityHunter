from datetime import date
from licitaciones.domain.models import Tender, Bidder
from licitaciones.domain.models import Alert
from licitaciones.app.use_cases import GenerateAlertsUseCase
from licitaciones.infrastructure.repositories import InMemoryTenderRepository
from licitaciones.infrastructure.persistence import LocalFilePersistence
from licitaciones.infrastructure.sources import ChileCompraAPISource, CompranetMexicoSource
from licitaciones.domain.services import AnomalyService


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


def test_generate_alerts_uses_tender_id_for_persistence(tmp_path):
    repo = InMemoryTenderRepository()
    tender = make_tender(500)
    repo.save_all([tender])
    persistence = LocalFilePersistence(tmp_path)
    use_case = GenerateAlertsUseCase(repo, [], persistence)

    class FixedAlertService:
        def build_opportunity_alerts(self, tenders, filters):
            return [Alert(level="info", message="Mensaje desacoplado del título", tender_id=tender.tender_id)]

    use_case._alert = FixedAlertService()

    alerts = use_case.execute({"keywords": ["software"], "countries": ["CO"], "min_amount": 0, "max_amount": 1000})
    assert len(alerts) == 1

    reports = persistence.load_execution_history("opportunities_report", limit=1)
    assert len(reports) == 1
    opportunity = reports[0]["data"]["opportunities"][0]
    assert opportunity["tender_details"]["tender_id"] == tender.tender_id

    alert_reports = persistence.load_execution_history("alerts", limit=1)
    assert alert_reports[0]["data"]["alert_tenders"][0]["tender_id"] == tender.tender_id


def test_chilecompra_source_requires_ticket_and_returns_no_fake_data():
    source = ChileCompraAPISource(
        endpoint="https://www.mercadopublico.cl/servicios/v1/publico/licitaciones.json",
        country="CL",
        ticket=None,
    )

    assert list(source.fetch(limit=1)) == []


def test_chilecompra_source_normalizes_api_records():
    source = ChileCompraAPISource(
        endpoint="https://www.mercadopublico.cl/servicios/v1/publico/licitaciones.json",
        country="CL",
        ticket="ticket-demo",
    )

    records = source._extract_records(
        {
            "Listado": [
                {
                    "CodigoExterno": "1234-56-LR26",
                    "Nombre": "Servicios de software",
                    "Descripcion": "Implementación de plataforma",
                    "NombreOrganismo": "Municipalidad Demo",
                    "CodigoCategoria": "81111500",
                    "Moneda": "CLP",
                    "MontoEstimado": "1250000",
                    "FechaCreacion": "2026-06-20T10:00:00",
                    "FechaCierre": "2026-07-05T18:00:00"
                }
            ]
        }
    )

    tender = source._build_tender(records[0])

    assert tender is not None
    assert tender.tender_id == "CL-1234-56-LR26"
    assert tender.amount == 1250000.0
    assert tender.currency == "CLP"
    assert tender.publish_date.isoformat() == "2026-06-20"
    assert tender.deadline.isoformat() == "2026-07-05"


def test_compranet_source_extracts_csv_resource_from_ckan_payload():
    source = CompranetMexicoSource(
        search_url="https://datos.gob.mx/api/3/action/package_search",
        name="Compranet",
        country="MX",
        query="compranet",
    )

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "result": {
                    "results": [
                        {
                            "resources": [
                                {
                                    "format": "CSV",
                                    "url": "https://repodatos.atdt.gob.mx/api_update/sabg/contratos_expedientes_sistema_historico_compranet/compranet_historico.csv",
                                }
                            ]
                        }
                    ]
                }
            }

    import requests
    original_get = requests.get
    requests.get = lambda *args, **kwargs: DummyResponse()
    try:
        csv_url = source._resolve_csv_resource_url(limit=5)
    finally:
        requests.get = original_get

    assert csv_url.endswith("compranet_historico.csv")


def test_compranet_source_normalizes_csv_row():
    source = CompranetMexicoSource(
        search_url="https://datos.gob.mx/api/3/action/package_search",
        name="Compranet",
        country="MX",
        query="compranet",
    )

    tender = source._build_tender_from_csv_row(
        {
            "codigo_contrato": "2376191",
            "codigo_expediente": "2161394",
            "proveedor": "Equity Appraisal Specialists Sa de Cv",
            "titulo_contrato": "Servicios Profesionales Para la Elaboracion de Avaluos",
            "descripcion_contrato": "Mexico, Morelos, Cuautla",
            "work_category_id": "7.0",
            "importe": "89012.0",
            "moneda": "MXN",
            "fecha_inicio": "2020-07-22 05:00:00.000000 +00:00",
            "fecha_fin": "2020-08-27 04:59:00.000000 +00:00",
            "project_code": "tender_1976501",
        }
    )

    assert tender is not None
    assert tender.tender_id == "MX-tender_1976501"
    assert tender.amount == 89012.0
    assert tender.currency == "MXN"
    assert tender.publish_date.isoformat() == "2020-07-22"
    assert tender.deadline.isoformat() == "2020-08-27"
