# OmeTV Clean Browser

Chromium browser com Tor embutido + auto-cleanup + login OAuth liberado.

## Como usar

```bash
python ometv.py
```

**Primeira execução:** abre uma janela de setup baixando as dependências automaticamente (PyQt6 + Tor).

**Execuções seguintes:** abre o navegador direto no ome.tv com Tor rodando por trás.

## Funcionalidades

- **Tor embutido** — funciona como VPN falsa, IP diferente a cada sessão
- **Auto-cleanup** — limpa DNS, cookies, cache de todos os browsers ao iniciar
- **Perfil temporário** — toda sessão é isolada, dados deletados ao fechar
- **Login OAuth liberado** — Facebook/Google bypassam o Tor (evita CAPTCHA)
- **New IP** — troca o circuito Tor na hora
- **New Session** — reset completo (novo perfil + novo IP + novo fingerprint)
- **Fingerprint aleatório** — User-Agent diferente por sessão, WebRTC bloqueado

## Dependências

Instaladas automaticamente na primeira execução:
- PyQt6 + PyQt6-WebEngine (Chromium)
- Tor Expert Bundle (~21MB)

## Estrutura

```
ometv.py          # Arquivo único — só rodar
tor/tor.exe       # Tor (baixado na primeira execução)
```
