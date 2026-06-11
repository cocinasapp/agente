
import os, uvicorn
from db import DBCA
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from logger_config import setup_logging
from procesa_mensajes import procesar_mensajes_entrantes
from supabase_utils import write_log

load_dotenv()
setup_logging()

USER_ID=os.getenv('USER_ID')

supabase_class = DBCA()
informacion_cliente=supabase_class.obtener_config_cocina(user_id=USER_ID)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def leer_conversaciones_supabase(phone_number: str, limit: int = 100, supabase_client=supabase_class.supabase):
    try:
        user_id = os.getenv('USER_ID')

        if not user_id:
            print("⚠️ USER_ID no configurado en .env")
            return []

        response = supabase_client.table('conversations')\
            .select('*')\
            .eq('user_id', user_id)\
            .eq('phone_number', phone_number)\
            .order('created_at', desc=False)\
            .limit(limit)\
            .execute()

        return response.data or []

    except Exception as e:
        print(f"❌ Error al leer conversaciones: {e}")
        return []

# Endpoint para obtener conversaciones de un cliente específico, filtrando solo por USER_ID
@app.get('/api/v1/conversations/{phone_number}')
def obtener_conversacion(phone_number: str, limit: int = 100):
    mensajes = leer_conversaciones_supabase(phone_number, limit)
    
    return {
        "phone_number": phone_number,
        "total_messages": len(mensajes),
        "messages": mensajes
    }

# Endpoint para listar clientes que han conversado, SOLO de la cocina actual
@app.get('/api/v1/conversations')
def listar_clientes_con_conversaciones(supabase_client=supabase_class.supabase):
    try:
        user_id = os.getenv('USER_ID')
        
        if not user_id:
            return {"error": "USER_ID no configurado"}, 500
        
        # Query filtrando por user_id
        response = supabase_client.table('conversations') \
            .select('phone_number, message, created_at, role') \
            .eq('user_id', user_id) \
            .order('created_at', desc=True) \
            .execute()
        
        # Agrupar por phone_number y tomar el último mensaje
        clientes = {}
        for msg in response.data:
            phone = msg['phone_number']
            if phone not in clientes:
                clientes[phone] = {
                    'phone_number': phone,
                    'last_message': msg['message'],
                    'last_message_time': msg['created_at'],
                    'last_role': msg['role']
                }
        
        return {
            "total_clients": len(clientes),
            "clients": list(clientes.values())
        }
        
    except Exception as e:
        print(f"❌ Error al listar clientes: {e}")
        return {"error": str(e)}, 500

@app.api_route('/', methods=['GET', 'HEAD'])
def index():
    '''Route de bienvenida'''
    return 'La API de Cocinas App funciona correctamente.'

@app.get('/health')
def health_check():
    return {"status": "ok"}

@app.api_route('/api/v1/webhook', methods=['GET', 'POST'])
async def webhook(request: Request):
    if request.method == "GET":
        params = dict(request.query_params)
        procesar_mensajes_entrantes(params)
        return JSONResponse(content={"status": "ok-get"}, status_code=200)

    elif request.method == "POST":
        json_data = await request.json()
        procesar_mensajes_entrantes(json_data)
        return JSONResponse(content={'status': 'ok-post'}, status_code=200)

