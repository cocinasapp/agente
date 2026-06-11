import json, logging, os
from chat_history import (
    get_orden_temporal,
    save_orden_temporal,
    get_estado_entrega
)
from db import DBCA
from dotenv import load_dotenv

from states.pedido.prompts import (
    PROMPT_EXTRAER_ORDEN,
    PROMPT_EXTRAER_EDICION,
    PROMPT_ATTENTION,
    CAT_CONFIRMACION,
    CAT_INTENTION,
    PROMPT_EXTRAER_MODIFICACION
)
from states.generic import (
    get_username,
    tiene_contenido,
    expandir_tool_input,
    normalizar_a_extra_si_unico,
    reconstruir_tool_input,
    eliminar_platillos_de_orden,
    reemplazar_platillos_en_orden
)
from states.shared_prompts import CONTEXT
from states.generic import que_falta
from supabase_utils import write_log
from utils_llm import llamar_llm, empty_placeholders

load_dotenv()

USER_ID = os.getenv('USER_ID')
supabase_class = DBCA()

logger = logging.getLogger(__name__)


def handle_pedido(messages, data, telefono, session_context, supabase_client=supabase_class):

    if 'nombre_usuario' not in session_context:
        get_username(session_context, telefono, data)

    menu_data = supabase_client.consultar_menu_del_dia(user_id=USER_ID)
    campos_platillos_validos = list(menu_data.get('menu', {}).keys())
    config = supabase_client.obtener_config_cocina(user_id=USER_ID)

    # breakpoint()
    # print('Esperando confirmacion')
    # Esperando confirmación
    if session_context.get("esperando_confirmacion"):
        confirmacion = llamar_llm(CAT_CONFIRMACION, messages, data["body"]).strip().lower()
        logger.debug("Confirmación | telefono: %s | resultado: %s", telefono, confirmacion)
        write_log(telefono, "confirmacion", f"Confirmación detectada en pedido: {confirmacion}")

        if confirmacion == "confirma":
            session_context.pop("esperando_confirmacion", None)
            from states.recolectar_info.prompts import PROMPT_ATTENTION as PROMPT_ATTENTION_INFO
            orden_temporal = get_orden_temporal(telefono)
            faltantes = que_falta(orden_temporal, campos_platillos_validos)
            content = {
                "status": "orden_confirmada",
                "tiempos_faltantes": faltantes,
                "campos_faltantes": ["nombre_completo", "metodo_de_entrega"]
            }
            respuesta = llamar_llm(PROMPT_ATTENTION_INFO + str(content), messages, data["body"])
            write_log(telefono, "respuesta_estado_recolectar_info", f"Respuesta generada en recolectar_info: {respuesta}")
            return {"answer": respuesta, "nuevo_estado": "recolectar_info", "session_context": session_context}

        session_context.pop("esperando_confirmacion", None)

    # Clasificar intención
    intencion = llamar_llm(CAT_INTENTION, messages, data["body"]).strip().lower()
    logger.debug("Intención | telefono: %s | resultado: %s", telefono, intencion)
    write_log(telefono, "intencion", f"Intención detectada en pedido: {intencion}")


    # # Pedido ya confirmado — solo bloquear si NO es modificación
    # breakpoint()
    # if get_estado_entrega(telefono) and intencion not in ("eliminar_platillo", "reemplazar_platillo"):
    #     content = {
    #         "status": "pedido_ya_confirmado",
    #         "mensaje": "El pedido ya fue guardado. Continúa recopilando datos de entrega.",
    #     }
    #     respuesta = llamar_llm(PROMPT_RESPONDER_ORDEN + str(content), messages, data["body"])
    #     return {"answer": respuesta, "nuevo_estado": "recolectar_info", "session_context": session_context}

    if intencion == "eliminar_platillo":
        raw = llamar_llm(CONTEXT + PROMPT_EXTRAER_EDICION, messages, data["body"])
        try:
            raw = raw.strip().replace("```json", "").replace("```", "").strip()
            tool_input_edicion = json.loads(raw)
            if not isinstance(tool_input_edicion, dict):
                raise ValueError("Se esperaba un objeto JSON")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("JSON inválido en extracción de edición: %s | error: %s", raw, e)
            respuesta = llamar_llm(CONTEXT + PROMPT_ATTENTION, messages, data["body"])
            write_log(telefono, "json_invalido_edicion", f"JSON inválido en extracción de edición: {raw} | error: {e}")
            return {"answer": respuesta, "nuevo_estado": "pedido", "session_context": session_context}

        orden_temporal = get_orden_temporal(telefono)
        if not orden_temporal:
            respuesta = llamar_llm(PROMPT_ATTENTION + str({"status": "sin_orden_activa"}), messages, data["body"])
            write_log(telefono, "sin_orden_activa", "No hay orden activa en pedido")
            return {"answer": respuesta, "nuevo_estado": "pedido", "session_context": session_context}

        orden_temporal, content = eliminar_platillos_de_orden(
            orden_temporal, tool_input_edicion, campos_platillos_validos, supabase_client, config
        )
        save_orden_temporal(telefono, orden_temporal)
        session_context["orden"] = orden_temporal

        session_context["esperando_confirmacion"] = True
        faltantes = que_falta(orden_temporal, campos_platillos_validos)
        content["tiempos_faltantes"] = faltantes
        respuesta = llamar_llm(PROMPT_ATTENTION + str(content), messages, data["body"])
        return {"answer": respuesta, "nuevo_estado": "pedido", "session_context": session_context}

    if intencion == "reemplazar_platillo":
        raw = llamar_llm(CONTEXT + PROMPT_EXTRAER_MODIFICACION, messages, data["body"])
        try:
            raw = raw.strip().replace("```json", "").replace("```", "").strip()
            tool_input_modificacion = json.loads(raw)
            if not isinstance(tool_input_modificacion, dict) or "cambios" not in tool_input_modificacion:
                raise ValueError("Se esperaba un objeto JSON con clave 'cambios'")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("JSON inválido en extracción de modificación: %s | error: %s", raw, e)
            write_log(telefono, "json_invalido_modificacion", f"JSON inválido en extracción de modificación: {raw} | error: {e}")
            respuesta = llamar_llm(CONTEXT + PROMPT_ATTENTION, messages, data["body"])
            return {"answer": respuesta, "nuevo_estado": "pedido", "session_context": session_context}

        # breakpoint()
        orden_temporal = get_orden_temporal(telefono)
        if not orden_temporal:
            respuesta = llamar_llm(PROMPT_ATTENTION + str({"status": "sin_orden_activa"}), messages, data["body"])
            write_log(telefono, "sin_orden_activa", "No hay orden activa en pedido")
            return {"answer": respuesta, "nuevo_estado": "pedido", "session_context": session_context}

        orden_temporal, content = reemplazar_platillos_en_orden(
            orden_temporal, tool_input_modificacion["cambios"], campos_platillos_validos, supabase_client, config
        )
        save_orden_temporal(telefono, orden_temporal)
        session_context["orden"] = orden_temporal

        session_context["esperando_confirmacion"] = True
        faltantes = que_falta(orden_temporal, campos_platillos_validos)
        content["tiempos_faltantes"] = faltantes
        respuesta = llamar_llm(PROMPT_ATTENTION + str(content), messages, data["body"])
        return {"answer": respuesta, "nuevo_estado": "pedido", "session_context": session_context}
    
    if intencion == "agregar_platillo":
        # Extracción de orden via LLM
        raw = llamar_llm(CONTEXT + PROMPT_EXTRAER_ORDEN, messages, data["body"])
        try:
            raw = raw.strip().replace("```json", "").replace("```", "").strip()
            tool_input = json.loads(raw)
            if not isinstance(tool_input, dict):
                raise ValueError("Se esperaba un objeto JSON")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("JSON inválido en extracción de orden: %s | error: %s", raw, e)
            write_log(telefono, "json_invalido_orden", f"JSON inválido en extracción de orden: {raw} | error: {e}")
            respuesta = llamar_llm(CONTEXT + PROMPT_ATTENTION, messages, data["body"])
            return {"answer": respuesta, "nuevo_estado": "pedido", "session_context": session_context}

        # Validar que al menos una orden tiene platillos o extras
        campos_menu_actuales = [c for c in campos_platillos_validos if c != 'a_la_carta']

        if not tiene_contenido(tool_input, campos_platillos_validos):
            logger.debug("Fallback: mensaje sin platillos ni extras | telefono: %s", telefono)
            write_log(telefono, "mensaje_sin_contenido", "El mensaje no contiene platillos ni extras detectables", nivel="warning")
            faltantes = que_falta(get_orden_temporal(telefono), campos_platillos_validos)
            context_falta = {"tiempos_disponibles": faltantes} if faltantes else {}
            respuesta = llamar_llm(PROMPT_ATTENTION + str(context_falta), messages, data["body"])
            return {"answer": respuesta, "nuevo_estado": "pedido", "session_context": session_context}

        # Reconstruir orden como salida del LLM
        tool_input = reconstruir_tool_input(tool_input, get_orden_temporal(telefono) or {}, campos_platillos_validos, menu_data)

        # De diccionario de listas a lista de diccionarios
        lista_tool_inputs = expandir_tool_input(tool_input, campos_menu_actuales)

        # Normalizar: 1 platillo solo → extra_1
        lista_tool_inputs = normalizar_a_extra_si_unico(tool_inputs=lista_tool_inputs, campos_menu_actuales=campos_menu_actuales, campos_platillos_validos=campos_platillos_validos)

        # Acumular en orden_temporal
        from states.generic import construir_orden_temporal, agregar_extra_a_orden, agregar_platillos_a_orden

        # Si ya existe una orden rehidratada en Redis (viene de handler_terminar_pedido),
        # preservar pedido_grupo y comanda_ids; vaciar ordenes para acumular desde cero.
        orden_redis = get_orden_temporal(telefono)
        if orden_redis and any(o.get("comanda_id") for o in orden_redis.get("ordenes", [])):
            orden_temporal = {
                "pedido_grupo": orden_redis["pedido_grupo"],
                "ordenes": [],
                "total_ordenes": 0,
                "monto_total_general": 0,
                "nombre_cliente": orden_redis.get("nombre_cliente"),
                "_comanda_ids_originales": [
                    o.get("comanda_id") for o in orden_redis["ordenes"]
                ]
            }
        else:
            orden_temporal = construir_orden_temporal(None)
        content = {}

        for tool_input in lista_tool_inputs:
            if not tiene_contenido(tool_input, campos_platillos_validos):
                continue

            es_solo_extra = (
                not any(tool_input.get(campo) not in empty_placeholders for campo in campos_menu_actuales) and
                any(tool_input.get(k) not in empty_placeholders for k in ['extra_1', 'extra_2', 'extra_3', 'a_la_carta'])
            )

            if es_solo_extra and len(lista_tool_inputs) == 1 and len(orden_temporal.get("ordenes", [])) > 0:
                orden_temporal, content = agregar_extra_a_orden(orden_temporal, tool_input, config, supabase_client, campos_platillos_validos)
            else:
                orden_temporal, content = agregar_platillos_a_orden(orden_temporal, tool_input, config, supabase_client, campos_platillos_validos)

        save_orden_temporal(telefono, orden_temporal)
        session_context["orden"] = orden_temporal
        get_orden_temporal(telefono)

        # Preguntar si es todo
        session_context["esperando_confirmacion"] = True
        faltantes = que_falta(orden_temporal, campos_platillos_validos)
        content["tiempos_faltantes"] = faltantes
        respuesta = llamar_llm(PROMPT_ATTENTION + str(content), messages, data["body"])
        write_log(telefono, "respuesta_esperando_confirmacion", f"Respuesta generada esperando confirmación: {respuesta}")
        return {"answer": respuesta, "nuevo_estado": "pedido", "session_context": session_context}