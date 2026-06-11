
import logging, os, sys
from dotenv import load_dotenv
from logger_utils import write_log
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    supabase_client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY")
    )
    logger.info("Cliente de Supabase inicializado correctamente")

except Exception as e:
    logger.error("Supabase no disponible: %s", e)
    write_log("system", "supabase_client_init_error", f"Error al inicializar el cliente de Supabase: {e}", nivel="error")
    sys.exit(1)

