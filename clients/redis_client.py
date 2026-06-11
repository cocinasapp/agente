# python3 -m clients.redis_client

import logging, os, redis, sys
from dotenv import load_dotenv
from supabase_utils import write_log

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=os.getenv("REDIS_PORT"),
    decode_responses=True,
    username="default",
    password=os.getenv("REDIS_PASSWORD"),
    socket_connect_timeout=5
)

try:
    redis_client.ping()
    logger.info("Cliente de Redis inicializado correctamente")

except (redis.exceptions.RedisError, TypeError, ValueError) as e:
    logger.error("Redis no disponible: %s", e)
    write_log("system", "redis_client_init_error", f"Error al inicializar el cliente de Redis: {e}", nivel="error")
    sys.exit(1)