@app.post('/api/v1/notify/status')
async def notify_status_change(request: Request, _sc=supabase_class.supabase):
    try:
        from procesa_mensajes import enviar_mensaje

        payload = await request.json()
        write_log("system", "info_webhook_received", f"Webhook recibido: {payload}", nivel="info")

        record = payload.get('record', {})
        status = record.get('status')
        cliente_nombre = record.get('cliente_nombre')
        telefono_cliente = record.get('telefono_cliente')
        pedido_grupo = record.get('pedido_grupo')
        user_id = record.get('user_id')

        if status not in ['EN_PROCESO', 'ENVIADO']:
            print(f"⏭️ Status '{status}' ignorado")
            write_log("system", "info_webhook_ignored", f"Status '{status}' ignorado en payload: {payload}", nivel="info")
            return JSONResponse(content={"status": "ignored"}, status_code=200)

        if not telefono_cliente:
            print(f"⚠️ No hay teléfono - comanda: {record.get('id')}")
            return JSONResponse(content={"status": "no_phone"}, status_code=200)

        # NUEVO: lookup de credenciales por user_id
        if not user_id:
            print(f"⚠️ No hay user_id en la comanda: {record.get('id')}")
            return JSONResponse(content={"status": "no_user_id"}, status_code=200)

        config_result = _sc.table('tbl_cocina_config')\
            .select('wasender_api_key, wasender_token')\
            .eq('user_id', user_id)\
            .single()\
            .execute()

        if not config_result.data:
            print(f"❌ No se encontró config para user_id: {user_id}")
            write_log("system", "error_no_config", f"No se encontró configuración de Wasender para user_id: {user_id}", nivel="error")
            return JSONResponse(content={"status": "no_config"}, status_code=200)

        wasender_api_key = config_result.data['wasender_api_key']
        # wasender_token disponible si lo necesitas: config_result.data['wasender_token']
        
        # NUEVO: verificar que TODAS las comandas no-extra del grupo
        # estén en el mismo status antes de notificar
        if pedido_grupo:
            grupo_result = _sc.table(os.getenv('TLB_COMANDAS'))\
                .select('id, status')\
                .eq('pedido_grupo', pedido_grupo)\
                .eq('es_extra', False)\
                .execute()

            comandas_principales = grupo_result.data or []
            todas_en_status = all(
                c['status'] == status for c in comandas_principales
            )

            if not todas_en_status:
                print(f"⏳ Grupo {pedido_grupo[:8]}... aún no está completo en {status}, esperando")
                return JSONResponse(content={"status": "waiting_group"}, status_code=200)

        if status == 'EN_PROCESO':
            mensaje = f"¡Hola {cliente_nombre}! Tu pedido ya está siendo preparado. 🍳"
        elif status == 'ENVIADO':
            mensaje = f"¡Hola {cliente_nombre}! Tu pedido ya va en camino. 🛵"

        telefono_formateado = f"52{telefono_cliente}@s.whatsapp.net"
        print(f"📞 Teléfono formateado: {telefono_formateado}")
        write_log("system", "info_sending_message", f"Intentando enviar mensaje: {mensaje} a {telefono_formateado} con status {status}", nivel="info")

        telefono_limpio = telefono_cliente.strip().replace(" ", "").replace("-", "").replace("+", "")
        if telefono_limpio.startswith("521"):
            numero_base = telefono_limpio[3:]
        elif telefono_limpio.startswith("52"):
            numero_base = telefono_limpio[2:]
        else:
            numero_base = telefono_limpio

        # Buscar JID exacto en conversations
        whatsapp_jid = None
        conv = _sc.table('conversations')\
            .select('whatsapp_jid')\
            .eq('phone_number', telefono_cliente)\
            .eq('user_id', user_id)\
            .not_.is_('whatsapp_jid', 'null')\
            .limit(1)\
            .execute()

        if conv.data:
            whatsapp_jid = conv.data[0].get('whatsapp_jid')

        if whatsapp_jid:
            print(f"✅ JID encontrado: {whatsapp_jid}")
            resultado = enviar_mensaje(whatsapp_jid, mensaje, api_key=wasender_api_key)
            if resultado.get('success'):
                return JSONResponse(content={"status": "ok"}, status_code=200)
            else:
                print(f"❌ Error enviando con JID: {resultado}")
                return JSONResponse(content={"status": "error"}, status_code=500)
        else:
            print(f"⚠️ Sin JID guardado, intentando con prefijos 52/521")
            telefono_limpio = telefono_cliente.strip().replace(" ", "").replace("-", "").replace("+", "")
            if telefono_limpio.startswith("521"):
                numero_base = telefono_limpio[3:]
            elif telefono_limpio.startswith("52"):
                numero_base = telefono_limpio[2:]
            else:
                numero_base = telefono_limpio

            enviado = False
            for prefijo in ["521", "52"]:
                telefono_formateado = f"{prefijo}{numero_base}@s.whatsapp.net"
                resultado = enviar_mensaje(telefono_formateado, mensaje, api_key=wasender_api_key)
                if resultado.get("success"):
                    print(f"✅ Enviado con prefijo {prefijo}")
                    enviado = True
                    break
                print(f"⚠️ Falló con prefijo {prefijo}: {resultado}")

            if enviado:
                return JSONResponse(content={"status": "ok"}, status_code=200)
            else:
                print(f"❌ No se pudo enviar con ningún prefijo")
                return JSONResponse(content={"status": "error"}, status_code=500)

    except Exception as e:
        print(f"❌ Error en notify_status_change: {e}")
        return JSONResponse(content={"status": "error", "detail": str(e)}, status_code=500)

