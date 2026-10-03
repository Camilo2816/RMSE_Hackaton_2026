"""sources/*.yaml: el inventario que consume la ingesta."""
import re

import pytest

from src.ingest import fuentes

DOCS = fuentes.cargar()


def test_doc_id_unicos_y_snake_case():
    """doc_id únicos entre todos los YAML (cargar() falla si hay repetidos) y en snake_case."""
    malos = [k for k in DOCS if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", k)]
    assert not malos, malos


@pytest.mark.parametrize("doc_id", sorted(k for k, d in DOCS.items() if d.get("canonico")))
def test_nombre_citable_produce_canonico(doc_id):
    """nombre_citable produce exactamente su canonico con scripts/citations.py."""
    d = DOCS[doc_id]
    assert fuentes.canonico_de_encabezado(d["nombre_citable"]) == {tuple(d["canonico"])}


@pytest.mark.parametrize("doc_id", sorted(k for k, d in DOCS.items() if d.get("alias_citables")))
def test_encabezado_con_alias_incluye_canonico(doc_id):
    """Con alias, el encabezado respalda el canónico propio y cada alias."""
    d = DOCS[doc_id]
    leidos = fuentes.canonico_de_encabezado(fuentes.norma_de(d))
    assert tuple(d["canonico"]) in leidos
    for alias in d["alias_citables"]:
        assert fuentes.canonico_de_encabezado(alias) <= leidos


def test_campos_de_planeacion():
    for k, d in DOCS.items():
        assert d.get("estado") in fuentes.ESTADOS, k
        assert d.get("prioridad") in fuentes.PRIORIDADES, k
        assert d.get("ola") in (0, 1, 2, 3), k
        if d["estado"] == "excluido":
            assert d.get("motivo_exclusion"), f"{k}: excluido sin motivo (va a CORPUS.md)"


def test_codigos_del_extractor_presentes():
    """Los 15 cuerpos que citations.CODES reconoce por nombre están en el inventario."""
    canon = {tuple(d["canonico"]) for d in DOCS.values() if d.get("canonico")}
    faltan = [c for c in fuentes.oficial.CODES if (c, None, None) not in canon]
    assert not faltan, faltan
