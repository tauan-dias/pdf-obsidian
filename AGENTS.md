# Orientações para próximas sessões

Antes de trabalhar, leia [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), que registra o estado do projeto, decisões do usuário e validações pendentes. Consulte também `README.md` e `VALIDATION.md` quando necessário.

- Converse com o usuário em português brasileiro.
- Preserve a aplicação local e offline e a integridade dos PDFs originais.
- O usuário autorizou o filtro automático conservador de imagens recorrentes nos 10% superiores/inferiores, com revisão e restauração individual. Preserve seus limites (três páginas e 70% do documento, mesma identidade/posição), o histórico e os arquivos temporários para recuperação. Outras remoções continuam manuais pela prévia; não ampliar o filtro sem nova solicitação. OCR permanece fora do escopo.
- O PDF pessoal na raiz não deve ser alterado, publicado, incluído em commits ou copiado para os testes. Gere PDFs sintéticos para regressões.
- Preserve edições do usuário, desfazer/refazer, navegação por página e referências relativas dos anexos ao fazer mudanças.
- Execute verificações pertinentes às alterações. O comando da suíte é `.venv/bin/python -m pytest -q`.
