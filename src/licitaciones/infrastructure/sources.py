from __future__ import annotations
from typing import Iterable, Optional, Dict, Any, List
from pathlib import Path
import json
import csv
from datetime import datetime
import time
from ..domain.models import Tender, Bidder
import logging

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    truststore = None

logger = logging.getLogger(__name__)


def _request_with_retries(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    stream: bool = False,
    max_attempts: int = 3,
):
    import requests

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                stream=stream,
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            backoff_seconds = 1.5 ** (attempt - 1)
            logger.warning(
                "HTTP request failed for %s (attempt %s/%s): %s. Retrying in %.1fs",
                url,
                attempt,
                max_attempts,
                exc,
                backoff_seconds,
            )
            time.sleep(backoff_seconds)

    raise RuntimeError(f"HTTP request failed for {url}: {last_error}")


class JsonLinesSource:
    def __init__(self, file_path: str | Path, source_name: str, country: str) -> None:
        self._path = Path(file_path)
        self._source = source_name
        self._country = country

    def fetch(self, limit: Optional[int] = None) -> Iterable[Tender]:
        count = 0
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                # normalize fields
                publish_date = None
                if data.get("publish_date"):
                    publish_date = datetime.fromisoformat(data["publish_date"]).date()
                deadline = None
                if data.get("deadline"):
                    deadline = datetime.fromisoformat(data["deadline"]).date()
                bidders = [Bidder(**b) for b in data.get("bidders", [])]
                t = Tender(
                    source=data.get("source", self._source),
                    country=data.get("country", self._country),
                    tender_id=data["tender_id"],
                    title=data.get("title", ""),
                    description=data.get("description", ""),
                    buyer_name=data.get("buyer_name", ""),
                    item_code=data.get("item_code"),
                    currency=data.get("currency", ""),
                    amount=float(data.get("amount", 0.0)),
                    publish_date=publish_date,
                    deadline=deadline,
                    bidders=bidders,
                    raw=data,
                )
                yield t
                count += 1
                if limit and count >= limit:
                    break


class Secop2SocrataSource:
    """Fuente HTTP para SECOP II (dataset p6dx-8zbt en datos.gov.co). Uso opcional.

    Nota: Respetar límites de tasa; puede requerir un token de aplicación Socrata (X-App-Token).
    """

    def __init__(self, endpoint: str, country: str = "CO", app_token: Optional[str] = None) -> None:
        self.endpoint = endpoint.rstrip(".json") + ".json"
        self.country = country
        self.app_token = app_token
        self.name = "SECOP2"

    def fetch(self, limit: Optional[int] = None) -> Iterable[Tender]:
        params: Dict[str, Any] = {}
        if limit:
            params["$limit"] = limit
        
        headers = {}
        if self.app_token:
            headers["X-App-Token"] = self.app_token
            
        try:
            logger.info(f"Fetching from SECOP II: {self.endpoint}")
            resp = _request_with_retries(self.endpoint, params=params, headers=headers, timeout=30)
            data = resp.json()
        except Exception as e:
            logger.warning("SECOP II fetch failed: %s", e)
            return
            
        if not isinstance(data, list):
            data = []
            
        for row in data:
            try:
                # Campos reales del dataset SECOP II
                t_id = str(row.get("id_del_proceso") or f"secop2-{hash(str(row))}")
                title = row.get("nombre_del_procedimiento") or ""
                desc = row.get("descripci_n_del_procedimiento") or ""
                buyer = row.get("entidad") or ""
                item_code = row.get("codigo_principal_de_categoria")
                currency = "COP"  # SECOP II siempre en pesos colombianos
                
                # Valor del proceso - usar precio_base o valor_total_adjudicacion
                precio_base = row.get("precio_base", "0")
                valor_adjudicado = row.get("valor_total_adjudicacion", "0")
                
                # Usar el valor adjudicado si existe y es mayor a 0, sino el precio base
                amount_str = valor_adjudicado if float(valor_adjudicado or 0) > 0 else precio_base
                
                try:
                    amount = float(amount_str or 0)
                except (ValueError, AttributeError):
                    amount = 0.0
                
                # Fecha de publicación
                pub_str = row.get("fecha_de_publicacion_del") 
                publish_date = None
                if pub_str:
                    try:
                        # SECOP II usa formato "2024-11-28T00:00:00.000"
                        publish_date = datetime.fromisoformat(str(pub_str).replace("T00:00:00.000", "")).date()
                    except Exception:
                        try:
                            # Formato alternativo
                            publish_date = datetime.strptime(str(pub_str)[:10], "%Y-%m-%d").date()
                        except Exception:
                            publish_date = None

                yield Tender(
                    source=self.name,
                    country=self.country,
                    tender_id=t_id,
                    title=title,
                    description=desc,
                    buyer_name=buyer,
                    item_code=item_code,
                    currency=currency,
                    amount=amount,
                    publish_date=publish_date,
                    bidders=[],  # SECOP II API público no incluye ofertas detalladas
                    raw=row,
                )
            except Exception as e:
                logger.warning(f"Error processing SECOP II tender: {e}")
                continue


