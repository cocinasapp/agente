# python3 -m states.generic

import logging, uuid
import os
from dotenv import load_dotenv
from logger_utils import write_log
from utils_llm import (
    get_nombre_usuario, 
    empty_placeholders
)

load_dotenv()

USER_ID = os.getenv('USER_ID')

logger = logging.getLogger(__name__)

def get_username(session_context, telefono, data):
    if not session_context.get("nombre_usuario"):
        write_log(telefono, "USERNAME", "entró al if de username")
        nombre = get_nombre_usuario(data)
        write_log(telefono, "USERNAME", f"NOMBRE Extraído: {nombre}")
        session_context["nombre_usuario"] = nombre if nombre else ""

def construir_orden_temporal(orden_temporal):
    if not orden_temporal:
        return {
            "pedido_grupo": str(uuid.uuid4()),
            "ordenes": [],
            "total_ordenes": 0,
            "monto_total_general": 0
        }
    return orden_temporal

# def agregar_extra_a_orden(orden_temporal, tool_input, config, supabase_client, campos_platillos_validos):
#     ultima_orden = orden_temporal["ordenes"][-1]

#     for key in ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']:
#         if key in tool_input and tool_input[key] not in ['', '<UNKNOWN>', None]:
#             # ultima_orden["platillos"][key] = [tool_input[key]]
#             valor = tool_input[key]
#             ultima_orden["platillos"][key] = valor if isinstance(valor, list) else [valor]

#     tool_input_recalculo = {}
#     for tiempo_key, platillos_tiempo in ultima_orden["platillos"].items():
#         if platillos_tiempo:
#             tool_input_recalculo[tiempo_key] = platillos_tiempo[0] if len(platillos_tiempo) == 1 else platillos_tiempo

#     costo_anterior = ultima_orden["costos"].get("monto_total", 0)
#     costo_nuevo = supabase_client.determinar_costo_comanda(tool_input_recalculo, config=config, campos_platillos=campos_platillos_validos)
#     orden_temporal["monto_total_general"] -= costo_anterior
#     ultima_orden["costos"] = costo_nuevo
#     orden_temporal["monto_total_general"] += costo_nuevo.get("monto_total", 0)
#     orden_temporal["ordenes"][-1] = ultima_orden

#     content = {
#         "status": "extra_agregado_a_orden_existente",
#         "orden_numero": ultima_orden["orden_numero"],
#         "costo_orden_actualizado": costo_nuevo.get("monto_total", 0),
#         "monto_total_acumulado": orden_temporal["monto_total_general"],
#     }
#     if config.get('cobro_desechables'):
#         content["aviso_desechables"] = f"Se cobran desechables por ${config.get('precio_desechables', 0)} por comida"

#     return orden_temporal, content

def agregar_extra_a_orden1(orden_temporal, tool_input, config, supabase_client, campos_platillos_validos):
    extras_keys = ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']
    
    platillos_extra = {}
    for key in extras_keys:
        val = tool_input.get(key)
        if val not in ['', '<UNKNOWN>', None]:
            platillos_extra[key] = [val] if not isinstance(val, list) else val

    # costo_orden = supabase_client.determinar_costo_comanda(
    #     {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in platillos_extra.items()},
    #     config=config,
    #     campos_platillos=campos_platillos_validos
    # )
    # En agregar_extra_a_orden, antes de llamar determinar_costo_comanda
    config_sin_desechables = {**config, 'cobro_desechables': False}
    costo_orden = supabase_client.determinar_costo_comanda(
        {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in platillos_extra.items()},
        config=config_sin_desechables,
        campos_platillos=campos_platillos_validos
    )

    nueva_orden = {
        "orden_numero": len(orden_temporal["ordenes"]) + 1,
        "platillos": platillos_extra,
        "desechables": False,
        "costos": costo_orden,
        "es_extra": True
    }
    orden_temporal["ordenes"].append(nueva_orden)
    orden_temporal["total_ordenes"] = len(orden_temporal["ordenes"])
    orden_temporal["monto_total_general"] += costo_orden.get("monto_total", 0)

    content = {
        "status": "extra_agregado_a_orden_existente",
        "orden_numero": nueva_orden["orden_numero"],
        "costo_orden_actualizado": costo_orden.get("monto_total", 0),
        "monto_total_acumulado": orden_temporal["monto_total_general"],
    }
    if config.get('cobro_desechables'):
        content["aviso_desechables"] = f"Se cobran desechables por ${config.get('precio_desechables', 0)} por comida"

    return orden_temporal, content

def agregar_platillos_a_orden_0(orden_temporal, tool_input, config, supabase_client, campos_platillos_validos):
    nueva_comida = supabase_client.construir_platillos_dict(tool_input, campos_platillos_validos)

    for orden_existente in orden_temporal["ordenes"]:
        existente_vals = set()
        for v in orden_existente["platillos"].values():
            if isinstance(v, list):
                existente_vals.update(supabase_client.unaccent_simple(p.lower()) for p in v if p)
            elif v:
                existente_vals.add(supabase_client.unaccent_simple(v.lower()))
        nueva_vals = set()
        for v in nueva_comida.values():
            if isinstance(v, list):
                nueva_vals.update(supabase_client.unaccent_simple(p.lower()) for p in v if p)
            elif v:
                nueva_vals.add(supabase_client.unaccent_simple(v.lower()))
        if nueva_vals and existente_vals:
            match = (
                all(any(nv in ev or ev in nv for ev in existente_vals) for nv in nueva_vals) and
                all(any(ev in nv or nv in ev for nv in nueva_vals) for ev in existente_vals)
            )
            if match:
                content = {
                    "status": "orden_ya_existe",
                    "mensaje": "Esta orden ya fue registrada.",
                    "total_ordenes": orden_temporal["total_ordenes"],
                    "monto_total_acumulado": orden_temporal["monto_total_general"],
                }
                return orden_temporal, content

    costo_orden = supabase_client.determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)
    nueva_orden = {
        "orden_numero": len(orden_temporal["ordenes"]) + 1,
        "platillos": nueva_comida,
        "desechables": tool_input.get('desechables', False),
        "costos": costo_orden
    }
    orden_temporal["ordenes"].append(nueva_orden)
    orden_temporal["total_ordenes"] = len(orden_temporal["ordenes"])
    orden_temporal["monto_total_general"] += costo_orden.get('monto_total', 0)

    content = {
        "status": "orden_temporal_guardada",
        "orden_numero": nueva_orden["orden_numero"],
        "platillos": nueva_orden["platillos"],
        "costo_orden": costo_orden.get('monto_total', 0),
        "total_ordenes": orden_temporal["total_ordenes"],
        "monto_total_acumulado": orden_temporal["monto_total_general"],
    }
    if config.get('cobro_desechables'):
        content["aviso_desechables"] = f"Se cobran desechables por ${config.get('precio_desechables', 0)} por comida"

    return orden_temporal, content

