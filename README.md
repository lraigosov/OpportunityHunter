# OpportunityHunter 🎯

**Plataforma de análisis de licitaciones públicas para detección inteligente de oportunidades de negocio**

OpportunityHunter es una plataforma avanzada que analiza procesos de contratación pública de múltiples países (Colombia, Chile, México) para generar alertas automáticas de oportunidades, detectar anomalías en precios y identificar patrones de colusión.

Nota: PR de validación de reglas de protección de rama.

## 🚀 Características Principales

### Análisis Inteligente
- **Detección de Oportunidades**: Alertas automáticas basadas en palabras clave, montos y criterios personalizables
- **Análisis de Tendencias**: Seguimiento de precios por categoría y país
- **Detección de Anomalías**: Identificación de licitaciones con precios sospechosos
- **Análisis de Colusión**: Detección de posibles carteles en procesos de licitación

### Filtrado Avanzado
- **Oportunidades Activas**: Filtra automáticamente licitaciones cuyo deadline no ha vencido
- **Filtros Temporales**: Análisis por rangos de fechas personalizables
- **Filtros Geográficos**: Selección por países específicos
- **Filtros de Valor**: Rangos de montos configurables

### Persistencia y Reportes
- **Reportes Detallados en JSON**: Información completa de cada oportunidad encontrada
- **Historial de Ejecuciones**: Seguimiento temporal de todas las búsquedas
- **Estadísticas Agregadas**: Métricas por país, fuente, rangos de valor
- **Gestión de Archivos**: Limpieza automática de archivos antiguos

### Fuentes de Datos
- **SECOP II (Colombia)**: Sistema Electrónico de Contratación Pública
- **ChileCompra (Chile)**: Plataforma de compras públicas de Chile
- **CompraNet (México)**: Sistema de compras gubernamentales de México

## 📦 Instalación

### Requisitos
- Python 3.12+
- pip

### Instalación rápida
```bash
git clone <repository-url>
cd opportunity-hunter
pip install -r requirements.txt
```

### Configuración inicial
```bash
# Crear configuración personalizada
python tools/config_manager.py create-config --output config/config.local.json

# Verificar configuración
python tools/config_manager.py validate --config config/config.json
```

## 🎮 Uso

### Ejecución Básica
```bash
# Análisis completo con persistencia
python main.py --config config/config.json --enable-persistence

# Análisis con filtros temporales
python main.py --config config/config.json --days-back 60 --enable-persistence

# Solo oportunidades activas (deadline no vencido)
python main.py --config config/config.json --enable-persistence
# Los reportes activos se generan automáticamente en active_opportunities/
```

### Ejecución Productiva Recomendada
```powershell
# Usa SECOP II y CompraNet en línea con límites controlados
pwsh -File tools/run_productive.ps1

# Personalizar límites por fuente
pwsh -File tools/run_productive.ps1 -SecopLimit 200 -CompranetLimit 200
```

### Opciones de CLI
```bash
# Todas las opciones disponibles
python main.py --help

# Ejemplos de uso
python main.py --config config/config.json \
  --enable-persistence \
  --days-back 90 \
  --temporal-analysis \
  --temporal-interval monthly \
  --verbose

# Ver historial de ejecuciones
python main.py --config config/config.json --show-history

# Limpiar archivos antiguos (más de 30 días)
python main.py --config config/config.json --cleanup-old 30
```

### Gestión de Persistencia
```bash
# Ver historial completo
python tools/persistence_manager.py history

# Ver estadísticas
python tools/persistence_manager.py stats

# Ver contenido específico
python tools/persistence_manager.py show <archivo.json>

# Limpiar archivos antiguos
python tools/persistence_manager.py cleanup --days 30
```

### Visualización de Reportes
```bash
# Visualizar reportes de forma interactiva
python tools/report_viewer.py

# Ver reporte específico
python tools/report_viewer.py --file data/executions/opportunities_report/<archivo.json>
```

## 📊 Tipos de Reportes Generados

### 1. Reporte Completo de Oportunidades (`opportunities_report`)
Incluye todas las oportunidades encontradas con información detallada:
- Datos completos de la licitación
- Información de oferentes
- Análisis de palabras clave coincidentes
- Scoring de oportunidades
- Estadísticas agregadas

