"""
Mapeo de ubicaciones para Propifai.
Generado automáticamente por crear_mapeo_ubicaciones.py
NO MODIFICAR MANUALMENTE - Regenerar con el script si cambian los datos.
"""

# Mapeo de departamentos (ID -> Nombre)
DEPARTAMENTOS = {
    "1": "Amazonas",
    "2": "Ancash",
    "3": "Apurimac",
    "4": "Arequipa",
    "5": "Ayacucho",
    "6": "Cajamarca",
    "7": "Cuzco",
    "8": "Huancavelica",
    "9": "Huanuco",
    "10": "Ica",
    "11": "Junin",
    "12": "La Libertad",
    "13": "Lambayeque",
    "14": "Lima",
    "15": "Loreto",
    "16": "Madre de Dios",
    "17": "Moquegua",
    "18": "Pasco",
    "19": "Piura",
    "20": "Puno",
    "21": "San Martin",
    "22": "Tacna",
    "23": "Tumbes",
    "24": "Ucayali",
    "25": "Callao",
}

# Mapeo de provincias (ID -> Nombre)
PROVINCIAS = {
    "1": "Arequipa",
    "2": "Camana",
    "3": "Caraveli",
    "4": "Castilla",
    "5": "Caylloma",
    "6": "Condesuyos",
    "7": "Islay",
    "8": "La Union",
}

# Mapeo de distritos (ID -> Nombre)
DISTRITOS = {
    "1": "Arequipa",
    "2": "Alto Selva Alegre",
    "3": "Cayma",
    "4": "Cerro Colorado",
    "5": "Characato",
    "6": "Chiguata",
    "7": "Jacobo Hunter",
    "8": "Jose Luis Bustamante y Rivero",
    "9": "La Joya",
    "10": "Mariano Melgar",
    "11": "Miraflores",
    "12": "Mollebaya",
    "13": "Paucarpata",
    "14": "Pocsi",
    "15": "Polobaya",
    "16": "Quequeña",
    "17": "Sabandia",
    "18": "Sachaca",
    "19": "San Juan de Siguas",
    "20": "San Juan de Tarucani",
    "21": "Santa Isabel de Siguas",
    "22": "Santa Rita de Siguas",
    "23": "Socabaya",
    "24": "Tiabaya",
    "25": "Uchumayo",
    "26": "Vitor",
    "27": "Yanahuara",
    "28": "Yarabamba",
    "29": "Yura",
    "30": "Camana",
    "31": "Jose Maria Quimper",
    "32": "Mariano Nicolas Quimper",
    "33": "Mariscal Caceres",
    "34": "Nicolas de Perierola",
    "35": "Ocoña",
    "36": "Quilca",
    "37": "Samuel Pastor",
    "38": "Umacollo",
}

def obtener_nombre_departamento(id_departamento):
    """Devuelve el nombre del departamento dado su ID."""
    return DEPARTAMENTOS.get(str(id_departamento), str(id_departamento))

def obtener_nombre_provincia(id_provincia):
    """Devuelve el nombre de la provincia dado su ID."""
    return PROVINCIAS.get(str(id_provincia), str(id_provincia))

def obtener_nombre_distrito(id_distrito):
    """Devuelve el nombre del distrito dado su ID."""
    return DISTRITOS.get(str(id_distrito), str(id_distrito))

def obtener_ubicacion_completa(departamento_id, provincia_id, distrito_id):
    """Devuelve una tupla con los nombres completos de la ubicación."""
    return (
        obtener_nombre_departamento(departamento_id),
        obtener_nombre_provincia(provincia_id),
        obtener_nombre_distrito(distrito_id)
    )

def formatear_ubicacion(departamento_id, provincia_id, distrito_id, separador=", "):
    """Devuelve una cadena formateada con la ubicación completa."""
    depto = obtener_nombre_departamento(departamento_id)
    prov = obtener_nombre_provincia(provincia_id)
    dist = obtener_nombre_distrito(distrito_id)
    
    partes = []
    if dist and dist != str(distrito_id):
        partes.append(dist)
    if prov and prov != str(provincia_id):
        partes.append(prov)
    if depto and depto != str(departamento_id):
        partes.append(depto)
    
    return separador.join(partes) if partes else f"Distrito {distrito_id}, Provincia {provincia_id}, Departamento {departamento_id}"
