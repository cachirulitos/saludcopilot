"""
Tests del motor de reglas clínicas.
Cada test corresponde a una regla específica.
Correr con: pytest packages/rules_engine/tests/
"""
import sys
sys.path.insert(0, "packages/rules_engine/src")

from engine import Estudio, calcular_secuencia


def test_r01_papanicolaou_antes_que_transvaginal():
    """R-01: Papanicolaou siempre antes que Ultrasonido transvaginal."""
    estudios = [
        Estudio(id="1", tipo="ultrasonido_transvaginal"),
        Estudio(id="2", tipo="papanicolaou"),
    ]
    resultado = calcular_secuencia(estudios)
    tipos_ordenados = [p.estudio.tipo for p in resultado.pasos]
    assert tipos_ordenados.index("papanicolaou") < tipos_ordenados.index("ultrasonido_transvaginal")
    assert resultado.pasos[0].regla_aplicada == "R-01"


def test_r03_densitometria_antes_que_tomografia():
    """R-03: Densitometría antes que Tomografía con contraste."""
    estudios = [
        Estudio(id="1", tipo="tomografia"),
        Estudio(id="2", tipo="densitometria"),
    ]
    resultado = calcular_secuencia(estudios)
    tipos = [p.estudio.tipo for p in resultado.pasos]
    assert tipos.index("densitometria") < tipos.index("tomografia")


def test_r04_laboratorio_ayuno_antes_que_ultrasonido():
    """R-04: Laboratorio con ayuno antes que Ultrasonido."""
    estudios = [
        Estudio(id="1", tipo="ultrasonido"),
        Estudio(id="2", tipo="laboratorio", requiere_ayuno=True),
    ]
    resultado = calcular_secuencia(estudios)
    tipos = [p.estudio.tipo for p in resultado.pasos]
    assert tipos.index("laboratorio") < tipos.index("ultrasonido")


def test_urgente_primero():
    """Pacientes urgentes tienen prioridad sobre cualquier orden de estudios."""
    estudios = [
        Estudio(id="1", tipo="laboratorio"),
        Estudio(id="2", tipo="ultrasonido", es_urgente=True),
    ]
    resultado = calcular_secuencia(estudios)
    assert resultado.pasos[0].estudio.es_urgente is True


def test_secuencia_vacia():
    """Sin estudios, devuelve secuencia vacía sin error."""
    resultado = calcular_secuencia([])
    assert resultado.pasos == []
    assert resultado.tiempo_estimado_minutos == 0


def test_tiempo_estimado():
    """El tiempo estimado es coherente con el número de estudios."""
    estudios = [
        Estudio(id="1", tipo="laboratorio"),
        Estudio(id="2", tipo="electrocardiograma"),
    ]
    resultado = calcular_secuencia(estudios)
    # 2 estudios × 15min + 1 traslado × 5min = 35min
    assert resultado.tiempo_estimado_minutos == 35