### 2. Reporte de Oportunidades Activas (`active_opportunities`)
Filtra solo oportunidades cuyo deadline no ha vencido:
- Solo licitaciones participables
- Comparación activas vs. total
- Estadísticas específicas para oportunidades vigentes

### 3. Reportes de Análisis
- **Alertas** (`alerts`): Notificaciones de oportunidades
- **Tendencias** (`trends`): Análisis de precios por categoría
- **Anomalías** (`anomalies`): Detección de precios sospechosos
- **Colusión** (`collusion`): Identificación de posibles carteles

## ⚙️ Configuración

### Estructura de Configuración
```json
{
  "sources": {
    "secop2": {
      "enabled": true,
      "mode": "online",  // o "offline"
      "endpoint": "https://www.datos.gov.co/resource/p6dx-8zbt.json",
      "sample_file": "data/samples/secop2_sample.jsonl"
    }
  },
  "filters": {
    "keywords": ["software", "consultoría", "servicios"],
    "countries": ["CO", "CL", "MX"],
    "min_amount": 0,
    "max_amount": 1000000000,
    "days_back": 120
  },
  "persistence": {
    "enabled": true,
    "directory": "data/executions",
    "cleanup_days": 30
  }
}
```

### Configuración de Fuentes
- **Modo Online**: Conexión directa a APIs gubernamentales
- **Modo Offline**: Usa archivos de muestra para desarrollo/testing

La configuración base del proyecto ya viene orientada a producción para SECOP II y CompraNet.
ChileCompra permanece deshabilitada por defecto solo porque su API oficial exige ticket previo.

Para ChileCompra, el modo online usa la API oficial de Mercado Público y requiere un ticket.
Puedes entregarlo en `sources.chilecompra.ticket` o por variable de entorno `CHILECOMPRA_TICKET`.
Si no hay ticket configurado, el adaptador omite la carga en línea y no fabrica resultados de muestra.

Para CompraNet, el modo online consume el dataset público real publicado en datos.gob.mx.
La configuración por defecto resuelve el recurso CSV desde `package_search`; también puedes fijar un CSV directo en `sources.compranet.endpoint`.
El cliente HTTP intenta usar el almacén de certificados del sistema para mejorar compatibilidad TLS en Windows y entornos corporativos.

## 🏗️ Arquitectura

### Arquitectura Hexagonal
```
src/licitaciones/
├── domain/           # Modelos y lógica de negocio
├── app/             # Casos de uso y orquestación
└── infrastructure/  # Adaptadores externos (APIs, DB, archivos)
```

### Componentes Principales
- **Use Cases**: Lógica de negocio encapsulada
- **Ports**: Interfaces para inversión de dependencias  
- **Adapters**: Implementaciones concretas (APIs, persistencia)
- **Services**: Servicios de dominio especializados

## 🔧 Desarrollo

### Ejecutar Tests
```bash
pytest tests/ -v
```

### Estructura del Proyecto
```
opportunity-hunter/
├── src/licitaciones/        # Código fuente principal
├── tools/                   # Herramientas auxiliares
├── config/                  # Archivos de configuración
├── data/                    # Datos y reportes (ignorado en git)
├── tests/                   # Tests unitarios
└── requirements.txt         # Dependencias
```

### Agregar Nueva Fuente
1. Implementar adapter en `infrastructure/sources.py`
2. Registrar en configuración
3. Agregar tests correspondientes

## 📈 Casos de Uso

### Para PyMEs
- Detección automática de licitaciones relevantes
- Análisis de competencia y precios de mercado
- Identificación de oportunidades por región

### Para Analistas
- Detección de anomalías en procesos de contratación
- Análisis de tendencias temporales
- Identificación de posibles irregularidades

### Para Investigadores
- Análisis de transparencia en contratación pública
- Estudios de mercado gubernamental
- Detección de patrones de colusión

## 🤝 Contribuir

1. Fork del proyecto
2. Crear rama para feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit de cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

## 🙏 Agradecimientos

- APIs públicas de SECOP II, ChileCompra y CompraNet
- Comunidad de Python y bibliotecas utilizadas
- Contribuidores y testers del proyecto

---

**OpportunityHunter** - Transformando datos públicos en oportunidades de negocio 🎯