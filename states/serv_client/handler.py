
from logger_utils import write_log
from states.serv_client.prompts import PROMPT_EXECUTIVE
from states.shared_prompts import CONTEXT
from utils_llm import llamar_llm, get_datetime_mexico

def handle_serv_client(messages, data, telefono, session_context):

    if 'flag_executive' not in session_context:
        respuesta = llamar_llm(CONTEXT + PROMPT_EXECUTIVE + f"{session_context.get('nombre_usuario', '')}", messages, data["body"])
        session_context["flag_executive"] = True

    else:
        respuesta = ""

    write_log(telefono, "respuesta_estado_serv_client", f"Respuesta generada en serv_client: {respuesta}")
    return {
        "answer": respuesta,
        "nuevo_estado": "serv_client",
        "session_context": session_context
    }