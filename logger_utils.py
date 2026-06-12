
import asyncio
from clients.supabase_client import supabase_client
from dotenv import load_dotenv

load_dotenv()

def write_log(telefono: str, etiqueta: str, mensaje: str, nivel: str = "info"):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_persist_log(telefono, etiqueta, mensaje, nivel))
    except RuntimeError:
        # Contexto sync puro (startup, inicialización) — skip silencioso
        pass

async def _persist_log(telefono: str, etiqueta: str, mensaje: str, nivel: str):
    try:
        await supabase_client.table("logs").insert({
            "telefono": telefono,
            "nivel": nivel,
            "etiqueta": etiqueta,
            "mensaje": str(mensaje)
        }).execute()

    except Exception as e:
        print(f"❌ Error persistiendo log: {e}")

if __name__ == '__main__':
    print("Modulo de persistencia de logs")