def agregar_platillos_a_orden(orden_temporal, tool_input, config, supabase_client, campos_platillos_validos):
    nueva_comida = supabase_client.construir_platillos_dict(tool_input, campos_platillos_validos)
 
    costo_orden = supabase_client.determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)
    nueva_orden = {
        "orden_numero": len(orden_temporal["ordenes"]) + 1,
        "platillos": nueva_comida,
        "desechables": tool_input.get('desechables', False),
        "costos": costo_orden
    }

    # Si viene de un flujo de modificación, inyectar comanda_id en la primera orden
    # para que persistir_pedido detecte UPDATE en vez de INSERT
    comanda_id_original = orden_temporal.pop("_comanda_id_original", None)
    if comanda_id_original and not orden_temporal["ordenes"]:
        nueva_orden["comanda_id"] = comanda_id_original

    orden_temporal["ordenes"].append(nueva_orden)
    orden_temporal["total_ordenes"] = len(orden_temporal["ordenes"])
    orden_temporal["monto_total_general"] += costo_orden.get('monto_total', 0)
 
    content = {
        "status": "orden_temporal_guardada",
        "orden_numero": nueva_orden["orden_numero"],
        "platillos": nueva_orden["platillos"],
        "costo_orden": costo_orden.get('monto_total', 0),
        "total_ordenes": orden_temporal["total_ordenes"],
        "monto_total_acumulado": orden_temporal["monto_total_general"],
    }
    if config.get('cobro_desechables'):
        content["aviso_desechables"] = f"Se cobran desechables por ${config.get('precio_desechables', 0)} por comida"
 
    return orden_temporal, content

def agregar_extra_a_orden(orden_temporal, tool_input, config, supabase_client, campos_platillos_validos):
    extras_keys = ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']

    platillos_extra = {}
    for key in extras_keys:
        val = tool_input.get(key)
        if val not in ['', '<UNKNOWN>', None]:
            platillos_extra[key] = [val] if not isinstance(val, list) else val

    # Agregar el extra a la última orden existente (no crear orden nueva)
    ultima_orden = orden_temporal["ordenes"][-1]

    for key, val in platillos_extra.items():
        slot_libre = next(
            (ek for ek in extras_keys
             if ultima_orden["platillos"].get(ek) in empty_placeholders
             or ultima_orden["platillos"].get(ek) in [[], ['']]),
            None
        )
        if slot_libre:
            ultima_orden["platillos"][slot_libre] = val

    # Recalcular costo de esa orden completa (platillos originales + extra nuevo)
    config_sin_desechables = {**config, 'cobro_desechables': False}
    tool_input_recalculo = {}
    for campo, vals in ultima_orden["platillos"].items():
        if isinstance(vals, list) and vals:
            tool_input_recalculo[campo] = vals[0]
        elif vals and vals not in empty_placeholders:
            tool_input_recalculo[campo] = vals

    costo_orden = supabase_client.determinar_costo_comanda(
        tool_input_recalculo,
        config=config_sin_desechables,
        campos_platillos=campos_platillos_validos
    )

    # Actualizar costo de la última orden y el total general (resta lo viejo, suma lo nuevo)
    monto_anterior = ultima_orden.get("costos", {}).get("monto_total", 0)
    ultima_orden["costos"] = costo_orden
    orden_temporal["monto_total_general"] = (
        orden_temporal["monto_total_general"] - monto_anterior + costo_orden.get("monto_total", 0)
    )

    content = {
        "status": "extra_agregado_a_orden_existente",
        "orden_numero": ultima_orden["orden_numero"],
        "costo_orden_actualizado": costo_orden.get("monto_total", 0),
        "monto_total_acumulado": orden_temporal["monto_total_general"],
    }
    if config.get('cobro_desechables'):
        content["aviso_desechables"] = f"Se cobran desechables por ${config.get('precio_desechables', 0)} por comida"

    return orden_temporal, content

