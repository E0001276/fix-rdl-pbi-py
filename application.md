# Aplicación Python de post-deploy para Power BI / Microsoft Fabric

## 1. Objetivo

`fix-rdl-pbi-py` es una aplicación Python de **post-deploy** para Power BI / Microsoft Fabric.

Su objetivo es corregir, directamente en el **workspace destino**, las referencias y relaciones dinámicas que no pueden resolverse únicamente mediante reemplazos estáticos en Git.

La aplicación trabaja con una estrategia **target-only**: descubre los objetos reales existentes en el workspace destino y realiza las correcciones utilizando sus IDs actuales. No compara el workspace de origen contra el workspace destino.

La aplicación corrige principalmente cuatro áreas:

1. Vinculación de los modelos semánticos con el gateway Oracle correcto.
2. Actualización y refresh de los modelos semánticos.
3. Corrección de los informes paginados y su datasource runtime hacia el modelo semántico destino.
4. Corrección de los RDL Visuals de los reportes principales para que apunten al informe paginado real del workspace destino.

---

## 2. Problema técnico que resuelve la aplicación

Durante un despliegue entre workspaces, algunas referencias pueden reemplazarse de forma estática mediante GitHub Actions, por ejemplo:

- nombre de base de datos;
- nombre del workspace;
- prefijos de datasource;
- `workspaceId` conocido del ambiente.

Sin embargo, otros valores solamente existen después de que los objetos fueron creados o sincronizados en el workspace destino, por ejemplo:

- `itemId` real de un informe paginado;
- `datasetId` / Semantic Model ID real;
- datasource runtime de un informe paginado;
- asociación del modelo semántico con un gateway;
- referencias de un RDL Visual hacia un informe paginado.

Por este motivo, esos valores se resuelven después del despliegue mediante la aplicación Python.

---

## 3. Principio de diseño: resolución target-only

La aplicación no necesita conocer el workspace fuente para resolver los objetos.

El algoritmo general es:

```text
Workspace destino
      |
      +--> descubre Reports
      +--> descubre Semantic Models
      +--> descubre Paginated Reports
      |
      +--> lee definiciones reales
      |
      +--> relaciona objetos por carpeta, nombre, página y parámetros
      |
      +--> obtiene los IDs reales del destino
      |
      +--> aplica las correcciones en el mismo workspace
```

Esto evita depender de que DEV, QA o Producción tengan los mismos IDs internos.

---

## 4. Flujo general de la aplicación

El flujo general de la aplicación puede representarse con el siguiente pseudocódigo:

```text
INICIO

    cargar configuración JSON

    autenticar contra Fabric API
    autenticar contra Power BI API

    workspace_destino <- obtener workspace configurado

    reports <- descubrir Reports en workspace_destino
    semantic_models <- descubrir Semantic Models en workspace_destino
    paginated_reports <- descubrir Paginated Reports en workspace_destino

    leer definiciones reales de reports
    leer definiciones reales de paginated_reports

    detectar RDL Visuals en los reports

    PARA CADA semantic_model
        obtener datasources actuales
        identificar datasource Oracle
        localizar gateway y datasource esperados
        vincular semantic_model con gateway/datasource

        SI refreshSemanticModels = true
            solicitar refresh

            SI waitForRefresh = true
                esperar hasta Completed o Failed
            FIN SI
        FIN SI
    FIN PARA

    PARA CADA paginated_report
        resolver semantic_model correspondiente
        validar referencias del RDL

        SI requiere corrección
            actualizar RDL preservando el XML
            aplicar updateDefinition sobre el mismo itemId
        FIN SI
    FIN PARA

    redescubrir objetos del workspace_destino

    PARA CADA paginated_report
        resolver semantic_model destino
        obtener datasource runtime actual
        conservar server actual
        actualizar database virtual al semanticModelId destino
        ejecutar TakeOver
        ejecutar Default.UpdateDatasources
    FIN PARA

    volver a leer definiciones de reports

    PARA CADA rdl_visual detectado
        resolver paginated_report destino usando:
            - carpeta
            - nombre
            - página
            - parámetros

        SI existe una resolución única y segura
            itemId <- id real del paginated_report destino
            workspaceId <- id del workspace_destino

            actualizar visual.json
            ejecutar updateDefinition del report
        SI NO
            registrar visual no resuelto

            SI failOnUnresolvedRdlVisual = true
                terminar con error
            FIN SI
        FIN SI
    FIN PARA

    guardar logs y evidencia HTTP

FIN
```