class ChileCompraAPISource:
    """Fuente para ChileCompra usando la API oficial de Mercado Público."""

    def __init__(self, endpoint: str, country: str = "CL", ticket: Optional[str] = None) -> None:
        self.endpoint = endpoint
        self.country = country
        self.ticket = ticket
        self.name = "ChileCompra"

    def fetch(self, limit: Optional[int] = None) -> Iterable[Tender]:
        if not self.ticket:
            logger.warning(
                "ChileCompra online fetch skipped: missing API ticket. "
                "Configure sources.chilecompra.ticket or CHILECOMPRA_TICKET."
            )
            return

        params: Dict[str, Any] = {"ticket": self.ticket}
        if limit:
            params["limit"] = limit

        try:
            logger.info("Fetching from ChileCompra API: %s", self.endpoint)
            resp = _request_with_retries(self.endpoint, params=params, timeout=30)
            records = self._extract_records(resp.json())
        except Exception as e:
            logger.warning("ChileCompra fetch failed: %s", e)
            return

        count = 0
        for lic in records:
            if limit and count >= limit:
                break

            tender = self._build_tender(lic)
            if tender is None:
                continue
            yield tender
            count += 1

    def _extract_records(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]

        if not isinstance(payload, dict):
            return []

        for key in ("Listado", "listaLicitaciones", "items", "Items", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]

        return []

    def _build_tender(self, lic: Dict[str, Any]) -> Optional[Tender]:
        try:
            tender_id = str(
                lic.get("CodigoExterno")
                or lic.get("codigoExterno")
                or lic.get("Codigo")
                or lic.get("codigo")
                or lic.get("tender_id")
                or ""
            ).strip()
            if not tender_id:
                return None

            title = str(lic.get("Nombre") or lic.get("nombre") or lic.get("title") or "")
            description = str(lic.get("Descripcion") or lic.get("descripcion") or lic.get("description") or title)
            buyer_name = str(lic.get("NombreOrganismo") or lic.get("nombreOrganismo") or lic.get("buyer_name") or "")
            item_code = lic.get("CodigoCategoria") or lic.get("codigoCategoria") or lic.get("item_code")
            currency = str(lic.get("Moneda") or lic.get("moneda") or lic.get("currency") or "CLP")
            amount = self._to_float(
                lic.get("MontoEstimado")
                or lic.get("montoEstimado")
                or lic.get("MontoTotal")
                or lic.get("montoTotal")
                or lic.get("amount")
                or 0
            )

            publish_date = self._parse_date(
                lic.get("FechaCreacion")
                or lic.get("fechaCreacion")
                or lic.get("FechaPublicacion")
                or lic.get("fechaPublicacion")
                or lic.get("publish_date")
            )
            deadline = self._parse_date(
                lic.get("FechaCierre")
                or lic.get("fechaCierre")
                or lic.get("deadline")
            )

            return Tender(
                source=self.name,
                country=self.country,
                tender_id=f"CL-{tender_id}",
                title=title,
                description=description,
                buyer_name=buyer_name,
                item_code=item_code,
                currency=currency,
                amount=amount,
                publish_date=publish_date,
                deadline=deadline,
                bidders=[],
                raw=lic,
            )
        except Exception as e:
            logger.warning("Error processing ChileCompra tender: %s", e)
            return None

    def _parse_date(self, value: Any) -> Optional[datetime.date]:
        if not value:
            return None

        text = str(value).strip()
        candidates = [text, text.replace("Z", "+00:00")]
        if "T" in text:
            candidates.append(text.split("T")[0])

        for candidate in candidates:
            try:
                return datetime.fromisoformat(candidate).date()
            except ValueError:
                continue

        return None

    def _to_float(self, value: Any) -> float:
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return 0.0


