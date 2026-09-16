# `paginated.py`

Documentación del módulo Python [`src/paginated.py`](../../src/paginated.py).

## Responsabilidad del módulo

Modifica in-place el XML RDL persistido de informes paginados conservando su identidad.

## Dependencias

- `base64`
- `re`
- `xml.etree.ElementTree`
- `dataclasses: dataclass`
- `workspace: get_paginated_report_definition, update_paginated_report_definition`

## Clases

### `PaginatedBindingResult`

Estructura de datos con los siguientes campos:

| Campo | Tipo | Valor predeterminado |
|---|---|---|
| `paginated_report_id` | `str` | `Requerido` |
| `paginated_report_name` | `str` | `Requerido` |
| `semantic_model_id` | `str` | `Requerido` |
| `semantic_model_name` | `str` | `Requerido` |
| `status` | `str` | `Requerido` |
| `message` | `str` | `''` |

## Funciones

### `_local_name(tag: str)`

Obtiene el nombre local de una etiqueta XML eliminando el namespace.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `tag` | `str` | `Requerido` |

**Retorno**

`str`

### `_normalize_workspace_datasource_prefix(workspace_name: str)`

Normaliza el nombre del workspace para formar el prefijo de datasource utilizado en RDL.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `workspace_name` | `str` | `Requerido` |

**Retorno**

`str`

### `_target_datasource_name(current_name: str, workspace_name: str)`

Target-only equivalent of the .NET workspace-prefix replacement.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `current_name` | `str` | `Requerido` |
| `workspace_name` | `str` | `Requerido` |

**Retorno**

`str`

### `_decode_part(part: dict)`

Decodifica el payload InlineBase64 de una parte de definición Fabric.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `part` | `dict` | `Requerido` |

**Retorno**

`str`

**Comportamiento y efectos**

Llamadas relevantes: `base64.b64decode`.

### `_encode_rdl(xml_text: str)`

Codifica el XML RDL en Base64 para enviarlo a `updateDefinition`.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `xml_text` | `str` | `Requerido` |

**Retorno**

`str`

**Comportamiento y efectos**

Llamadas relevantes: `base64.b64encode`.

### `_validate_rdl_namespace(xml_text: str)`

Fail fast if the RDL root no longer declares the report namespace as default.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `xml_text` | `str` | `Requerido` |

**Retorno**

`None`

**Excepciones explícitas**

- `RuntimeError('RDL root <Report> element was not found.')`
- `RuntimeError('RDL root Report element does not preserve the expected 2016/01 reportdefinition default namespace.')`
- `RuntimeError('RDL root was namespace-rewritten (for example ns0:Report). The post-deploy refuses to upload a rewritten RDL.')`

### `_replace_tag_text(xml_text: str, tag_name: str, transform)`

Reemplaza selectivamente el contenido textual de etiquetas XML sin reserializar por completo el RDL.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `xml_text` | `str` | `Requerido` |
| `tag_name` | `str` | `Requerido` |
| `transform` | `No especificado` | `Requerido` |

**Retorno**

`tuple[str, bool]`

### `_replace_datasource_names(xml_text: str, workspace_name: str)`

Actualiza los nombres de datasource del RDL para que correspondan al workspace destino.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `xml_text` | `str` | `Requerido` |
| `workspace_name` | `str` | `Requerido` |

**Retorno**

Devuelve tupla, valor calculado.

### `_find_rdl_part(definition_response: dict)`

Localiza la parte `.rdl` dentro de una respuesta de definición Fabric.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `definition_response` | `dict` | `Requerido` |

**Retorno**

`dict`

**Excepciones explícitas**

- `RuntimeError(f'Expected exactly one RDL definition part, found {len(rdl_parts)}.')`

### `_extract_rdl_binding(xml_text: str)`

Extrae del XML RDL la información de workspace, modelo semántico, datasource y cadena de conexión.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `xml_text` | `str` | `Requerido` |