Vista resumida del algoritmo:

```text
Workspace destino
      |
      +--> descubre Reports
      +--> descubre Semantic Models
      +--> descubre Paginated Reports
      |
      +--> lee definiciones reales
      |
      +--> relaciona objetos por carpeta, nombre, página y parámetros
      |
      +--> obtiene los IDs reales del destino
      |
      +--> aplica las correcciones en el mismo workspace
```

---

## 5. Orden de ejecución

El orden implementado en `main.py` es importante.

### Paso 1. Cargar configuración

La aplicación lee el archivo JSON indicado mediante:

```text
--config
```

Si no se proporciona, utiliza la ruta configurada como valor predeterminado en `main.py`.

La configuración se carga mediante:

```python
load_config(args.config)
```

---

### Paso 2. Autenticación

La aplicación solicita dos access tokens diferentes:

```text
Fabric API:
https://api.fabric.microsoft.com
Power BI API:
https://analysis.windows.net/powerbi/api
```

La autenticación se realiza mediante Azure CLI desde `auth.py`.

Se inicializan dos clientes HTTP:

```text
Fabric:
https://api.fabric.microsoft.com/v1
Power BI:
https://api.powerbi.com/v1.0/myorg
```

---

### Paso 3. Descubrimiento del workspace destino

`workspace.py` obtiene los objetos existentes en el workspace configurado:
- Reports;
- Semantic Models;
- Paginated Reports.

Para cada elemento se conserva:
- ID;
- nombre;
- tipo;
- folder ID.

La aplicación utiliza esta información para resolver relaciones sin consultar un workspace fuente.

---

### Paso 4. Descubrimiento de RDL Visuals

Para cada reporte principal se obtiene su definición mediante Fabric REST API.

La aplicación inspecciona los `visual.json` y detecta aquellos cuyo tipo es:

```json
"visualType": "rdlVisual"
```

Para cada RDL Visual obtiene, entre otros datos:

- reporte propietario;
- carpeta del reporte;
- página;
- ruta del `visual.json` dentro de la definición;
- `itemId` actual;
- `workspaceId` actual;
- parámetros configurados.

Estos datos se utilizan posteriormente para resolver el informe paginado correcto.

---

## 6. Vinculación de Semantic Models con Gateway

La vinculación se ejecuta antes de actualizar los informes paginados.

El módulo principal es:

```text
powerbi_gateway.py
```

Para cada Semantic Model:

1\. obtiene los datasources actuales;
2\. identifica el datasource Oracle;
3\. consulta gateways compatibles;
4\. busca una coincidencia segura con la base configurada;
5\. realiza el binding del Semantic Model con el datasource del gateway;
6\. valida el resultado.

La configuración utiliza:

```json
"expectedOracleDatabase": "NCI_QA_DB"
```

La resolución busca que el datasource corresponda al ambiente esperado y evita seleccionar conexiones incompatibles.

---

## 7. Refresh de Semantic Models

Después del gateway binding se ejecuta el refresh.

El módulo es:

```text
semantic_refresh.py
```

Este paso es el equivalente programático de:

```text
Power BI Service
    > Semantic Model
    > Actualizar ahora
```

Para cada modelo:
1\. consulta sus propiedades;
2\. verifica si es refrescable;
3\. solicita un refresh;
4\. opcionalmente espera hasta que termine;
5\. puede fallar la ejecución si el refresh termina con error.

La espera se controla mediante configuración:

```json
{
  "refreshSemanticModels": true,
  "waitForRefresh": true,
  "failOnRefreshError": true,
  "refreshPollSeconds": 5,
  "refreshTimeoutSeconds": 1800
}
```

---

## 8. Corrección de informes paginados

El módulo principal es:

```text
paginated.py
```

La aplicación lee la definición RDL actual del informe paginado y resuelve el Semantic Model correcto dentro del mismo workspace destino.

### 8.1 Campos corregidos

