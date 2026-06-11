
import os, pytz
from clients.anthropic_client import anthropic_client
from clients.openai_client import openai_client
from datetime import datetime
from dotenv import load_dotenv
from logger_utils import write_log

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL_NAME", "claude-sonnet-4-6")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-2026-03-05")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", 0.1))

def llamar_llm(prompt_sistema: str, messages: list, mensaje_usuario: str, anthropic: bool = True) -> str:

    if anthropic:

        try:
            response = anthropic_client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=16000,
                system=prompt_sistema,
                messages=[
                    *messages,
                    {"role": "user", "content": mensaje_usuario}
                ]
            )
            return response.content[0].text.strip()

        except Exception as e:
            print(f"Error al llamar a Anthropic: {e}")
            write_log("system", "anthropic_call_error", f"Error al llamar a Anthropic: {e}", nivel="error")

            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    *messages,
                    {"role": "user", "content": mensaje_usuario}
                ],
                temperature=OPENAI_TEMPERATURE
            )
            return response.choices[0].message.content.strip()
    else:
        try:
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    *messages,
                    {"role": "user", "content": mensaje_usuario}
                ],
                temperature=OPENAI_TEMPERATURE
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error al llamar a OpenAI: {e}")
            write_log("system", "openai_call_error", f"Error al llamar a OpenAI: {e}", nivel="error")

            response = anthropic_client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=16000,
                system=prompt_sistema,
                messages=[
                    *messages,
                    {"role": "user", "content": mensaje_usuario}
                ]
            )
            return response.content[0].text.strip()

def get_datetime_mexico() -> str:
    """
    Retorna la fecha y hora actual en Ciudad de México en español.
    Ej: 'viernes 27 de marzo de 2025, 14:35'
    """
    tz = pytz.timezone("America/Mexico_City")
    now = datetime.now(tz)

    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

    dia_semana = dias[now.weekday()]
    mes        = meses[now.month - 1]

    return f"{dia_semana} {now.day} de {mes} de {now.year}, {now.strftime('%H:%M')}"

def get_nombre_usuario(data: dict) -> str:
    """
    Extrae el nombre del usuario del payload de WATI.
    Fallback: número de teléfono si no hay nombre.
    """
    nombre = (
        data.get('senderName') or
        data.get('pushName') or
        data.get('contactName') or
        ""
    ).strip()

    # Evitar nombres genéricos que WATI a veces manda
    if not nombre or nombre == data.get('waId') or nombre == data.get('phone'):
        return ""

    # Capitalizar por si viene en minúsculas
    return nombre.title()

empty_placeholders = ['PENDIENTE', '<UNKNOWN>', 'UNKNOWN', 'N/A', 'NA', 'SIN NOMBRE', '', None]

if __name__ == "__main__":
    print(get_datetime_mexico())