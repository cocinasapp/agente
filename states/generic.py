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
        nombre_usuario = f"El usuario se llama {nombre}." if nombre else ""
        write_log(telefono, "USERNAME", f"NOMBRE Extraído: {nombre}")
        if nombre:
            session_context["nombre_usuario"] = nombre_usuario
        else:
            session_context["nombre_usuario"] = ""

def construir_orden_temporal(orden_temporal):
    if not orden_temporal:
        return {
            "pedido_grupo": str(uuid.uuid4()),
            "ordenes": [],
            "total_ordenes": 0,
            "monto_total_general": 0,
            "nombre_cliente": None
        }
    return orden_temporal

def agregar_extra_a_orden(orden_temporal, tool_input, config, supabase_client, campos_platillos_validos):
    ultima_orden = orden_temporal["ordenes"][-1]

    for key in ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']:
        if key in tool_input and tool_input[key] not in ['', '<UNKNOWN>', None]:
            ultima_orden["platillos"][key] = [tool_input[key]]

    tool_input_recalculo = {}
    for tiempo_key, platillos_tiempo in ultima_orden["platillos"].items():
        if platillos_tiempo:
            tool_input_recalculo[tiempo_key] = platillos_tiempo[0] if len(platillos_tiempo) == 1 else platillos_tiempo

    costo_anterior = ultima_orden["costos"].get("monto_total", 0)
    costo_nuevo = supabase_client.determinar_costo_comanda(tool_input_recalculo, config=config, campos_platillos=campos_platillos_validos)
    orden_temporal["monto_total_general"] -= costo_anterior
    ultima_orden["costos"] = costo_nuevo
    orden_temporal["monto_total_general"] += costo_nuevo.get("monto_total", 0)
    orden_temporal["ordenes"][-1] = ultima_orden

    content = {
        "status": "extra_agregado_a_orden_existente",
        "orden_numero": ultima_orden["orden_numero"],
        "costo_orden_actualizado": costo_nuevo.get("monto_total", 0),
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
    orden_temporal["nombre_cliente"] = nombre_completo
    campos_menu_keys = [c for c in campos_platillos_validos if c != 'a_la_carta']

    # Si la orden viene de agregar_platillo sobre un pedido ya confirmado,
    # inyectar comanda_ids originales por índice antes del loop.
    comanda_ids_originales = orden_temporal.pop("_comanda_ids_originales", [])
    for i, comanda_id_original in enumerate(comanda_ids_originales):
        if i < len(orden_temporal["ordenes"]) and comanda_id_original:
            orden_temporal["ordenes"][i]["comanda_id"] = comanda_id_original

    comandas_ids = []
    for orden in orden_temporal["ordenes"]:
        es_extra_comanda = not any(
            campo in orden["platillos"] and orden["platillos"][campo]
            for campo in campos_menu_keys
        )

        todos_platillos = []
        for platillos_tiempo in orden['platillos'].values():
            if platillos_tiempo and platillos_tiempo not in ['', '<UNKNOWN>']:
                if isinstance(platillos_tiempo, list):
                    todos_platillos.extend(platillos_tiempo)
                else:
                    todos_platillos.append(platillos_tiempo)

        comanda_id = orden.get('comanda_id')

        if comanda_id:
            # UPDATE: comanda ya existe en Supabase (viene de rehidratar_orden_desde_supabase)
            ids_platillos = supabase_client.extraer_ids_platillos(todos_platillos, user_id=os.getenv('USER_ID'))
            nuevos_platillos_ids = [obj.get('id') for obj in ids_platillos]
            resultado = supabase_client.actualizar_platillos_comanda(
                comanda_id=comanda_id,
                nuevos_platillos_ids=nuevos_platillos_ids,
                nuevos_costos=orden['costos']
            )
            if not resultado.get('success'):
                logger.error(
                    "persistir_pedido: fallo al actualizar comanda | telefono: %s | orden_numero: %s | comanda_id: %s",
                    telefono, orden["orden_numero"], comanda_id
                )
                continue
            supabase_client.update_data(
                table=os.getenv('TLB_COMANDAS'),
                data={'cliente_nombre': nombre_completo},
                filters={'id': comanda_id}
            )
        else:
            # INSERT: comanda nueva
            _info = info_entrega or {}
            _metodo = _info.get('metodo_de_entrega') or 'local'
            _tipo_entrega = 'domicilio' if 'domicilio' in _metodo.lower() else 'local'
            _domicilio = _info.get('domicilio') or ''
            _referencia = _info.get('referencia') or ''
            _direccion = ', '.join(filter(None, [_domicilio, _referencia]))
            comanda = {
                'user_id': os.getenv('USER_ID'),
                'cliente_nombre': nombre_completo,
                'pedido_grupo': pedido_grupo,
                'monto_estandar': orden['costos'].get('monto_estandar', 0),
                'monto_extras': orden['costos'].get('monto_extras', 0),
                'monto_desechables': orden['costos'].get('monto_desechables', 0),
                'monto_total': orden['costos'].get('monto_total', 0),
                'telefono_cliente': telefono,
                'es_extra': es_extra_comanda,
                'tipo_entrega': _tipo_entrega,
                'direccion': _direccion,
            }
            comanda_id = supabase_client.insert_data(comanda, os.getenv('TLB_COMANDAS'), return_id=True)
            if not comanda_id:
                logger.error(
                    "persistir_pedido: fallo al insertar comanda | telefono: %s | orden_numero: %s | comanda: %s",
                    telefono, orden["orden_numero"], comanda
                )
                continue

            if todos_platillos:
                ids_platillos = supabase_client.extraer_ids_platillos(todos_platillos, user_id=os.getenv('USER_ID'))
                for id_platillo_obj in ids_platillos:
                    supabase_client.insert_data(
                        {'comanda_id': comanda_id, 'platillo_id': id_platillo_obj.get('id')},
                        os.getenv('TLB_DESGLOSE')
                    )

        comandas_ids.append(comanda_id)

    estado_entrega = {
        "comandas_ids": comandas_ids,
        "pedido_grupo": pedido_grupo,
        "nombre_cliente": nombre_completo,
        "monto_total": orden_temporal["monto_total_general"],
        "total_ordenes": orden_temporal["total_ordenes"]
    }

    content = {
        "status": "pedido_guardado_esperando_entrega",
        "nombre_cliente": nombre_completo,
        "pedido_grupo": pedido_grupo,
        "total_ordenes": orden_temporal["total_ordenes"],
        "monto_total": orden_temporal["monto_total_general"],
        "comandas_ids": comandas_ids,
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

CAMPOS_ENTREGA_REQUERIDOS = ['nombre_completo', 'metodo_de_entrega']

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

def tiene_contenido_0(ti, campos_platillos_validos):
    tiene_platillos = any(str(ti.get(c, '')).strip() not in empty_placeholders for c in campos_platillos_validos)
    tiene_extras = any(ti.get(k) not in empty_placeholders for k in ['extra_1', 'extra_2', 'extra_3', 'a_la_carta'])
    return tiene_platillos or tiene_extras

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
    
    {'Plato fuerte': ['Tacos dorados', 'Enchiladas verdes'], ...}
    →
    [{'Plato fuerte': 'Tacos dorados', ...}, {'Plato fuerte': 'Enchiladas verdes', ...}]
    """
    # Determinar cuántas órdenes hay (longitud máxima de las listas)
    max_ordenes = max(
        (len(v) for c in campos_menu_actuales if isinstance(v := tool_input.get(c), list)),
        default=1
    )

    extras = {k: tool_input.get(k) for k in ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']}

    lista = []
    for i in range(max_ordenes):
        entry = {}
        for campo in campos_menu_actuales:
            val = tool_input.get(campo)
            if isinstance(val, list):
                entry[campo] = val[i] if i < len(val) else None
            else:
                entry[campo] = val  # None o string directo
        entry.update(extras)
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
            ordenes_nuevas.append({
                "orden_numero": len(ordenes_nuevas) + 1,
                "platillos": platillos_nuevos,
                "desechables": orden.get("desechables", False),
                "costos": costo
            })

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

def rehidratar_orden_desde_supabase(pedido_data, config, supabase_client, campos_platillos_validos):
    """
    Convierte las comandas de Supabase al formato de orden_temporal
    que espera handle_pedido.

    Args:
        pedido_data: dict retornado por obtener_pedido_reciente_usuario()
                     {'pedido_grupo': str, 'comandas': [...], 'cliente_nombre': str}
        config: dict de configuración de cocina
        supabase_client: instancia de DBCA
        campos_platillos_validos: list de tiempos del menú del día

    Returns:
        orden_temporal: dict con la estructura estándar
    """
    campos_menu_actuales = [c for c in campos_platillos_validos if c != 'a_la_carta']
    extras_keys = ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']

    pedido_grupo = pedido_data['pedido_grupo']
    cliente_nombre = pedido_data.get('cliente_nombre')

    # obtener_comandas_con_platillos trae platillos con su campo (tiempo en snake_case)
    comandas_con_platillos = supabase_client.obtener_comandas_con_platillos(pedido_grupo)

    ordenes = []
    monto_total_general = 0.0

    for comanda in comandas_con_platillos:
        platillos_dict = {}
        extras_usados = []

        for platillo in comanda['platillos']:
            campo = platillo.get('campo', '')      # ej. "sopa_o_consome", "plato_fuerte"
            nombre = platillo.get('platillo', '')

            # Buscar si el campo coincide con algún tiempo válido
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
                # Platillo fuera de tiempos del menú → extra
                extras_usados.append(nombre)

        # Asignar extras
        for i, extra_nombre in enumerate(extras_usados):
            if i < len(extras_keys):
                platillos_dict[extras_keys[i]] = extra_nombre

        # Recalcular costo desde los platillos rehidratados
        tool_input_recalculo = {}
        for campo, valores in platillos_dict.items():
            if isinstance(valores, list):
                tool_input_recalculo[campo] = valores[0] if len(valores) == 1 else valores
            else:
                tool_input_recalculo[campo] = valores

        costo = supabase_client.determinar_costo_comanda(
            tool_input_recalculo, config=config, campos_platillos=campos_platillos_validos
        )

        monto_total_general += costo.get('monto_total', 0.0)

        ordenes.append({
            'orden_numero': comanda['numero'],
            'comanda_id': comanda['comanda_id'],   # preservar para edición en Supabase
            'platillos': platillos_dict,
            'desechables': False,
            'costos': costo
        })

    orden_temporal = {
        'pedido_grupo': pedido_grupo,
        'ordenes': ordenes,
        'total_ordenes': len(ordenes),
        'monto_total_general': monto_total_general,
        'nombre_cliente': cliente_nombre
    }

    return orden_temporal