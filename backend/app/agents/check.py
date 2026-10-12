"""Validate model configuration locally without network access or inference."""
import argparse
import json
from app.agents.inference import configuration
from app.config import settings
from app.integrations.clients import ProviderError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        result = configuration(settings())
    except (ProviderError, ValueError):
        parser.exit(1, 'Model configuration invalid; check provider, HTTPS endpoint, model and API key presence. No network requests made.\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
