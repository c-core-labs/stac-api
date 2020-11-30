import os
from dotenv import load_dotenv


# Fix for fiona/gdal not finding ssl certificates:
# https://github.com/cogeotiff/rio-tiler/issues/53#issuecomment-412198813
os.environ["CURL_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"

# Load .env file into environment variables
load_dotenv()

es_key = os.environ.get("ES_KEY")
es_url = os.environ.get("ES_URL")
