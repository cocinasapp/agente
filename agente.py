
from dotenv import load_dotenv
from logger_config import setup_logging
from states.dispatcher import dispatch

load_dotenv()
setup_logging()

def responder_usuario(messages, data, telefono, id_conversacion=None):
    """
    Punto de entrada del agente.
    Recibe el historial, los datos del mensaje y el teléfono.
    Delega toda la lógica al dispatcher de estados.
    """
    resultado = dispatch(messages, data, telefono)
    return resultado

if __name__ == "__main__":
    # Esta versión es para pruebas locales, simulando la conversación sin necesidad de WhatsApp.
    from chat_history import add_to_chat_history, get_chat_history, reset_chat_history, delete_orden_temporal, delete_estado_entrega
    from clients.redis_client import redis_client
    from supabase_utils import set_session_context, upsert_usuario
    import random

    # TELEFONO_PRUEBA = "5566098295"
    TELEFONO_PRUEBA = str(random.randint(1000000000, 9999999999))
    id_chat_history = f"fp-chatHistory:{TELEFONO_PRUEBA}@s.whatsapp.net"

    print("🤖 Agente TRG - Modo prueba local")
    print("Escribe 'salir' para terminar")
    print("Escribe 'reset' para borrar historial y estado")
    print("=" * 60)

    while True:
        query = input("\nUsuario: ").strip()

        if query.lower() == 'salir':
            print("¡Hasta luego!")
            break

        if query.lower() == 'reset':
            reset_chat_history(id_chat_history)
            delete_orden_temporal(TELEFONO_PRUEBA)
            delete_estado_entrega(TELEFONO_PRUEBA)
            set_session_context(TELEFONO_PRUEBA, {})
            redis_client.delete(f"estado:{TELEFONO_PRUEBA}")
            upsert_usuario(telefono=TELEFONO_PRUEBA, 
                        campos={"estado_actual": "new", "datos_recolectados": {}})
            print("🗑️ Historial, estado Redis y estado Supabase borrados")
            continue

        # test local
        messages = get_chat_history(id_chat_history, telefono=TELEFONO_PRUEBA)

        data = {
            'type': 'chat',
            'body': query,
            'from': f"{TELEFONO_PRUEBA}@s.whatsapp.net",
            'fromMe': False,
            'pushName': 'Prueba Local',
            'timestamp': 0,
            'media': ''
        }

        answer = responder_usuario(
            messages=messages,
            data=data,
            telefono=TELEFONO_PRUEBA,
            id_conversacion="prueba_local"
        )

        print(f"\n🤖 Agente: {answer['answer']}")
        print(f"📍 Estado: {answer.get('nuevo_estado', 'N/A')}")

        # test local
        add_to_chat_history(id_chat_history, query, "user", TELEFONO_PRUEBA)
        add_to_chat_history(id_chat_history, answer['answer'], "assistant", TELEFONO_PRUEBA)