class CompranetMexicoSource:
    """Fuente productiva para CompraNet usando datasets públicos de datos.gob.mx."""

    def __init__(self, search_url: str, name: str, country: str, query: str = "") -> None:
        self.search_url = search_url
        self.name = name
        self.country = country
        self.query = query

    def fetch(self, limit: Optional[int] = None) -> Iterable[Tender]:
        try:
            csv_url = self._resolve_csv_resource_url(limit)
            if not csv_url:
                logger.warning("Compranet fetch skipped: no CSV resource found for query '%s'", self.query)
                return

            logger.info("Fetching from Compranet México: %s", csv_url)
            resp = _request_with_retries(csv_url, stream=True, timeout=60)
        except Exception as e:
            logger.warning("Compranet fetch failed: %s", e)
            return

        lines = resp.iter_lines(decode_unicode=True)
        reader = csv.DictReader(lines)
        count = 0
        for row in reader:
            if limit and count >= limit:
                break

            tender = self._build_tender_from_csv_row(row)
            if tender is None:
                continue

            yield tender
            count += 1

    def _resolve_csv_resource_url(self, limit: Optional[int] = None) -> Optional[str]:
        if self.search_url.lower().endswith(".csv"):
            return self.search_url

        params: Dict[str, Any] = {"q": self.query or "compranet", "rows": max(limit or 10, 10)}
        response = _request_with_retries(self.search_url, params=params, timeout=30)
        payload = response.json()

        results = payload.get("result", {}).get("results", []) if isinstance(payload, dict) else []
        for dataset in results:
            for resource in dataset.get("resources", []):
                resource_url = resource.get("url")
                resource_format = str(resource.get("format") or "").upper()
                if resource_url and (resource_format == "CSV" or str(resource_url).lower().endswith(".csv")):
                    return str(resource_url)

        return None

    def _build_tender_from_csv_row(self, row: Dict[str, Any]) -> Optional[Tender]:
        tender_id = str(row.get("project_code") or row.get("codigo_expediente") or row.get("codigo_contrato") or "").strip()
        if not tender_id:
            return None

        title = str(row.get("titulo_contrato") or "").strip()
        description = str(row.get("descripcion_contrato") or title).strip()
        buyer_name = str(
            row.get("dependencia")
            or row.get("unidad_compradora")
            or row.get("comprador")
            or "No disponible en dataset historico"
        ).strip()
        currency = str(row.get("moneda") or "MXN").strip() or "MXN"
        amount = self._to_float(row.get("importe"))
        publish_date = self._parse_datetime_to_date(row.get("fecha_inicio") or row.get("ff_fecha_inicio"))
        deadline = self._parse_datetime_to_date(row.get("fecha_fin") or row.get("ff_fecha_fin"))

        return Tender(
            source=self.name,
            country=self.country,
            tender_id=f"MX-{tender_id}",
            title=title,
            description=description,
            buyer_name=buyer_name,
            item_code=str(row.get("work_category_id") or "").strip() or None,
            currency=currency,
            amount=amount,
            publish_date=publish_date,
            deadline=deadline,
            bidders=[],
            raw=row,
        )

    def _parse_datetime_to_date(self, value: Any) -> Optional[datetime.date]:
        if not value:
            return None

        text = str(value).strip()
        candidates = [text, text.replace("Z", "+00:00")]
        if "." in text and "+" in text:
            candidates.append(text.split(".")[0])
        if " " in text:
            candidates.append(text.split(" ")[0])

        for candidate in candidates:
            try:
                return datetime.fromisoformat(candidate).date()
            except ValueError:
                continue

        return None

    def _to_float(self, value: Any) -> float:
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return 0.0


class CKANPackageSearchSource:
    """Fuente genérica para CKAN package_search (p.ej., legacy Compranet) que retorna metadatos."""

    def __init__(self, search_url: str, name: str, country: str, query: str = "") -> None:
        self.search_url = search_url
        self.name = name
        self.country = country
        self.query = query

    def fetch(self, limit: Optional[int] = None) -> Iterable[Tender]:
        params: Dict[str, Any] = {"rows": limit or 50}
        if self.query:
            params["q"] = self.query
            
        try:
            logger.info(f"Fetching from CKAN: {self.search_url} with params: {params}")
            resp = _request_with_retries(self.search_url, params=params, timeout=30)
            data = resp.json()
        except Exception as e:
            logger.warning("CKAN fetch failed: %s", e)
            return
            
        results: List[Dict[str, Any]] = data.get("result", {}).get("results", []) if isinstance(data, dict) else []
        for pkg in results:
            t_id = pkg.get("id", "ckan-unknown")
            title = pkg.get("title") or ""
            desc = pkg.get("notes") or ""
            yield Tender(
                source=self.name,
                country=self.country,
                tender_id=t_id,
                title=title,
                description=desc,
                buyer_name=pkg.get("author") or "",
                item_code=None,
                currency="MXN",
                amount=0.0,
                publish_date=None,
                bidders=[],
                raw=pkg,
            )
