# python3 procesa_mensajes.py

import logging, os, requests, time
from agente import responder_usuario
from chat_history import (
    add_to_chat_history,
    get_chat_history,
    reset_chat_history,
    delete_orden_temporal,
    delete_estado_entrega,
    delete_atencion_clientes,
)
from clients.redis_client import redis_client
from datetime import datetime
from dotenv import load_dotenv
from logger_utils import write_log
from supabase_utils import set_session_context, upsert_usuario

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

wasender_api_key = os.getenv("WASENDER_API_KEY")
USER_ID = os.getenv("USER_ID")

# ============================================================================
# 📤 ENVÍO DE MENSAJES
# ============================================================================

def enviar_mensaje(telefono, texto, api_key=wasender_api_key, max_retries=3):
    url = "https://wasenderapi.com/api/send-message"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {"to": telefono, "text": texto}

    for intento in range(max_retries):
        try:
            print(f"📤 Enviando mensaje (intento {intento + 1}/{max_retries}): {texto[:50]}...")
            write_log(telefono, "enviar_mensaje_intento", f"Intento {intento + 1} de enviar mensaje: {texto[:50]}...", nivel="info")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            print(f"STATUS CODE: {response.status_code}")

            if response.status_code == 429:
                wait_time = response.json().get('retry_after', 60)
                print(f"⏳ Rate limit. Esperando {wait_time}s...")
                time.sleep(wait_time + 2)
                continue

            if response.status_code in [520, 502, 503, 504]:
                wait_time = 5 * (intento + 1)
                print(f"⚠️ Error servidor ({response.status_code}). Reintentando en {wait_time}s...")
                write_log(telefono, "enviar_mensaje_error_servidor", f"Error servidor ({response.status_code}). Reintentando en {wait_time}s...", nivel="warning")
                time.sleep(wait_time)
                continue

            if 200 <= response.status_code < 300:
                print("✅ Mensaje enviado exitosamente")
                return {"success": True, "response": response.json()}

            response.raise_for_status()

        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout en intento {intento + 1}/{max_retries}")
            write_log(telefono, "enviar_mensaje_timeout", f"Timeout en intento {intento + 1} de enviar mensaje: {texto[:50]}...", nivel="warning")
            if intento < max_retries - 1:
                time.sleep(3 * (intento + 1))
                continue
            return {"success": False, "error": "Timeout después de múltiples intentos"}

        except requests.exceptions.RequestException as e:
            print(f"❌ ERROR en intento {intento + 1}/{max_retries}: {str(e)}")
            write_log(telefono, "enviar_mensaje_exception", f"Error en intento {intento + 1} de enviar mensaje: {str(e)}", nivel="error")
            if intento < max_retries - 1:
                time.sleep(3 * (intento + 1))
                continue
            return {"success": False, "error": str(e)}

    return {"success": False, "error": "Falló después de todos los reintentos"}

# ============================================================================
# 🗑️ BORRAR MEMORIA
# ============================================================================

def borrar_memoria_orig(telefono_jid: str, telefono: str):
    id_chat_history = f'fp-chatHistory:{telefono_jid}'
    reset_chat_history(id_chat_history)
    delete_orden_temporal(telefono)
    delete_estado_entrega(telefono)
    set_session_context(telefono, {})
    redis_client.delete(f"estado:{telefono}")
    upsert_usuario(telefono, campos={"estado_actual": "new"})
    print(f"🗑️ Memoria borrada para {telefono}")

def borrar_memoria(telefono_jid: str, telefono: str):
    id_chat_history = f'fp-chatHistory:{telefono_jid}'

    # Supabase primero — así el fallback ya tiene el estado correcto
    # antes de que Redis se limpie y el siguiente mensaje llegue
    upsert_usuario(telefono, campos={"estado_actual": "new", "datos_recolectados": {}})

    try:
        reset_chat_history(id_chat_history)
        delete_orden_temporal(telefono)
        delete_estado_entrega(telefono)
        delete_atencion_clientes(telefono)
        # Escribir "new" directo en vez de borrar: si llega un mensaje
        # antes de que Supabase confirme, Redis ya tiene el estado correcto
        redis_client.set(f"estado:{telefono}", "new", ex=60*60*24)
        redis_client.set(f"session_context:{telefono}", "{}", ex=60*60*24*7)

    except Exception as e:
        logger.error(f"⚠️ Redis caído al borrar memoria | error: {e}")
        write_log(telefono, "borrar_memoria_redis_error", f"Error al borrar memoria en Redis para {telefono}: {str(e)}", nivel="error")
    logger.info(f"🗑️ Memoria borrada para {telefono}")
    write_log(telefono, "borrar_memoria", f"Memoria borrada para {telefono}", nivel="info")

# ============================================================================
# 🟢 PROCESAMIENTO PRINCIPAL (WASender)
# ============================================================================

