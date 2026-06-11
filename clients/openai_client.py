
import logging, os, sys
from dotenv import load_dotenv
from openai import OpenAI
from supabase_utils import write_log

load_dotenv()

logger = logging.getLogger(__name__)

try:
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger.info("Cliente de OpenAI inicializado correctamente!")

except Exception as e:
    logger.error("Error al inicializar el cliente de OpenAI: %s", e)
    write_log("system", "openai_client_init_error", f"Error al inicializar el cliente de OpenAI: {e}", nivel="error")