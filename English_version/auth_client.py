import os
import warnings
from urllib3.exceptions import InsecureRequestWarning
from binance import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

# Load the .env file from the project root directory (adjust path as needed)
load_dotenv()  # Reads the .env file from the current working directory by default

# Ignore insecure request warnings
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# Proxy configuration (global variables, can be imported and used)
proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7897'
}

# Global client instance (Singleton)
_global_client = None


def get_binance_client():
    """
    Initialize and return the Binance client using the Singleton pattern (globally reused to avoid repeated logins)
    :return: Verified Binance Client object
    """
    global _global_client

    # If the client is already initialized, return it directly for reuse
    if _global_client is not None:
        return _global_client

    # Read keys (reading values from the .env file, not system-wide environment variables)
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')

    # Verify if keys exist (to avoid subsequent errors)
    if not api_key or not api_secret:
        raise ValueError("Please set the BINANCE_API_KEY and BINANCE_API_SECRET environment variables first")
    if len(api_key) < 50 or len(api_secret) < 50:
        raise ValueError("API key length is abnormal, please check if copied correctly")

    try:
        # 2. Initialize the client (with proxy and SSL configurations)
        client = Client(
            api_key,
            api_secret,
            requests_params={'proxies': proxies, 'verify': False}
        )
        # 3. Proactively ping to test the connection
        client.ping()
        print("✅ Binance client initialized successfully (Connection verified)")

        # Assign to the global variable for direct reuse next time
        _global_client = client
        return client

    except BinanceAPIException as e:
        raise Exception(f"API key/permission error: {e}") from e
    except Exception as e:
        raise Exception(f"Client initialization failed: {e}") from e


# Retain the ability to run independently
if __name__ == "__main__":
    get_binance_client()