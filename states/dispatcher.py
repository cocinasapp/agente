import logging
import sys, os
from dotenv import load_dotenv

load_dotenv()

USER_ID=os.getenv('USER_ID')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)

try:
    from clients.redis_client import redis_client
    from config import ENABLE_GATHER_INFO
    from supabase_utils import (
        get_estado_desde_supabase, 
        get_session_context,
        guardar_mensaje,
        set_session_context,
        upsert_usuario
        )
    from states.new.handler import handle_new
    from states.gral.handler import handle_gral
    from states.comensal.handler import handle_comensal    
    from states.pedido.handler import handle_pedido
    from states.recolectar_info.handler import handle_recolectar_info
    from states.terminar_pedido.handler import handle_terminar_pedido
    from states.serv_client.handler import handle_serv_client

except Exception as e:
    logger.critical("Error al importar dependencias: %s", e)
    sys.exit(1)

HANDLERS = {
    "new": handle_new,
    "gral": handle_gral,
    "comensal": handle_comensal,
    "pedido": handle_pedido,
    "recolectar_info": handle_recolectar_info,
    "terminar_pedido": handle_terminar_pedido,
    "serv_client": handle_serv_client
    # "gather_info": handle_gather_info,
    # "follow_up": handle_follow_up,
}

# ============================ FUNCIONES ORIGINALES ================================
def get_estado_orig(telefono: str) -> str:
    """
    1. Busca estado en Redis
    2. Si no hay, busca en Supabase
    3. Si tampoco hay, es new
    """
    redis_key = f"estado:{telefono}"

    # inicio test local
    estado_redis = redis_client.get(redis_key)

    if estado_redis:
        if estado_redis == "gather_info" and not ENABLE_GATHER_INFO:
            return "follow_up"
        logger.debug("Estado desde Redis | telefono: %s | estado: %s", telefono, estado_redis)
        return estado_redis

    estado_supa = get_estado_desde_supabase(telefono)
    if estado_supa:
        if estado_supa == "gather_info" and not ENABLE_GATHER_INFO:
            return "follow_up"
        logger.debug("Estado desde Supabase | telefono: %s | estado: %s", telefono, estado_supa)
        redis_client.set(redis_key, estado_supa, ex=60*60*24)
        return estado_supa

    logger.debug("Usuario nuevo: %s", telefono)
    return "new"

def set_estado_orig(telefono: str, nuevo_estado: str, user_id: str = USER_ID):
    """Persiste el estado en Redis y Supabase."""

    redis_key = f"estado:{telefono}"
    redis_client.set(redis_key, nuevo_estado, ex=60*60*24)
    upsert_usuario(telefono=telefono, 
                   campos={
                       "estado_actual": nuevo_estado
                       }
                   )
    logger.debug("Estado guardado | telefono: %s | estado: %s", telefono, nuevo_estado)

# ============================ FUNCIONES PROPUESTAS ================================
def get_estado(telefono: str) -> str:
    redis_key = f"estado:{telefono}"

    try:
        estado_redis = redis_client.get(redis_key)
        if estado_redis:
            if estado_redis == "gather_info" and not ENABLE_GATHER_INFO:
                return "follow_up"
            logger.debug("Estado desde Redis | telefono: %s | estado: %s", telefono, estado_redis)
            return estado_redis
    except Exception as e:
        logger.warning("Redis caído en get_estado, usando Supabase | error: %s", e)

    estado_supa = get_estado_desde_supabase(telefono)
    if estado_supa:
        if estado_supa == "gather_info" and not ENABLE_GATHER_INFO:
            return "follow_up"
        logger.debug("Estado desde Supabase | telefono: %s | estado: %s", telefono, estado_supa)
        try:
            redis_client.set(redis_key, estado_supa, ex=60*60*24)
        except Exception as e:
            logger.warning("No se pudo cachear estado en Redis | error: %s", e)
        return estado_supa

    logger.debug("Usuario nuevo: %s", telefono)
    return "new"

def set_estado(telefono: str, nuevo_estado: str, user_id: str = USER_ID):
    redis_key = f"estado:{telefono}"

    try:
        redis_client.set(redis_key, nuevo_estado, ex=60*60*24)
    except Exception as e:
        logger.warning("No se pudo escribir estado en Redis | error: %s", e)

    # Supabase siempre se escribe
    upsert_usuario(telefono=telefono, campos={"estado_actual": nuevo_estado})
    logger.debug("Estado guardado | telefono: %s | estado: %s", telefono, nuevo_estado)

# ============================================================
# DISPATCH
# ============================================================

def dispatch(messages, data, telefono):
    estado_actual = get_estado(telefono)
    logger.debug("Estado actual | telefono: %s | estado: %s", telefono, estado_actual)

    session_context = get_session_context(telefono)

    # Seleccionador de funciones de acuerdo al estado actual
    handler = HANDLERS.get(estado_actual, HANDLERS["gral"])

    resultado = handler(messages, data, telefono, session_context)

    if resultado is None:
        logger.error("Handler retornó None | telefono: %s | estado: %s", telefono, estado_actual)
        from states.shared_prompts import CONTEXT
        from utils_llm import llamar_llm
        respuesta = llamar_llm(CONTEXT, messages, data["body"])
        resultado = {"answer": respuesta, "nuevo_estado": estado_actual, "session_context": session_context}

    nuevo_estado = resultado.get("nuevo_estado", estado_actual)
    datos_extraidos = resultado.get("datos_extraidos", {})
    nuevo_contexto = resultado.get("session_context")

    if nuevo_estado != estado_actual:
        logger.info("Transición | telefono: %s | %s → %s", telefono, estado_actual, nuevo_estado)
    set_estado(telefono, nuevo_estado)

    if datos_extraidos:
        campos = {k: v for k, v in datos_extraidos.items() if v is not None}
        if campos:
            upsert_usuario(telefono, campos={"message":data["body"]})

    if nuevo_contexto is not None:
        set_session_context(telefono, nuevo_contexto)

    guardar_mensaje(telefono, "user", data["body"], estado_actual)
    guardar_mensaje(telefono, "assistant", resultado["answer"], nuevo_estado)

    return resultado

if __name__=='__main__':
    print(
        # f'estado: {get_estado(telefono='5624307972')}'
        set_estado('5624307972', 'new')
        )