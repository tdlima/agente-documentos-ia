"""DocAgent — agente de IA que redige documentos empresariais."""

from .agent import AgenteClaude, AgenteDemo, ErroAgente, Resultado, criar_agente
from .models import Bloco, Documento, Metadado, ModeloDocumento, Organizacao, Solicitacao
from .registry import carregar_modelos, obter_modelo
from .renderers import exportar

__version__ = "1.0.0"

__all__ = [
    "AgenteClaude",
    "AgenteDemo",
    "Bloco",
    "Documento",
    "ErroAgente",
    "Metadado",
    "ModeloDocumento",
    "Organizacao",
    "Resultado",
    "Solicitacao",
    "carregar_modelos",
    "criar_agente",
    "exportar",
    "obter_modelo",
]
