# python3 -m chat_history

import json, logging, os, tiktoken
from clients.redis_client import redis_client
from dotenv import load_dotenv
from logger_utils import write_log

load_dotenv()

logger = logging.getLogger(__name__)

TIEMPO_NUEVO = os.getenv("TIEMPO_NUEVO") if os.getenv("TIEMPO_NUEVO") else 60 * 5

def get_chat_history(chat_historiy_id, telefono=None, redis_client=redis_client):
    stored_messages_json = redis_client.get(chat_historiy_id)
    if stored_messages_json:
        return json.loads(stored_messages_json)
    write_log("system", "chat_history_not_found", f"No se encontró historial para {chat_historiy_id} (teléfono {telefono})", nivel="warning")
    return []

def num_tokens(text, model="gpt-4o"):
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def add_to_chat_history(chat_historiy_id, mensaje, rol, telefono, redis_client=redis_client):
    redis_messages = get_chat_history(chat_historiy_id, telefono)

    token_budget = 40000
    current_count = 0

    for message in redis_messages:
        current_count += num_tokens(message["content"])

    while current_count + num_tokens(mensaje) > token_budget:
        if len(redis_messages) == 0:
            return False
        current_count -= num_tokens(redis_messages.pop(0)["content"])

    redis_messages.append({"content": mensaje, "role": rol})

    redis_client.setex(
        chat_historiy_id, TIEMPO_NUEVO, json.dumps(redis_messages)
    )

    return redis_messages

def reset_chat_history(chat_history_id, redis_client=redis_client):
    if not chat_history_id.startswith('fp-chatHistory:'):
        chat_history_id = f'fp-chatHistory:{chat_history_id}'

    ans = redis_client.delete(chat_history_id)

    if ans > 0:
        logger.info("Historial eliminado: %s", chat_history_id)
        write_log("system", "chat_history_reset", f"Historial reseteado para {chat_history_id}", nivel="info")

    else:
        logger.warning("Key no encontrada en Redis: %s", chat_history_id)
        write_log("system", "chat_history_reset_not_found", f"Intento de resetear historial no encontrado para {chat_history_id}", nivel="warning")

    return ans

def listar_chat_histories(redis_client=redis_client):
    pattern = 'fp-chatHistory:*'
    keys = redis_client.keys(pattern)

    logger.info("Total de chat histories: %d", len(keys))

    if not keys:
        logger.warning("No hay chat histories almacenados en Redis")
        return []

    for key in keys:
        content = redis_client.get(key)
        telefono = key.replace('fp-chatHistory:', '')

        try:
            mensajes = json.loads(content) if content else []
            num_mensajes = len(mensajes)
        except Exception:
            num_mensajes = "N/A"

        logger.debug(
            "Chat history | telefono: %s | mensajes: %s | ttl: %s segundos",
            telefono, num_mensajes, redis_client.ttl(key)
        )

    return keys

def get_orden_temporal(telefono, redis_client=redis_client):
    """
    Obtiene la orden temporal del usuario desde Redis
    
    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis
    
    Returns:
        dict o None: estructura de la orden temporal o None si no existe
    """
    key = f"orden_temporal:{telefono}"
    orden_json = redis_client.get(key)

    if orden_json:
        return json.loads(orden_json)

    return None

def save_orden_temporal(telefono, orden_data, redis_client=redis_client, ttl=1800):
    """
    Guarda o actualiza la orden temporal en Redis
    
    Args:
        telefono: número de teléfono del usuario
        orden_data: diccionario con la estructura de la orden temporal
        redis_client: cliente de Redis
        ttl: tiempo de expiración en segundos (default: 1800 = 30 minutos)
    
    Returns:
        bool: True si se guardó exitosamente
    """
    key = f"orden_temporal:{telefono}"

    try:
        redis_client.setex(
            key,
            ttl,
            json.dumps(orden_data)
        )
        return True

    except Exception as e:
        print(f"Error al guardar orden temporal: {e}")
        write_log(telefono, "error_save_orden_temporal", f"Error al guardar orden temporal: {orden_data} para {telefono}: {str(e)}", nivel="error")
        return False

def delete_orden_temporal(telefono, redis_client=redis_client):
    """
    Elimina la orden temporal de Redis (cuando se confirma o cancela)

    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis

    Returns:
        int: número de keys eliminadas (1 si exitoso, 0 si no existía)
    """
    key = f"orden_temporal:{telefono}"
    write_log(telefono, "delete_orden_temporal", f"Orden temporal eliminada para {telefono}", nivel="info")
    return redis_client.delete(key)

