
import logging

from states.generic import get_username
from states.comensal.prompts import CAT_INTENTION
from supabase_utils import write_log
from utils_llm import llamar_llm

logger = logging.getLogger(__name__)

def handle_comensal(messages, data, telefono, session_context):

    if 'nombre_usuario' not in session_context:
        get_username(session_context, telefono, data)

    cat_intention = llamar_llm(CAT_INTENTION, messages, data["body"]).lower()
    logger.debug("CAT INTENTION COMENSAL: %s", cat_intention)
    write_log(telefono, "cat_intention", f"Categoría de intención detectada en comensal: {cat_intention}")
    
    if 'pedido' in cat_intention.lower():
        from states.pedido.handler import handle_pedido
        return handle_pedido(messages, data, telefono, session_context)

    else:
        # Al incluir ésta función, este estado ya no debe de canalizar a ejecutivo ni dar informacion del menu
        from states.gral.handler import handle_gral
        return handle_gral(messages, data, telefono, session_context)