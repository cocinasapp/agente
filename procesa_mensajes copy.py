# # python3 procesa_mensajes.py

# import logging, os, requests, time
# from chat_history import (
#     add_to_chat_history, 
#     get_chat_history, 
#     reset_chat_history,
#     reset_chat_history,
#     delete_orden_temporal,
#     delete_estado_entrega
# )
# from clients.redis_client import redis_client
# from datetime import datetime
# from dotenv import load_dotenv
# from agente import responder_usuario
# from supabase_utils import set_session_context, upsert_usuario, write_log

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# load_dotenv()

# wasender_api_key = os.getenv("WASENDER_API_KEY")
# USER_ID = os.getenv("USER_ID")

# # ============================================================================
# # 📤 ENVÍO DE MENSAJES
# # ============================================================================

# def enviar_mensaje(telefono, texto, api_key=wasender_api_key, max_retries=3):
#     url = "https://wasenderapi.com/api/send-message"
#     headers = {
#         "Authorization": f"Bearer {api_key}",
#         "Content-Type": "application/json"
#     }
#     payload = {"to": telefono, "text": texto}

#     for intento in range(max_retries):
#         try:
#             print(f"📤 Enviando mensaje (intento {intento + 1}/{max_retries}): {texto[:50]}...")
#             write_log(telefono, "enviar_mensaje_intento", f"Intento {intento + 1} de enviar mensaje: {texto[:50]}...", nivel="info")
#             response = requests.post(url, headers=headers, json=payload, timeout=30)
#             # print(f"STATUS CODE: {response.status_code}")

#             if response.status_code == 429:
#                 wait_time = response.json().get('retry_after', 60)
#                 print(f"⏳ Rate limit. Esperando {wait_time}s...")
#                 time.sleep(wait_time + 2)
#                 continue

#             if response.status_code in [520, 502, 503, 504]:
#                 wait_time = 5 * (intento + 1)
#                 print(f"⚠️ Error servidor ({response.status_code}). Reintentando en {wait_time}s...")
#                 write_log(telefono, "enviar_mensaje_error_servidor", f"Error servidor ({response.status_code}). Reintentando en {wait_time}s...", nivel="warning")
#                 time.sleep(wait_time)
#                 continue

#             if 200 <= response.status_code < 300:
#                 print("✅ Mensaje enviado exitosamente")
#                 return {"success": True, "response": response.json()}

#             response.raise_for_status()

#         except requests.exceptions.Timeout:
#             print(f"⏱️ Timeout en intento {intento + 1}/{max_retries}")
#             if intento < max_retries - 1:
#                 time.sleep(3 * (intento + 1))
#                 continue
#             return {"success": False, "error": "Timeout después de múltiples intentos"}

#         except requests.exceptions.RequestException as e:
#             print(f"❌ ERROR en intento {intento + 1}/{max_retries}: {str(e)}")
#             write_log(telefono, "enviar_mensaje_exception", f"Error en intento {intento + 1} de enviar mensaje: {str(e)}", nivel="error")
#             if intento < max_retries - 1:
#                 time.sleep(3 * (intento + 1))
#                 continue
#             return {"success": False, "error": str(e)}

#     return {"success": False, "error": "Falló después de todos los reintentos"}

# # ============================================================================
# # 🗑️ BORRAR MEMORIA
# # ============================================================================

# def borrar_memoria_orig(telefono_jid: str, telefono: str):
#     id_chat_history = f'fp-chatHistory:{telefono_jid}'
#     reset_chat_history(id_chat_history)
#     delete_orden_temporal(telefono)
#     delete_estado_entrega(telefono)
#     set_session_context(telefono, {})
#     redis_client.delete(f"estado:{telefono}")
#     upsert_usuario(telefono, campos={"estado_actual": "new"})
#     print(f"🗑️ Memoria borrada para {telefono}")
#     write_log(telefono, "borrar_memoria", f"Memoria borrada para {telefono}", nivel="info")

# def borrar_memoria(telefono_jid: str, telefono: str):
#     id_chat_history = f'fp-chatHistory:{telefono_jid}'

#     try:
#         reset_chat_history(id_chat_history)
#         delete_orden_temporal(telefono)
#         delete_estado_entrega(telefono)
#         redis_client.delete(f"estado:{telefono}")

#     except Exception as e:
#         logger.error(f"⚠️ Redis caído al borrar memoria | error: {e}")

#     # Supabase siempre se ejecuta
#     set_session_context(telefono, {})
#     upsert_usuario(telefono, campos={"estado_actual": "new"})
#     logger.info(f"🗑️ Memoria borrada para {telefono}")
#     write_log(telefono, "borrar_memoria", f"Memoria borrada para {telefono}", nivel="info")

# # ============================================================================
# # 🟢 PROCESAMIENTO PRINCIPAL (WASender)
# # ============================================================================

# def procesar_mensajes_entrantes(json_data):
#     eventos_validos = ['messages.received', 'messages-personal.received']

