
ENABLE_GATHER_INFO = False

# Mapa de referencia de transiciones
# Los handlers lo consultan pero la decisión final es de ellos
TRANSICIONES = {
    "new": "gral",
    "gral": "gather_info",  
    "gather_info": "follow_up",
    "follow_up": "follow_up"
    # "executive": "executive"
}