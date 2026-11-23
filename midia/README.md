# Mídia da NAI (cópias para estudo)

Estes arquivos são **cópias** do que está embutido (em base64) dentro do `NAI-IA-SENAI-Gama.html`.
Trocar um arquivo aqui **não muda a NAI sozinho**. Depois de trocar, rode na pasta do projeto:

```
python ferramentas/embutir_midia.py
```

## Imagens

| Arquivo | Uso |
|---|---|
| `imagens/nai-avatar-2d.webp` | Avatar oficial do SENAI (632x2032, fundo transparente). Usado no modo 2D animado por *shader* |
| `imagens/logo-senai.svg` | Logo do SENAI no canto da tela (vetor, está escrito direto no HTML) |
| `imagens/qrcode-curso-ia.svg` | QR Code padrão da inscrição (cursos.senaidf.org.br). A NAI gera outro se o link mudar |
| `imagens/qrcode-lista-cursos.svg` | Mesmo QR Code, usado no rodapé da lista de cursos |

## Vídeos

Todos foram gerados no **Google Gemini / Google Flow**, com **fundo verde** (o HTML recorta o verde)
e no **mesmo enquadramento**, para encaixarem no mesmo lugar da tela.

| Arquivo | Duração | Resolução | Som | Quando toca |
|---|---|---|---|---|
| `videos/nai-parada-loop-1.mp4` | 8 s | 720x1280 | não | NAI parada, respirando, em loop (alterna com o -2) |
| `videos/nai-parada-loop-2.mp4` | 8 s | 720x1280 | não | idem |
| `videos/nai-aceno-1.mp4` | 8 s | 720x1280 | sim | Aceno curto ("Oi!"), sorteado entre os dois |
| `videos/nai-aceno-2.mp4` | 8 s | 720x1280 | sim | idem |
| `videos/nai-boas-vindas.mp4` | 10 s | 720x1280 | sim | Saudação de boas-vindas |
| `videos/nai-fala-divulgacao.mp4` | 11,8 s | 360x640 | sim | **A fala principal** sobre os cursos. Termina com "escolha uma área" |

Dicas para gerar um vídeo novo:
- Peça **fundo verde liso** (chroma key) e **câmera parada**.
- Use sempre a mesma imagem de referência e o mesmo quadro (9:16).
- Mantenha os vídeos curtos (até 12 s) e leves (menos de 1 MB): todos vão para dentro do HTML.
