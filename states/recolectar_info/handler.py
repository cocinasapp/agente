import json, logging, os
from chat_history import (
    get_orden_temporal,
    save_orden_temporal,
    delete_orden_temporal,
    get_estado_entrega,
    save_estado_entrega
)

from db import DBCA
from dotenv import load_dotenv
from logger_utils import write_log
from states.generic import get_username
from states.recolectar_info.prompts import (
    PROMPT_EXTRAER_INFO,
    PROMPT_ATTENTION,
    CAT_INTENCION_INFO,
    PROMPT_CONFIRMAR_INFO
)
from states.shared_prompts import CONTEXT
from states.generic import info_esta_completa, que_falta_info
from utils_llm import llamar_llm

load_dotenv()

USER_ID = os.getenv('USER_ID')
supabase_class = DBCA()

logger = logging.getLogger(__name__)


def handle_recolectar_info(messages, data, telefono, session_context, supabase_client=supabase_class):

    if 'nombre_usuario' not in session_context:
        get_username(session_context, telefono, data)

    # Si venimos de una edición de pedido ya confirmado, la info_entrega ya existe.
    # Saltamos directo a terminar_pedido para aplicar los cambios.
    if 'pedido_grupo_modificando' in session_context:
        logger.info("Flujo de edición detectado | pedido_grupo: %s | telefono: %s",
                    session_context['pedido_grupo_modificando'], telefono)
        write_log(telefono, "flujo_edicion_detectado", f"Flujo de edición detectado para pedido grupo {session_context['pedido_grupo_modificando']}")
        from states.terminar_pedido.handler import handle_terminar_pedido
        return handle_terminar_pedido(messages, data, telefono, session_context)
    
    # Si ya tenemos info de entrega completa, mostrarla y pedir confirmación
    info_actual = session_context.get("entrega", {})
    if info_esta_completa(info_actual):
        logger.info("Info de entrega ya existe | telefono: %s", telefono)
        write_log(telefono, "info_ya_existe", "Info de entrega completa ya registrada, solicitando confirmación")
        context_info = {"entrega": info_actual}
        respuesta = llamar_llm(PROMPT_CONFIRMAR_INFO + str(context_info), messages, data["body"])
        return {"answer": respuesta, "nuevo_estado": "recolectar_info", "session_context": session_context}

    # Clasificar intención
    intencion = llamar_llm(CAT_INTENCION_INFO, messages, data["body"]).strip().lower()
    logger.debug("Intención detectada | telefono: %s | intención: %s", telefono, intencion)
    write_log(telefono, "intencion_info", f"Intención detectada en recolectar_info: {intencion}")

    if "agregar_platillo" in intencion:
        logger.info("Transición interna | recolectar_info → pedido | telefono: %s", telefono)
        write_log(telefono, "transicion_interna", "Transición interna de recolectar_info a pedido por intención de agregar platillo")
        from states.pedido.handler import handle_pedido
        return handle_pedido(messages, data, telefono, session_context, supabase_client)

    elif "consulta_precio" in intencion:
        from states.pedido.handler import handle_pedido
        return handle_pedido(messages, data, telefono, session_context, supabase_client)

    # Extracción de info via LLM
    raw = llamar_llm(PROMPT_EXTRAER_INFO, messages[-4:], data["body"])
    try:
        raw = raw.strip().replace("```json", "").replace("```", "").strip()
        tool_input = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("JSON inválido en extracción de info: %s", raw)
        write_log(telefono, "json_invalido_info", f"JSON inválido en extracción de info: {raw}", nivel="warning")
        respuesta = llamar_llm(CONTEXT + PROMPT_ATTENTION, messages, data["body"])
        return {"answer": respuesta, "nuevo_estado": "recolectar_info", "session_context": session_context}

    # Acumular info de entrega en session_context
    info_actual = session_context.get("entrega", {})
    for campo, valor in tool_input.items():
        if valor is not None:
            info_actual[campo] = valor
    session_context["entrega"] = info_actual

    # Validación de completitud
    if info_esta_completa(info_actual):
        logger.info("Info de entrega completa | telefono: %s", telefono)
        write_log(telefono, "info_completa", "Información de entrega completa detectada")
        from states.terminar_pedido.handler import handle_terminar_pedido
        return handle_terminar_pedido(messages, data, telefono, session_context)

    # Info parcial: preguntar por lo que falta
    faltantes = que_falta_info(info_actual)
    logger.debug("Info parcial | faltantes: %s | telefono: %s", faltantes, telefono)
    write_log(telefono, "info_parcial", f"Información parcial detectada, campos faltantes: {faltantes}")
    context_falta = {"campos_faltantes": faltantes}
    respuesta = llamar_llm(PROMPT_ATTENTION + str(context_falta), messages, data["body"])
    return {"answer": respuesta, "nuevo_estado": "recolectar_info", "session_context": session_context}