# con una pequeña modificacion 
def persistir_pedido(
        orden_temporal,
        nombre_completo,
        telefono,
        config,
        supabase_client,
        campos_platillos_validos,
        info_entrega=None
        ):
    pedido_grupo = orden_temporal["pedido_grupo"]
    campos_menu_keys = [c for c in campos_platillos_validos if c != 'a_la_carta']

    logger.info("PERSISTIR_PEDIDO | total ordenes a procesar: %s", len(orden_temporal['ordenes']))

    # ── Acumular TODOS los platillos de TODAS las órdenes en lista plana ──────
    todos_platillos = []
    for orden in orden_temporal["ordenes"]:
        for platillos_tiempo in orden['platillos'].values():
            if platillos_tiempo and platillos_tiempo not in ['', '<UNKNOWN>']:
                if isinstance(platillos_tiempo, list):
                    todos_platillos.extend(platillos_tiempo)
                else:
                    todos_platillos.append(platillos_tiempo)

    # ── Agregar costos de todas las órdenes ───────────────────────────────────
    monto_estandar = sum(o['costos'].get('monto_estandar', 0) for o in orden_temporal['ordenes'])
    monto_extras   = sum(o['costos'].get('monto_extras',   0) for o in orden_temporal['ordenes'])
    monto_desech   = sum(o['costos'].get('monto_desechables', 0) for o in orden_temporal['ordenes'])
    monto_total    = orden_temporal["monto_total_general"]

    # ── es_extra a nivel de grupo: True solo si ningún orden tiene tiempos de menú
    es_extra_grupo = not any(
        campo in orden['platillos'] and orden['platillos'][campo]
        for orden in orden_temporal['ordenes']
        for campo in campos_menu_keys
    )

    # ── Determinar INSERT o UPDATE: buscar comanda_id en la primera orden rehidratada
    comanda_id = next(
        (o.get('comanda_id') for o in orden_temporal['ordenes'] if o.get('comanda_id')),
        None
    )

    if comanda_id:
        # UPDATE: comanda única ya existe en Supabase (viene de rehidratar_orden_desde_supabase)
        ids_platillos = supabase_client.extraer_ids_platillos(todos_platillos, user_id=os.getenv('USER_ID'))
        nombre_a_id = {
            supabase_client.unaccent_simple(obj['platillo'].lower()): obj.get('id')
            for obj in ids_platillos
        }
        nuevos_platillos_ids = [
            nombre_a_id.get(supabase_client.unaccent_simple(nombre.lower()))
            for nombre in todos_platillos
            if nombre_a_id.get(supabase_client.unaccent_simple(nombre.lower()))
        ]
        resultado = supabase_client.actualizar_platillos_comanda(
            comanda_id=comanda_id,
            nuevos_platillos_ids=nuevos_platillos_ids,
            nuevos_costos={
                'monto_estandar': monto_estandar,
                'monto_extras':   monto_extras,
                'monto_desechables': monto_desech,
                'monto_total':    monto_total
            }
        )
        if not resultado.get('success'):
            logger.error(
                "persistir_pedido: fallo al actualizar comanda | telefono: %s | comanda_id: %s",
                telefono, comanda_id
            )
        supabase_client.update_data(
            table=os.getenv('TLB_COMANDAS'),
            data={'cliente_nombre': nombre_completo},
            filters={'id': comanda_id}
        )
    else:
        # INSERT: una comanda por cada orden (comida) del grupo
        _info = info_entrega or {}
        _metodo = _info.get('metodo_de_entrega') or 'local'
        _tipo_entrega = 'domicilio' if 'domicilio' in _metodo.lower() else 'local'
        _domicilio = _info.get('domicilio') or ''
        _referencia = _info.get('referencia') or ''

        comanda_id = None  # último comanda_id insertado, se usa abajo en estado_entrega/content

        for orden in orden_temporal["ordenes"]:
            platillos_orden = []
            for platillos_tiempo in orden['platillos'].values():
                if platillos_tiempo and platillos_tiempo not in ['', '<UNKNOWN>']:
                    if isinstance(platillos_tiempo, list):
                        platillos_orden.extend(platillos_tiempo)
                    else:
                        platillos_orden.append(platillos_tiempo)

            costos_orden = orden.get('costos', {})
            es_extra_orden = orden.get('es_extra', False) or not any(
                campo in orden['platillos'] and orden['platillos'][campo]
                for campo in campos_menu_keys
            )

            comanda = {
                'user_id':          os.getenv('USER_ID'),
                'cliente_nombre':   nombre_completo,
                'pedido_grupo':     pedido_grupo,
                'monto_estandar':   costos_orden.get('monto_estandar', 0),
                'monto_extras':     costos_orden.get('monto_extras', 0),
                'monto_desechables': costos_orden.get('monto_desechables', 0),
                'monto_total':      costos_orden.get('monto_total', 0),
                'telefono_cliente': telefono,
                'es_extra':         es_extra_orden,
                'tipo_entrega':     _tipo_entrega,
                'direccion':        _domicilio,
                'referencia_1':     _referencia,
            }
            comanda_id_orden = supabase_client.insert_data(comanda, os.getenv('TLB_COMANDAS'), return_id=True)
            if not comanda_id_orden:
                logger.error(
                    "persistir_pedido: fallo al insertar comanda | telefono: %s | orden_numero: %s | comanda: %s",
                    telefono, orden.get('orden_numero'), comanda
                )
                continue

            comanda_id = comanda_id_orden  # se conserva el último para content/estado_entrega

            if platillos_orden:
                ids_platillos = supabase_client.extraer_ids_platillos(platillos_orden, user_id=os.getenv('USER_ID'))
                nombre_a_id = {
                    supabase_client.unaccent_simple(obj['platillo'].lower()): obj.get('id')
                    for obj in ids_platillos
                }
                for nombre_platillo in platillos_orden:
                    platillo_id = nombre_a_id.get(supabase_client.unaccent_simple(nombre_platillo.lower()))
                    if platillo_id:
                        supabase_client.insert_data(
                            {'comanda_id': comanda_id_orden, 'platillo_id': platillo_id},
                            os.getenv('TLB_DESGLOSE')
                        )
                        supabase_client._decrementar_stock(platillo_id)
    # ELSE ORIGINAL SIN LAS CONDICIONES NUEVAS INTEGRADAS
    # else:
    #     # INSERT: comanda nueva — una sola para todo el grupo
    #     _info = info_entrega or {}
    #     _metodo = _info.get('metodo_de_entrega') or 'local'
    #     _tipo_entrega = 'domicilio' if 'domicilio' in _metodo.lower() else 'local'
    #     _domicilio = _info.get('domicilio') or ''
    #     _referencia = _info.get('referencia') or ''
    #     comanda = {
    #         'user_id':          os.getenv('USER_ID'),
    #         'cliente_nombre':   nombre_completo,
    #         'pedido_grupo':     pedido_grupo,
    #         'monto_estandar':   monto_estandar,
    #         'monto_extras':     monto_extras,
    #         'monto_desechables': monto_desech,
    #         'monto_total':      monto_total,
    #         'telefono_cliente': telefono,
    #         'es_extra':         es_extra_grupo,
    #         'tipo_entrega':     _tipo_entrega,
    #         'direccion':        _domicilio,
    #         'referencia_1':     _referencia,
    #     }
    #     comanda_id = supabase_client.insert_data(comanda, os.getenv('TLB_COMANDAS'), return_id=True)
    #     if not comanda_id:
    #         logger.error(
    #             "persistir_pedido: fallo al insertar comanda | telefono: %s | comanda: %s",
    #             telefono, comanda
    #         )

    #     if todos_platillos and comanda_id:
    #         ids_platillos = supabase_client.extraer_ids_platillos(todos_platillos, user_id=os.getenv('USER_ID'))
    #         nombre_a_id = {
    #             supabase_client.unaccent_simple(obj['platillo'].lower()): obj.get('id')
    #             for obj in ids_platillos
    #         }
    #         for nombre_platillo in todos_platillos:
    #             platillo_id = nombre_a_id.get(supabase_client.unaccent_simple(nombre_platillo.lower()))
    #             if platillo_id:
    #                 supabase_client.insert_data(
    #                     {'comanda_id': comanda_id, 'platillo_id': platillo_id},
    #                     os.getenv('TLB_DESGLOSE')
    #                 )
    #                 supabase_client._decrementar_stock(platillo_id)

    estado_entrega = {
        "comanda_id":    comanda_id,
        "pedido_grupo":  pedido_grupo,
        "nombre_cliente": nombre_completo,
        "monto_total":   orden_temporal["monto_total_general"],
        "total_ordenes": orden_temporal["total_ordenes"]
    }

    content = {
        "status":        "pedido_guardado_esperando_entrega",
        "nombre_cliente": nombre_completo,
        "pedido_grupo":  pedido_grupo,
        "total_ordenes": orden_temporal["total_ordenes"],
        "monto_total":   orden_temporal["monto_total_general"],
        "comanda_id":    comanda_id,
        "resumen_completo": [
            {
                "comida": i + 1,
                "platillos": [
                    p for vals in orden.get("platillos", {}).values()
                    for p in (vals if isinstance(vals, list) else [vals])
                    if p and p not in ['', '<UNKNOWN>', None]
                ],
                "monto": orden.get("costos", {}).get("monto_total", 0),
            }
            for i, orden in enumerate(orden_temporal["ordenes"])
        ],
    }
    if config.get('cobro_desechables'):
        content["aviso_desechables"] = f"Se cobran desechables por ${config.get('precio_desechables', 0)} por comida"

    return estado_entrega, content


