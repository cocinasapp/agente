
import logging, os
from anthropic import Anthropic
from dotenv import load_dotenv
from supabase_utils import write_log

load_dotenv()

logger = logging.getLogger(__name__)

anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

try:
    anthropic_client = Anthropic(api_key=anthropic_api_key)
    logger.info("Cliente de Anthropic inicializado exitosamente.")

except Exception as e:
    logger.error("Error al inicializar el cliente de Anthropic: %s", e)
    write_log("system", "anthropic_client_init_error", f"Error al inicializar el cliente de Anthropic: {e}", nivel="error")