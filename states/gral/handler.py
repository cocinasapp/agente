import logging, os
from db import DBCA
from dotenv import load_dotenv
from logger_utils import write_log
from states.generic import get_username
from states.gral.prompts import CAT_INTENTION, PROMPT_INFOMENU, PROMPT_ATTENTION
from states.shared_prompts import CONTEXT
from utils_llm import llamar_llm

load_dotenv()
USER_ID = os.getenv('USER_ID')
supabase_class = DBCA()

logger = logging.getLogger(__name__)

def handle_gral(messages, data, telefono, session_context, supabase_client=supabase_class):

    if 'nombre_usuario' not in session_context:
        get_username(session_context, telefono, data)

    cat_intention = llamar_llm(CAT_INTENTION, messages, data["body"]).lower()
    logger.debug("CAT INTENTION GRAL: %s", cat_intention)
    write_log(telefono, "cat_intention", f"Categoría de intención detectada en gral: {cat_intention}")

    if 'gral' in cat_intention:
        menu_del_dia = supabase_client.consultar_menu_del_dia(user_id=USER_ID)
        respuesta = llamar_llm(CONTEXT + PROMPT_INFOMENU(menu_del_dia) + f"{session_context.get('nombre_usuario', '')}", messages, data["body"])
        nuevo_estado = "gral"

    elif 'comensal' in cat_intention:
        from states.comensal.handler import handle_comensal
        return handle_comensal(messages, data, telefono, session_context)

    else:
        respuesta = llamar_llm(CONTEXT + PROMPT_ATTENTION + f"{session_context.get('nombre_usuario', '')}", messages, data["body"])
        nuevo_estado = "serv_client"
    
    logger.debug("RESPUESTA ESTADO GRAL: %s", respuesta)
    write_log(telefono, "respuesta_estado_gral", f"Respuesta generada en gral: {respuesta}")

    return {
        "answer": respuesta,
        "nuevo_estado": nuevo_estado,
        "session_context": session_context
    }