#     if json_data.get('event') not in eventos_validos:
#         print(f"Evento ignorado: {json_data.get('event')}")
#         return 'NoCommand'

#     if 'data' not in json_data or 'messages' not in json_data['data']:
#         return 'NoCommand'

#     messages_data = json_data['data']['messages']

#     # Construir data interna
#     data = {
#         'id':        messages_data.get('id', ''),
#         'from':      messages_data.get('remoteJid', ''),
#         'to':        json_data.get('sessionId', ''),
#         'body':      messages_data.get('messageBody', ''),
#         'fromMe':    messages_data.get('key', {}).get('fromMe', False),
#         'type':      'chat',
#         'pushName':  messages_data.get('pushName', ''),
#         'timestamp': messages_data.get('messageTimestamp', 0),
#         'media':     ''
#     }

#     if 'message' in messages_data:
#         message_content = messages_data['message']
#         if 'conversation' in message_content:
#             data['type'] = 'chat'
#             data['body'] = message_content['conversation']
#         elif 'imageMessage' in message_content:
#             data['type'] = 'image'
#             data['media'] = message_content['imageMessage'].get('url', '')

#     # Validaciones mínimas
#     if not data['from']:
#         print("Mensaje sin remitente")
#         return 'NoCommand'

#     if not data['body'] and data['type'] == 'chat':
#         print("Mensaje de texto sin contenido")
#         return 'NoCommand'

#     # Filtrar grupos y mensajes propios
#     if '@g.us' in data['from'] or data['fromMe'] is True:
#         print("Mensaje de grupo o propio — ignorado")
#         return 'NoCommand'

#     # Extraer teléfono limpio
#     telefono = data['from'].split('@')[0]
#     print(f"📱 Teléfono: {telefono}")

#     # Verificar silencio de agente
#     flag_agente = redis_client.get(f"agente_activo:{telefono}")
#     if flag_agente and flag_agente.decode() == "false":
#         print(f"🔇 Agente silenciado para {telefono}")
#         write_log(telefono, "agente_silenciado", f"Agente silenciado para {telefono}. Ignorando mensaje.", nivel="warning")
#         return 'AgenteSilenciado'

#     # Deduplicación
#     dedup_key = f"msg:{telefono}:{data['timestamp']}"
#     if redis_client.exists(dedup_key):
#         print(f"⚠️ Mensaje duplicado: {dedup_key}")
#         write_log(telefono, "mensaje_duplicado", f"Mensaje duplicado detectado: {dedup_key}, ignorando.", nivel="warning")
#         return 'NoCommand'

#     # 🗑️ COMANDO: BORRAR MEMORIA (producción vía WhatsApp)
#     if 'borrar memoria' in data['body'].lower():
#         write_log(telefono, "borrar_memoria_comando", f"Comando de borrar memoria recibido para {telefono}. Iniciando proceso de borrado.", nivel="info")
#         borrar_memoria(telefono_jid=data['from'], telefono=telefono)
#         resultado = enviar_mensaje(data['from'], "✅ Tu memoria ha sido borrada.")
#         if resultado.get('success'):
#             redis_client.set(dedup_key, 'exists', ex=600)
#         return resultado

#     # Tipos no soportados por ahora
#     if data['type'] not in ['chat']:
#         print(f"Tipo de mensaje no soportado: {data['type']}")
#         return 'NoCommand'

#     # Obtener historial
#     id_chat_history = f'fp-chatHistory:{data["from"]}'
#     messages = get_chat_history(id_chat_history, telefono=telefono)

#     # Llamar al dispatcher
#     resultado = responder_usuario(messages, data, telefono)

#     if not resultado.get('answer'):
#         print("⚠️ Dispatcher no devolvió respuesta")
#         write_log(telefono, "dispatcher_no_answer", f"Dispatcher no devolvió respuesta para {telefono}.", nivel="warning")
#         return 'NoAnswer'

#     # Enviar respuesta
#     resultado_envio = enviar_mensaje(data['from'], str(resultado['answer']))

#     if not resultado_envio.get('success'):
#         print(f"❌ Error al enviar: {resultado_envio.get('error')}")
#         write_log(telefono, "error_envio_mensaje", f"Error al enviar mensaje a {telefono}: {resultado_envio.get('error')}", nivel="error")
#         return 'ErrorEnvio'

#     # Marcar como procesado y guardar historial
#     redis_client.set(dedup_key, 'exists', ex=600)
#     # add_to_chat_history(id_chat_history, data['body'], "user", telefono, whatsapp_jid=data['from'])
#     # add_to_chat_history(id_chat_history, resultado['answer'], "assistant", telefono, whatsapp_jid=data['from'])
    
#     add_to_chat_history(id_chat_history, data['body'], "user", telefono)
#     add_to_chat_history(id_chat_history, resultado['answer'], "assistant", telefono)

#     print('✅ Procesamiento completado.')
#     write_log(telefono, "procesamiento_completado", f"Mensaje procesado exitosamente para {telefono}.", nivel="info")
#     return 'OK'