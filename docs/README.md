# Documentación navegable de fix-rdl-pbi-py

Se generó un archivo Markdown por cada archivo `.py` encontrado en `src/`.

## Ver con panel de navegación

1. Abra una terminal en esta carpeta.
2. Instale MkDocs:

```powershell
pip install mkdocs
```

3. Ejecute:

```powershell
mkdocs serve
```

4. Abra la URL indicada, normalmente:

```text
http://127.0.0.1:8000/
```

El tema `readthedocs` crea un panel lateral. Al hacer clic en cada archivo Python se muestra su Markdown correspondiente.

## Generar sitio estático

```powershell
mkdocs build
```

Esto crea la carpeta `site/`.
