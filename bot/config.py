import importlib.util

def load_config():
    """Load configuration from """
    spec = importlib.util.spec_from_file_location('secrets', 'secrets.py')
    secrets_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(secrets_module)

    return secrets_module.CREDENTIALS