La aplicación puede ajustar en el RDL:
- nombre del datasource;
- `PowerBIWorkspaceName`;
- `PowerBIDatasetName`;
- connect string hacia el modelo semántico.

### 8.2 Actualización in-place

El informe paginado se actualiza utilizando `updateDefinition` sobre el mismo objeto.

La aplicación **\*\*no elimina, recrea ni renombra\*\*** el informe paginado.

Esto es importante porque recrearlo cambiaría su `itemId` y Git Integration podría interpretar la operación como:

```text
DELETE del informe anterior
\+
ADD de un informe nuevo
```

La estrategia implementada preserva la identidad del objeto.

### 8.3 Preservación del XML

La modificación del RDL utiliza una estrategia de reemplazo de texto que evita reserializar completamente el XML.

El código la identifica como:

```text
TEXT-PRESERVING
```

El objetivo es modificar únicamente las referencias necesarias sin alterar innecesariamente el resto del archivo RDL.

---

## 9. Binding runtime del informe paginado

Actualizar el XML del RDL no siempre es suficiente para cambiar la conexión efectiva que Power BI mantiene en runtime.

Por este motivo existe una segunda fase en:

```text
powerbi_paginated.py
```

El proceso puede expresarse con el siguiente pseudocódigo:

```text
PARA CADA paginated_report

    datasource_runtime <- obtener datasource runtime actual

    datasource_name <- leer nombre de datasource persistido en el RDL

    semantic_model_destino <- resolver Semantic Model correspondiente
                              dentro del workspace destino

    server_actual <- datasource_runtime.server

    database_destino <- "sobe_wowvirtualserver-" + semantic_model_destino.id

    realizar TakeOver del paginated_report

    ejecutar Default.UpdateDatasources con:

        datasourceName = datasource_name

        connectionDetails.server = server_actual

        connectionDetails.database = database_destino

    validar resultado de la actualización

FIN PARA
```

La aplicación conserva el servidor reportado por Power BI y modifica únicamente la base virtual para que apunte al Semantic Model real del workspace destino.

---

## 10. Resolución de RDL Visuals

Después de corregir los informes paginados, la aplicación vuelve a leer las definiciones de los reportes principales.

El módulo responsable es:

```text
remediation.py
```

Para cada RDL Visual intenta encontrar el informe paginado correcto utilizando información del workspace destino.

### Estrategias de resolución

La resolución considera:
- carpeta del reporte;
- nombre del reporte;
- nombre de página;
- palabras normalizadas;
- parámetros del RDL Visual;
- parámetros definidos en el informe paginado.

La aplicación utiliza reglas de normalización para equivalencias como:

```text
aceptada  -> aceptado
aceptado  -> aceptado
rechazada -> rechazado
rechazado -> rechazado
recibidas -> recibido
recibidos -> recibido
```

Esto permite relacionar nombres funcionalmente equivalentes aunque exista variación de género o número.

---

## 11. Corrección del RDL Visual

Cuando el informe paginado destino queda resuelto, la aplicación modifica el `visual.json` correspondiente.

Se actualizan principalmente:

```text
itemId
workspaceId
```

con:

```text
itemId     = ID real del Paginated Report destino
workspaceId = ID del workspace destino
```

La definición del reporte principal se actualiza mediante Fabric `updateDefinition`.

---

## 12. Algoritmo de post-deploy

El comportamiento completo puede expresarse con el siguiente pseudocódigo:

```text

INICIO

leer configuración
obtener token Fabric
obtener token Power BI
listar objetos del workspace destino
leer definiciones de Reports
detectar RDL Visuals
leer definiciones de Paginated Reports

PARA CADA Semantic Model
    obtener datasources
    descubrir gateways compatibles
    seleccionar datasource Oracle esperado
    bind Semantic Model -> Gateway
FIN PARA

PARA CADA Semantic Model
    SI refresh está habilitado
        solicitar refresh
        SI waitForRefresh = true
            esperar hasta Completed o Failed
        FIN SI
    FIN SI
FIN PARA

PARA CADA Paginated Report
    resolver Semantic Model de la misma carpeta
    leer RDL actual
    validar referencias
    SI requiere cambios
        modificar RDL preservando XML
        updateDefinition sobre el mismo itemId
    FIN SI
FIN PARA

redescubrir workspace

PARA CADA Paginated Report
    resolver Semantic Model destino
    obtener datasource runtime actual
    leer datasourceName del RDL persistido
    realizar TakeOver
    ejecutar Default.UpdateDatasources
FIN PARA

volver a leer definiciones de Reports

PARA CADA RDL Visual
    buscar Paginated Report candidato
    resolver por carpeta/nombre/página/parámetros
    SI existe una única resolución segura
        actualizar itemId
        actualizar workspaceId
        updateDefinition del Report
    SI NO
        reportar unresolved
        fallar si la configuración lo exige
    FIN SI
FIN PARA

FIN

```

