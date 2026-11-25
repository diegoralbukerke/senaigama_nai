# NAI · Mundo SENAI — versão IA

A **NAI** é a assistente virtual do SENAI Gama que roda numa **TV vertical** no evento Mundo SENAI.
Quando alguém para na frente da TV, ela fala sobre os cursos gratuitos. Depois mostra o
**curso de Aperfeiçoamento Profissional em Inteligência Artificial (40h, online)** em destaque e as **10 áreas de cursos**.
A pessoa escolhe **apontando o dedo no ar**: uma "mãozinha" aparece na tela e funciona como um mouse.

> 📖 Para saber **como o projeto foi feito**, leia [`docs/COMO-FOI-FEITO.md`](docs/COMO-FOI-FEITO.md).
> 🎬 As imagens e os vídeos originais estão separados em [`midia/`](midia/).

---

## O que você precisa

| Item | Detalhe |
|---|---|
| Computador | Windows 10/11 **64 bits** |
| Câmera | Webcam USB virada para o público (a do notebook também serve para testar) |
| Tela | Qualquer monitor. No evento é uma TV em pé (1080x1920) |
| Navegador | Firefox (recomendado), Edge ou Chrome |
| Internet | Obrigatória na instalação e na **primeira** abertura (para baixar as bibliotecas e os modelos de IA) |

## Instalação (só na primeira vez)

1. **Baixe o projeto**: botão verde **Code → Download ZIP** (ou `git clone`) e extraia numa pasta.
2. Dê dois cliques em **`instalar.bat`** e espere de 5 a 10 minutos. Ele:
   1. instala o **Python 3.12**, se faltar (sem precisar de administrador);
   2. instala o **Visual C++ Redistributable**, se faltar (clique em *Sim* se o Windows pedir);
   3. cria um ambiente Python em `%LOCALAPPDATA%\NAI-venv` e instala as bibliotecas do `requirements.txt`;
   4. testa tudo e cria o atalho **"NAI Mundo SENAI"** na Área de Trabalho.
3. Rode **`testar_maos.bat`** para conferir a câmera. Deve abrir uma janela com os pontos da mão e os rostos.

> O ambiente Python fica fora da pasta do projeto porque o MediaPipe não funciona em caminhos com acento
> (como "Área de Trabalho"). Por isso o projeto pode ficar em qualquer pasta.

## Como usar

Abra o **`iniciar_NAI.bat`** ou o atalho. Abrem duas coisas:

- uma **janela preta** com o programa Python que lê a câmera. **Deixe ela aberta**;
- a **NAI em tela cheia** no navegador.

**Teclas na janela preta** (clique nela antes de apertar):

| Tecla | Ação |
|---|---|
| `F` | Fecha tudo |
| `R` | Reabre a tela da NAI |
| `T` | Troca o monitor onde a NAI aparece |
| `I` | Mostra o número de cada monitor |
| `C` | Troca a câmera |
| `N` | Troca o navegador (Firefox → Edge → Chrome) |
| `J` | Mostra ou esconde a janela de teste da câmera |

**Teclas na tela da NAI:**

| Tecla | Ação |
|---|---|
| `S` | Abre o painel de configurações |
| `P` | A NAI fala o vídeo de divulgação |
| `1` | Abre o curso de IA |
| `2`–`9`, `0`, `-` | Abrem as 10 áreas |
| `Esc` | Fecha a lista |

**Notebook + TV:** ao abrir, o programa ajusta o Windows para não dormir nem apagar a tela ao
fechar a tampa. Pode fechar a tampa: a NAI vai sozinha, em tela cheia, para a TV. Sem tela escolhida,
a NAI já abre na TV (a maior tela que não é a principal). Ao apertar `F`, a ação da tampa volta ao
que era antes. Deixe o notebook na tomada.

As escolhas de monitor, câmera e navegador ficam salvas em `nai_config.json`, que é criado sozinho
e não vai para o GitHub porque é diferente em cada PC.

Mais detalhes e solução de problemas: [`LEIA-ME.txt`](LEIA-ME.txt).

## Estrutura do projeto

```
NAI-IA/
├── NAI-IA-SENAI-Gama.html   ← a NAI inteira (HTML + CSS + JavaScript, com os vídeos embutidos)
├── nai_maos.py              ← programa Python: câmera, mãos, rostos, servidor WebSocket, abre o navegador
├── instalar.bat             ← instala Python, Visual C++ e bibliotecas
├── iniciar_NAI.bat          ← abre tudo para o evento
├── testar_maos.bat          ← janela de teste da câmera
├── requirements.txt         ← bibliotecas Python
├── LEIA-ME.txt              ← manual rápido para quem vai operar no evento
├── midia/                   ← CÓPIAS das imagens e vídeos que estão embutidos no HTML
│   ├── imagens/
│   └── videos/
├── ferramentas/
│   └── embutir_midia.py     ← põe os arquivos de midia/ de volta dentro do HTML
└── docs/
    ├── COMO-FOI-FEITO.md    ← história, arquitetura e decisões do projeto
    └── lista-de-cursos.txt  ← lista de áreas e cursos usada por padrão
```

> ⚠️ Os arquivos em `midia/` são **cópias para estudo**. O HTML **não** lê essa pasta: os vídeos e a
> imagem estão dentro dele, em base64. Se trocar um vídeo em `midia/`, nada muda na NAI.
> Para trocar de verdade, rode `python ferramentas/embutir_midia.py` depois de substituir o arquivo.

## Créditos

Projeto do **SENAI Gama**, idealizado por **Diego Rosa Albuquerque**, gerente da unidade, para o Mundo SENAI 2026.
O código foi escrito com apoio de IA generativa (Claude). Os vídeos da NAI foram gerados no Google Gemini e no Google Flow
a partir do avatar oficial do SENAI.

O logo, o avatar e a identidade visual são do SENAI. Use apenas em projetos do SENAI.
