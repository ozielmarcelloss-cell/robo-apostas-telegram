# Robô de apostas 100+ → Telegram

Esta versão:
- consulta jogos do dia na API-Football;
- procura odds da Bet365 quando disponíveis na base da API;
- usa as probabilidades do endpoint de previsões;
- elimina seleções sem vantagem estatística mínima;
- monta combinações entre odd 100 e 150;
- não coloca duas seleções do mesmo jogo;
- envia o resultado para o Telegram;
- não faz a aposta automaticamente.

## Onde colocar

Para começar sem PC, use GitHub Actions. Em repositórios públicos, os runners padrão são gratuitos. Os agendamentos podem ser feitos pelo arquivo `.github/workflows/robo.yml`.

## Segredos necessários no GitHub

Em:
Settings → Secrets and variables → Actions → New repository secret

Crie:
- API_FOOTBALL_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

Nunca coloque esses valores diretamente no código.

## Telegram

1. Abra o Telegram.
2. Procure `@BotFather`.
3. Use `/newbot`.
4. Copie o token gerado e salve em `TELEGRAM_BOT_TOKEN`.
5. Envie uma mensagem para o seu novo bot.
6. Descubra seu chat ID e salve em `TELEGRAM_CHAT_ID`.

## API-Football

Crie uma conta gratuita e copie sua API key para `API_FOOTBALL_KEY`.

## Observações

- A API pode não ter Bet365 para todos os eventos/mercados.
- O código não cria um link de cupom oficial da Bet365; ele envia as seleções e odds.
- Odds podem mudar antes da aposta.
- Odd 100 não significa 80% de chance de acerto.
- Esta é uma primeira versão para teste. Antes de usar dinheiro real, faça backtest e validação fora da amostra.