def orden_esta_completa(orden_temporal: dict) -> bool:
    """
    Una orden está completa si existe al menos una orden en el array
    con al menos un platillo válido en cualquier tiempo.
    """
    if not orden_temporal:
        return False

    ordenes = orden_temporal.get("ordenes", [])
    if not ordenes:
        return False

    for orden in ordenes:
        platillos = orden.get("platillos", {})
        for tiempo, valores in platillos.items():
            if isinstance(valores, list):
                if any(v not in empty_placeholders for v in valores):
                    return True
            else:
                if valores not in empty_placeholders:
                    return True

    return False


def que_falta(orden_temporal: dict, campos_platillos_validos: list) -> list[str]:
    """
    Retorna los campos del menú del día que no tienen ningún platillo
    en ninguna de las órdenes acumuladas.
    """
    if not orden_temporal:
        return campos_platillos_validos

    campos_cubiertos = set()

    for orden in orden_temporal.get("ordenes", []):
        platillos = orden.get("platillos", {})
        for tiempo, valores in platillos.items():
            if isinstance(valores, list):
                if any(v not in empty_placeholders for v in valores):
                    campos_cubiertos.add(tiempo)
            else:
                if valores not in empty_placeholders:
                    campos_cubiertos.add(tiempo)

    # return [c for c in campos_platillos_validos if c not in campos_cubiertos]
    return [c for c in campos_platillos_validos if c not in campos_cubiertos and c != 'a_la_carta']

CAMPOS_ENTREGA_REQUERIDOS = ['nombre_para_pedido', 'metodo_de_entrega']

def info_esta_completa(info_entrega: dict) -> bool:
    """
    La info está completa si tiene nombre, método de entrega,
    y domicilio cuando el método es 'domicilio'.
    """
    if not info_entrega:
        return False

    for campo in CAMPOS_ENTREGA_REQUERIDOS:
        if info_entrega.get(campo) in empty_placeholders:
            return False

    metodo = str(info_entrega.get('metodo_de_entrega', '')).strip().lower()
    if metodo == 'domicilio':
        if info_entrega.get('domicilio') in empty_placeholders:
            return False

    return True


def que_falta_info(info_entrega: dict) -> list[str]:
    """
    Retorna los campos de entrega que aún faltan.
    """
    if not info_entrega:
        return CAMPOS_ENTREGA_REQUERIDOS + ['domicilio']

    faltantes = []

    for campo in CAMPOS_ENTREGA_REQUERIDOS:
        if info_entrega.get(campo) in empty_placeholders:
            faltantes.append(campo)

    metodo = str(info_entrega.get('metodo_de_entrega', '')).strip().lower()
    if metodo == 'domicilio':
        if info_entrega.get('domicilio') in empty_placeholders:
            faltantes.append('domicilio')

    return faltantes

