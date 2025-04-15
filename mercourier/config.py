import importlib.util


def load_config():
    spec = importlib.util.spec_from_file_location("secrets", "config_secrets.py")
    secrets_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(secrets_module)

    return secrets_module.CREDENTIALS
