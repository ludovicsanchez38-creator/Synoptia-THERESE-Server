"""
THÉRÈSE v2 - Browser Router

Endpoints pour la navigation web automatisée via Playwright.
v0.6 - Inspiré de Manus Browser Operator.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.rbac import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


# --- Schemas de requête ---


class NavigateRequest(BaseModel):
    """Requête de navigation vers une URL."""
    url: str = Field(..., description="URL cible (http/https uniquement)")


class ExtractRequest(BaseModel):
    """Requête d'extraction de texte."""
    selector: str | None = Field(None, description="Sélecteur CSS (optionnel, body par défaut)")


class ClickRequest(BaseModel):
    """Requête de clic sur un élément."""
    selector: str = Field(..., description="Sélecteur CSS de l'élément à cliquer")


class FillRequest(BaseModel):
    """Requête de remplissage d'un champ."""
    selector: str = Field(..., description="Sélecteur CSS du champ")
    value: str = Field(..., description="Valeur à saisir")


class ActionRequest(BaseModel):
    """Requête d'action générique."""
    action: str = Field(..., description="Nom de l'action (navigate, click, fill, etc.)")
    params: dict = Field(default_factory=dict, description="Paramètres de l'action")


# --- Schema de réponse ---


class BrowserActionResponse(BaseModel):
    """Réponse standardisée d'une action du browser."""
    success: bool
    action: str
    url: str = ""
    title: str = ""
    content: str = ""
    screenshot_path: str | None = None
    links: list[dict[str, str]] = []
    error: str | None = None


class BrowserStatusResponse(BaseModel):
    """Statut du browser agent."""
    active: bool
    current_url: str | None = None


# --- Helpers ---


def _to_response(result) -> BrowserActionResponse:
    """Convertit un BrowserResult en BrowserActionResponse."""
    return BrowserActionResponse(
        success=result.success,
        action=result.action,
        url=result.url,
        title=result.title,
        content=result.content,
        screenshot_path=result.screenshot_path,
        links=result.links,
        error=result.error,
    )


# --- Endpoints ---


@router.post("/navigate", response_model=BrowserActionResponse)
async def navigate(request: NavigateRequest) -> BrowserActionResponse:
    """Navigue vers une URL et retourne le titre + contenu textuel (max 5000 chars)."""
    from app.services.browser_agent import get_browser_agent

    agent = get_browser_agent()
    result = await agent.navigate(request.url)
    return _to_response(result)


@router.post("/extract", response_model=BrowserActionResponse)
async def extract_text(request: ExtractRequest) -> BrowserActionResponse:
    """Extrait le texte de la page courante ou d'un sélecteur CSS."""
    from app.services.browser_agent import get_browser_agent

    agent = get_browser_agent()
    result = await agent.extract_text(request.selector)
    return _to_response(result)


@router.post("/screenshot", response_model=BrowserActionResponse)
async def take_screenshot() -> BrowserActionResponse:
    """Prend un screenshot de la page courante, sauvegardé dans ~/.therese/outputs/."""
    from app.services.browser_agent import get_browser_agent

    agent = get_browser_agent()
    result = await agent.screenshot()
    return _to_response(result)


@router.post("/click", response_model=BrowserActionResponse)
async def click_element(request: ClickRequest) -> BrowserActionResponse:
    """Clique sur un élément identifié par un sélecteur CSS."""
    from app.services.browser_agent import get_browser_agent

    agent = get_browser_agent()
    result = await agent.click(request.selector)
    return _to_response(result)


@router.post("/fill", response_model=BrowserActionResponse)
async def fill_field(request: FillRequest) -> BrowserActionResponse:
    """Remplit un champ de formulaire."""
    from app.services.browser_agent import get_browser_agent

    agent = get_browser_agent()
    result = await agent.fill(request.selector, request.value)
    return _to_response(result)


@router.post("/links", response_model=BrowserActionResponse)
async def get_links() -> BrowserActionResponse:
    """Liste les liens de la page courante (max 50)."""
    from app.services.browser_agent import get_browser_agent

    agent = get_browser_agent()
    result = await agent.get_links()
    return _to_response(result)


@router.post("/action", response_model=BrowserActionResponse)
async def execute_action(request: ActionRequest) -> BrowserActionResponse:
    """Dispatcher générique : exécute une action par nom avec ses paramètres."""
    from app.services.browser_agent import get_browser_agent

    agent = get_browser_agent()
    result = await agent.execute_action(request.action, request.params)
    return _to_response(result)


@router.get("/status", response_model=BrowserStatusResponse)
async def get_status() -> BrowserStatusResponse:
    """Retourne le statut du browser (actif ou non, URL courante)."""
    from app.services.browser_agent import get_browser_agent

    agent = get_browser_agent()
    return BrowserStatusResponse(
        active=agent.is_active,
        current_url=agent.current_url,
    )


@router.post("/close", response_model=BrowserActionResponse)
async def close_browser() -> BrowserActionResponse:
    """Ferme le browser et libère les ressources."""
    from app.services.browser_agent import get_browser_agent

    agent = get_browser_agent()
    if not agent.is_active:
        return BrowserActionResponse(
            success=True,
            action="close",
            content="Browser déjà fermé",
        )

    url = agent.current_url or ""
    await agent.stop()
    return BrowserActionResponse(
        success=True,
        action="close",
        url=url,
        content="Browser fermé",
    )
