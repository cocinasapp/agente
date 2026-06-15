
import logging, os

from chat_history import (
    delete_orden_temporal, 
    save_estado_entrega, 
    get_orden_temporal, 
    save_orden_temporal
)

from db import DBCA
from dotenv import load_dotenv
from utils_llm import llamar_llm
from logger_utils import write_log
from states.generic import (
    get_username, 
    persistir_pedido, 
    rehidratar_orden_desde_supabase
)
from states.generic import info_esta_completa
from states.shared_prompts import CONTEXT
from states.terminar_pedido.prompts import PROMPT_ATTENTION, PROMPT_ATTENTION_MODIFICACION
from states.terminar_pedido.prompts import CAT_INTENTION_TERMINAR_PEDIDO
from states.pedido.handler import handle_pedido

load_dotenv()

USER_ID = os.getenv('USER_ID')
supabase_class = DBCA()

logger = logging.getLogger(__name__)

def handle_terminar_pedido(messages, data, telefono, session_context, supabase_client=supabase_class):

    if 'nombre_usuario' not in session_context:
        get_username(session_context, telefono, data)

    menu_data = supabase_client.consultar_menu_del_dia(user_id=USER_ID)
    campos_platillos_validos = list(menu_data.get('menu', {}).keys())
    config = supabase_client.obtener_config_cocina(user_id=USER_ID)

    # ── Clasificar intención ───────────────────────────────────────────────────
    # intencion = llamar_llm(CAT_INTENTION_TERMINAR_PEDIDO, messages, data["body"]).strip().lower()
    ultimo_mensaje = messages[-2]["content"] if len(messages) >= 2 else ""
    prompt_cat = CAT_INTENTION_TERMINAR_PEDIDO.format(ultimo_mensaje_agente=ultimo_mensaje)
    intencion = llamar_llm(prompt_cat, messages, data["body"]).strip().lower()
    logger.debug("Intención terminar_pedido | telefono: %s | resultado: %s", telefono, intencion)
    write_log(telefono, "intencion_terminar_pedido", f"Intención detectada en terminar_pedido: {intencion}")

    if "modificar_orden" in intencion:

        # Traer pedido desde Supabase
        pedido_data = supabase_client.obtener_pedido_reciente_usuario(telefono)
        if not pedido_data:
            logger.warning("No se encontró pedido reciente para modificar | telefono: %s", telefono)
            write_log(telefono, "pedido_no_encontrado_modificacion", "No se encontró pedido reciente para modificar", nivel="warning")
            respuesta = llamar_llm(
                CONTEXT + PROMPT_ATTENTION_MODIFICACION + str({"status": "sin_pedido_activo"}),
                messages, data["body"]
            )
            return {"answer": respuesta, "nuevo_estado": "terminar_pedido", "session_context": session_context}

        pedido_grupo = pedido_data['pedido_grupo']

        # Validar que el pedido sea editable
        validacion = supabase_client.validar_pedido_editable(pedido_grupo)
        if not validacion['editable']:
            logger.info(
                "Pedido no editable | telefono: %s | pedido_grupo: %s | estados: %s",
                telefono, pedido_grupo, validacion['estados']
            )
            respuesta = llamar_llm(
                CONTEXT + PROMPT_ATTENTION_MODIFICACION + str({
                    "status": "pedido_no_editable",
                    "mensaje": validacion['mensaje']
                }),
                messages, data["body"]
            )
            write_log(telefono, "pedido_no_editable", f"Pedido no editable para pedido grupo {pedido_grupo}: {validacion['mensaje']} --- respuesta: {respuesta}", nivel="warning")
            return {"answer": respuesta, "nuevo_estado": "terminar_pedido", "session_context": session_context}

        # Rehidratar orden_temporal desde Supabase y guardar en Redis
        orden_temporal = rehidratar_orden_desde_supabase(
            pedido_data, config, supabase_client, campos_platillos_validos
        )
        save_orden_temporal(telefono, orden_temporal)
        # breakpoint()
        session_context["orden"] = orden_temporal

        logger.info(
            "Orden rehidratada | telefono: %s | pedido_grupo: %s | ordenes: %s",
            telefono, pedido_grupo, len(orden_temporal['ordenes'])
        )
        write_log(telefono, "orden_rehidratada", f"Orden rehidratada para pedido grupo {pedido_grupo}, número de órdenes: {len(orden_temporal['ordenes'])}", nivel="info")
        # Congelar pedido mientras se procesa la modificación
        if not supabase_client.congelar_pedido(pedido_grupo):
            logger.error("Fallo al congelar pedido | telefono: %s | pedido_grupo: %s", telefono, pedido_grupo)
            write_log(telefono, "congelar_pedido_fallido", f"Fallo al congelar pedido para pedido grupo {pedido_grupo}", nivel="error")
        else:
            logger.info("Pedido congelado | telefono: %s | pedido_grupo: %s", telefono, pedido_grupo)
            write_log(telefono, "pedido_congelado", f"Pedido congelado para pedido grupo {pedido_grupo} mientras se procesa modificación", nivel="info")
        session_context["pedido_grupo_modificando"] = pedido_grupo

        # Delegar a handle_pedido — caso equivalente al flujo normal
        return handle_pedido(messages, data, telefono, session_context, supabase_client)

    elif "consulta_precio" in intencion:
        from states.pedido.handler import handle_pedido
        return handle_pedido(messages, data, telefono, session_context, supabase_client)

    # ── Flujo normal: persistir pedido ────────────────────────────────────────
    # orden_temporal = get_orden_temporal(telefono)
    orden_temporal = session_context.get("orden") or get_orden_temporal(telefono)
    
    info_entrega = session_context.get("info_entrega", {})

    # Antes de persistir, verificar que no se haya persistido ya
    from chat_history import get_estado_entrega
    if get_estado_entrega(telefono):
        logger.info("Pedido ya persistido anteriormente | telefono: %s", telefono)
        respuesta = llamar_llm(CONTEXT + PROMPT_ATTENTION, messages, data["body"])
        return {"answer": respuesta, "nuevo_estado": "terminar_pedido", "session_context": session_context}

    if not orden_temporal or not info_esta_completa(info_entrega):
        logger.error(
            "terminar_pedido: faltan datos | orden: %s | info_entrega: %s",
            orden_temporal, info_entrega
        )
        respuesta = llamar_llm(CONTEXT + PROMPT_ATTENTION, messages, data["body"])
        return {"answer": respuesta, "nuevo_estado": "recolectar_info", "session_context": session_context}

    nombre_completo = info_entrega.get("nombre_completo")

    # FINALIZAR
    # Se carga orden temporal a Supabase
    # Si venimos de una modificación, descongelar el pedido antes de persistir
    pedido_grupo_modificando = session_context.pop("pedido_grupo_modificando", None)
    if pedido_grupo_modificando:
        if not supabase_client.descongelar_pedido(pedido_grupo_modificando):
            logger.error("Fallo al descongelar pedido | telefono: %s | pedido_grupo: %s", telefono, pedido_grupo_modificando)
            write_log(telefono, "descongelar_pedido_fallido", f"Fallo al descongelar pedido para pedido grupo {pedido_grupo_modificando}", nivel="error")
        else:
            logger.info("Pedido descongelado | telefono: %s | pedido_grupo: %s", telefono, pedido_grupo_modificando)
            write_log(telefono, "pedido_descongelado", f"Pedido descongelado para pedido grupo {pedido_grupo_modificando}", nivel="info")
 
    estado_entrega, content = persistir_pedido(
        orden_temporal, nombre_completo, telefono, config, supabase_client, campos_platillos_validos,
        info_entrega=info_entrega
    )

    content["metodo_de_entrega"] = info_entrega.get("metodo_de_entrega")
    content["domicilio"] = info_entrega.get("domicilio")
    content["referencia"] = info_entrega.get("referencia")

    save_estado_entrega(telefono, estado_entrega)
    delete_orden_temporal(telefono)

    logger.info("Pedido persistido | telefono: %s | pedido_grupo: %s", telefono, content.get("pedido_grupo"))
    write_log(telefono, "pedido_persistido", f"Pedido persistido con grupo {content.get('pedido_grupo')}", nivel="info")

    respuesta = llamar_llm(CONTEXT + PROMPT_ATTENTION + str(content), messages, data["body"])
    return {"answer": respuesta, "nuevo_estado": "terminar_pedido", "session_context": session_context}