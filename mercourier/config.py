import importlib.util


def load_config(path="config_secrets.py"):
    spec = importlib.util.spec_from_file_location("secrets", path)
    secrets_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(secrets_module)

    return secrets_module.CREDENTIALS