# def tiene_contenido_0(ti, campos_platillos_validos):
#     tiene_platillos = any(str(ti.get(c, '')).strip() not in empty_placeholders for c in campos_platillos_validos)
#     tiene_extras = any(ti.get(k) not in empty_placeholders for k in ['extra_1', 'extra_2', 'extra_3', 'a_la_carta'])
#     return tiene_platillos or tiene_extras


def tiene_contenido(ti, campos_platillos_validos):
    tiene_platillos = any(
        ti.get(c) not in empty_placeholders and ti.get(c) != []
        for c in campos_platillos_validos
    )
    tiene_extras = any(
        ti.get(k) not in empty_placeholders
        for k in ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']
    )
    return tiene_platillos or tiene_extras

def normalizar_a_extra_si_unico(tool_inputs, campos_menu_actuales, campos_platillos_validos):
    """
    Para cada tool_input en la lista: si tiene exactamente 1 campo de menú no nulo
    y sin extras ya asignados, lo reescribe como extra_1.
    """
    resultado = []
    for ti in tool_inputs:
        campos_con_valor = [
            c for c in campos_menu_actuales
            if ti.get(c) not in empty_placeholders
        ]
        ya_tiene_extras = any(
            ti.get(k) not in empty_placeholders
            for k in ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']
        )

        if len(campos_con_valor) == 1 and not ya_tiene_extras:
            platillo = ti[campos_con_valor[0]]
            nuevo_ti = {c: None for c in campos_platillos_validos}
            nuevo_ti.update({'extra_1': platillo, 'extra_2': None, 'extra_3': None, 'a_la_carta': None})
            logger.debug("Platillo único reasignado a extra_1: %s", platillo)
            resultado.append(nuevo_ti)
        else:
            resultado.append(ti)

    return resultado

def expandir_tool_input(tool_input, campos_menu_actuales):
    """
    Convierte el nuevo formato (dict con listas) al formato original (lista de dicts).

    {'Plato fuerte': ['Tacos dorados', 'Enchiladas verdes'], 'extra_1': ['Flan', 'Gelatina'], ...}
    →
    [{'Plato fuerte': 'Tacos dorados', 'extra_1': 'Flan', ...}, {'Plato fuerte': 'Enchiladas verdes', 'extra_1': 'Gelatina', ...}]
    """
    extras_keys = ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']
    all_keys = campos_menu_actuales + extras_keys

    max_ordenes = max(
        (len(v) for k in all_keys if isinstance(v := tool_input.get(k), list)),
        default=1
    )

    lista = []
    for i in range(max_ordenes):
        entry = {}
        for campo in all_keys:
            val = tool_input.get(campo)
            if isinstance(val, list):
                entry[campo] = val[i] if i < len(val) else None
            else:
                # Scalar: only assign to first entry when multi-comida to avoid duplication
                entry[campo] = val if (max_ordenes == 1 or i == 0) else None
        lista.append(entry)

    return lista

def reconstruir_tool_input(tool_input_nuevo, orden_temporal, campos_platillos_validos, menu_data):
    campos_menu_actuales = [c for c in campos_platillos_validos if c != 'a_la_carta']
    extras_keys = ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']

    # Lookup inverso: nombre platillo → tiempo
    platillo_a_tiempo = {}
    for tiempo, platillos in menu_data.get('menu', {}).items():
        for p in platillos:
            platillo_a_tiempo[p['platillo'].lower()] = tiempo

    # Recolectar platillos existentes, asignando al tiempo correcto
    platillos_existentes = {c: [] for c in campos_menu_actuales}
    extras_existentes = {k: [] for k in extras_keys}

    for orden in orden_temporal.get("ordenes", []):
        for campo, valores in orden.get("platillos", {}).items():
            if isinstance(valores, list):
                items = valores
            elif valores not in empty_placeholders:
                items = [valores]
            else:
                continue

            for platillo in items:
                if not platillo or platillo in empty_placeholders:
                    continue
                tiempo_correcto = platillo_a_tiempo.get(platillo.lower())
                if tiempo_correcto and tiempo_correcto in platillos_existentes:
                    platillos_existentes[tiempo_correcto].append(platillo)
                else:
                    # No está en menú → es extra
                    for k in extras_keys:
                        if not extras_existentes[k]:
                            extras_existentes[k].append(platillo)
                            break

    # Mergear con tool_input nuevo
    resultado = {}
    for campo in campos_menu_actuales:
        nuevos = tool_input_nuevo.get(campo)
        if isinstance(nuevos, list):
            nuevos = [v for v in nuevos if v not in empty_placeholders]
        elif nuevos not in empty_placeholders:
            nuevos = [nuevos]
        else:
            nuevos = []
        combinados = platillos_existentes[campo] + nuevos
        resultado[campo] = combinados if combinados else None

    for k in extras_keys:
        nuevo = tool_input_nuevo.get(k)
        if nuevo not in empty_placeholders:
            extras_existentes[k].append(nuevo)
        resultado[k] = extras_existentes[k][0] if extras_existentes[k] else None

    return resultado

