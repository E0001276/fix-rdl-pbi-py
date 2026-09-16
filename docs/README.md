# Documentación MkDocs

La estructura se conserva de esta forma:

```text
docs/
├── mkdocs.yml
├── README.md
└── files/
    ├── index.md
    ├── arquitectura.md
    ├── auth.md
    ├── config.md
    └── ...
```

Desde la carpeta `docs`:

```powershell
mkdocs build
mkdocs serve
```

`mkdocs.yml` usa:

```yaml
docs_dir: files
```

El sitio generado se crea en `docs/site/`.
