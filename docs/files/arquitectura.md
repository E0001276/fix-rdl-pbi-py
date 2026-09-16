# Arquitectura y orden de ejecución

## Flujo activo

```text
main.py
  |
  +--> auth.py
  +--> config.py
  +--> diagnostics.py
  +--> http_clients.py
  +--> workspace.py
  |      +--> descubre Reports / Semantic Models / Paginated Reports
  |
  +--> powerbi_gateway.py
  |      +--> bind Semantic Models -> Gateway
  |
  +--> semantic_refresh.py
  |      +--> refresh Semantic Models
  |
  +--> paginated.py
  |      +--> corrige RDL persistido in-place
  |
  +--> powerbi_paginated.py
  |      +--> corrige datasource runtime
  |
  +--> remediation.py
         +--> corrige RDL Visual itemId/workspaceId
```

## Módulos auxiliares

`gateway.py`, `fabric_connections.py` y `repository.py` existen en el repositorio pero no forman parte del camino principal importado por `main.py` en la versión analizada.