def eliminar_platillos_de_orden(orden_temporal, tool_input_edicion, campos_platillos_validos, supabase_client, config):
    extras_keys = ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']
    campos_menu_actuales = [c for c in campos_platillos_validos if c != 'a_la_carta']

    # Construir set de platillos a eliminar (normalizados)
    a_eliminar = set()
    for campo in campos_menu_actuales + extras_keys:
        val = tool_input_edicion.get(campo)
        if isinstance(val, list):
            a_eliminar.update(v.lower() for v in val if v and v not in empty_placeholders)
        elif val and val not in empty_placeholders:
            a_eliminar.add(val.lower())

    ordenes_nuevas = []
    comanda_ids_eliminadas = []

    for orden in orden_temporal.get("ordenes", []):
        platillos_nuevos = {}
        for campo, valores in orden.get("platillos", {}).items():
            if isinstance(valores, list):
                filtrados = [v for v in valores if v and v.lower() not in a_eliminar]
                if filtrados:
                    platillos_nuevos[campo] = filtrados
            elif valores and valores not in empty_placeholders:
                if valores.lower() not in a_eliminar:
                    platillos_nuevos[campo] = valores

        # Solo conservar la orden si le quedó algún platillo
        if platillos_nuevos:
            tool_input_recalculo = {
                k: v[0] if isinstance(v, list) and len(v) == 1 else v
                for k, v in platillos_nuevos.items()
            }
            costo = supabase_client.determinar_costo_comanda(
                tool_input_recalculo, config=config, campos_platillos=campos_platillos_validos
            )
            nueva_orden = {
                "orden_numero": len(ordenes_nuevas) + 1,
                "platillos": platillos_nuevos,
                "desechables": orden.get("desechables", False),
                "costos": costo,
            }
            if orden.get("comanda_id"):
                nueva_orden["comanda_id"] = orden["comanda_id"]
            ordenes_nuevas.append(nueva_orden)
        else:
            # Orden eliminada completamente — registrar su id para borrarla de Supabase
            if orden.get("comanda_id"):
                comanda_ids_eliminadas.append(orden["comanda_id"])

    monto_total = sum(o["costos"].get("monto_total", 0) for o in ordenes_nuevas)
    orden_temporal["ordenes"] = ordenes_nuevas
    orden_temporal["total_ordenes"] = len(ordenes_nuevas)
    orden_temporal["monto_total_general"] = monto_total

    content = {
        "status": "orden_editada",
        "total_ordenes": len(ordenes_nuevas),
        "monto_total_acumulado": monto_total,
    }
    return orden_temporal, content

def reemplazar_platillos_en_orden(orden_temporal, cambios, campos_platillos_validos, supabase_client, config):
    campos_menu_actuales = [c for c in campos_platillos_validos if c != 'a_la_carta']
    extras_keys = ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']

    # Lookup inverso: nombre platillo → tiempo
    # Necesario para saber a qué tiempo pertenece el platillo nuevo
    from db import DBCA
    menu_data = supabase_client.consultar_menu_del_dia()
    platillo_a_tiempo = {}
    for tiempo, platillos in menu_data.get('menu', {}).items():
        for p in platillos:
            platillo_a_tiempo[p['platillo'].lower()] = tiempo

    # Convertir orden_temporal a lista de dicts {campo: platillo} para manipulación
    ordenes = []
    for orden in orden_temporal.get("ordenes", []):
        od = {}
        for campo, valores in orden.get("platillos", {}).items():
            if isinstance(valores, list):
                items = [v for v in valores if v and v not in empty_placeholders]
            elif valores and valores not in empty_placeholders:
                items = [valores]
            else:
                items = []
            for item in items:
                od[campo] = item  # una orden tiene un platillo por campo
        ordenes.append(od)
    import logging
    logging.getLogger(__name__).info("ORDENES_PLANAS | %s", ordenes)

    # Aplicar cada cambio [original, nuevo] a la primera orden que contenga original
    for cambio in cambios:
        if not isinstance(cambio, list) or len(cambio) != 2:
            continue
        original, nuevo = cambio[0], cambio[1]
        tiempo_nuevo = platillo_a_tiempo.get(nuevo.lower())

        for od in ordenes:
            # Buscar el campo que contiene el platillo original
            campo_original = next(
                (campo for campo, platillo in od.items() if platillo.lower() == original.lower()),
                None
            )
            if campo_original is None:
                continue

            # Forzar reemplazo: eliminar original, insertar nuevo en su tiempo correcto
            del od[campo_original]
            if tiempo_nuevo:
                od[tiempo_nuevo] = nuevo
            else:
                # No está en menú → es extra
                for k in extras_keys:
                    if k not in od:
                        od[k] = nuevo
                        break
            break  # solo la primera orden que tenga el original

    # Resolver colisiones: si una orden tiene dos platillos del mismo tiempo, separar
    ordenes_limpias = []
    for od in ordenes:
        campos_vistos = {}
        desbordamiento = {}
        for campo, platillo in od.items():
            if campo not in campos_vistos:
                campos_vistos[campo] = platillo
            else:
                # Colisión — el duplicado va a una nueva orden
                desbordamiento[campo] = platillo
        ordenes_limpias.append(campos_vistos)
        if desbordamiento:
            ordenes_limpias.append(desbordamiento)
    logging.getLogger(__name__).info("ORDENES_LIMPIAS_POST_COLISION | %s", ordenes_limpias)

    # Normalizar: órdenes con un solo platillo de menú → extra
    # Reutilizamos la lógica de normalizar_a_extra_si_unico adaptada a dicts planos
    ordenes_normalizadas = []
    for od in ordenes_limpias:
        campos_menu_presentes = [c for c in campos_menu_actuales if c in od]
        extras_presentes = [k for k in extras_keys if k in od]

        if len(campos_menu_presentes) == 1 and not extras_presentes:
            # Convertir a extra
            platillo = od[campos_menu_presentes[0]]
            od_nuevo = {}
            for k in extras_keys:
                if k not in od:
                    od_nuevo[k] = platillo
                    break
            ordenes_normalizadas.append(od_nuevo)
        else:
            ordenes_normalizadas.append(od)

    # Reconstruir orden_temporal con costos recalculados
    ordenes_finales = []
    for i, od in enumerate(ordenes_normalizadas):
        if not od:
            continue
        tool_input_recalculo = {
            k: v for k, v in od.items() if v and v not in empty_placeholders
        }
        costo = supabase_client.determinar_costo_comanda(
            tool_input_recalculo, config=config, campos_platillos=campos_platillos_validos
        )
        platillos_dict = {k: [v] if k in campos_menu_actuales else v for k, v in od.items()}
        orden_original = orden_temporal["ordenes"][i] if i < len(orden_temporal["ordenes"]) else {}
        nueva_orden = {
            "orden_numero": i + 1,
            "platillos": platillos_dict,
            "desechables": orden_original.get("desechables", False),
            "costos": costo
        }
        if orden_original.get("comanda_id"):
            nueva_orden["comanda_id"] = orden_original["comanda_id"]
        ordenes_finales.append(nueva_orden)

    monto_total = sum(o["costos"].get("monto_total", 0) for o in ordenes_finales)
    orden_temporal["ordenes"] = ordenes_finales
    orden_temporal["total_ordenes"] = len(ordenes_finales)
    orden_temporal["monto_total_general"] = monto_total

    content = {
        "status": "orden_modificada",
        "total_ordenes": len(ordenes_finales),
        "monto_total_acumulado": monto_total,
    }
    return orden_temporal, content

