"""src/index/tokenizar.py: identificadores jurídicos como tokens de BM25."""
from src.index.tokenizar import normalizar, tokenizar


def test_articulo_de_un_digito_y_ordinal():
    assert "5" in tokenizar("artículo 5 de la Constitución")
    assert tokenizar("ARTICULO 3o. ") == tokenizar("artículo 3") == tokenizar("Artículo 3º")


def test_tildes_y_mayusculas():
    assert tokenizar("ACCIÓN DE TUTELA") == tokenizar("accion de tutela")
    assert "ñ" in normalizar("Año")


def test_identificadores_compuestos():
    assert "c_355" in tokenizar("Sentencia C-355 de 2006")
    assert "su_016" in tokenizar("sentencia SU - 016 de 2020")
    assert "2_2_1_1_1_1" in tokenizar("Artículo 2.2.1.1.1.1 del Decreto 1072 de 2015")
    assert "240_1" in tokenizar("artículo 240-1 del Estatuto Tributario")


def test_stopwords_y_stemming():
    toks = tokenizar("los contratos de la sociedad")
    assert "los" not in toks and "de" not in toks and "la" not in toks
    assert tokenizar("contratos") == tokenizar("contrato")