@app.post('/api/v1/ordenes/manual')
async def crear_orden_manual_endpoint(request: Request, supabase_client=supabase_class.supabase):
    """
    Crea una orden manual desde el dashboard (sin WhatsApp).
    Recibe: cliente_nombre, tipo_entrega, direccion,
            comidas, extras, precio_menu, descuento_por_platillo
    """
    try:

        body = await request.json()

        cliente_nombre = body.get('cliente_nombre', '').strip()
        tipo_entrega = body.get('tipo_entrega', 'local')
        direccion = body.get('direccion', '')
        comidas = body.get('comidas', [])
        extras = body.get('extras', [])
        precio_menu = float(body.get('precio_menu', 0.0))
        descuento_por_platillo = bool(body.get('descuento_por_platillo', False))

        if not cliente_nombre:
            return JSONResponse(content={"ok": False, "error": "Falta el nombre del cliente"}, status_code=400)

        if not comidas and not extras:
            return JSONResponse(content={"ok": False, "error": "La orden no tiene items"}, status_code=400)

        resultado = supabase_client.crear_orden_manual(
            cliente_nombre=cliente_nombre,
            tipo_entrega=tipo_entrega,
            direccion=direccion,
            comidas=comidas,
            extras=extras,
            precio_menu=precio_menu,
            descuento_por_platillo=descuento_por_platillo,
        )

        if resultado["ok"]:
            return JSONResponse(content=resultado, status_code=200)
        else:
            return JSONResponse(content=resultado, status_code=500)

    except Exception as e:
        print(f"❌ Error en endpoint orden manual: {e}")
        write_log("system", "error_orden_manual", f"Error al crear orden manual: {str(e)}", nivel="error")
        return JSONResponse(content={"ok": False, "error": str(e)}, status_code=500)

@app.put('/api/v1/ordenes/grupo/{pedido_grupo}/editar')
async def editar_grupo_endpoint(pedido_grupo: str, request: Request, supabase_client=supabase_class.supabase):
    """
    Edita todas las comandas de un grupo (o solo las que vengan en el payload).
    Recibe: lista de {comanda_id, platillos: [...], precio_menu, descuento_por_platillo}
    """
    try:

        body = await request.json()
        comandas = body.get("comandas", [])
        precio_menu = float(body.get("precio_menu", 0.0))
        descuento_por_platillo = bool(body.get("descuento_por_platillo", False))

        if not comandas:
            return JSONResponse(content={"ok": False, "error": "No hay comandas para editar"}, status_code=400)

        todos_los_platillos = supabase_client.read_data(
            table_name=os.getenv("TLB_PLATILLOS"),
            variables="id, platillo, precio",
            filters={"activo": "TRUE"},
        )

        resultados = []
        for comanda in comandas:
            resultado = supabase_client.editar_comanda(
                comanda_id=comanda["comanda_id"],
                platillos=comanda.get("platillos", []),
                precio_menu=precio_menu,
                descuento_por_platillo=descuento_por_platillo,
                todos_los_platillos=todos_los_platillos,
            )
            resultados.append(resultado)

        todos_ok = all(r["ok"] for r in resultados)
        return JSONResponse(
            content={"ok": todos_ok, "resultados": resultados},
            status_code=200 if todos_ok else 500
        )

    except Exception as e:
        print(f"❌ Error en editar_grupo_endpoint: {e}")
        write_log("system", "error_editar_grupo", f"Error al editar grupo {pedido_grupo}: {str(e)}", nivel="error")
        return JSONResponse(content={"ok": False, "error": str(e)}, status_code=500)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    # Timeout de 2 segundos para liberar memoria rápido
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=port, 
        reload=False,
        timeout_keep_alive=2
    )