def procesar_mensajes_entrantes(json_data):
    logger.info(f"📦 PAYLOAD CRUDO: {json_data}")   # <--- aquí
    eventos_validos = ['messages.received', 'messages-personal.received']

    if json_data.get('event') not in eventos_validos:
        print(f"Evento ignorado: {json_data.get('event')}")
        return 'NoCommand'

    if 'data' not in json_data or 'messages' not in json_data['data']:
        return 'NoCommand'

    messages_data = json_data['data']['messages']

    data = {
        'id':        messages_data.get('id', ''),
        'from':      messages_data.get('remoteJid', ''),
        'to':        json_data.get('sessionId', ''),
        'body':      messages_data.get('messageBody', ''),
        'fromMe':    messages_data.get('key', {}).get('fromMe', False),
        'type':      'chat',
        'pushName':  messages_data.get('pushName', ''),
        'timestamp': messages_data.get('messageTimestamp', 0),
        'media':     ''
    }

    if 'message' in messages_data:
        message_content = messages_data['message']
        if 'conversation' in message_content:
            data['type'] = 'chat'
            data['body'] = message_content['conversation']
        elif 'imageMessage' in message_content:
            data['type'] = 'image'
            data['media'] = message_content['imageMessage'].get('url', '')

    if not data['from']:
        print("Mensaje sin remitente")
        return 'NoCommand'

    if not data['body'] and data['type'] == 'chat':
        print("Mensaje de texto sin contenido")
        return 'NoCommand'

    if '@g.us' in data['from'] or data['fromMe'] is True:
        print("Mensaje de grupo o propio — ignorado")
        return 'NoCommand'

    telefono = data['from'].split('@')[0]
    print(f"📱 Teléfono: {telefono}")

    # FIX 1: flag_agente con fallback
    try:
        flag_agente = redis_client.get(f"agente_activo:{telefono}")
        if flag_agente and flag_agente.decode() == "false":
            print(f"🔇 Agente silenciado para {telefono}")
            write_log(telefono, "agente_silenciado", f"Agente silenciado para {telefono}", nivel="warning")
            return 'AgenteSilenciado'
    except Exception as e:
        print(f"⚠️ Redis caído en flag_agente, asumiendo agente activo | error: {e}")

    # FIX 2: dedup con fallback
    dedup_key = f"msg:{telefono}:{data['timestamp']}"
    try:
        if redis_client.exists(dedup_key):
            print(f"⚠️ Mensaje duplicado: {dedup_key}")
            write_log(telefono, "mensaje_duplicado", f"Mensaje duplicado: {dedup_key}", nivel="warning")
            return 'NoCommand'
    except Exception as e:
        print(f"⚠️ Redis caído en dedup, procesando sin deduplicar | error: {e}")
        write_log(telefono, "dedup_redis_error", f"Redis caído en dedup, procesando sin deduplicar | error: {e}", nivel="error")
        dedup_key = None

    if 'borrar memoria' in data['body'].lower():
        print(f"🗑️ Borrando memoria para: {telefono}")
        borrar_memoria(telefono_jid=data['from'], telefono=telefono)
        resultado = enviar_mensaje(data['from'], "✅ Tu memoria ha sido borrada.")
        if resultado.get('success') and dedup_key:
            try:
                redis_client.set(dedup_key, 'exists', ex=600)
            except Exception as e:
                print(f"⚠️ No se pudo marcar dedup en Redis | error: {e}")
                write_log(telefono, "dedup_redis_error", f"No se pudo marcar dedup en Redis | error: {e}", nivel="error")
        return resultado

    if data['type'] not in ['chat']:
        print(f"Tipo de mensaje no soportado: {data['type']}")
        return 'NoCommand'

    id_chat_history = f'fp-chatHistory:{data["from"]}'
    messages = get_chat_history(id_chat_history, telefono=telefono)

    resultado = responder_usuario(messages, data, telefono)

    if not resultado.get('answer'):
        print("⚠️ Dispatcher no devolvió respuesta")
        return 'NoAnswer'

    resultado_envio = enviar_mensaje(data['from'], str(resultado['answer']))

    if not resultado_envio.get('success'):
        print(f"❌ Error al enviar: {resultado_envio.get('error')}")
        return 'ErrorEnvio'

    # FIX 3: marcar dedup solo si Redis estaba disponible
    if dedup_key:
        try:
            redis_client.set(dedup_key, 'exists', ex=600)
        except Exception as e:
            print(f"⚠️ No se pudo marcar dedup en Redis | error: {e}")
            write_log(telefono, "dedup_redis_error", f"No se pudo marcar dedup en Redis | error: {e}", nivel="error")
    add_to_chat_history(id_chat_history, data['body'], "user", telefono)
    add_to_chat_history(id_chat_history, resultado['answer'], "assistant", telefono)

    print('✅ Procesamiento completado.')
    return 'OK'