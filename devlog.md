## 2026-06-30

### Sesión 1

- Se revisó la arquitectura, el empaquetado y el estado operativo de los conectores de datos.
- Se corrigió el empaquetado Python con layout src para permitir instalación editable y entrypoint de consola consistente.
- Se migraron importaciones absolutas desde src.licitaciones a licitaciones en CLI, herramientas auxiliares y pruebas.
- Se validó la instalación y la prueba existente en un entorno Python 3.13 compatible; resultado: 2 pruebas aprobadas.
- Se confirmó que SECOP II usa una fuente pública real y que los conectores de ChileCompra y CompraNet siguen dependiendo de datos simulados.

### Sesión 2

- Se reemplazó la simulación online de ChileCompra por consumo de la API oficial de Mercado Público con ticket obligatorio.
- Se reemplazó la simulación online de CompraNet por ingestión del dataset público real de datos.gob.mx resuelto vía package_search y recurso CSV.
- Se desacopló la persistencia de oportunidades del texto de alertas, priorizando tender_id para enlazar licitaciones y reportes.
- Se actualizaron configuración y documentación para los conectores productivos de ChileCompra y CompraNet.
- Se ampliaron las pruebas de regresión y la validación final cerró con 7 pruebas aprobadas.

### Sesión 3

- Se endurecieron las fuentes HTTP con reintentos y backoff para mitigar fallos transitorios de red.
- Se activó configuración base orientada a operación real para SECOP II y CompraNet.
- Se integró truststore para usar certificados del sistema y resolver conectividad TLS con datos.gob.mx sin desactivar validación SSL.
- Se ejecutó corrida real end-to-end con fuentes en línea; resultado: ingestión de SECOP II y CompraNet, persistencia activa y resumen de ejecución generado.

### Sesión 4

- Se creó el comando operativo único `tools/run_productive.ps1` para ejecutar la corrida productiva con límites por fuente y limpieza de config temporal.
- Se eliminó el entorno virtual obsoleto `.venv` (Python 3.10) y se dejó únicamente `.venv313` (Python 3.13).
- Se validó la ejecución productiva usando el script y se confirmó persistencia con resumen generado en `data/executions/full_execution`.