# FUNCION ORIGINAL DE REHIDRATAR LA ORDEN DESDE SUPABASE ANTES DE LA ADAPTACION DE DEJARLO EN GRUPOS
# def rehidratar_orden_desde_supabase_orig(pedido_data, config, supabase_client, campos_platillos_validos):
#     """
#     Convierte la comanda única de Supabase al formato de orden_temporal
#     que espera handle_pedido.

#     Nuevo paradigma: 1 comanda por pedido_grupo en Supabase.
#     Se reconstruye una sola orden sintética con todos los platillos del grupo.
#     La trazabilidad por persona no se recupera desde Supabase — vive solo en sesión.

#     Args:
#         pedido_data: dict retornado por obtener_pedido_reciente_usuario()
#                      {'pedido_grupo': str, 'comandas': [...], 'cliente_nombre': str}
#         config: dict de configuración de cocina
#         supabase_client: instancia de DBCA
#         campos_platillos_validos: list de tiempos del menú del día

#     Returns:
#         orden_temporal: dict con la estructura estándar (una sola orden sintética)
#     """
#     campos_menu_actuales = [c for c in campos_platillos_validos if c != 'a_la_carta']
#     extras_keys = ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']

#     pedido_grupo = pedido_data['pedido_grupo']

#     comandas_con_platillos = supabase_client.obtener_comandas_con_platillos(pedido_grupo)

#     if not comandas_con_platillos:
#         return {
#             'pedido_grupo': pedido_grupo,
#             'ordenes': [],
#             'total_ordenes': 0,
#             'monto_total_general': 0.0
#         }

#     # Nuevo paradigma: primera (y única) comanda del grupo
#     comanda = comandas_con_platillos[0]
#     comanda_id = comanda['comanda_id']
#     monto_total_general = float(comanda['monto_total'] or 0.0)

#     # Reconstruir platillos_dict desde el desglose plano
#     platillos_dict = {}
#     extras_usados = []

#     for platillo in comanda['platillos']:
#         campo = platillo.get('campo', '')
#         nombre = platillo.get('platillo', '')

#         tiempo_match = next(
#             (c for c in campos_menu_actuales
#              if supabase_client.unaccent_simple(c.lower().replace(' ', '_')) ==
#                 supabase_client.unaccent_simple(campo.lower())),
#             None
#         )

#         if tiempo_match:
#             if tiempo_match not in platillos_dict:
#                 platillos_dict[tiempo_match] = []
#             platillos_dict[tiempo_match].append(nombre)
#         else:
#             extras_usados.append(nombre)

#     for i, extra_nombre in enumerate(extras_usados):
#         if i < len(extras_keys):
#             platillos_dict[extras_keys[i]] = extra_nombre

#     # Costo: tomado directamente de Supabase, no recalculado
#     # (evita inconsistencias con múltiples platillos por tiempo de grupo)
#     costos = {
#         'monto_estandar':    monto_total_general,
#         'monto_extras':      0,
#         'monto_desechables': 0,
#         'monto_total':       monto_total_general
#     }

#     ordenes = [{
#         'orden_numero': 1,
#         'comanda_id':   comanda_id,   # preservar para UPDATE en Supabase
#         'platillos':    platillos_dict,
#         'desechables':  False,
#         'costos':       costos
#     }]

#     orden_temporal = {
#         'pedido_grupo':       pedido_grupo,
#         'ordenes':            ordenes,
#         'total_ordenes':      1,
#         'monto_total_general': monto_total_general
#     }

#     return orden_temporal


