"""
================================================================================
  SISTEMA INTEGRAL DE GESTIÓN DE CLIENTES, SERVICIOS Y RESERVAS
================================================================================

Implementacion del programaga SOFWARE JF:
- Abstracción, Herencia, Polimorfismo y Encapsulación.
- Manejo robusto de excepciones (personalizadas, try/except/else, try/except/finally
  y encadenamiento de excepciones.
- Registro de errores y eventos en el sofware.
- Resistencia a fallos.
- Menú interactivo por consola.
================================================================================
"""


import os
import sys
import re
import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any




# CONFIGURACIÓN DE LOGS Y AUDITORÍA EN ARCHIVO


RUTA_BASE = Path(__file__).resolve().parent if "__file__" in locals() else Path.cwd()
RUTA_ARCHIVO_LOG = RUTA_BASE / "software_fj.log"


class FormatoConsolaLimpio(logging.Formatter):
   
    def format(self, record: logging.LogRecord) -> str:
        temp_exc = record.exc_info
        temp_text = getattr(record, "exc_text", None)
        record.exc_info = None
        record.exc_text = None
        salida = super().format(record)
        record.exc_info = temp_exc
        record.exc_text = temp_text
        return salida


 #Configuracion del logger en el sistema para eventos y errores en software_fj.log.
def inicializar_logger(nombre: str = "SoftwareFJ") -> logging.Logger:
    
    logger = logging.getLogger(nombre)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        formato_archivo = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | [%(filename)s:%(funcName)s:%(lineno)d] | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        formato_consola = FormatoConsolaLimpio(
            fmt="[%(levelname)s] %(message)s"
        )

        handler_archivo = logging.FileHandler(RUTA_ARCHIVO_LOG, encoding="utf-8")
        handler_archivo.setLevel(logging.INFO)
        handler_archivo.setFormatter(formato_archivo)

        handler_consola = logging.StreamHandler(sys.stdout)
        handler_consola.setLevel(logging.WARNING)
        handler_consola.setFormatter(formato_consola)

        logger.addHandler(handler_archivo)
        logger.addHandler(handler_consola)

    return logger


logger = inicializar_logger()



# JERARQUÍA DE EXCEPCIONES PERSONALIZADAS DE DOMINIO

