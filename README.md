# Discord Music RPC (Selfbot Port)

### Atenção: Antes de usar este code lembre-se que o uso de selfbots (userbots) é totalmente contra o T.O.S. do discord! Use por sua conta em risco!

Este code é um port desta [source](https://github.com/zRitsu/Discord-MusicBot-RPC) para servir como alternativa pra permitir o uso de rich-presence em dispositivos não suportados (devido a limitações do discord o rpc suporta apenas no discord desktop)

![](https://camo.githubusercontent.com/18ec3804e06f2854a62d4df1dd5bd4e8ee53679ab9ebec8c0f12b6a37177206b/68747470733a2f2f6d656469612e646973636f72646170702e6e65742f6174746163686d656e74732f3535343436383634303934323938313134372f313038393637383634373233303732363138352f7270635f737570706f72742e706e67)

### Requisitos:
* Python 3.8 ou superior (Ao instalar, caso esteja usando windows não esqueça de marcar a opção: Add python to the PATH)
* Já ter o seu token de usuário em mãos (não irei abordar aqui o processo de como obter isso, pesquise por: how to get discord token).
* Link do websocket do RPC Server de um bot compatível (ex: que use esta [source](https://github.com/zRitsu/disnake-LL-music-bot), para obter o link use o comando /rich_presence ou verifique o link exibido no html gerado)
* Apenas em caso especifico: Token de acesso do RPC Server (se realmente for necessário, ao usar o comando /rich_presence no bot ele irá avisar).

### Como usar:

Antes de seguir, se estiver usando windows talvez será necessário trocar o comando `python3` informando nos passos abaixo por: `py -3`

* Baixe esta source como [zip](https://github.com/zRitsu/Discord-MusicBot-RPC-Selfbot/archive/refs/heads/main.zip) e extraia em seguida.

* Use o comando abaixo no terminal:
```
python3 -m pip install -r requirements.txt
```
* Renomeie o arquivo .example.env para apenas .env
* Abra o arquivo .env e no campo token coloque o seu token de usuário.
* No campo RPC_URL coloque o link do websocket do bot (use o comando /rich_presence nele para obter essas informações)
* Dependendo de como o bot foi configurado, pode ser necessário preencher o campo RPC_TOKEN
* Inicie o code usando o comando:
```
python3 main.py
```