---

## 13. Configuración

La clase `PostDeployConfig` de `config.py` soporta actualmente las siguientes propiedades:

| Propiedad | Uso |
|---|---|
| `workspaceId` | ID del workspace destino. |
| `workspaceName` | Nombre del workspace destino. |
| `expectedOracleDatabase` | Base Oracle esperada para el ambiente. |
| `failOnUnresolvedRdlVisual` | Falla si un RDL Visual no puede resolverse de forma segura. |
| `applyRdlVisualFix` | Habilita la corrección de RDL Visuals. |
| `applyPaginatedReportFix` | Habilita la corrección del RDL paginado. |
| `failOnUnresolvedPaginatedReport` | Falla si no puede resolverse un informe paginado. |
| `bindSemanticModelsToConnection` | Habilita el binding de modelos semánticos. |
| `failOnUnresolvedConnectionBinding` | Falla si el binding de gateway/conexión no puede resolverse. |
| `bindPaginatedReportsToSemanticModels` | Habilita el binding runtime de paginados. |
| `failOnUnresolvedPaginatedDatasourceBinding` | Falla si no puede corregirse el datasource runtime. |
| `recreatePaginatedOnDefinitionMismatch` | Se conserva por compatibilidad de configuración; el flujo actual no recrea paginados. |
| `refreshSemanticModels` | Habilita refresh de Semantic Models. |
| `waitForRefresh` | Espera a que el refresh termine. |
| `failOnRefreshError` | Falla si un refresh falla. |
| `refreshPollSeconds` | Intervalo de consulta del estado del refresh. |
| `refreshTimeoutSeconds` | Timeout máximo del refresh. |

Ejemplo:

```json

{
  "workspaceId": "<workspace-id>",
  "workspaceName": "ws-delta-cicd",
  "expectedOracleDatabase": "NCI_QA_DB",
  "failOnUnresolvedRdlVisual": true,
  "applyRdlVisualFix": true,
  "applyPaginatedReportFix": true,
  "failOnUnresolvedPaginatedReport": true,
  "bindSemanticModelsToConnection": true,
  "failOnUnresolvedConnectionBinding": true,
  "bindPaginatedReportsToSemanticModels": true,
  "failOnUnresolvedPaginatedDatasourceBinding": true,
  "recreatePaginatedOnDefinitionMismatch": false,
  "refreshSemanticModels": true,
  "waitForRefresh": true,
  "failOnRefreshError": true,
  "refreshPollSeconds": 5,
  "refreshTimeoutSeconds": 1800
}
```

---

## 14. Estructura del código

```text
src/
├── main.py
├── auth.py
├── config.py
├── diagnostics.py
├── fabric_connections.py
├── gateway.py
├── http_clients.py
├── paginated.py
├── powerbi_gateway.py
├── powerbi_paginated.py
├── remediation.py
├── repository.py
├── semantic_refresh.py
├── workspace.py
└── requirements.txt
```