class SoftwareFJException(Exception):
    """Excepción raíz del sistema Software FJ."""

    def __init__(self, mensaje: str, codigo_error: str = "ERR-GEN-001", detalles: Optional[Any] = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo_error = codigo_error
        self.detalles = detalles

    def __str__(self) -> str:
        res = f"[{self.codigo_error}] {self.mensaje}"
        if self.detalles:
            res += f" | Detalles: {self.detalles}"
        return res


# Base para fallos de validación en reglas de negocio.
class ValidacionError(SoftwareFJException):
    def __init__(self, mensaje: str, detalles: Optional[Any] = None) -> None:
        super().__init__(mensaje, codigo_error="ERR-VAL-001", detalles=detalles)


class DatoInvalidoError(ValidacionError):
    def __init__(self, campo: str, valor: Any, razon: str) -> None:
        mensaje = f"El campo '{campo}' contiene un valor inválido ({repr(valor)}): {razon}"
        super().__init__(mensaje=mensaje, detalles={"campo": campo, "valor": valor, "razon": razon})
        self.codigo_error = "ERR-DAT-002"
        self.campo = campo
        self.valor = valor


class ParametroFaltanteError(ValidacionError):
    def __init__(self, parametro: str) -> None:
        mensaje = f"Parámetro requerido ausente o nulo: '{parametro}'"
        super().__init__(mensaje=mensaje, detalles={"parametro_faltante": parametro})
        self.codigo_error = "ERR-PAR-003"
        self.parametro = parametro


class CapacidadExcedidaError(ValidacionError):
    def __init__(self, servicio_nombre: str, solicitado: int, maximo_permitido: int) -> None:
        mensaje = (
            f"Capacidad o inventario excedido en '{servicio_nombre}'. "
            f"Solicitado: {solicitado}, Disponible/Máximo: {maximo_permitido}"
        )
        super().__init__(mensaje=mensaje, detalles={"servicio": servicio_nombre, "solicitado": solicitado, "limite": maximo_permitido})
        self.codigo_error = "ERR-CAP-004"


class ServicioNoDisponibleError(SoftwareFJException):
    def __init__(self, codigo_servicio: str, razon: str = "Servicio inactivo o sin disponibilidad") -> None:
        mensaje = f"El servicio con código '{codigo_servicio}' no está disponible: {razon}"
        super().__init__(mensaje=mensaje, codigo_error="ERR-SRV-002", detalles={"codigo": codigo_servicio, "razon": razon})


class ReservaInvalidaError(SoftwareFJException):
    def __init__(self, mensaje: str, detalles: Optional[Any] = None) -> None:
        super().__init__(mensaje, codigo_error="ERR-RES-001", detalles=detalles)


class OperacionNoPermitidaError(SoftwareFJException):
    def __init__(self, accion: str, estado_actual: str, razon: str) -> None:
        mensaje = f"No se permite '{accion}' cuando el estado actual es '{estado_actual}'. Motivo: {razon}"
        super().__init__(mensaje=mensaje, codigo_error="ERR-OPE-001", detalles={"accion": accion, "estado": estado_actual, "razon": razon})


# Cuando un cálculo financiero arroja montos negativos, tasas inválidas o inconsistencias.
class CalculoInconsistenteError(SoftwareFJException):
    def __init__(self, mensaje: str, formula_o_valores: Optional[Any] = None) -> None:
        super().__init__(mensaje=mensaje, codigo_error="ERR-CALC-001", detalles={"inconsistencia": formula_o_valores})



# Al buscar una entidad inexistente en la memoria.
class EntidadNoEncontradaError(SoftwareFJException):
    def __init__(self, tipo_entidad: str, identificador: str) -> None:
        mensaje = f"No se encontró ninguna entidad de tipo '{tipo_entidad}' con identificador '{identificador}'"
        super().__init__(mensaje=mensaje, codigo_error="ERR-NOTFOUND-404", detalles={"tipo": tipo_entidad, "id": identificador})



# PRINCIPIO DE ABSTRACCIÓN


class EntidadBase(ABC):

    def __init__(self, id_entidad: Optional[str] = None, activo: bool = True) -> None:
        self._id: str = id_entidad if id_entidad else str(uuid.uuid4())[:8].upper()
        self._fecha_creacion: datetime = datetime.now()
        self._activo: bool = bool(activo)

    @property
    def id(self) -> str:
        return self._id

    @property
    def fecha_creacion(self) -> datetime:
        return self._fecha_creacion

    @property
    def activo(self) -> bool:
        return self._activo

    @activo.setter
    def activo(self, estado: bool) -> None:
        if not isinstance(estado, bool):
            raise TypeError("El atributo 'activo' debe ser de tipo booleano.")
        self._activo = estado

    def activar(self) -> None:
        self._activo = True

    def desactivar(self) -> None:
        self._activo = False

    @abstractmethod
    def validar(self) -> None:
        """Valida rigurosamente la coherencia de la entidad."""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serializa la entidad a un diccionario estándar."""
        pass

    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, EntidadBase):
            return False
        return self._id == otro._id and type(self) is type(otro)

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self._id))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id='{self._id}' activo={self._activo}>"



# PRINCIPIO DE ENCAPSULACIÓN: CLASE CLIENTE


class Cliente(EntidadBase):

    REGEX_EMAIL = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    REGEX_TELEFONO = re.compile(r"^\+?[0-9]{7,15}$")
    REGEX_IDENTIFICACION = re.compile(r"^[a-zA-Z0-9.\-_]{3,25}$")

    def __init__(
        self,
        identificacion: str,
        nombre: str,
        email: str,
        telefono: str,
        direccion: str,
        id_entidad: Optional[str] = None,
        activo: bool = True
    ) -> None:
        super().__init__(id_entidad=id_entidad, activo=activo)

        self.__identificacion: str = ""
        self.__nombre: str = ""
        self.__email: str = ""
        self.__telefono: str = ""
        self.__direccion: str = ""

        self.identificacion = identificacion
        self.nombre = nombre
        self.email = email
        self.telefono = telefono
        self.direccion = direccion

        self.validar()

    @property
    def identificacion(self) -> str:
        return self.__identificacion

    @identificacion.setter
    def identificacion(self, valor: str) -> None:
        if valor is None:
            raise ParametroFaltanteError("identificacion")
        if not isinstance(valor, str):
            raise DatoInvalidoError("identificacion", valor, "Debe ser una cadena de texto")
        limpio = valor.strip()
        if not self.REGEX_IDENTIFICACION.match(limpio):
            raise DatoInvalidoError("identificacion", valor, "Debe tener entre 3 y 25 caracteres alfanuméricos")
        self.__identificacion = limpio

    @property
    def nombre(self) -> str:
        return self.__nombre

    @nombre.setter
    def nombre(self, valor: str) -> None:
        if valor is None:
            raise ParametroFaltanteError("nombre")
        if not isinstance(valor, str):
            raise DatoInvalidoError("nombre", valor, "Debe ser una cadena de texto")
        limpio = valor.strip()
        if len(limpio) < 3:
            raise DatoInvalidoError("nombre", valor, "Debe tener al menos 3 caracteres")
        if any(char.isdigit() for char in limpio):
            raise DatoInvalidoError("nombre", valor, "No puede contener números")
        self.__nombre = limpio

    @property
    def email(self) -> str:
        return self.__email

    @email.setter
    def email(self, valor: str) -> None:
        if valor is None:
            raise ParametroFaltanteError("email")
        if not isinstance(valor, str):
            raise DatoInvalidoError("email", valor, "Debe ser una cadena de texto")
        limpio = valor.strip()
        if not self.REGEX_EMAIL.match(limpio):
            raise DatoInvalidoError("email", valor, "Formato de correo inválido (ej: usuario@dominio.com)")
        self.__email = limpio.lower()

    @property
    def telefono(self) -> str:
        return self.__telefono

    @telefono.setter
    def telefono(self, valor: str) -> None:
        if valor is None:
            raise ParametroFaltanteError("telefono")
        if not isinstance(valor, str):
            raise DatoInvalidoError("telefono", valor, "Debe ser una cadena de texto")
        limpio = valor.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "")
        if not self.REGEX_TELEFONO.match(limpio):
            raise DatoInvalidoError("telefono", valor, "Debe contener entre 7 y 15 dígitos numéricos (admite +)")
        self.__telefono = limpio

    @property
    def direccion(self) -> str:
        return self.__direccion

    @direccion.setter
    def direccion(self, valor: str) -> None:
        if valor is None:
            raise ParametroFaltanteError("direccion")
        if not isinstance(valor, str):
            raise DatoInvalidoError("direccion", valor, "Debe ser una cadena de texto")
        limpio = valor.strip()
        if len(limpio) < 3:
            raise DatoInvalidoError("direccion", valor, "Debe tener al menos 3 caracteres descriptivos")
        self.__direccion = limpio

    def validar(self) -> None:
        if not self.__identificacion:
            raise ParametroFaltanteError("identificacion")
        if not self.__nombre:
            raise ParametroFaltanteError("nombre")
        if not self.__email:
            raise ParametroFaltanteError("email")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "identificacion": self.__identificacion,
            "nombre": self.__nombre,
            "email": self.__email,
            "telefono": self.__telefono,
            "direccion": self.__direccion,
            "activo": self.activo
        }

    def __str__(self) -> str:
        return f"Cliente: {self.__nombre} (ID: {self.__identificacion}) | Email: {self.__email} | Tel: {self.__telefono}"



# POLIMORFISMO Y SERVICIOS ESPECIALIZADOS


class Servicio(EntidadBase):
    
    def __init__(
        self,
        codigo: str,
        nombre: str,
        descripcion_corta: str,
        precio_base: float,
        disponible: bool = True,
        id_entidad: Optional[str] = None
    ) -> None:
        super().__init__(id_entidad=id_entidad, activo=disponible)
        self._codigo: str = ""
        self._nombre: str = ""
        self._descripcion_corta: str = ""
        self._precio_base: float = 0.0

        self.codigo = codigo
        self.nombre = nombre
        self.descripcion_corta = descripcion_corta
        self.precio_base = precio_base

    @property
    def codigo(self) -> str:
        return self._codigo

    @codigo.setter
    def codigo(self, valor: str) -> None:
        if not valor or not isinstance(valor, str):
            raise DatoInvalidoError("codigo", valor, "Debe ser un código no vacío")
        self._codigo = valor.strip().upper()

    @property
    def nombre(self) -> str:
        return self._nombre

    @nombre.setter
    def nombre(self, valor: str) -> None:
        if not valor or not isinstance(valor, str) or len(valor.strip()) < 3:
            raise DatoInvalidoError("nombre", valor, "Debe ser descriptivo con más de 2 caracteres")
        self._nombre = valor.strip()

    @property
    def descripcion_corta(self) -> str:
        return self._descripcion_corta

    @descripcion_corta.setter
    def descripcion_corta(self, valor: str) -> None:
        if not valor or not isinstance(valor, str):
            raise DatoInvalidoError("descripcion_corta", valor, "Debe ser un texto descriptivo")
        self._descripcion_corta = valor.strip()

    @property
    def precio_base(self) -> float:
        return self._precio_base

    @precio_base.setter
    def precio_base(self, valor: float) -> None:
        try:
            val_float = float(valor)
        except (ValueError, TypeError) as err:
            raise DatoInvalidoError("precio_base", valor, "Debe ser un valor numérico") from err

        if val_float < 0:
            raise CalculoInconsistenteError(f"El precio base no puede ser negativo: {val_float}")
        self._precio_base = val_float

    @property
    def disponible(self) -> bool:
        return self.activo

    @disponible.setter
    def disponible(self, valor: bool) -> None:
        self.activo = valor

    @abstractmethod
    def describir_servicio(self) -> str:
        pass

    @abstractmethod
    def calcular_costo(self, duracion: float, **kwargs) -> float:
        pass

    @abstractmethod
    def validar_parametros(self, **kwargs) -> None:
        pass

    def calcular_costo_completo(
        self,
        duracion: float,
        descuento: float = 0.0,
        impuesto: float = 0.19,
        cupon: Optional[str] = None,
        **kwargs
    ) -> Dict[str, float]:
       
        if not self.disponible:
            raise ServicioNoDisponibleError(self.codigo, "El servicio está inactivo o fuera de catálogo")

        try:
            duracion_num = float(duracion)
        except (ValueError, TypeError) as err:
            raise DatoInvalidoError("duracion", duracion, "La duración debe ser un número") from err

        if duracion_num <= 0:
            raise CalculoInconsistenteError(f"La duración debe ser estrictamente positiva: {duracion}")

        self.validar_parametros(**kwargs)

        try:
            costo_bruto = self.calcular_costo(duracion_num, **kwargs)

            if not (0.0 <= descuento <= 1.0):
                raise CalculoInconsistenteError(f"El descuento debe estar entre 0.0 y 1.0. Recibido: {descuento}")
            if impuesto < 0.0:
                raise CalculoInconsistenteError(f"El impuesto no puede ser negativo: {impuesto}")

            # Cupones promocionales corporativos
            descuento_cupon = 0.0
            if cupon:
                c_norm = cupon.strip().upper()
                if c_norm == "FJ_BIENVENIDO":
                    descuento_cupon = 0.05
                elif c_norm == "FJ_VIP":
                    descuento_cupon = 0.15
                elif c_norm == "FJ_CORPORATIVO":
                    descuento_cupon = 0.20
                else:
                    raise DatoInvalidoError("cupon", cupon, "Cupón promocional desconocido o expirado")

            descuento_total = min(1.0, descuento + descuento_cupon)
            monto_descuento = round(costo_bruto * descuento_total, 2)
            subtotal = round(costo_bruto - monto_descuento, 2)
            monto_impuesto = round(subtotal * impuesto, 2)
            total = round(subtotal + monto_impuesto, 2)

            if total < 0:
                raise CalculoInconsistenteError(f"Total resultante inconsistente o negativo: {total}")

        except SoftwareFJException:
            raise
        except Exception as ex_inesperada:
            raise CalculoInconsistenteError(
                f"Fallo aritmético en cálculo de costos de '{self.codigo}'"
            ) from ex_inesperada

        return {
            "precio_base_unitario": self._precio_base,
            "costo_bruto": round(costo_bruto, 2),
            "tasa_descuento": descuento_total,
            "monto_descuento": monto_descuento,
            "subtotal": subtotal,
            "tasa_impuesto": impuesto,
            "monto_impuesto": monto_impuesto,
            "total": total
        }

    def validar(self) -> None:
        if not self._codigo or not self._nombre:
            raise ParametroFaltanteError("codigo y nombre del servicio")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "codigo": self._codigo,
            "nombre": self._nombre,
            "precio_base": self._precio_base,
            "disponible": self.disponible,
            "tipo": self.__class__.__name__
        }


# Primera sub clases: Reserva de Salas de Reuniones
class SalaReunionesServicio(Servicio):

    def __init__(
        self,
        codigo: str,
        nombre: str,
        descripcion_corta: str,
        precio_por_hora: float,
        capacidad_maxima: int,
        tiene_proyector: bool = True,
        tiene_videoconferencia: bool = True,
        costo_catering_por_persona: float = 60000.0,
        costo_soporte_tecnico: float = 100000.0,
        piso: int = 1,
        disponible: bool = True
    ) -> None:
        super().__init__(codigo, nombre, descripcion_corta, precio_por_hora, disponible)
        if not isinstance(capacidad_maxima, int) or capacidad_maxima <= 0:
            raise DatoInvalidoError("capacidad_maxima", capacidad_maxima, "Debe ser un entero mayor a cero")
        self._capacidad_maxima = capacidad_maxima
        self._tiene_proyector = bool(tiene_proyector)
        self._tiene_videoconferencia = bool(tiene_videoconferencia)
        self._costo_catering_por_persona = float(costo_catering_por_persona)
        self._costo_soporte_tecnico = float(costo_soporte_tecnico)
        self._piso = int(piso)

    @property
    def capacidad_maxima(self) -> int:
        return self._capacidad_maxima

    def describir_servicio(self) -> str:
        p = "Sí" if self._tiene_proyector else "No"
        v = "Sí" if self._tiene_videoconferencia else "No"
        return (
            f"[Sala de Reuniones] {self.nombre} (Cód: {self.codigo})\n"
            f"  - Capacidad: hasta {self._capacidad_maxima} personas | Piso: {self._piso}\n"
            f"  - Proyector HD: {p} | Videoconferencia: {v}\n"
            f"  - Tarifa: ${self.precio_base:,.2f} COP/hora | Catering: ${self._costo_catering_por_persona:,.2f} COP/persona\n"
            f"  - Soporte técnico en sitio: ${self._costo_soporte_tecnico:,.2f} COP"
        )

    def validar_parametros(self, **kwargs) -> None:
        asistentes = kwargs.get("numero_asistentes", 1)
        if not isinstance(asistentes, int) or asistentes <= 0:
            raise DatoInvalidoError("numero_asistentes", asistentes, "Debe ser un entero mayor a 0")
        if asistentes > self._capacidad_maxima:
            raise CapacidadExcedidaError(self.nombre, asistentes, self._capacidad_maxima)

    def calcular_costo(self, duracion: float, **kwargs) -> float:
        self.validar_parametros(**kwargs)
        costo = self.precio_base * duracion
        if kwargs.get("solicita_catering", False):
            asistentes = kwargs.get("numero_asistentes", 1)
            costo += asistentes * self._costo_catering_por_persona
        if kwargs.get("requiere_soporte_tecnico", False):
            costo += self._costo_soporte_tecnico
        return costo


# Segunda sub Clase: Alquiler de Equipamiento Tecnológico
class AlquilerEquipoServicio(Servicio):

    def __init__(
        self,
        codigo: str,
        nombre: str,
        descripcion_corta: str,
        precio_por_dia: float,
        tipo_equipo: str,
        stock_disponible: int,
        deposito_garantia: float = 350000.0,
        seguro_diario: float = 50000.0,
        disponible: bool = True
    ) -> None:
        super().__init__(codigo, nombre, descripcion_corta, precio_por_dia, disponible)
        if not tipo_equipo:
            raise DatoInvalidoError("tipo_equipo", tipo_equipo, "Debe indicar el tipo de equipo")
        if not isinstance(stock_disponible, int) or stock_disponible < 0:
            raise DatoInvalidoError("stock_disponible", stock_disponible, "El stock no puede ser negativo")
        self._tipo_equipo = tipo_equipo
        self._stock_disponible = stock_disponible
        self._deposito_garantia = float(deposito_garantia)
        self._seguro_diario = float(seguro_diario)

    @property
    def stock_disponible(self) -> int:
        return self._stock_disponible

    def actualizar_stock(self, delta: int) -> None:
        nuevo = self._stock_disponible + delta
        if nuevo < 0:
            raise CapacidadExcedidaError(self.nombre, abs(delta), self._stock_disponible)
        self._stock_disponible = nuevo

    def describir_servicio(self) -> str:
        return (
            f"[Alquiler de Equipos] {self.nombre} (Cód: {self.codigo})\n"
            f"  - Categoría: {self._tipo_equipo} | Stock disponible: {self._stock_disponible} unidades\n"
            f"  - Tarifa: ${self.precio_base:,.2f} COP/día | Seguro opcional: ${self._seguro_diario:,.2f} COP/día por unidad\n"
            f"  - Depósito de garantía: ${self._deposito_garantia:,.2f} COP por unidad"
        )

    def validar_parametros(self, **kwargs) -> None:
        cant = kwargs.get("cantidad_equipos", 1)
        if not isinstance(cant, int) or cant <= 0:
            raise DatoInvalidoError("cantidad_equipos", cant, "La cantidad debe ser entero positivo")
        if cant > self._stock_disponible:
            raise CapacidadExcedidaError(self.nombre, cant, self._stock_disponible)

    def calcular_costo(self, duracion: float, **kwargs) -> float:
        self.validar_parametros(**kwargs)
        cant = kwargs.get("cantidad_equipos", 1)
        costo_alquiler = self.precio_base * duracion * cant
        costo_seguro = (self._seguro_diario * duracion * cant) if kwargs.get("incluye_seguro", True) else 0.0
        return costo_alquiler + costo_seguro


# Tercera sub Clase: Asesorías Especializadas
class AsesoriaEspecializadaServicio(Servicio):

    FACTORES_NIVEL = {"JUNIOR": 1.0, "SENIOR": 1.5, "LEAD": 2.2, "PRINCIPAL": 2.2}
    MODALIDADES = {"REMOTA", "PRESENCIAL"}

    def __init__(
        self,
        codigo: str,
        nombre: str,
        descripcion_corta: str,
        precio_por_hora: float,
        area_experticia: str,
        nivel_consultor: str = "SENIOR",
        modalidad_default: str = "REMOTA",
        recargo_presencial: float = 70000.0,
        disponible: bool = True
    ) -> None:
        super().__init__(codigo, nombre, descripcion_corta, precio_por_hora, disponible)
        nivel = nivel_consultor.strip().upper()
        if nivel not in self.FACTORES_NIVEL:
            raise DatoInvalidoError("nivel_consultor", nivel_consultor, f"Permitidos: {list(self.FACTORES_NIVEL.keys())}")
        modalidad = modalidad_default.strip().upper()
        if modalidad not in self.MODALIDADES:
            raise DatoInvalidoError("modalidad_default", modalidad_default, f"Permitidas: {list(self.MODALIDADES)}")
        self._area_experticia = area_experticia.strip()
        self._nivel_consultor = nivel
        self._modalidad_default = modalidad
        self._recargo_presencial = float(recargo_presencial)

    def describir_servicio(self) -> str:
        factor = self.FACTORES_NIVEL[self._nivel_consultor]
        return (
            f"[Asesoría Especializada] {self.nombre} (Cód: {self.codigo})\n"
            f"  - Área: {self._area_experticia} | Consultor Rango: {self._nivel_consultor} ({factor}x)\n"
            f"  - Modalidad base: {self._modalidad_default}\n"
            f"  - Tarifa base: ${self.precio_base:,.2f} COP/h | Tarifa efectiva: ${self.precio_base * factor:,.2f} COP/h\n"
            f"  - Recargo por sesión presencial: +${self._recargo_presencial:,.2f} COP"
        )

    def validar_parametros(self, **kwargs) -> None:
        mod = kwargs.get("modalidad", self._modalidad_default).strip().upper()
        if mod not in self.MODALIDADES:
            raise DatoInvalidoError("modalidad", mod, f"Modalidades válidas: {list(self.MODALIDADES)}")

    def calcular_costo(self, duracion: float, **kwargs) -> float:
        self.validar_parametros(**kwargs)
        nivel = kwargs.get("nivel_consultor", self._nivel_consultor).strip().upper()
        mult = self.FACTORES_NIVEL.get(nivel, self.FACTORES_NIVEL[self._nivel_consultor])
        mod = kwargs.get("modalidad", self._modalidad_default).strip().upper()
        recargo = self._recargo_presencial if mod == "PRESENCIAL" else 0.0
        return (self.precio_base * duracion * mult) + recargo



# GESTIÓN DE RESERVAS 

class EstadoReserva(Enum):
    PENDIENTE = "PENDIENTE"
    PROCESADA = "PROCESADA"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    FINALIZADA = "FINALIZADA"

    def __str__(self) -> str:
        return self.value


class Reserva(EntidadBase):

    def __init__(
        self,
        cliente: Cliente,
        servicio: Servicio,
        fecha_inicio: datetime,
        duracion: float,
        codigo_reserva: Optional[str] = None,
        parametros_servicio: Optional[Dict[str, Any]] = None,
        id_entidad: Optional[str] = None
    ) -> None:
        super().__init__(id_entidad=id_entidad, activo=True)
        self._codigo_reserva = codigo_reserva if codigo_reserva else f"RES-{self.id}"
        self._cliente: Cliente = cliente
        self._servicio: Servicio = servicio
        self._fecha_inicio: datetime = datetime.now()
        self._duracion: float = 0.0
        self._parametros_servicio: Dict[str, Any] = parametros_servicio if parametros_servicio else {}
        self._estado: EstadoReserva = EstadoReserva.PENDIENTE
        self._desglose_costos: Optional[Dict[str, float]] = None
        self._motivo_cancelacion: Optional[str] = None
        self._historial_transiciones: List[Dict[str, Any]] = []

        self.fecha_inicio = fecha_inicio
        self.duracion = duracion
        self.validar()

        self._registrar_historial(EstadoReserva.PENDIENTE, "Reserva creada inicialmente")
        logger.info("Reserva instanciada: %s para Cliente %s y Servicio %s", self._codigo_reserva, cliente.identificacion, servicio.codigo)

    @property
    def codigo_reserva(self) -> str:
        return self._codigo_reserva

    @property
    def cliente(self) -> Cliente:
        return self._cliente

    @property
    def servicio(self) -> Servicio:
        return self._servicio

    @property
    def fecha_inicio(self) -> datetime:
        return self._fecha_inicio

    @fecha_inicio.setter
    def fecha_inicio(self, fecha: datetime) -> None:
        if not isinstance(fecha, datetime):
            raise DatoInvalidoError("fecha_inicio", fecha, "Debe ser objeto datetime")
        if fecha < datetime.now() - timedelta(minutes=10):
            raise ReservaInvalidaError(f"No se admiten reservas en fechas pasadas: {fecha.strftime('%Y-%m-%d %H:%M')}")
        self._fecha_inicio = fecha

    @property
    def duracion(self) -> float:
        return self._duracion

    @duracion.setter
    def duracion(self, valor: float) -> None:
        try:
            dur_float = float(valor)
        except (ValueError, TypeError) as err:
            raise DatoInvalidoError("duracion", valor, "La duración debe ser un número") from err

        if dur_float <= 0:
            raise ReservaInvalidaError(f"La duración debe ser estrictamente positiva. Recibido: {valor}")
        self._duracion = dur_float

    @property
    def estado(self) -> EstadoReserva:
        return self._estado

    @property
    def desglose_costos(self) -> Optional[Dict[str, float]]:
        return self._desglose_costos

    def _registrar_historial(self, nuevo_estado: EstadoReserva, motivo: str) -> None:
        self._historial_transiciones.append({
            "timestamp": datetime.now().isoformat(),
            "estado_anterior": str(self._estado),
            "estado_nuevo": str(nuevo_estado),
            "motivo": motivo
        })

    def procesar(self, descuento: float = 0.0, impuesto: float = 0.19, cupon: Optional[str] = None) -> Dict[str, float]:
        if self._estado in (EstadoReserva.CANCELADA, EstadoReserva.FINALIZADA):
            raise OperacionNoPermitidaError("procesar", str(self._estado), "La reserva ya está finalizada o cancelada")

        if not self._servicio.disponible:
            raise ServicioNoDisponibleError(self._servicio.codigo, "El servicio fue inhabilitado")

        operacion_limpia = False
        try:
            logger.debug("Procesando costos para reserva %s", self._codigo_reserva)
            desglose = self._servicio.calcular_costo_completo(
                duracion=self._duracion,
                descuento=descuento,
                impuesto=impuesto,
                cupon=cupon,
                **self._parametros_servicio
            )
            self._desglose_costos = desglose

        except (ValueError, TypeError, ZeroDivisionError) as err:
            logger.error("Fallo matemático procesando reserva %s: %s", self._codigo_reserva, str(err), exc_info=True)
            raise CalculoInconsistenteError("Error aritmético en liquidación de reserva") from err

        except SoftwareFJException as ex_dominio:
            logger.error("Excepción de dominio procesando reserva %s: %s", self._codigo_reserva, str(ex_dominio))
            raise

        else:
            operacion_limpia = True
            if self._estado == EstadoReserva.PENDIENTE:
                self._estado = EstadoReserva.PROCESADA
                self._registrar_historial(EstadoReserva.PROCESADA, f"Procesada con éxito. Total: ${desglose['total']:,.2f} COP")
            logger.info("Reserva %s procesada exitosamente. Total: $%.2f COP", self._codigo_reserva, desglose["total"])

        finally:
            logger.info("[FINALLY] Rutina de procesamiento finalizada para %s (Éxito limpio: %s)", self._codigo_reserva, operacion_limpia)

        return self._desglose_costos

        
    def confirmar(self) -> None:
        if self._estado == EstadoReserva.CONFIRMADA:
            raise OperacionNoPermitidaError("confirmar", str(self._estado), "La reserva ya está confirmada")
        if self._estado in (EstadoReserva.CANCELADA, EstadoReserva.FINALIZADA):
            raise OperacionNoPermitidaError("confirmar", str(self._estado), "No se puede confirmar una reserva cerrada")

        try:
            if self._desglose_costos is None or self._estado == EstadoReserva.PENDIENTE:
                self.procesar()

            if isinstance(self._servicio, AlquilerEquipoServicio):
                cant = self._parametros_servicio.get("cantidad_equipos", 1)
                self._servicio.actualizar_stock(-cant)

            estado_previo = self._estado
            self._estado = EstadoReserva.CONFIRMADA
            self._registrar_historial(EstadoReserva.CONFIRMADA, f"Confirmada desde {estado_previo}")
            logger.info("Reserva %s confirmada.", self._codigo_reserva)

        except SoftwareFJException as ex:
            logger.error("Error confirmando reserva %s: %s", self._codigo_reserva, str(ex))
            raise
        finally:
            logger.debug("[FINALLY] Proceso de confirmación concluido para %s", self._codigo_reserva)

    def cancelar(self, motivo: str) -> None:
        
        if not motivo or len(motivo.strip()) < 4:
            raise DatoInvalidoError("motivo", motivo, "Debe proveer una justificación de al menos 4 caracteres")
        if self._estado == EstadoReserva.CANCELADA:
            raise OperacionNoPermitidaError("cancelar", str(self._estado), "La reserva ya se encuentra cancelada")
        if self._estado == EstadoReserva.FINALIZADA:
            raise OperacionNoPermitidaError("cancelar", str(self._estado), "No se puede cancelar un servicio concluido")

        logger.warning("Cancelando reserva %s. Motivo: %s", self._codigo_reserva, motivo)
        try:
            if self._estado == EstadoReserva.CONFIRMADA and isinstance(self._servicio, AlquilerEquipoServicio):
                cant = self._parametros_servicio.get("cantidad_equipos", 1)
                self._servicio.actualizar_stock(cant)
                logger.info("Inventario reintegrado: +%d unidades de %s", cant, self._servicio.nombre)

            self._estado = EstadoReserva.CANCELADA
            self._motivo_cancelacion = motivo.strip()
            self._registrar_historial(EstadoReserva.CANCELADA, f"Cancelada: {motivo}")

        finally:
            logger.info("[FINALLY] Reserva %s en estado post-cancelación: %s", self._codigo_reserva, self._estado)

    def finalizar(self) -> None:
        if self._estado != EstadoReserva.CONFIRMADA:
            raise OperacionNoPermitidaError("finalizar", str(self._estado), "Solo reservas CONFIRMADAS pueden finalizarse")

        if isinstance(self._servicio, AlquilerEquipoServicio):
            cant = self._parametros_servicio.get("cantidad_equipos", 1)
            self._servicio.actualizar_stock(cant)
            logger.info("Equipos devueltos por fin de alquiler: +%d unidades", cant)

        self._estado = EstadoReserva.FINALIZADA
        self._registrar_historial(EstadoReserva.FINALIZADA, "Servicio finalizado a satisfacción")
        logger.info("Reserva %s finalizada.", self._codigo_reserva)

    def validar(self) -> None:
        if not isinstance(self._cliente, Cliente) or not self._cliente.activo:
            raise OperacionNoPermitidaError("reservar", "CLIENTE_INVALIDO", "Cliente nulo o inactivo")
        if not isinstance(self._servicio, Servicio) or not self._servicio.disponible:
            raise ServicioNoDisponibleError(getattr(self._servicio, "codigo", "N/A"), "Servicio no disponible")
        if self._duracion <= 0:
            raise ReservaInvalidaError("La duración debe ser positiva")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "codigo_reserva": self._codigo_reserva,
            "cliente": self._cliente.to_dict(),
            "servicio": self._servicio.to_dict(),
            "fecha_inicio": self._fecha_inicio.isoformat(),
            "duracion": self._duracion,
            "estado": str(self._estado),
            "desglose": self._desglose_costos
        }

    def __str__(self) -> str:
        costo_str = f"${self._desglose_costos['total']:,.2f} COP" if self._desglose_costos else "Sin liquidar"
        return (
            f"Reserva [{self._codigo_reserva}] - Estado: {self._estado.value} | "
            f"Cliente: {self._cliente.nombre} | Servicio: {self._servicio.nombre} | "
            f"Inicio: {self._fecha_inicio.strftime('%Y-%m-%d %H:%M')} | Total: {costo_str}"
        )



# CONTROLADOR Y GESTIÓN EN MEMORIA 


@dataclass
class ResultadoOperacion:
    exito: bool
    mensaje: str
    datos: Optional[Any] = None
    codigo_error: Optional[str] = None
    detalles_error: Optional[Any] = None

# Controlador de memoria (sin bases de datos).
class GestorSoftwareFJ:

    def __init__(self) -> None:
        self._clientes: Dict[str, Cliente] = {}
        self._servicios: Dict[str, Servicio] = {}
        self._reservas: Dict[str, Reserva] = {}
        logger.info("Gestor de Software inicializado en memoria.")

    def registrar_cliente(self, identificacion: str, nombre: str, email: str, telefono: str, direccion: str) -> ResultadoOperacion:
        try:
            if not identificacion:
                raise ParametroFaltanteError("identificacion")
            id_limpio = str(identificacion).strip()
            if id_limpio in self._clientes:
                raise DatoInvalidoError("identificacion", id_limpio, "Ya existe un cliente con esta identificación")

            nuevo_cliente = Cliente(id_limpio, nombre, email, telefono, direccion)
            self._clientes[nuevo_cliente.identificacion] = nuevo_cliente
            logger.info("Cliente registrado: %s (%s)", nuevo_cliente.nombre, nuevo_cliente.identificacion)
            return ResultadoOperacion(True, f"Cliente '{nuevo_cliente.nombre}' registrado con éxito.", nuevo_cliente)

        except SoftwareFJException as ex:
            logger.error("Error al registrar cliente: %s", str(ex), exc_info=True)
            return ResultadoOperacion(False, ex.mensaje, codigo_error=ex.codigo_error, detalles_error=ex.detalles)
        except Exception as err:
            logger.critical("Error inesperado en cliente: %s", str(err), exc_info=True)
            return ResultadoOperacion(False, "Error crítico inesperado al registrar cliente.", "ERR-CRIT-001", str(err))

    def obtener_cliente(self, identificacion: str) -> ResultadoOperacion:
        try:
            id_l = str(identificacion).strip()
            if id_l not in self._clientes:
                raise EntidadNoEncontradaError("Cliente", id_l)
            return ResultadoOperacion(True, "Cliente encontrado.", self._clientes[id_l])
        except SoftwareFJException as ex:
            logger.warning("Cliente no hallado: %s", str(ex))
            return ResultadoOperacion(False, ex.mensaje, codigo_error=ex.codigo_error, detalles_error=ex.detalles)

    def listar_clientes(self) -> List[Cliente]:
        return list(self._clientes.values())

    def registrar_servicio(self, servicio: Servicio) -> ResultadoOperacion:
        try:
            if servicio is None or not isinstance(servicio, Servicio):
                raise ParametroFaltanteError("Servicio válido")
            if servicio.codigo in self._servicios:
                raise DatoInvalidoError("codigo", servicio.codigo, "Código de servicio ya registrado")

            servicio.validar()
            self._servicios[servicio.codigo] = servicio
            logger.info("Servicio añadido: [%s] %s", servicio.codigo, servicio.nombre)
            return ResultadoOperacion(True, f"Servicio '{servicio.nombre}' incorporado al catálogo.", servicio)
        except SoftwareFJException as ex:
            logger.error("Error en alta de servicio: %s", str(ex), exc_info=True)
            return ResultadoOperacion(False, ex.mensaje, codigo_error=ex.codigo_error, detalles_error=ex.detalles)

    def obtener_servicio(self, codigo: str) -> ResultadoOperacion:
        try:
            c = str(codigo).strip().upper()
            if c not in self._servicios:
                raise EntidadNoEncontradaError("Servicio", c)
            return ResultadoOperacion(True, "Servicio localizado.", self._servicios[c])
        except SoftwareFJException as ex:
            logger.warning("Servicio no hallado: %s", str(ex))
            return ResultadoOperacion(False, ex.mensaje, codigo_error=ex.codigo_error, detalles_error=ex.detalles)

    def listar_servicios(self) -> List[Servicio]:
        return list(self._servicios.values())

    def crear_reserva(
        self,
        identificacion_cliente: str,
        codigo_servicio: str,
        fecha_inicio: datetime,
        duracion: float,
        codigo_reserva: Optional[str] = None,
        parametros_servicio: Optional[Dict[str, Any]] = None,
        descuento: float = 0.0,
        impuesto: float = 0.19,
        cupon: Optional[str] = None,
        confirmar_inmediatamente: bool = False
    ) -> ResultadoOperacion:
        try:
            res_cli = self.obtener_cliente(identificacion_cliente)
            if not res_cli.exito:
                return res_cli
            cliente: Cliente = res_cli.datos

            res_srv = self.obtener_servicio(codigo_servicio)
            if not res_srv.exito:
                return res_srv
            servicio: Servicio = res_srv.datos

            if not servicio.disponible:
                raise ServicioNoDisponibleError(servicio.codigo, "El servicio está deshabilitado")

            params = parametros_servicio or {}
            servicio.validar_parametros(**params)

            reserva = Reserva(
                cliente=cliente,
                servicio=servicio,
                fecha_inicio=fecha_inicio,
                duracion=duracion,
                codigo_reserva=codigo_reserva,
                parametros_servicio=params
            )

            reserva.procesar(descuento=descuento, impuesto=impuesto, cupon=cupon)

            if confirmar_inmediatamente:
                reserva.confirmar()

            self._reservas[reserva.codigo_reserva] = reserva
            logger.info("Reserva exitosa: %s | Total: $%.2f COP", reserva.codigo_reserva, reserva.desglose_costos["total"])
            return ResultadoOperacion(True, f"Reserva '{reserva.codigo_reserva}' creada con total de ${reserva.desglose_costos['total']:,.2f} COP", reserva)

        except SoftwareFJException as ex:
            logger.error("Error al crear reserva: %s", str(ex), exc_info=True)
            return ResultadoOperacion(False, ex.mensaje, codigo_error=ex.codigo_error, detalles_error=ex.detalles)
        except Exception as err:
            logger.critical("Error imprevisto creando reserva: %s", str(err), exc_info=True)
            return ResultadoOperacion(False, "Fallo imprevisto al generar reserva.", "ERR-CRIT-RES", str(err))

    def confirmar_reserva(self, codigo: str) -> ResultadoOperacion:
        try:
            c = str(codigo).strip().upper()
            if c not in self._reservas:
                raise EntidadNoEncontradaError("Reserva", c)
            reserva = self._reservas[c]
            reserva.confirmar()
            return ResultadoOperacion(True, f"Reserva '{reserva.codigo_reserva}' confirmada exitosamente.", reserva)
        except SoftwareFJException as ex:
            logger.error("Error confirmando reserva: %s", str(ex), exc_info=True)
            return ResultadoOperacion(False, ex.mensaje, codigo_error=ex.codigo_error, detalles_error=ex.detalles)

    def cancelar_reserva(self, codigo: str, motivo: str) -> ResultadoOperacion:
        try:
            c = str(codigo).strip().upper()
            if c not in self._reservas:
                raise EntidadNoEncontradaError("Reserva", c)
            reserva = self._reservas[c]
            reserva.cancelar(motivo)
            return ResultadoOperacion(True, f"Reserva '{reserva.codigo_reserva}' cancelada. Recursos restituidos.", reserva)
        except SoftwareFJException as ex:
            logger.error("Error cancelando reserva: %s", str(ex), exc_info=True)
            return ResultadoOperacion(False, ex.mensaje, codigo_error=ex.codigo_error, detalles_error=ex.detalles)

    def finalizar_reserva(self, codigo: str) -> ResultadoOperacion:
        try:
            c = str(codigo).strip().upper()
            if c not in self._reservas:
                raise EntidadNoEncontradaError("Reserva", c)
            reserva = self._reservas[c]
            reserva.finalizar()
            return ResultadoOperacion(True, f"Reserva '{reserva.codigo_reserva}' finalizada con éxito.", reserva)
        except SoftwareFJException as ex:
            logger.error("Error finalizando reserva: %s", str(ex), exc_info=True)
            return ResultadoOperacion(False, ex.mensaje, codigo_error=ex.codigo_error, detalles_error=ex.detalles)

    def listar_reservas(self) -> List[Reserva]:
        return list(self._reservas.values())

    def generar_reporte_financiero(self) -> Dict[str, Any]:
        confirmados = 0.0
        proyectados = 0.0
        estados = {e.value: 0 for e in EstadoReserva}
        for r in self._reservas.values():
            estados[r.estado.value] += 1
            if r.desglose_costos:
                proyectados += r.desglose_costos["total"]
                if r.estado in (EstadoReserva.CONFIRMADA, EstadoReserva.FINALIZADA):
                    confirmados += r.desglose_costos["total"]
        return {
            "total_clientes": len(self._clientes),
            "total_servicios": len(self._servicios),
            "total_reservas": len(self._reservas),
            "reservas_por_estado": estados,
            "ingresos_confirmados": f"${confirmados:,.2f} COP",
            "ingresos_proyectados": f"${proyectados:,.2f} COP"
        }

    def precargar_datos_demo(self) -> None:
        """Carga datos iniciales representativos de Software FJ en Pesos Colombianos (COP)."""
        self.registrar_cliente("1017123456", "Technology  SAS", "contacto@technologyG.com", "+573001234567", "Calle 100 # 15-20, Bogotá")
        self.registrar_cliente("9008765432", "Inversions SAS", "admin@inversions.co", "+573159876543", "Cra 43A # 1-50, Huila")
        self.registrar_cliente("CC55443322", "Carlos Martines", "Grancar@gmail.com", "+573204445566", "Avenida Palmas # 22-10, Medellin")

       # Sala de reuniones
        self.registrar_servicio(SalaReunionesServicio(
            codigo="SALA-EXEC",
            nombre="Sala Ejecutiva Premium",
            descripcion_corta="Sala premium con videoconferencia 4K y acabados ejecutivos",
            precio_por_hora=1200000.0,
            capacidad_maxima=52,
            tiene_proyector=True,
            costo_catering_por_persona=25000.0,
            costo_soporte_tecnico=50000.0,
            piso=5
        ))
        # Alquiler de equipos
        self.registrar_servicio(AlquilerEquipoServicio(
            codigo="LAPTOP-PRO",
            nombre="Portátil i9 16GB",
            descripcion_corta="Laptop de alto rendimiento para desarrollo intensivo",
            precio_por_dia=120000.0,
            tipo_equipo="Laptops de Desarrollo",
            stock_disponible=6,
            deposito_garantia=350000.0,
            seguro_diario=25000.0
        ))
        #  Asesoría 
        self.registrar_servicio(AsesoriaEspecializadaServicio(
            codigo="CONS-PERSONS-FJ",
            nombre="Consultoría especializada por SOFWARE_FJ",
            descripcion_corta="Asesoría de alto nivel en diseño de Software y asistentes de IA",
            precio_por_hora=180000.0,
            area_experticia="Soft & IA",
            nivel_consultor="LEAD",
            modalidad_default="REMOTA",
            recargo_presencial=70000.0
        ))



# DEMOSTRACIÓN AUTOMATIZADA


def linea_divisor(titulo: str = "", char: str = "=") -> None:
    ancho = 75
    if titulo:
        print(f"\n{char * 5} {titulo} {char * (ancho - len(titulo) - 7)}")
    else:
        print(char * ancho)


def ejecutar_demostracion() -> None:
    linea_divisor("DEMOSTRACIÓN INTEGRAL - SOFTWARE FJ")
    print("Iniciando auditoría funcional y técnica del sistema orientado a objetos...")

    gestor = GestorSoftwareFJ()

    # Encapsulación y validación de Cliente
    linea_divisor("ESCENARIO 1: Encapsulación y Validación de Datos (Cliente)")
    print("[*] 1.1 Intentando registrar cliente con correo inválido...")
    r1 = gestor.registrar_cliente("CLI-01", "Daniel Madrigal", "correo_sin_arroba", "+573001234567", "Calle 10 # 20")
    print(f" -> Resultado: {'Éxito' if r1.exito else 'Error Controlado'}")
    print(f"    Mensaje: {r1.mensaje} ({r1.codigo_error})")

    print("\n[*] 1.2 Registrando cliente con datos legítimos...")
    r2 = gestor.registrar_cliente("1017123456", "Technology SAS", "contacto@technologyG.com", "+573001234567", "Calle 100 # 15-20, Bogotá")
    print(f" -> [OK] Cliente registrado: {r2.datos}")

    print("\n[*] 1.3 Intentando registrar cliente duplicado...")
    r3 = gestor.registrar_cliente("1017123456", "Technology SAS", "contacto@technologyG.com", "+573001234567", "Calle 100")
    print(f" -> Resultado: {'Éxito' if r3.exito else 'Error Controlado'}")
    print(f"    Mensaje: {r3.mensaje}")
    print("    -> La aplicación se mantiene activa y el error se auditó en logs.")

    # Polimorfismo en Servicios
    linea_divisor("ESCENARIO 2: Polimorfismo en 3 Servicios Especializados (COP)")
    sala = SalaReunionesServicio("SALA-EXEC", "Sala Boardroom", "Sala de juntas", 80000.0, capacidad_maxima=10, costo_catering_por_persona=25000.0, costo_soporte_tecnico=50000.0)
    equipo = AlquilerEquipoServicio("LAPTOP-PRO", "Laptop i9 Dev", "Laptops", 120000.0, "Computadores", stock_disponible=5, deposito_garantia=350000.0, seguro_diario=25000.0)
    asesoria = AsesoriaEspecializadaServicio("CONS-PERSONS-FJ", "Consultoría IA", "Asesoría", 180000.0, "Inteligencia Artificial", "LEAD", recargo_presencial=70000.0)

    gestor.registrar_servicio(sala)
    gestor.registrar_servicio(equipo)
    gestor.registrar_servicio(asesoria)

    print("[*] Descripciones polimórficas sobrescritas (Tarifas en Pesos Colombianos):")
    for s in gestor.listar_servicios():
        print(f"\n{s.describir_servicio()}")

    # Sobrecarga de Costos
    linea_divisor("ESCENARIO 3: Sobrecarga de Métodos de Costo (Pesos Colombianos - COP)")
    duracion = 3.0
    print(f"[*] Evaluando variantes de costos para '{sala.nombre}' ({duracion} horas):")
    ca = sala.calcular_costo_completo(duracion)
    print(f"  Variante Básica: Total = ${ca['total']:,.2f} COP (Base: ${ca['costo_bruto']:,.2f} COP, IVA 19%: ${ca['monto_impuesto']:,.2f} COP)")

    cb = sala.calcular_costo_completo(duracion, numero_asistentes=6, solicita_catering=True)
    print(f"  Variante con Catering (6 personas): Total = ${cb['total']:,.2f} COP")

    cc = sala.calcular_costo_completo(duracion, numero_asistentes=6, solicita_catering=True, descuento=0.10, cupon="FJ_VIP")
    print(f"  Variante Descuento 10% + Cupón VIP FJ (+15%): Total = ${cc['total']:,.2f} COP (Ahorro: ${cc['monto_descuento']:,.2f} COP)")

    
    linea_divisor(" Ciclo de Vida de Reserva y Bloques ")
    fecha_reserva = datetime.now() + timedelta(days=2)

    print("[*] 4.1 Intentando reservar sala para 52 personas (Capacidad máxima: 60)...")
    r_aforo = gestor.crear_reserva("1017123456", "SALA-EXEC", fecha_reserva, 3.0, parametros_servicio={"numero_asistentes": 52})
    print(f" -> Resultado: {'Éxito' if r_aforo.exito else 'Error Controlado'}")
    print(f"    Mensaje: {r_aforo.mensaje}")

    print("\n[*] 4.2 Creando reserva válida...")
    r_valida = gestor.crear_reserva("1017123456", "SALA-EXEC", fecha_reserva, 3.0, parametros_servicio={"numero_asistentes": 12, "solicita_catering": True})
    res_obj = r_valida.datos
    print(f" -> [OK] Reserva creada: {res_obj}")
    print(f"    Estado: {res_obj.estado}")

    print("\n[*] 4.3 Confirmando reserva...")
    gestor.confirmar_reserva(res_obj.codigo_reserva)
    print(f"    Estado: {res_obj.estado}")

    print("\n[*] 4.4 Intentando re-confirmar reserva confirmada (operación no permitida)...")
    r_reconf = gestor.confirmar_reserva(res_obj.codigo_reserva)
    print(f" -> Resultado: {'Éxito' if r_reconf.exito else 'Operación Denegada Controlada'}")
    print(f"    Mensaje: {r_reconf.mensaje}")

    print("\n[*] 4.5 Finalizando reserva...")
    gestor.finalizar_reserva(res_obj.codigo_reserva)
    print(f"    Estado final: {res_obj.estado}")

    print("\n[*] 4.6 Intentando cancelar reserva ya finalizada...")
    r_canc_post = gestor.cancelar_reserva(res_obj.codigo_reserva, "Cancelación extemporánea")
    print(f" -> Resultado: {'Éxito' if r_canc_post.exito else 'Operación Denegada Controlada'}")
    print(f"    Mensaje: {r_canc_post.mensaje}")

    #  Control de inventario en alquiler
    linea_divisor(" Control de Inventario y Liberación Stock ")
    print(f"[*] Stock inicial de laptops: {equipo.stock_disponible} unidades")
    r_equipo = gestor.crear_reserva(
        "1017123456", "EQ-LAPTOP", datetime.now() + timedelta(days=1), 4.0,
        parametros_servicio={"cantidad_equipos": 3, "incluye_seguro": True},
        confirmar_inmediatamente=True
    )
    print(f" -> Reserva confirmada: {r_equipo.datos.codigo_reserva}")
    print(f" -> Stock restante en inventario: {equipo.stock_disponible} unidades (reducido en 3)")

    print("\n[*] Cancelando la reserva para restituir inventario...")
    gestor.cancelar_reserva(r_equipo.datos.codigo_reserva, "Reprogramación del proyecto")
    print(f" -> Stock post-cancelación: {equipo.stock_disponible} unidades (reintegrado a 5)")

    #  Encadenamiento de excepciones y logs
    linea_divisor("Encadenamiento de Excepciones y Auditoría de Logs")
    print("[*] Provocando intencionalmente un error de formato numérico:")
    try:
        r_equipo.datos.duracion = "texto_invalido"
    except DatoInvalidoError as err:
        print(f"  -> Excepción de Dominio: {type(err).__name__}")
        print(f"  -> Mensaje: {err}")
        print(f"  -> Causa original encadenada (__cause__): {repr(err.__cause__)}")

    linea_divisor("REPORTE FINANCIERO CONSOLIDADO")
    rep = gestor.generar_reporte_financiero()
    for k, v in rep.items():
        print(f"  {k}: {v}")

    linea_divisor("VERIFICACIÓN DE ARCHIVO DE LOGS")
    print(f"Ruta del archivo de log: {RUTA_ARCHIVO_LOG}")
    if RUTA_ARCHIVO_LOG.exists():
        with open(RUTA_ARCHIVO_LOG, "r", encoding="utf-8") as f:
            lineas = f.readlines()
        print(f"Total de líneas registradas: {len(lineas)}")
        print("Últimas 5 entradas:")
        for l in lineas[-5:]:
            print(f"  {l.strip()}")

    linea_divisor("FIN DE LA DEMOSTRACIÓN - SISTEMA ESTABLE Y OPERATIVO")



# MENÚ INTERACTIVO POR CONSOLA A PRUEBA DE FALLOS


def menu_interactivo() -> None:
    gestor = GestorSoftwareFJ()
    gestor.precargar_datos_demo()

    while True:
        try:
            linea_divisor("SOFTWARE FJ - SISTEMA DE GESTIÓN (CONSOLA)")
            print("1. Registrar nuevo cliente")
            print("2. Consultar cliente por ID")
            print("3. Listar catálogo de servicios")
            print("4. Crear nueva reserva de servicio")
            print("5. Confirmar reserva existente")
            print("6. Cancelar reserva existente")
            print("7. Finalizar servicio de reserva")
            print("8. Listar todas las reservas")
            print("9. Ver reporte financiero consolidado")
            print("10. Ejecutar demostración integral automatizada")
            print("0. Salir")
            linea_divisor()

            opcion = input("Seleccione una opción: ").strip()

            if opcion == "0":
                print("\nGracias por utilizar el Sistema Integral. Sesión cerrada con éxito.\n")
                break

            elif opcion == "1":
                print("\n--- Registro de Cliente ---")
                ident = input("Identificación (Cédula/NIT): ").strip()
                nombre = input("Nombre completo o razón social: ").strip()
                email = input("Correo electrónico: ").strip()
                telefono = input("Teléfono: ").strip()
                direccion = input("Dirección física: ").strip()

                res = gestor.registrar_cliente(ident, nombre, email, telefono, direccion)
                if res.exito:
                    print(f"\n[OK] {res.mensaje}")
                else:
                    print(f"\n[ERROR CONTROLADO] {res.mensaje} ({res.codigo_error})")

            elif opcion == "2":
                ident = input("\nIngrese la identificación del cliente: ").strip()
                res = gestor.obtener_cliente(ident)
                if res.exito:
                    print(f"\n[OK] {res.datos}")
                else:
                    print(f"\n[AVISO] {res.mensaje}")

            elif opcion == "3":
                print("\n--- Catálogo de Servicios Disponibles ---")
                for s in gestor.listar_servicios():
                    print(f"\n{s.describir_servicio()}")

            elif opcion == "4":
                print("\n--- Crear Reserva de Servicio ---")
                clientes = gestor.listar_clientes()
                if not clientes:
                    print("[AVISO] No hay clientes registrados. Registre uno primero (Opción 1).")
                    continue
                print("\nClientes registrados:")
                for idx, c in enumerate(clientes, 1):
                    print(f"  [{idx}] ID: {c.identificacion} - {c.nombre}")

                sel_cli = input("\nSeleccione el número de cliente o ingrese su ID directamente: ").strip()
                if sel_cli.isdigit() and 1 <= int(sel_cli) <= len(clientes):
                    id_cli = clientes[int(sel_cli) - 1].identificacion
                else:
                    id_cli = sel_cli

                servicios = [s for s in gestor.listar_servicios() if s.disponible]
                if not servicios:
                    print("[AVISO] No hay servicios disponibles en el catálogo.")
                    continue
                print("\nServicios en catálogo:")
                for idx, s in enumerate(servicios, 1):
                    print(f"  [{idx}] [{s.codigo}] {s.nombre} (Base: ${s.precio_base:,.2f} COP)")

                sel_srv = input("\nSeleccione el número de servicio o ingrese su código: ").strip().upper()
                if sel_srv.isdigit() and 1 <= int(sel_srv) <= len(servicios):
                    cod_srv = servicios[int(sel_srv) - 1].codigo
                else:
                    cod_srv = sel_srv

                dias_adelanto = input("\n¿En cuántos días a partir de hoy iniciará la reserva? (ej. 1, 2, 5): ").strip()
                duracion = input("Duración requerida (horas para salas/asesorías, días para equipos): ").strip()

                try:
                    dias_num = int(dias_adelanto)
                    dur_num = float(duracion)
                except ValueError:
                    print("\n[ERROR] Los días y la duración deben ser valores numéricos válidos.")
                    continue

                fecha_inicio = datetime.now() + timedelta(days=dias_num)
                res_srv = gestor.obtener_servicio(cod_srv)
                if not res_srv.exito:
                    print(f"\n[ERROR] {res_srv.mensaje}")
                    continue

                servicio = res_srv.datos
                params = {}
                if isinstance(servicio, SalaReunionesServicio):
                    asist = input(f"Número de asistentes (máximo permitido: {servicio.capacidad_maxima}): ").strip()
                    cat = input("¿Desea servicio de refrigerios/catering? (s/n): ").strip().lower() == "s"
                    params["numero_asistentes"] = int(asist) if asist.isdigit() else 1
                    params["solicita_catering"] = cat
                elif isinstance(servicio, AlquilerEquipoServicio):
                    cant = input(f"Cantidad de unidades a alquilar (stock disponible: {servicio.stock_disponible}): ").strip()
                    seg = input("¿Desea seguro contra daños y accidentes? (s/n, default s): ").strip().lower() != "n"
                    params["cantidad_equipos"] = int(cant) if cant.isdigit() else 1
                    params["incluye_seguro"] = seg
                elif isinstance(servicio, AsesoriaEspecializadaServicio):
                    mod = input("Modalidad (REMOTA / PRESENCIAL): ").strip().upper()
                    if mod:
                        params["modalidad"] = mod

                cupon = input("Cupón de descuento opcional (ej. FJ_BIENVENIDA, FJ_VIP o presione Enter para omitir): ").strip() or None

                res_reserva = gestor.crear_reserva(
                    identificacion_cliente=id_cli,
                    codigo_servicio=cod_srv,
                    fecha_inicio=fecha_inicio,
                    duracion=dur_num,
                    parametros_servicio=params,
                    cupon=cupon,
                    confirmar_inmediatamente=False
                )

                if res_reserva.exito:
                    r_creada = res_reserva.datos
                    print(f"\n[OK] {res_reserva.mensaje}")
                    print(f"     Código asignado: {r_creada.codigo_reserva}")
                    print(f"     Subtotal: ${r_creada.desglose_costos['subtotal']:,.2f} COP | IVA (19%): ${r_creada.desglose_costos['monto_impuesto']:,.2f} COP | TOTAL: ${r_creada.desglose_costos['total']:,.2f} COP")
                else:
                    print(f"\n[ERROR CONTROLADO] {res_reserva.mensaje}")

            elif opcion == "5":
                print("\n--- Confirmar Reserva ---")
                pendientes = [r for r in gestor.listar_reservas() if r.estado in (EstadoReserva.PENDIENTE, EstadoReserva.PROCESADA)]
                if not pendientes:
                    print("No hay reservas pendientes o procesadas para confirmar.")
                    continue
                print("Reservas listas para confirmación:")
                for idx, r in enumerate(pendientes, 1):
                    costo_str = f"${r.desglose_costos['total']:,.2f} COP" if r.desglose_costos else "Sin liquidar"
                    print(f"  [{idx}] {r.codigo_reserva} | Cliente: {r.cliente.nombre} | Servicio: {r.servicio.nombre} | Total: {costo_str} [{r.estado}]")

                sel = input("\nSeleccione el número de reserva o ingrese su código (ej. RES-XXXX): ").strip().upper()
                if sel.isdigit() and 1 <= int(sel) <= len(pendientes):
                    cod = pendientes[int(sel) - 1].codigo_reserva
                else:
                    cod = sel

                res = gestor.confirmar_reserva(cod)
                print(f"\n[{'OK' if res.exito else 'ERROR'}] {res.mensaje}")

            elif opcion == "6":
                print("\n--- Cancelar Reserva ---")
                cancelables = [r for r in gestor.listar_reservas() if r.estado in (EstadoReserva.PENDIENTE, EstadoReserva.PROCESADA, EstadoReserva.CONFIRMADA)]
                if not cancelables:
                    print("No hay reservas activas disponibles para cancelar.")
                    continue
                print("Reservas activas cancelables:")
                for idx, r in enumerate(cancelables, 1):
                    print(f"  [{idx}] {r.codigo_reserva} | Cliente: {r.cliente.nombre} | Estado: {r.estado}")

                sel = input("\nSeleccione el número de reserva a cancelar o ingrese su código: ").strip().upper()
                if sel.isdigit() and 1 <= int(sel) <= len(cancelables):
                    cod = cancelables[int(sel) - 1].codigo_reserva
                else:
                    cod = sel

                motivo = input("Motivo explícito de la cancelación: ").strip()
                res = gestor.cancelar_reserva(cod, motivo)
                print(f"\n[{'OK' if res.exito else 'ERROR'}] {res.mensaje}")

            elif opcion == "7":
                print("\n--- Finalizar Servicio de Reserva ---")
                confirmadas = [r for r in gestor.listar_reservas() if r.estado == EstadoReserva.CONFIRMADA]
                if not confirmadas:
                    print("No hay reservas en estado CONFIRMADA pendientes de culminación.")
                    continue
                print("Reservas confirmadas activas:")
                for idx, r in enumerate(confirmadas, 1):
                    print(f"  [{idx}] {r.codigo_reserva} | Cliente: {r.cliente.nombre} | Servicio: {r.servicio.nombre}")

                sel = input("\nSeleccione el número de reserva a finalizar o ingrese su código: ").strip().upper()
                if sel.isdigit() and 1 <= int(sel) <= len(confirmadas):
                    cod = confirmadas[int(sel) - 1].codigo_reserva
                else:
                    cod = sel

                res = gestor.finalizar_reserva(cod)
                print(f"\n[{'OK' if res.exito else 'ERROR'}] {res.mensaje}")

            elif opcion == "8":
                print("\n--- Listado de Reservas Registradas ---")
                reservas = gestor.listar_reservas()
                if not reservas:
                    print("No hay reservas registradas en el sistema.")
                for r in reservas:
                    print(f" - {r}")

            elif opcion == "9":
                print("\n--- Reporte Financiero Consolidado ---")
                rep = gestor.generar_reporte_financiero()
                for k, v in rep.items():
                    print(f"  {k}: {v}")

            elif opcion == "10":
                ejecutar_demostracion()

            else:
                print("\n[AVISO] Opción no válida. Por favor seleccione un número del menú.")

        except (KeyboardInterrupt, EOFError):
            print("\nOperación interrumpida por el usuario. Saliendo de la aplicación...")
            break
        except Exception as e:
            logger.critical("Error en menú de consola: %s", str(e), exc_info=True)
            print(f"\n[SISTEMA PROTEGIDO] Se capturó un fallo inesperado, pero la aplicación sigue activa: {e}")




if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        ejecutar_demostracion()
    else:
        menu_interactivo()
