from pathlib import Path

import yaml


def load_yaml_mapping(path: str | Path, description: str) -> tuple[Path, dict]:
    """Load a YAML file and require a mapping/object at the document root."""
    yaml_path = Path(path).expanduser().resolve()

    if yaml_path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError(
            f"{description} must be a YAML file (.yaml or .yml): {yaml_path}"
        )

    if not yaml_path.is_file():
        raise FileNotFoundError(f"{description} was not found: {yaml_path}")

    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {description} '{yaml_path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{description} root must be a YAML mapping/object.")

    return yaml_path, data
