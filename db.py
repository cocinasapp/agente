# python3 db.py

import logging, os, uuid
from clients.supabase_client import supabase_client
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from logger_utils import write_log
# from supabase import create_client, Client
from supabase import Client
from utils_llm import empty_placeholders

logger = logging.getLogger(__name__)

load_dotenv()

TBL_CLIENTES = os.getenv('TLB_CLIENTES')
TBL_COMANDAS = os.getenv('TLB_COMANDAS')
TBL_DESGLOSE = os.getenv('TLB_DESGLOSE')
TBL_PLATILLOS = os.getenv('TLB_PLATILLOS')
TLB_TIEMPOS=os.getenv('TLB_TIEMPOS')
TBL_CONVERSATIONS=os.getenv('TBL_CONVERSATIONS')

class DBCA:
    def __init__(self, supabase_client: Client = supabase_client):
        self.supabase = supabase_client
        self.table_comandas = TBL_COMANDAS
        self.table_desglose = TBL_DESGLOSE
        self.table_platillos = TBL_PLATILLOS
        self.table_clientes = TBL_CLIENTES
        self.table_tiempos = TLB_TIEMPOS
        self.table_conversations = TBL_CONVERSATIONS

    def insert_data(
        self,
        data, 
        table,
        return_id: bool = False
        ):
        if not data:
            print("No se proporcionaron datos para insertar.")
            return False
        try:
            response = self.supabase.table(table).insert(data).execute()
            if response.data:
                print(f"Datos insertados en la tabla '{table}'.")
                if return_id:
                    ids = [item["id"] for item in response.data if "id" in item]
                    return ids[0] if len(ids) == 1 else ids
                return True

            else:
                print(f"Error al insertar datos en '{table}': {response.error}")
                return False

        except Exception as e:
            print(f"Excepción al insertar en '{table}': {e}")
            return False

    def read_data(
            self,
            table_name:str,
            variables:str='*',
            filters:dict=None
            ):
        try:
            query=self.supabase.table(table_name).select(variables)
            if filters:
                for var, value in filters.items():
                    if isinstance(value, list):
                        query=query.in_(var, value)

                    else:
                        query=query.eq(var, value)
            supabase_client_response=query.execute()
            data = supabase_client_response.data or []
            if data:
                return data

            else:
                print(f"No se encontraron registros en '{table_name}' con los filtros {filters}.")
                return []

        except Exception as error:
                print(f"Error al consultar '{table_name}': {error}")
                return []
        
    def update_data(
            self,
            table: str,
            data,
            filters
        ) -> bool:
        """
        Actualiza registros en una tabla de Supabase.

        Args:
            table: nombre de la tabla
            data: diccionario con los campos a actualizar
            filters: diccionario con las condiciones (ej: {'id': '123'})
            supabase_client: cliente de Supabase

        Returns:
            bool: True si se actualizó exitosamente
        """
        if not data:
            print("No se proporcionaron datos para actualizar.")
            return False

        if not filters:
            print("No se proporcionaron filtros para el update. Operación cancelada por seguridad.")
            return False

        try:
            query = self.supabase.table(table).update(data)

            for var, value in filters.items():
                query = query.eq(var, value)

            response = query.execute()

            if response.data:
                print(f"✅ Datos actualizados en '{table}': {len(response.data)} registro(s).")
                return True
            else:
                print(f"⚠️ Update ejecutado en '{table}' pero sin registros afectados. Filters: {filters}")
                return False

        except Exception as e:
            print(f"❌ Excepción al actualizar en '{table}': {e}")
            return False

    def obtener_config_cocina(self, user_id=None):
        try:
            if user_id is None:
                user_id = os.getenv('USER_ID')

            if not user_id:
                print("⚠️ USER_ID no configurado - usando valores por defecto")
                write_log("system", "config_cocina_user_id_missing", "USER_ID no configurado en el entorno. Usando valores por defecto.", nivel="warning")
                return {
                    'user_id': None,
                    'business_name': 'Mi Cocina',
                    'agent_name': 'Lucía'
                }

            result = self.supabase.table('tbl_cocina_config')\
                .select('business_name, agent_name, precio_menu, descuento_por_platillo, cobro_desechables, precio_desechables')\
                .eq('user_id', user_id)\
                .execute()

            if result.data and len(result.data) > 0:
                config = result.data[0]
                return {
                    'user_id': user_id,
                    'business_name': config['business_name'],
                    'agent_name': config['agent_name'],
                    'precio_menu': float(config.get('precio_menu') or 0.0),
                    'descuento_por_platillo': bool(config.get('descuento_por_platillo') or False),
                    'cobro_desechables': bool(config.get('cobro_desechables') or False),      # ← nuevo
                    'precio_desechables': float(config.get('precio_desechables') or 0.0)      # ← nuevo
                }
            else:
                print(f"⚠️ No se encontró config para user_id: {user_id} - usando defaults")
                write_log(user_id, "config_cocina_not_found", f"No se encontró configuración de cocina para user_id: {user_id}. Usando valores por defecto.", nivel="warning")
                return {
                    'user_id': user_id,
                    'business_name': 'Mi Cocina',
                    'agent_name': 'Lucía',
                    'precio_menu': 0.0,
                    'descuento_por_platillo': False,
                    'cobro_desechables': False,      # ← nuevo
                    'precio_desechables': 0.0       # ← nuevo
                }

        except Exception as e:
            print(f"❌ Error obteniendo config de cocina: {e}")
            write_log(user_id or "system", "config_cocina_error", f"Error al obtener configuración de cocina para user_id: {user_id}: {str(e)}. Usando valores por defecto.", nivel="error")
            return {
                'user_id': user_id or os.getenv('USER_ID'),
                'business_name': os.getenv('BUSINESS_NAME', 'Mi Cocina'),
                'agent_name': os.getenv('AGENT_NAME', 'Lucía'),
                'precio_menu': 0.0,
                'descuento_por_platillo': False,
                'cobro_desechables': False,      # ← nuevo
                'precio_desechables': 0.0       # ← nuevo
            }

    def obtener_pedido_reciente_usuario(self, telefono):
        try:
            # Usar UTC-6 (hora México) para el límite del día
            ahora_utc = datetime.now(timezone.utc)
            ahora_cdmx = ahora_utc - timedelta(hours=6)
            hoy_cdmx = ahora_cdmx.date()
            manana_cdmx = hoy_cdmx + timedelta(days=1)

            response = (
                self.supabase
                .table(self.table_comandas)
                .select("*")
                .eq("telefono_cliente", telefono)
                .eq("status", "PENDIENTE")
                .gte("created_at", f"{hoy_cdmx.isoformat()}T06:00:00+00:00")
                .lt("created_at", f"{manana_cdmx.isoformat()}T06:00:00+00:00")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            
            if not response.data:
                print(f"⚠️ No se encontraron pedidos para el teléfono: {telefono}")
                return None
            
            pedido_grupo = response.data[0]['pedido_grupo']
            cliente_nombre = response.data[0]['cliente_nombre']
            
            # Obtener TODAS las comandas de ese pedido_grupo
            response_comandas = (
                self.supabase
                .table(self.table_comandas)
                .select("*")
                .eq("pedido_grupo", pedido_grupo)
                .order("created_at", desc=False)
                .execute()
            )
            
            return {
                'pedido_grupo': pedido_grupo,
                'comandas': response_comandas.data,
                'cliente_nombre': cliente_nombre
            }
            
        except Exception as error:
            print(f"❌ Error al obtener pedido reciente: {error}")
            return None

    def validar_pedido_editable(self, pedido_grupo):
        """
        Valida si un pedido puede ser editado (todas las comandas deben estar en PENDIENTE).
        
        Args:
            pedido_grupo: UUID del grupo de pedido
            supabase_client: Cliente de Supabase
            table_comandas: Nombre de la tabla de comandas
        
        Returns:
            dict con 'editable' (bool), 'mensaje' (str), 'estados' (list)
        """
        try:
            response = (
                self.supabase
                .table(self.table_comandas)
                .select("id, status")
                .eq("pedido_grupo", pedido_grupo)
                .execute()
            )
            
            if not response.data:
                return {
                    'editable': False,
                    'mensaje': 'No se encontraron comandas para este pedido.',
                    'estados': []
                }
            
            estados = [comanda['status'] for comanda in response.data]
            
            # Verificar que TODAS estén en PENDIENTE o MODIFICANDO
            if all(estado in ('PENDIENTE', 'MODIFICANDO') for estado in estados):
                return {
                    'editable': True,
                    'mensaje': 'El pedido puede ser editado.',
                    'estados': estados
                }
            
            # Si alguna está en otro estado
            estados_no_pendientes = [e for e in estados if e != 'PENDIENTE']
            
            if 'EN_PROCESO' in estados_no_pendientes or 'LISTO_COCINA' in estados_no_pendientes:
                return {
                    'editable': False,
                    'mensaje': 'Lo siento, tu pedido ya está siendo preparado y no puede modificarse.',
                    'estados': estados
                }
            
            if 'TERMINADO' in estados_no_pendientes or 'ENTREGADO' in estados_no_pendientes:
                return {
                    'editable': False,
                    'mensaje': 'Lo siento, tu pedido ya fue completado y no puede modificarse.',
                    'estados': estados
                }
            
            if 'ENVIADO' in estados_no_pendientes or 'ENTREGADO' in estados_no_pendientes:
                return {
                    'editable': False,
                    'mensaje': 'Lo siento, tu pedido ya fue enviado y no puede modificarse.',
                    'estados': estados
                }
            
            if 'CANCELADO' in estados_no_pendientes:
                return {
                    'editable': False,
                    'mensaje': 'Este pedido ya fue cancelado.',
                    'estados': estados
                }
            
            return {
                'editable': False,
                'mensaje': 'El pedido no puede ser editado en su estado actual.',
                'estados': estados
            }

        except Exception as error:
            print(f"❌ Error al validar pedido: {error}")
            write_log("system", "validar_pedido_error", f"Error al validar pedido editable para pedido_grupo: {pedido_grupo}: {str(error)}.", nivel="error")
            return {
                'editable': False,
                'mensaje': f'Error al validar el pedido: {error}',
                'estados': []
            }

    def obtener_comandas_con_platillos(self, pedido_grupo):
        """
        Obtiene todas las comandas de un pedido con sus platillos.
        
        Args:
            pedido_grupo: UUID del grupo de pedido
            supabase_client: Cliente de Supabase
        
        Returns:
            list de dict con estructura de cada comanda y sus platillos
        """
        try:
            # Obtener comandas
            response_comandas = (
                self.supabase
                .table(self.table_comandas)
                .select("*")
                .eq("pedido_grupo", pedido_grupo)
                .order("created_at", desc=False)
                .execute()
            )
            
            if not response_comandas.data:
                return []
            
            comandas_con_platillos = []

            for idx, comanda in enumerate(response_comandas.data, 1):
                response_desglose = (
                    self.supabase
                    .table(self.table_desglose)
                    .select(f"platillo_id, {self.table_platillos}(platillo, tiempo_id, tbl_cocina_tiempos(nombre, orden))")
                    .eq("comanda_id", comanda['id'])
                    .execute()
                )

                platillos = []
                if response_desglose.data:
                    for item in response_desglose.data:
                        platillo_data = item[self.table_platillos]
                        tiempo_data = platillo_data.get('tbl_cocina_tiempos', {})
                        # Convertir nombre del tiempo a snake_case igual que utils.py
                        tiempo_nombre = tiempo_data.get('nombre', '')
                        campo = tiempo_nombre.lower().replace(" ", "_") if tiempo_nombre else ''
                        platillos.append({
                            'platillo_id': item['platillo_id'],
                            'platillo': platillo_data['platillo'],
                            'tiempo_id': platillo_data['tiempo_id'],
                            'campo': campo,  # ← nuevo: ej. "primer_tiempo", "postre"
                        })

                comandas_con_platillos.append({
                    'numero': idx,
                    'comanda_id': comanda['id'],
                    'platillos': platillos,
                    'monto_total': comanda['monto_total'],
                    'status': comanda['status']
                })
            
            return comandas_con_platillos

        except Exception as error:
            print(f"❌ Error al obtener comandas con platillos: {error}")
            write_log("system", "obtener_comandas_con_platillos_error", f"Error al obtener comandas con platillos para pedido_grupo: {pedido_grupo}: {str(error)}.", nivel="error")
            return []

    def eliminar_comanda(self, comanda_id):
        """
        Elimina una comanda y sus platillos asociados.

        Args:
            comanda_id: UUID de la comanda a eliminar
            supabase_client: Cliente de Supabase

        Returns:
            dict con 'success' (bool) y 'mensaje' (str)
        """
        try:
            # Primero eliminar desglose
            response_desglose = (
                self.supabase
                .table(self.table_desglose)
                .delete()
                .eq("comanda_id", comanda_id)
                .execute()
            )

            # Luego eliminar comanda
            response_comanda = (
                self.supabase
                .table(self.table_comandas)
                .delete()
                .eq("id", comanda_id)
                .execute()
            )

            return {
                'success': True,
                'mensaje': f'Comanda {comanda_id} eliminada exitosamente.'
            }

        except Exception as error:
            print(f"❌ Error al eliminar comanda: {error}")
            write_log("system", "eliminar_comanda_error", f"Error al eliminar comanda_id: {comanda_id}: {str(error)}.", nivel="error")
            return {
                'success': False,
                'mensaje': f'Error al eliminar comanda: {error}'
            }

    def actualizar_platillos_comanda(self, comanda_id, nuevos_platillos_ids, nuevos_costos):
        """
        Actualiza los platillos y costos de una comanda.

        Args:
            comanda_id: UUID de la comanda
            nuevos_platillos_ids: Lista de IDs de platillos nuevos
            nuevos_costos: Dict con monto_estandar, monto_extras, monto_desechables, monto_total

        Returns:
            dict con 'success' (bool) y 'mensaje' (str)
        """
        try:
            # 1. Eliminar platillos viejos del desglose
            response_delete = (
                self.supabase
                .table(self.table_desglose)
                .delete()
                .eq("comanda_id", comanda_id)
                .execute()
            )

            # 2. Insertar nuevos platillos
            if nuevos_platillos_ids:
                nuevos_registros = [
                    {
                        'comanda_id': comanda_id,
                        'platillo_id': platillo_id
                    }
                    for platillo_id in nuevos_platillos_ids
                ]

                response_insert = (
                    self.supabase
                    .table(self.table_desglose)
                    .insert(nuevos_registros)
                    .execute()
                )

            # 3. Actualizar costos en la comanda
            response_update = (
                self.supabase
                .table(self.table_comandas)
                .update({
                    'monto_estandar': nuevos_costos.get('monto_estandar', 0),
                    'monto_extras': nuevos_costos.get('monto_extras', 0),
                    'monto_desechables': nuevos_costos.get('monto_desechables', 0),
                    'monto_total': nuevos_costos.get('monto_total', 0)
                })
                .eq("id", comanda_id)
                .execute()
            )

            return {
                'success': True,
                'mensaje': f'Comanda {comanda_id} actualizada exitosamente.'
            }

        except Exception as error:
            print(f"❌ Error al actualizar platillos: {error}")
            write_log("system", "actualizar_platillos_comanda_error", f"Error al actualizar platillos para comanda_id: {comanda_id}: {str(error)}.", nivel="error")
            return {
                'success': False,
                'mensaje': f'Error al actualizar platillos: {error}'
            }

    def congelar_pedido(self, pedido_grupo):
        """
        Cambia todas las comandas del grupo a MODIFICANDO para bloquear
        cambios de status mientras Lucía procesa la edición.
        """
        try:
            self.supabase.table(self.table_comandas)\
                .update({"status": "MODIFICANDO"})\
                .eq("pedido_grupo", pedido_grupo)\
                .in_("status", ["PENDIENTE"])\
                .execute()
            logger.info("Pedido congelado en Supabase | pedido_grupo: %s", pedido_grupo[:8])
            return True
        except Exception as e:
            logger.error("Error congelando pedido | pedido_grupo: %s | error: %s", pedido_grupo[:8], e)
            write_log("system", "congelar_pedido_error", f"Error al congelar pedido para pedido_grupo: {pedido_grupo}: {str(e)}.", nivel="error")
            return False

    def descongelar_pedido(self, pedido_grupo):
        """
        Regresa todas las comandas del grupo de MODIFICANDO a PENDIENTE.
        Se llama al terminar la edición (exitosa o con error).
        """
        try:
            self.supabase.table(self.table_comandas)\
                .update({"status": "PENDIENTE"})\
                .eq("pedido_grupo", pedido_grupo)\
                .in_("status", ["MODIFICANDO"])\
                .execute()
            logger.info("Pedido descongelado en Supabase | pedido_grupo: %s", pedido_grupo[:8])
            return True
        except Exception as e:
            logger.error("Error descongelando pedido | pedido_grupo: %s | error: %s", pedido_grupo[:8], e)
            write_log("system", "descongelar_pedido_error", f"Error al descongelar pedido para pedido_grupo: {pedido_grupo}: {str(e)}.", nivel="error")
            return False

    @staticmethod
    def _calcular_monto_comida(precio_menu: float, descuento_por_platillo: bool,
        platillos_seleccionados: list[dict],  # [{"platillo_id": int, "platillo_nombre": str, "precio": float}]
        todos_los_platillos: list[dict],      # todos los platillos activos del menú
    ) -> float:
        """
        Calcula el monto de UNA comida completa.
        Si descuento_por_platillo está activo, descuenta los platillos NO seleccionados.
        """
        if not descuento_por_platillo:
            return precio_menu

        ids_seleccionados = {str(p["platillo_id"]) for p in platillos_seleccionados}

        descuento = sum(
            float(p.get("precio", 0.0))
            for p in todos_los_platillos
            if str(p["id"]) not in ids_seleccionados
        )

        return max(0.0, precio_menu - descuento)

    def _decrementar_stock(self, platillo_id: str):
        try:
            result = self.supabase.table(self.table_platillos).select('stock').eq('id', platillo_id).single().execute()
            current = result.data.get('stock') if result.data else None
            if current is not None and current > 0:
                self.supabase.table(self.table_platillos).update({'stock': current - 1}).eq('id', platillo_id).execute()
        except Exception as e:
            print(f"⚠️ Error decrementando stock para {platillo_id}: {e}")

    def crear_orden_manual(
        self,
        cliente_nombre: str,
        tipo_entrega: str,
        direccion: str,
        comidas: list[dict],       # [{"platillos": [{"platillo_id": int, "platillo_nombre": str, "precio": float}]}]
        extras: list[dict],        # [{"platillo_id": int, "platillo_nombre": str, "precio": float}]
        precio_menu: float,
        descuento_por_platillo: bool,
        uid=os.getenv('USER_ID')
    ) -> dict:
        """
        Crea comandas desde el dashboard (sin WhatsApp).

        - Una comanda por cada comida completa, con sus platillos en desglose
        - Una comanda por cada extra
        - Todas vinculadas por el mismo pedido_grupo
        """

        if not comidas and not extras:
            write_log(uid or "system", "crear_orden_manual_no_items", f"Intento de crear orden manual sin items para {cliente_nombre}.", nivel="warning")
            return {"ok": False, "error": "La orden no tiene items"}

        if not cliente_nombre or not cliente_nombre.strip():
            write_log(uid or "system", "crear_orden_manual_no_cliente_nombre", f"Intento de crear orden manual sin nombre de cliente para {cliente_nombre}.", nivel="warning")
            return {"ok": False, "error": "El nombre del cliente es obligatorio"}

        pedido_grupo = str(uuid.uuid4())
        comandas_ids = []

        try:
            # Obtener todos los platillos activos para calcular descuentos
            todos_los_platillos = self.read_data(
                table_name=self.table_platillos,
                variables='id, platillo, precio',
                filters={'activo': 'TRUE'},
            )

            # ── Comidas completas ──────────────────────────────────────────
            for i, comida in enumerate(comidas):
                platillos_comida = comida.get("platillos", [])

                monto = self._calcular_monto_comida(
                    precio_menu=precio_menu,
                    descuento_por_platillo=descuento_por_platillo,
                    platillos_seleccionados=platillos_comida,
                    todos_los_platillos=todos_los_platillos,
                )

                comanda = {
                    "user_id": uid,
                    "cliente_nombre": cliente_nombre.strip(),
                    "pedido_grupo": pedido_grupo,
                    "telefono_cliente": "mostrador",
                    "tipo_entrega": tipo_entrega or "local",
                    "direccion": direccion.strip() if direccion else "",
                    "monto_estandar": monto,
                    "monto_extras": 0,
                    "monto_desechables": 0,
                    "monto_total": monto,
                    "status": "PENDIENTE",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

                comanda_id = self.insert_data(comanda, self.table_comandas, return_id=True)

                if not comanda_id:
                    return {"ok": False, "error": f"Error insertando comida {i + 1}"}

                comandas_ids.append(comanda_id)

                for platillo in platillos_comida:
                    self.insert_data(
                        {
                            "comanda_id": comanda_id,
                            "platillo_id": platillo["platillo_id"],
                        },
                        self.table_desglose
                    )
                    self._decrementar_stock(platillo["platillo_id"])

                print(f"✅ Comida {i + 1} creada: {comanda_id} | ${monto} | {len(platillos_comida)} platillos")
                write_log(uid or "system", "comida_creada_manual", f"Comida {i + 1} creada manualmente para {cliente_nombre} con comanda_id: {comanda_id} y monto: ${monto}.", nivel="info")

            # ── Extras ────────────────────────────────────────────────────
            for extra in extras:
                platillo_id = str(extra.get("platillo_id", "")).strip('"')
                precio_extra = float(extra.get("precio", 0.0))
                nombre_extra = extra.get("platillo_nombre", "")

                comanda_extra = {
                    "user_id": uid,
                    "cliente_nombre": cliente_nombre.strip(),
                    "pedido_grupo": pedido_grupo,
                    "telefono_cliente": "mostrador",
                    "tipo_entrega": tipo_entrega or "local",
                    "direccion": direccion.strip() if direccion else "",
                    "monto_estandar": 0,
                    "monto_extras": precio_extra,
                    "monto_desechables": 0,
                    "monto_total": precio_extra,
                    "status": "PENDIENTE",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "es_extra": True
                }

                comanda_id = self.insert_data(comanda_extra, self.table_comandas, return_id=True)

                if not comanda_id:
                    return {"ok": False, "error": f"Error insertando extra: {nombre_extra}"}

                comandas_ids.append(comanda_id)

                self.insert_data(
                    {"comanda_id": comanda_id, "platillo_id": platillo_id},
                    self.table_desglose
                )
                self._decrementar_stock(platillo_id)

                print(f"✅ Extra creado: {comanda_id} | {nombre_extra} | ${precio_extra}")

            print(f"📦 Orden manual completa | grupo: {pedido_grupo} | {len(comandas_ids)} comandas")
            write_log(uid or "system", "orden_manual_creada", f"Orden manual creada para {cliente_nombre} con pedido_grupo: {pedido_grupo} y {len(comandas_ids)} comandas.", nivel="info")

            return {
                "ok": True,
                "pedido_grupo": pedido_grupo,
                "comandas_ids": comandas_ids,
            }

        except Exception as e:
            print(f"❌ Error en crear_orden_manual: {e}")
            write_log(uid or "system", "crear_orden_manual_error", f"Error al crear orden manual para {cliente_nombre}: {str(e)}.", nivel="error")
            return {"ok": False, "error": str(e)}

    def editar_comanda(
        self,
        comanda_id: str,
        platillos: list[dict],  # [{"platillo_id": str, "tiempo_id": str, ...}]
        precio_menu: float,
        descuento_por_platillo: bool,
        todos_los_platillos: list[dict],
    ) -> dict:
        """
        Edita una comanda individual:
        - Limpia su desglose anterior
        - Inserta el nuevo desglose
        - Recalcula y actualiza monto_total
        """
        try:
            # 1. Borrar desglose anterior
            self.supabase.table(self.table_desglose)\
                .delete()\
                .eq("comanda_id", comanda_id)\
                .execute()

            # 2. Insertar nuevo desglose
            for platillo in platillos:
                self.insert_data(
                    {"comanda_id": comanda_id, "platillo_id": platillo["platillo_id"]},
                    self.table_desglose
                )

            # 3. Recalcular monto
            monto = self._calcular_monto_comida(
                precio_menu=precio_menu,
                descuento_por_platillo=descuento_por_platillo,
                platillos_seleccionados=platillos,
                todos_los_platillos=todos_los_platillos,
            )

            # 4. Actualizar comanda
            self.supabase.table(self.table_comandas)\
                .update({"monto_total": monto, "monto_estandar": monto})\
                .eq("id", comanda_id)\
                .execute()

            print(f"✅ Comanda editada: {comanda_id} | ${monto}")
            write_log("system", "comanda_editada", f"Comanda {comanda_id} editada con nuevo monto: ${monto}.", nivel="info")
            return {"ok": True, "comanda_id": comanda_id, "monto": monto}

        except Exception as e:
            print(f"❌ Error en editar_comanda: {e}")
            write_log("system", "editar_comanda_error", f"Error al editar comanda {comanda_id}: {str(e)}.", nivel="error")
            return {"ok": False, "error": str(e)}
    
    def consultar_menu_del_dia(self, user_id=None):
        try:
            if user_id is None:
                user_id = os.getenv('USER_ID')

            if not user_id:
                print("⚠️ USER_ID no configurado - No se puede consultar menú")
                write_log("system", "consultar_menu_user_id_missing", "USER_ID no configurado en el entorno. No se puede consultar menú del día.", nivel="warning")
                return {}
            
            # Consultar platillos (excluir stock=0, mantener null=ilimitado)
            response = (
                self.supabase
                .table(self.table_platillos)
                .select(
                    f"platillo, tiempo_id, precio, " +
                    f"{self.table_tiempos}(id, nombre)"
                )
                .eq("user_id", user_id)
                .eq("activo", True)
                .or_("stock.is.null,stock.gt.0")
                .execute()
            )

            data = response.data or []

            if not data:
                print(f"No se encontraron platillos activos para user_id '{user_id}' en '{self.table_platillos}'.")
                write_log(user_id, "menu_del_dia_empty", f"No se encontraron platillos activos para user_id: {user_id} en la tabla '{self.table_platillos}'.", nivel="warning")
                return {}

            # Consultar precio del menú desde config
            config_response = self.supabase.table('tbl_cocina_config')\
                .select('precio_menu, descuento_por_platillo')\
                .eq('user_id', user_id)\
                .execute()
            
            precio_menu = 0.0
            descuento_por_platillo = False
            if config_response.data and len(config_response.data) > 0:
                precio_menu = float(config_response.data[0].get('precio_menu') or 0.0)
                descuento_por_platillo = bool(config_response.data[0].get('descuento_por_platillo') or False)

            # Procesar platillos agrupados por tiempo
            menu_por_tiempos = defaultdict(list)
            for item in data:
                tiempo_info = item.get('tbl_cocina_tiempos', {})
                nombre_tiempo = tiempo_info.get('nombre', 'Desconocido')
                platillo = item.get('platillo', 'Sin nombre')
                precio = float(item.get('precio') or 0.0)
                menu_por_tiempos[nombre_tiempo].append({
                    'platillo': platillo,
                    'precio': precio
                })

            return {
                'menu': dict(menu_por_tiempos),
                'precio_menu': precio_menu,
                'descuento_por_platillo': descuento_por_platillo
            }

        except Exception as error:
            print(f"Error al consultar menú del día en '{self.table_platillos}': {error}")
            write_log("system", "consultar_menu_error", f"Error al consultar menú del día para user_id: {user_id} en la tabla '{self.table_platillos}': {str(error)}.", nivel="error")
            return {}

    @staticmethod
    def unaccent_simple(texto):
        reemplazos = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
            'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
        }
        return ''.join(reemplazos.get(c, c) for c in texto)

    @staticmethod
    def construir_platillos_dict(tool_input, campos_platillos_validos):
        platillos = {}
        for campo in campos_platillos_validos:
            valor = tool_input.get(campo)
            if valor and str(valor).strip() not in ['', '<UNKNOWN>']:
                platillos[campo] = [valor] if isinstance(valor, str) else valor
        for extra in ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']:
            valor = tool_input.get(extra)
            if valor and str(valor).strip() not in ['', '<UNKNOWN>']:
                platillos[extra] = [valor] if isinstance(valor, str) else valor
        write_log("system", "platillos_extraidos", f"Platillos extraídos del input: {platillos}", nivel="info")
        return platillos

    def extraer_ids_platillos(self, platillos, user_id=os.getenv('USER_ID', '')):
        try:
            print(f"🔍 Buscando IDs para platillos: {platillos}")
            write_log(user_id or "system", "buscar_ids_platillos", f"Buscando IDs para platillos: {platillos}", nivel="info")
            response = self.supabase.rpc(
                'buscar_platillos_flexible',
                {
                    'nombres': platillos,
                    'p_user_id': user_id
                }
            ).execute()

            data = response.data or []

            if len(data) < len(platillos):
                encontrados = [d['platillo'] for d in data]
                no_encontrados = [p for p in platillos if not any(
                    self.unaccent_simple(p.lower()) == self.unaccent_simple(e.lower()) 
                    for e in encontrados
                )]
                print(f"⚠️ Platillos NO encontrados en BD: {no_encontrados}")
                write_log(user_id or "system", "platillos_no_encontrados", f"Platillos no encontrados en BD para user_id {user_id}: {no_encontrados}", nivel="warning")

            print(f"✅ {len(data)}/{len(platillos)} platillos encontrados")
            return data

        except Exception as error:
            print(f"❌ Error en extraer_ids_platillos: {error}")
            write_log(user_id or "system", "extraer_ids_platillos_error", f"Error al extraer IDs de platillos para user_id {user_id}: {str(error)}.", nivel="error")
            return []

    def determinar_costo_comanda(self, tool_input, config=None, campos_platillos=None):
        precio_menu = float(config.get('precio_menu', 0.0)) if config else 0.0
        descuento_por_platillo = bool(config.get('descuento_por_platillo', False)) if config else False
        descuento_fijo_omision = config.get('descuento_fijo_omision', None) if config else None
        if descuento_fijo_omision is not None:
            try:
                descuento_fijo_omision = float(descuento_fijo_omision)
            except:
                descuento_fijo_omision = None

        write_log("system", "determinando_costo_comanda", f"Determinando costo de comanda con tool_input: {tool_input} y config: {config}", nivel="info")
        write_log("system", "descuento_fijo_por_omision", f"Descuento fijo por omision: {descuento_fijo_omision}", nivel="info")

        costos_platillos = self.read_data(
            table_name=self.table_platillos,
            variables='platillo, precio',
            filters={'activo': 'TRUE'},
        )

        campos_menu = [c for c in (campos_platillos or []) if c != 'a_la_carta']

        
        # if any(campo in tool_input for campo in campos_menu):
        if any(tool_input.get(campo) not in empty_placeholders for campo in campos_menu):

            if descuento_por_platillo:
                platillos_omitidos = [
                    tool_input[campo] for campo in campos_menu
                    if campo in tool_input and (not tool_input.get(campo) or tool_input[campo] in ['', '<UNKNOWN>'])
                ]
                descuento = 0.0
                for platillo_omitido in platillos_omitidos:
                    if descuento_fijo_omision is not None:
                        descuento += descuento_fijo_omision
                    else:
                        precio_individual = next(
                            (item['precio'] for item in costos_platillos
                            if item['platillo'] == platillo_omitido),
                            0.0
                        )
                        descuento += precio_individual
                monto_estandar = precio_menu - descuento
            else:
                monto_estandar = precio_menu

            a_la_carta = tool_input.get('a_la_carta')
            if a_la_carta and a_la_carta not in ['', '<UNKNOWN>']:
                precio_a_la_carta = next(
                    (item['precio'] for item in costos_platillos 
                        if self.unaccent_simple(item['platillo'].lower()) == self.unaccent_simple(a_la_carta.lower())),
                    0.0
                )
                monto_estandar += precio_a_la_carta

            platillos_extra = [v for k, v in tool_input.items() if 'extra' in k]
            monto_extras = sum(
                item['precio'] for item in costos_platillos 
                if item['platillo'] in platillos_extra
            ) if platillos_extra else 0

        else:
            todos_platillos = []
            for k, v in tool_input.items():
                if k in ['nombre_completo', 'desechables']:
                    continue
                if not v or v in ['', '<UNKNOWN>']:
                    continue
                if isinstance(v, list):
                    todos_platillos.extend([p for p in v if p and isinstance(p, str) and p not in ['', '<UNKNOWN>']])
                else:
                    if isinstance(v, str):  # ← esto es lo que faltaba
                        todos_platillos.append(v)

            todos_platillos_norm = [self.unaccent_simple(p.lower()) for p in todos_platillos]

            monto_estandar = sum(
                item['precio'] for item in costos_platillos
                if any(
                    norm in self.unaccent_simple(item['platillo'].lower()) or
                    self.unaccent_simple(item['platillo'].lower()) in norm
                    for norm in todos_platillos_norm
                )
            )
            monto_extras = 0

        cobro_desechables = bool(config.get('cobro_desechables', False)) if config else False
        precio_desechables = float(config.get('precio_desechables', 0.0)) if config else 0.0
        monto_desechables = precio_desechables if cobro_desechables else 0.0

        montos = {
            'monto_estandar': monto_estandar,
            'monto_extras': monto_extras,
            'monto_desechables': monto_desechables,
            'monto_total': monto_estandar + monto_extras + monto_desechables
        }
        return montos
    
    # def get_session_id(self, user_id):
    #     query=self.supabase.table(self.table_conversations).select('*').eq('user_id', user_id).execute()
    #     session_id=query.data[0].get('session_id')
    #     return session_id

    
    def get_session_id(self, user_id):
        query = self.supabase.table(self.table_conversations).select('*').eq('user_id', user_id).execute()
        if not query.data:
            return None
        return query.data[0].get('session_id')

if __name__=='__main__':
    import os
    from db import DBCA
    from dotenv import load_dotenv

    load_dotenv()

    USER_ID=os.getenv('USER_ID')

    supabase_class = DBCA()
    # informacion_cliente=supabase_class.obtener_config_cocina(user_id=USER_ID)
    # menu_del_dia=supabase_class.consultar_menu_del_dia(user_id=USER_ID)
    # supabase_class.obtener_pedido_reciente_usuario(telefono='2422341152')
    # print(
    # )
    menu_del_dia = supabase_class.consultar_menu_del_dia(user_id=os.getenv('USER_ID'))
    print("Menu del día:", menu_del_dia)