# NUEVA FUNCION PROPUESTA PARA QUE SE PUEDA MANTENER EL ORDEN DE PEDIDOS POR CADA COMIDA, PORQUE SUELTO NO SE VE BIEN EN LA EXPERIENCIA DE USUARIO
def rehidratar_orden_desde_supabase(pedido_data, config, supabase_client, campos_platillos_validos):
    """
    Convierte las comandas de Supabase al formato de orden_temporal
    que espera handle_pedido.

    Una orden por cada comanda real del grupo — preserva la separación
    por comida (1 comanda = 1 comida), y cada orden conserva su propio
    comanda_id para poder actualizar/eliminar esa comida específica
    durante una modificación.

    Args:
        pedido_data: dict retornado por obtener_pedido_reciente_usuario()
                     {'pedido_grupo': str, 'comandas': [...], 'cliente_nombre': str}
        config: dict de configuración de cocina
        supabase_client: instancia de DBCA
        campos_platillos_validos: list de tiempos del menú del día

    Returns:
        orden_temporal: dict con la estructura estándar (una orden por comanda)
    """
    campos_menu_actuales = [c for c in campos_platillos_validos if c != 'a_la_carta']
    extras_keys = ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']

    pedido_grupo = pedido_data['pedido_grupo']

    comandas_con_platillos = supabase_client.obtener_comandas_con_platillos(pedido_grupo)

    if not comandas_con_platillos:
        return {
            'pedido_grupo': pedido_grupo,
            'ordenes': [],
            'total_ordenes': 0,
            'monto_total_general': 0.0
        }

    # Una orden por cada comanda real del grupo
    ordenes = []
    monto_total_general = 0.0

    for comanda in comandas_con_platillos:
        comanda_id = comanda['comanda_id']
        monto_comanda = float(comanda['monto_total'] or 0.0)
        monto_total_general += monto_comanda

        platillos_dict = {}
        extras_usados = []

        for platillo in comanda['platillos']:
            campo = platillo.get('campo', '')
            nombre = platillo.get('platillo', '')

            tiempo_match = next(
                (c for c in campos_menu_actuales
                 if supabase_client.unaccent_simple(c.lower().replace(' ', '_')) ==
                    supabase_client.unaccent_simple(campo.lower())),
                None
            )

            if tiempo_match:
                if tiempo_match not in platillos_dict:
                    platillos_dict[tiempo_match] = []
                platillos_dict[tiempo_match].append(nombre)
            else:
                extras_usados.append(nombre)

        for i, extra_nombre in enumerate(extras_usados):
            if i < len(extras_keys):
                platillos_dict[extras_keys[i]] = extra_nombre

        # Costo: tomado directamente de Supabase, no recalculado
        costos = {
            'monto_estandar':    monto_comanda,
            'monto_extras':      0,
            'monto_desechables': 0,
            'monto_total':       monto_comanda
        }

        ordenes.append({
            'orden_numero': comanda['numero'],
            'comanda_id':   comanda_id,   # preservar para UPDATE/eliminación en Supabase
            'platillos':    platillos_dict,
            'desechables':  False,
            'costos':       costos
        })

    orden_temporal = {
        'pedido_grupo':       pedido_grupo,
        'ordenes':            ordenes,
        'total_ordenes':      len(ordenes),
        'monto_total_general': monto_total_general
    }

    return orden_temporal

# FUNCIONES NUEVAS PARA ARREGLAR EL TEMA DE QUE SI QUEDA UN TIEMPO VACIO LO META COMO EXTRA SIN ROMPER LA LOGICA EXISTENTE 
def detectar_extra_que_es_platillo_faltante(tool_input, orden_redis, menu_data, campos_menu_actuales, supabase_client):
    """
    Revisa extra_1/2/3 del tool_input recién extraído. Si algún valor coincide
    con el nombre de un platillo real del menú Y existe una orden que tiene ese
    tiempo vacío, lo separa del tool_input y lo regresa como asignación directa
    (orden_numero, tiempo, platillo) en vez de dejarlo como extra genuino.
    """
    if not orden_redis or not orden_redis.get("ordenes"):
        return tool_input, []

    platillo_a_tiempo = {}
    for tiempo, platillos in menu_data.get('menu', {}).items():
        if tiempo in campos_menu_actuales:
            for p in platillos:
                platillo_a_tiempo[supabase_client.unaccent_simple(p['platillo'].lower())] = tiempo

    asignaciones = []
    extras_keys = ['extra_1', 'extra_2', 'extra_3']

    for key in extras_keys:
        val = tool_input.get(key)
        if val in empty_placeholders:
            continue
        valores = val if isinstance(val, list) else [val]
        valores_restantes = []

        for v in valores:
            if not v or v in empty_placeholders:
                valores_restantes.append(v)
                continue
            tiempo_match = platillo_a_tiempo.get(supabase_client.unaccent_simple(v.lower()))
            if not tiempo_match:
                valores_restantes.append(v)
                continue

            orden_destino = next(
                (o for o in sorted(orden_redis["ordenes"], key=lambda o: o.get("orden_numero", 0))
                 if o["platillos"].get(tiempo_match) in empty_placeholders
                 or o["platillos"].get(tiempo_match) in [[], ['']]),
                None
            )

            if orden_destino:
                asignaciones.append((orden_destino["orden_numero"], tiempo_match, v))
            else:
                valores_restantes.append(v)

        valores_restantes = [v for v in valores_restantes if v]
        if valores_restantes:
            tool_input[key] = valores_restantes if isinstance(val, list) else valores_restantes[0]
        else:
            tool_input[key] = None

    return tool_input, asignaciones

def agregar_platillo_a_orden_existente(orden_temporal, orden_numero, campo_tiempo, platillo, config, supabase_client, campos_platillos_validos):
    orden = next((o for o in orden_temporal["ordenes"] if o.get("orden_numero") == orden_numero), None)
    if not orden:
        return orden_temporal, None

    valor_actual = orden["platillos"].get(campo_tiempo)
    if isinstance(valor_actual, list):
        nuevos_valores = valor_actual + [platillo]
    elif valor_actual and valor_actual not in empty_placeholders:
        nuevos_valores = [valor_actual, platillo]
    else:
        nuevos_valores = [platillo]
    orden["platillos"][campo_tiempo] = nuevos_valores

    tool_input_recalculo = {}
    for campo, vals in orden["platillos"].items():
        if isinstance(vals, list) and vals:
            tool_input_recalculo[campo] = vals if len(vals) > 1 else vals[0]
        elif vals and vals not in empty_placeholders:
            tool_input_recalculo[campo] = vals

    costo_nuevo = supabase_client.determinar_costo_comanda(tool_input_recalculo, config=config, campos_platillos=campos_platillos_validos)
    monto_anterior = orden.get("costos", {}).get("monto_total", 0)
    orden["costos"] = costo_nuevo
    orden_temporal["monto_total_general"] = orden_temporal["monto_total_general"] - monto_anterior + costo_nuevo.get("monto_total", 0)

    content = {
        "status": "platillo_agregado_a_comida_existente",
        "orden_numero": orden_numero,
        "tiempo": campo_tiempo,
        "platillo": platillo,
        "costo_orden_actualizado": costo_nuevo.get("monto_total", 0),
        "monto_total_acumulado": orden_temporal["monto_total_general"],
    }
    return orden_temporal, content