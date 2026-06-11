import asyncio, json, logging, os
from clients.redis_client import redis_client
from clients.supabase_client import supabase_client
from datetime import datetime
from db import DBCA
from dotenv import load_dotenv

load_dotenv()

TBL_USUARIOS=os.getenv('TBL_USUARIOS')
USER_ID=os.getenv('USER_ID')

supabase_class = DBCA()
session_id=supabase_class.get_session_id(USER_ID)

logger = logging.getLogger(__name__)

# TTL de 7 días para el session context en Redis
SESSION_CONTEXT_TTL = 60 * 60 * 24 * 7

def get_usuario(telefono: str):
    result = supabase_client.table(TBL_USUARIOS).select("*").eq("phone_number", telefono).execute()
    if result.data:
        return result.data[0]
    logger.warning("Usuario no encontrado: %s", telefono)
    return None

def upsert_usuario(telefono: str, campos: dict, user_id: str = USER_ID, session_id=session_id):
    payload = {
        "phone_number": telefono,
        "user_id": user_id,
        "session_id":session_id,
        "ultima_actividad": datetime.utcnow().isoformat(),
        **campos  # si campos trae business_unit explícito, lo pisa (correcto)
    }
    supabase_client.table(TBL_USUARIOS).upsert(payload).execute()
    logger.debug("Usuario upserted: %s", telefono)

def get_estado_desde_supabase(telefono: str):
    usuario = get_usuario(telefono)
    if usuario:
        return usuario.get("estado_actual", "new")
    return None

def guardar_mensaje(telefono: str, rol: str, mensaje: str, estado: str, user_id:str=USER_ID, session_id:str=session_id):
    supabase_client.table("conversations").insert({
        "phone_number": telefono,
        "role": rol,
        "message": mensaje,
        "estado_actual": estado,
        "user_id":user_id,
        "session_id":session_id,
        "type":"text"
    }).execute()
    logger.debug("Mensaje guardado | phone_number: %s | rol: %s | estado: %s", telefono, rol, estado)

# ============================================================
# SESSION CONTEXT
# ============================================================

def get_session_context(telefono: str) -> dict:
    """
    Lee el session context del usuario.
    1. Busca en Redis
    2. Si no hay, busca en Supabase (datos_recolectados)
    3. Si tampoco hay, retorna dict vacío
    """
    redis_key = f"session_context:{telefono}"
    
    context_redis = redis_client.get(redis_key)
    if context_redis:
        logger.debug("Session context desde Redis: %s", telefono)
        return json.loads(context_redis)
    
    usuario = get_usuario(telefono)
    if usuario and usuario.get("datos_recolectados"):
        contexto = usuario["datos_recolectados"]
        logger.debug("Session context desde Supabase: %s", telefono)
        redis_client.set(redis_key, json.dumps(contexto), ex=SESSION_CONTEXT_TTL)
        return contexto

    logger.debug("Session context vacío para: %s", telefono)
    return {}

def set_session_context(telefono: str, contexto: dict):
    """
    Persiste el session context.
    - Redis: síncrono, inmediato
    - Supabase: actualiza datos_recolectados
    """
    redis_key = f"session_context:{telefono}"
    
    redis_client.set(redis_key, json.dumps(contexto), ex=SESSION_CONTEXT_TTL)
    logger.debug("Session context guardado en Redis: %s", telefono)
    
    upsert_usuario(telefono, campos={"datos_recolectados": contexto})
    logger.debug("Session context guardado en Supabase: %s", telefono)

def update_session_context(telefono: str, nuevos_campos: dict):
    """
    Actualiza campos específicos del contexto sin pisar todo el diccionario.
    Útil para agregar flags o contadores desde los handlers.
    
    Ejemplo desde un handler:
        update_session_context(telefono, {"veces_en_gral": 3, "ultima_intencion": "gral"})
    """
    contexto_actual = get_session_context(telefono)
    contexto_actual.update(nuevos_campos)
    set_session_context(telefono, contexto_actual)
    logger.debug("Session context actualizado: %s | campos: %s", telefono, list(nuevos_campos.keys()))
    return contexto_actual

# ============================================================
# NOTIFICACIONES OPT_IN
# ============================================================

def update_notificacion_opt_in(telefono: str, order_id: str, producto: str, acepto: bool):
    supabase_client.table("notificaciones_programadas").update({
        "respondio_si": acepto,
        "activo": acepto
    }).eq("phone_number", telefono)\
      .eq("order_id", order_id)\
      .eq("tipo", "opt_in")\
      .execute()
    logger.debug("Opt_in actualizado | telefono: %s | order_id: %s | acepto: %s", telefono, order_id, acepto)

# ========== ========== WRITE LOG --- FUNCION ORIGINAL SINCRONA ========== ==========
# def write_log_orig(telefono: str, etiqueta: str, mensaje: str, nivel: str = "info"):
#     try:
#         # supabase_client.table("logs").insert({
#         #     "telefono": telefono,
#         #     "nivel": nivel,
#         #     "etiqueta": etiqueta,
#         #     "mensaje": str(mensaje)
#         # }).execute()
#         return 
#     except Exception as e:
#         logger.error("Error escribiendo log | telefono: %s | etiqueta: %s | error: %s", telefono, etiqueta, e)
#         print(f"❌ Error escribiendo log: {e}")  # fallback silencioso


# def write_log(telefono: str, etiqueta: str, mensaje: str, nivel: str = "info"):
#     try:
#         loop = asyncio.get_running_loop()
#         loop.create_task(_persist_log(telefono, etiqueta, mensaje, nivel))
#     except RuntimeError:
#         # Contexto sync puro (startup, inicialización) — skip silencioso
#         pass

# async def _persist_log(telefono: str, etiqueta: str, mensaje: str, nivel: str):
#     try:
#         await supabase_client.table("logs").insert({
#             "telefono": telefono,
#             "nivel": nivel,
#             "etiqueta": etiqueta,
#             "mensaje": str(mensaje)
#         }).execute()

#     except Exception as e:
#         print(f"❌ Error persistiendo log: {e}")

def borrar_conversaciones_usuario(telefono: str):
    try:
        supabase_client.table("conversations")\
            .delete()\
            .eq("phone_number", telefono)\
            .execute()
        logger.debug("Conversaciones borradas: %s", telefono)
    except Exception as e:
        logger.error("Error borrando conversaciones | telefono: %s | error: %s", telefono, e)

if __name__ == '__main__':
    upsert_usuario(
        telefono='5566098295', 
        user_id='ed4d8410-3cba-451f-90c1-0232e1a9ce31', 
        campos={
            "estado_actual": "new",
            "datos_recolectados": {}
        }
    )