### Responsabilidad por módulo

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Orquestación completa del post-deploy. |
| `auth.py` | Obtención de tokens mediante Azure CLI. |
| `config.py` | Lectura y modelado de la configuración JSON. |
| `http_clients.py` | Cliente HTTP, manejo de errores y operaciones LRO de Fabric. |
| `workspace.py` | Descubrimiento de objetos y lectura/actualización de definiciones Fabric. |
| `powerbi_gateway.py` | Binding de Semantic Models con gateway. |
| `semantic_refresh.py` | Refresh de Semantic Models. |
| `paginated.py` | Corrección in-place del XML RDL persistido. |
| `powerbi_paginated.py` | Corrección del datasource runtime de informes paginados. |
| `remediation.py` | Resolución de Paginated Reports y corrección de RDL Visuals. |
| `diagnostics.py` | Trazas, logs, payloads HTTP y comandos curl reproducibles. |
| `repository.py` | Utilidades de descubrimiento de contenido desde un repositorio local. |
| `fabric_connections.py` | Utilidades de resolución de conexiones Fabric. |
| `gateway.py` | Implementación auxiliar de lógica de gateway. |

---

## 15. Diagnóstico y trazabilidad

Cada ejecución genera una carpeta:

```text
log/postdeploy_YYYYMMDD_HHMMSS/
```

La carpeta incluye:

```text
execution.log
manifest.json
http/
```

Para cada llamada HTTP se almacenan artefactos como:

```text
metadata.json
request.json
response.json
response.txt
curl.txt
decoded-request-parts/
decoded-response-parts/
```

Los tokens Bearer son redactados y no se escriben en disco.

Esto permite reproducir una solicitud con `curl.exe`, inspeccionar payloads y relacionar cada llamada HTTP con el paso funcional correspondiente.

---

## 16. Operaciones de larga duración

Las operaciones `getDefinition` y `updateDefinition` de Fabric pueden responder con `202 Accepted`.

`http_clients.py` maneja el patrón LRO utilizando el `operationId` de Fabric y consulta:

```text
/operations/{operationId}
```

hasta obtener un estado terminal.

Cuando se necesita el resultado de una operación se consulta:

```text
/operations/{operationId}/result
```

---

## 17. Restricciones importantes

### No usar formatos explícitos para Paginated Report Definition

La implementación actual llama:

```text
POST /paginatedReports/{id}/getDefinition
```

sin enviar explícitamente:

```text
?format=PaginatedReportDefinition
```

ni un campo JSON equivalente.

Esto permite utilizar el formato predeterminado y evita incompatibilidades observadas en algunos tenants.

### No recrear informes paginados

La aplicación debe preservar el `itemId` existente.

No debe realizar como parte de la remediación normal:

```text
rename -> create -> delete -> move
```

El comportamiento correcto es:

```text
mismo Paginated Report
        |
        +--> updateDefinition
        +--> Default.UpdateDatasources
```

---

## 18. Momento de ejecución dentro del CI/CD

La aplicación se ejecuta después de que la versión del repositorio ya fue desplegada al workspace destino.

Flujo recomendado:

```text
Git branch de ambiente
        |
        v
Workspace destino
        |
        v
Update from Git
        |
        v
Validar sincronización
        |
        v
Ejecutar fix-rdl-pbi-py
        |
        v
Validar reportes
        |
        v
Registrar en Git únicamente los cambios de definición
que deban persistir en la rama de ambiente
```

La aplicación no sustituye los reemplazos estáticos realizados por GitHub Actions. Los complementa resolviendo valores que solamente pueden conocerse después del despliegue.

---

## 19. Resultado esperado

Al terminar correctamente la aplicación:

- los Semantic Models están vinculados con el gateway/datasource esperado;

- los Semantic Models pueden refrescarse;

- los Paginated Reports conservan su mismo `itemId`;

- el RDL persistido contiene referencias coherentes con el workspace destino;

- el datasource runtime del Paginated Report apunta al Semantic Model destino;

- los RDL Visuals contienen el `itemId` real del Paginated Report destino;

- los RDL Visuals contienen el `workspaceId` real del ambiente;

- se generan logs suficientes para auditar y reproducir cada operación.

---

## 20. Resumen

`fix-rdl-pbi-py` funciona como una capa de **\*\*remediación post-deploy\*\*** para Power BI/Fabric.

La idea central es separar:

```text
Valores estáticos conocidos antes del despliegue
        -> GitHub Actions / archivos de ambiente
Valores dinámicos conocidos solamente en el destino
        -> aplicación Python post-deploy
```

De esta manera, el despliegue puede promover la misma solución entre ambientes aunque los objetos de Fabric y Power BI tengan IDs internos diferentes.