def get_estado_entrega(telefono, redis_client=redis_client):
    """
    Obtiene el estado de espera de entrega desde Redis.
    Se activa después de que el pedido fue persistido en BD
    pero aún falta confirmar tipo de entrega y dirección.

    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis

    Returns:
        dict o None: estructura del estado o None si no existe
    """
    key = f"estado_entrega:{telefono}"
    estado_json = redis_client.get(key)

    if estado_json:
        return json.loads(estado_json)

    write_log(telefono, "estado_entrega_not_found", f"No se encontró estado de entrega para {telefono}", nivel="warning")
    return None

def save_estado_entrega(telefono, estado_data, redis_client=redis_client, ttl=1800):
    """
    Guarda el estado de espera de entrega en Redis.
    Contiene los comandas_ids ya creados en BD para poder
    actualizarlos cuando llegue la dirección.

    Args:
        telefono: número de teléfono del usuario
        estado_data: dict con comandas_ids, pedido_grupo, nombre_cliente
        redis_client: cliente de Redis
        ttl: tiempo de expiración en segundos (default: 1800 = 30 minutos)

    Returns:
        bool: True si se guardó exitosamente
    """
    key = f"estado_entrega:{telefono}"

    try:
        redis_client.setex(
            key,
            ttl,
            json.dumps(estado_data)
        )
        print(f"✅ Estado de entrega guardado para {telefono}")
        return True

    except Exception as e:
        print(f"❌ Error al guardar estado de entrega: {e}")
        write_log(telefono, "error_save_estado_entrega", f"Error al guardar estado de entrega: {estado_data} para {telefono}: {str(e)}", nivel="error")
        return False

def delete_estado_entrega(telefono, redis_client=redis_client):
    """
    Elimina el estado de entrega de Redis (cuando se confirma la entrega).

    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis

    Returns:
        int: número de keys eliminadas (1 si exitoso, 0 si no existía)
    """
    key = f"estado_entrega:{telefono}"
    result = redis_client.delete(key)
    print(f"🗑️ Estado de entrega eliminado para {telefono}")
    write_log(telefono, "delete_estado_entrega", f"Estado de entrega eliminado para {telefono}", nivel="info")
    return result

def get_atencion_clientes(telefono, redis_client=redis_client):
    """
    Obtiene si el usuario fue canalizado antes como atención al cliente desde Redis
    
    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis
    
    Returns:
        dict o None: estructura de la orden temporal o None si no existe
    """
    key = f"atencion_clientes:{telefono}"
    orden_json = redis_client.get(key)

    if orden_json:
        return json.loads(orden_json)

    write_log(telefono, "atencion_clientes_not_found", f"No se encontró atención a clientes para {telefono}", nivel="warning")
    return None

def save_atencion_clientes(telefono, atencion_clientes_data, redis_client=redis_client, ttl=1800):
    """
    Guarda o actualiza si el usuario es atención a clientes o no en Redis
    
    Args:
        telefono: número de teléfono del usuario
        atencion_clientes_data: diccionario con la estructura de la atención a clientes
        redis_client: cliente de Redis
        ttl: tiempo de expiración en segundos (default: 1800 = 30 minutos)
    
    Returns:
        bool: True si se guardó exitosamente
    """
    key = f"atencion_clientes:{telefono}"

    try:
        redis_client.setex(
            key,
            ttl,
            json.dumps(atencion_clientes_data)
        )
        return True

    except Exception as e:
        print(f"Error al guardar atención a clientes: {e}")
        write_log(telefono, "error_save_atencion_clientes", f"Error al guardar atención a clientes: {atencion_clientes_data} para {telefono}: {str(e)}", nivel="error")
        return False

def delete_atencion_clientes(telefono, redis_client=redis_client):
    """
    Elimina la atención a clientes de Redis (cuando se confirma o cancela)

    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis

    Returns:
        int: número de keys eliminadas (1 si exitoso, 0 si no existía)
    """
    key = f"atencion_clientes:{telefono}"
    write_log(telefono, "delete_atencion_clientes", f"Estado de Atención a clientes eliminada para {telefono}", nivel="info")
    return redis_client.delete(key)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    # reset_chat_history('5215566098295')
    listar_chat_histories(redis_client=redis_client)