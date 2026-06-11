import logging
import os

def setup_logging():
    """
    Configura el sistema de logging para toda la aplicación.

    Dev  (ENV != "prod"): nivel DEBUG — todo visible, solo stdout.
    Prod (ENV == "prod"): nivel INFO  — flujo principal + warnings + errores,
                          solo stdout (Render captura stdout automáticamente).

    IMPORTANTE: load_dotenv() debe llamarse antes de esta función
    para que la variable ENV esté disponible.

    Uso: llamar UNA SOLA VEZ desde app.py y agente.py, lo antes posible.
    En cada módulo: logger = logging.getLogger(__name__)
    """
    env = os.getenv("ENV", "dev")
    is_prod = env == "prod"

    level = logging.INFO if is_prod else logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler()],
    )

    if is_prod:
        # httpx genera una línea INFO por cada request a Supabase/OpenAI.
        # En prod solo nos interesan sus errores.
        logging.getLogger("httpx").setLevel(logging.WARNING)

        # uvicorn.access genera una línea por cada request HTTP entrante.
        # En prod solo nos interesan los 4xx/5xx, no los 200 OK.
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

        # openai genera logs internos de reintentos y conexiones.
        logging.getLogger("openai").setLevel(logging.WARNING)