**Retorno**

`dict`

### `_resolve_semantic_model(workspace_items, paginated_item)`

Resuelve el modelo semántico destino asociado al informe paginado usando el contexto del workspace.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `workspace_items` | `No especificado` | `Requerido` |
| `paginated_item` | `No especificado` | `Requerido` |

**Retorno**

Devuelve tupla.

### `_update_connect_string(value: str, target_model_id: str)`

Sustituye en la cadena de conexión el identificador virtual del modelo semántico.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `value` | `str` | `Requerido` |
| `target_model_id` | `str` | `Requerido` |

**Retorno**

`str`

### `_patch_rdl(xml_text: str, workspace_name: str, semantic_model_id: str, semantic_model_name: str)`

Patch only the binding values while preserving the original RDL XML.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `xml_text` | `str` | `Requerido` |
| `workspace_name` | `str` | `Requerido` |
| `semantic_model_id` | `str` | `Requerido` |
| `semantic_model_name` | `str` | `Requerido` |

**Retorno**

Devuelve tupla, valor calculado.

**Excepciones explícitas**

- `RuntimeError('RDL root default namespace was changed to AnalysisServices/QueryDefinition.')`

### `_is_binding_logically_correct(binding: dict, workspace_name: str, semantic_model_name: str)`

Match the .NET logical rule without consulting a source workspace.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `binding` | `dict` | `Requerido` |
| `workspace_name` | `str` | `Requerido` |
| `semantic_model_name` | `str` | `Requerido` |

**Retorno**

`bool`

### `_build_fabric_definition(original_response: dict, item_name: str, xml_after: str)`

Build the smallest supported PaginatedReportDefinition payload.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `original_response` | `dict` | `Requerido` |
| `item_name` | `str` | `Requerido` |
| `xml_after` | `str` | `Requerido` |

**Retorno**

`dict`

**Excepciones explícitas**

- `RuntimeError('The Fabric paginated definition did not contain an RDL part.')`

### `_expected_datasource_name(workspace_name: str, semantic_model_name: str)`

Calcula el nombre de datasource esperado para un modelo semántico del workspace destino.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `workspace_name` | `str` | `Requerido` |
| `semantic_model_name` | `str` | `Requerido` |

**Retorno**

`str`

### `_binding_matches_target(binding: dict, workspace_name: str, model_name: str)`

Comprueba que el binding extraído del RDL coincide con el destino esperado.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `binding` | `dict` | `Requerido` |
| `workspace_name` | `str` | `Requerido` |
| `model_name` | `str` | `Requerido` |

**Retorno**

`bool`

### `_extract_created_item_id(client, response)`

Extrae un identificador de item de una respuesta Fabric cuando existe.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `client` | `No especificado` | `Requerido` |
| `response` | `No especificado` | `Requerido` |

**Retorno**

Devuelve NoneType, valor calculado.

**Comportamiento y efectos**

Llamadas relevantes: `client.get_json_lro_result`.

### `remediate_paginated_reports(fabric, workspace_items, paginated_infos, config)`

Corrige in-place las definiciones de los informes paginados sin recrear los items.

**Parámetros**

| Parámetro | Tipo | Predeterminado |
|---|---|---|
| `fabric` | `No especificado` | `Requerido` |
| `workspace_items` | `No especificado` | `Requerido` |
| `paginated_infos` | `No especificado` | `Requerido` |
| `config` | `No especificado` | `Requerido` |

**Retorno**

Devuelve lista, valor `results`.

**Comportamiento y efectos**

Llamadas relevantes: `print`.
Escribe información de diagnóstico en consola.

**Excepciones explícitas**

- `RuntimeError(f'Unable to safely remediate {len(failures)} paginated report relationship(s).')`

## Archivo fuente

Ruta: `src/paginated.py`

Esta página documenta las clases, funciones y métodos definidos directamente en el archivo. No sustituye el código fuente como referencia de implementación.
