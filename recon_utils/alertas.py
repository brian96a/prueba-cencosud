"""Avisa que algo falló: busca el responsable en alertas.yml, envía por log y por correo (SNS) y deja registro."""
import os
from datetime import datetime

import yaml

from recon_utils.config import ARCHIVO_ALERTAS, CARPETA_PROYECTO
from recon_utils.traza import abrir_traza

ARCHIVO_CONFIG_ALERTAS = CARPETA_PROYECTO / "recon_utils" / "alertas.yml"


def buscar_destino(tabla):
    with open(ARCHIVO_CONFIG_ALERTAS) as archivo:
        config = yaml.safe_load(archivo)
    return config["canales"], config["destinos"].get(tabla, config["destinos"]["por_defecto"])


def enviar_a_log(mensaje):
    with open(ARCHIVO_ALERTAS, "a") as archivo:
        archivo.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  ALERTA  {mensaje}\n")
    return "ENVIADO"


def enviar_a_sns(mensaje, destino, variable):
    topic = os.environ.get(variable)
    if not topic:
        return "SIMULADO"  # sin topic configurado
    import boto3
    boto3.client("sns").publish(TopicArn=topic, Subject=f"Cuadratura FAILED - {destino['responsable']}", Message=mensaje)
    return "ENVIADO"


def enviar_alerta(mensaje, tabla=None, run_id=None):
    canales, destino = buscar_destino(tabla)
    print(f"ALERTA para {destino['responsable']}: {mensaje}")

    conexion = abrir_traza()
    for canal in destino["canales"]:
        try:
            if canal == "log":
                estado = enviar_a_log(mensaje)
            elif canal == "sns":
                estado = enviar_a_sns(mensaje, destino, canales["sns"]["variable"])
        except Exception as error:  # una alerta que no se pudo enviar no debe tapar la falla original
            estado = f"ERROR: {error}"
        conexion.execute("insert into audit.alertas values (?, ?, ?, ?, ?, ?, ?)",
                         [run_id, tabla, destino["responsable"], canal, estado, mensaje, datetime.now()])
        print(f"  canal {canal}: {estado}")
    conexion.close()
