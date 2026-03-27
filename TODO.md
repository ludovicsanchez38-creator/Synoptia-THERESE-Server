# TODO - THERESE Server

Audit jury du 27/03/2026 - Score : 7.4/10 (alpha v0.1.0)

## P0 - Sécurité (critique)

- [ ] Brancher `prompt_security.py` sur les routes de chat (`chat.py`, `chat_llm.py`) - le service existe mais n'est jamais appelé
- [ ] Ajouter `max_length` sur le champ `content` de `MessageCreate` et `ChatSendRequest.message`
- [ ] Rate limiting login : remplacer le dict in-memory par Redis ou store partagé (ne survit pas au restart, pas multi-worker)
- [ ] Supprimer le log du token de reset en clair dans `forgot_password()` (`logger.info("Reset token genere pour %s : %s"`)
- [ ] Restreindre CORS : `allow_methods` et `allow_headers` trop permissifs (`["*"]`)
- [ ] Migrer le stockage JWT de localStorage vers cookies HttpOnly + Secure + SameSite=Strict
- [ ] Ajouter `pip-audit` et `npm audit` dans le pipeline CI
- [ ] Supprimer les routes `/docs*`, `/redoc*`, `/openapi.json` du Caddyfile en production
- [ ] Forcer le changement de mot de passe admin au premier login (flag `must_change_password`)

## P1 - Produit (bloquant pour déploiement)

- [ ] Onboarding utilisateurs : endpoint admin de création d'utilisateurs + invitation par email
- [ ] Flux "mot de passe oublié" réel (pas un `alert()`)
- [ ] Pages frontend manquantes : factures, calendrier, email, RAG (les endpoints backend sont prêts)
- [ ] Vue fiche contact détaillée avec timeline d'activités
- [ ] Vue Kanban pour les tâches (drag-and-drop)
- [ ] Champ `assigned_to` sur les tâches et contacts
- [ ] Notifications in-app via SSE (le pattern est déjà maîtrisé pour le chat)
- [ ] Recherche globale : intégrer Qdrant (sémantique) + PostgreSQL full-text (`tsvector/tsquery`)
- [ ] Charger la liste des modèles LLM depuis une API backend (actuellement hardcodée dans ChatInput)
- [ ] Renommage de conversation (double-clic ou bouton d'édition)

## P2 - Architecture

- [ ] Supprimer la couche LLM de `chat_llm.py` et déléguer à `LLMService` (duplication de code)
- [ ] Éclater `entities.py` (500+ lignes, 20+ modèles) en modules thématiques (`models/crm.py`, `models/email.py`, etc.)
- [ ] Ajouter une couche DTO/mapper entre entités et réponses API (sérialisation dupliquée)
- [ ] Registre de providers LLM déclaratif (remplacer le if/elif de 60 lignes dans `_default_config()`)
- [ ] Adopter `error_handler.py` systématiquement dans les routers (actuellement sous-utilisé)
- [ ] Tests d'intégration : auth/login, RBAC, CRUD conversations, CRM pipeline, RGPD anonymisation, multi-tenant isolation

## P3 - Frontend

- [ ] Responsive : vue "card" pour les tableaux sous `md:` (CRM, admin, audit)
- [ ] Pagination ou scroll infini sur audit logs, contacts, conversations
- [ ] Remplacer `window.confirm()` par une modale custom cohérente avec le design system
- [ ] Ajouter confirmation de suppression sur les tâches
- [ ] Gestion offline : détecteur connexion (`online`/`offline`) + bandeau informatif + retry avec backoff
- [ ] Refactorer les formulaires CRM/Tasks pour utiliser les composants du design system (Input, Select, Textarea)
- [ ] Corriger les accents manquants dans les `aria-label` ("Tache" -> "Tâche")
- [ ] Ajouter `aria-label` sur les `<select>` orphelins (CRM, admin)

## P4 - DevOps

- [ ] Pipeline CD : build images Docker + push registry + deploy automatisé
- [ ] Monitoring externe avec alertes (Uptime Kuma, webhook Discord/email)
- [ ] Logs structurés JSON en production (python-json-logger est installé mais pas utilisé)
- [ ] Rotation des logs Docker (max-size, max-file dans docker-compose.yml)
- [ ] Stratégie haute disponibilité pour cible 300-500 agents (réplication PostgreSQL, cluster Qdrant)
- [ ] Scan de vulnérabilités images Docker (Trivy) dans la CI
- [ ] Lock file Python (uv.lock) pour reproductibilité des builds

## P5 - README

- [ ] Mettre à jour : retirer GPT-4o (obsolète), aligner avec les modèles actuels
- [ ] Ajouter screenshots/GIFs de l'interface
