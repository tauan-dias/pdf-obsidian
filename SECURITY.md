# Segurança

O PDF-Obsidian processa documentos localmente e preserva os PDFs originais. Downloads de dependências e modelos são etapas explícitas de instalação; documentos não são enviados a serviços de reconhecimento remoto.

## Controles

- O worker PDF bloqueia conexões pelo kernel com libseccomp. O OCR também restringe arquivos por Landlock e recebe um ambiente sem credenciais herdadas. Exige Linux x86_64/aarch64 com Landlock ABI 3+ e `libseccomp.so.2`; falha na proteção interrompe a operação, sem fallback desprotegido.
- Rasterizações têm limite de 24 milhões de pixels. O worker tem supervisão externa de memória, tempo e disco, além de limites de CPU e tamanho por arquivo. Detalhes em [OCR.md](OCR.md).
- A prévia carrega apenas PNGs regulares dentro dos anexos da sessão, sem symlinks ou referências externas. Os links do Markdown editável/exportado são preservados; a saída não é sanitizada para todo possível consumidor ou plugin.
- Instalações usam locks com hashes de wheels. Os modelos devem corresponder aos SHA-256 distribuídos com o pacote; reescrever o manifesto local não autoriza outros pesos. PyMuPDF 2.0 inclui a correção de CVE-2026-82035.
- A exportação verifica o original, rejeita symlinks nos anexos e publica por staging e rename sem sobrescrita. Temporários e edições são preservados durante a sessão para revisão e recuperação.

## Limites e manutenção

RSS e disco são monitorados periodicamente, podendo apresentar picos entre verificações. Não são quotas de cgroup. Documentos excessivos podem ser recusados ou interromper o worker. A aplicação conserva o texto em memória, mas não persiste a sessão automaticamente; copie ou salve as edições antes de fechar.

Os hashes pressupõem confiança no checkout, backend de build e canais usados para aprovar os artefatos. As proteções reduzem a exposição; não garantem resistência a todas as vulnerabilidades do kernel, bibliotecas nativas ou processos já controlados pelo mesmo usuário. Atualizações devem revisar versões, hashes e regressões em conjunto.

Valide alterações com `.venv/bin/python -m pytest -q` e `python -m pip check`. Testes e ferramentas usam PDFs sintéticos. Não publique documentos privados, credenciais ou provas de exploração com dados reais em issues ou testes.

## Referências

- [Correções do PyMuPDF](https://pymupdf.readthedocs.io/en/latest/changes.html).
- [Landlock](https://docs.kernel.org/userspace-api/landlock.html).
- [Verificação de hashes pelo pip](https://pip.pypa.io/en/stable/topics/secure-installs/).
