
import os
import logging
from logger_utils import write_log
from db import DBCA
from states.generic import get_username
from states.comensal.handler import handle_comensal
from states.new.prompts import CAT_INTENTION, PROMPT_INFOMENU, PROMPT_ATTENTION
from states.shared_prompts import CONTEXT
from utils_llm import llamar_llm

logger = logging.getLogger(__name__)

def handle_new(messages, data, telefono, session_context):

    get_username(session_context, telefono, data)
    write_log(telefono, "nombre_usuario", f"Nombre de usuario detectado en new: {session_context.get('nombre_usuario', '')}")

    cat_intention = llamar_llm(CAT_INTENTION, messages, data["body"]).lower()
    logger.debug("CAT INTENTION NEW: %s", cat_intention)
    write_log(telefono, "cat_intention", f"Categoría de intención detectada en new: {cat_intention}")

    if 'gral' in cat_intention:
        menu_del_dia = DBCA().consultar_menu_del_dia(user_id=os.getenv('USER_ID'))
        respuesta = llamar_llm(CONTEXT + PROMPT_INFOMENU(menu_del_dia) + f"{session_context.get('nombre_usuario', '')}", messages, data["body"])
        nuevo_estado = "gral"

    elif 'comensal' in cat_intention:
        return handle_comensal(messages, data, telefono, session_context)

    else:
        respuesta = llamar_llm(CONTEXT + PROMPT_ATTENTION + f"{session_context.get('nombre_usuario', '')}", messages, data["body"])
        nuevo_estado = "serv_client"

    logger.debug("RESPUESTA ESTADO NEW: %s", respuesta)
    write_log(telefono, "respuesta_estado_new", f"Respuesta generada en new: {respuesta}")

    return {
        "answer": respuesta,
        "nuevo_estado": nuevo_estado,
        "session_context": session_context
    }